"""Интеграционные тесты: ZIP import/export и payload экрана."""
from __future__ import annotations

import importlib
import io
import json
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

_PATH_MODULES = (
    "guardschool.gs_paths",
    "guardschool.gs_jsonio",
    "guardschool.gs_ensure_dirs",
    "guardschool.gs_import_bundle",
    "guardschool.gs_app_config",
    "guardschool.gs_data_loaders",
)


def _reload_data_path_modules() -> None:
    import guardschool.gs_paths as gs_paths

    importlib.reload(gs_paths)
    for name in _PATH_MODULES[1:]:
        mod = importlib.import_module(name)
        importlib.reload(mod)


class TempDataDirMixin:
    def setUp(self) -> None:
        self._prev_data_dir = os.environ.get("GUARDSCHOOL_DATA_DIR")
        self._td = tempfile.TemporaryDirectory()
        os.environ["GUARDSCHOOL_DATA_DIR"] = self._td.name
        _reload_data_path_modules()

    def tearDown(self) -> None:
        self._td.cleanup()
        if self._prev_data_dir is None:
            os.environ.pop("GUARDSCHOOL_DATA_DIR", None)
        else:
            os.environ["GUARDSCHOOL_DATA_DIR"] = self._prev_data_dir
        _reload_data_path_modules()

    @property
    def data_dir(self) -> Path:
        return Path(self._td.name)


class ImportBundleTests(TempDataDirMixin, unittest.TestCase):
    def test_import_rejects_zip_without_root_config(self) -> None:
        from guardschool.gs_import_bundle import import_bundle_bytes

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("schedule.json", b"[]")
        with self.assertRaises(HTTPException) as ctx:
            import_bundle_bytes(buf.getvalue(), lang="en")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("config.json", str(ctx.exception.detail).lower())

    def test_export_import_roundtrip_preserves_config(self) -> None:
        from guardschool.gs_ensure_dirs import ensure_dirs
        from guardschool.gs_import_bundle import export_bundle_bytes, import_bundle_bytes
        from guardschool.gs_jsonio import read_json, write_json
        from guardschool.gs_paths import CONFIG_PATH

        ensure_dirs()
        config = {
            "screens": [{"id": "s1", "name": "Hall", "slug": "hall", "is_active": True, "widgets": []}],
            "timezone": "Europe/Moscow",
            "clock_offset_minutes": 5,
            "ui_locale": "ru",
        }
        write_json(CONFIG_PATH, config)

        exported = export_bundle_bytes()
        with zipfile.ZipFile(io.BytesIO(exported), "r") as zf:
            self.assertIn("config.json", zf.namelist())

        mutated = dict(config)
        mutated["clock_offset_minutes"] = 99
        write_json(CONFIG_PATH, mutated)
        self.assertEqual(read_json(CONFIG_PATH, {})["clock_offset_minutes"], 99)

        import_bundle_bytes(exported, lang="ru")
        restored = read_json(CONFIG_PATH, {})
        self.assertEqual(restored["clock_offset_minutes"], 5)
        self.assertEqual(restored["screens"][0]["slug"], "hall")

    def test_weekly_schedule_import_writes_full_schedule(self) -> None:
        from guardschool.gs_import_bundle import import_weekly_schedule_bundle_bytes
        from guardschool.gs_jsonio import read_json
        from guardschool.gs_paths import FULL_SCHEDULE_PATH

        rows = [{"weekday": 0, "class_key": "5", "lessons": [{"index": 1, "subject": "Math"}]}]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("full_schedule.json", json.dumps(rows, ensure_ascii=False).encode("utf-8"))

        import_weekly_schedule_bundle_bytes(buf.getvalue(), lang="en")
        self.assertEqual(read_json(FULL_SCHEDULE_PATH, None), rows)


class SchedulePayloadTests(unittest.TestCase):
    def test_bell_status_current_lesson_during_slot(self) -> None:
        from guardschool.gs_schedule_bells import build_bell_status

        entries = [
            {"lesson": "1", "start": "08:30", "end": "09:10"},
            {"lesson": "2", "start": "09:30", "end": "10:10"},
        ]
        screen = {"bell_schedule_template": "standard"}
        config = {"timezone": "UTC", "clock_offset_minutes": 0, "ui_locale": "en"}

        with patch(
            "guardschool.gs_schedule_bells.get_screen_bell_entries_and_bells",
            return_value=(entries, {}, "Standard", None),
        ), patch("guardschool.gs_schedule_bells.wall_clock_minutes_for_config", return_value=8 * 60 + 45):
            status = build_bell_status(screen, date(2026, 5, 30), config)

        self.assertEqual(status["state"], "lesson")
        self.assertEqual(status["current_lesson"], 1)

    def test_build_schedule_payload_structure(self) -> None:
        from guardschool.gs_schedule_bells import build_schedule_payload

        screen = {"selected_classes": ["5"], "bell_schedule_template": "standard"}
        config = {"timezone": "UTC", "clock_offset_minutes": 0, "ui_locale": "en"}
        target = date(2026, 5, 30)

        with patch("guardschool.gs_schedule_bells.load_schedule", return_value=[]), patch(
            "guardschool.gs_schedule_bells.load_full_schedule", return_value=[]
        ), patch("guardschool.gs_schedule_bells.load_schedule_sample", return_value=[]), patch(
            "guardschool.gs_schedule_bells.load_overrides", return_value=[]
        ), patch(
            "guardschool.gs_schedule_bells.get_screen_bell_entries_and_bells",
            return_value=([], {}, "Empty", None),
        ), patch("guardschool.gs_schedule_bells.wall_clock_minutes_for_config", return_value=12 * 60):
            payload = build_schedule_payload(screen, target, config)

        self.assertEqual(payload["today"], "2026-05-30")
        self.assertIn("today_rows", payload)
        self.assertIn("tomorrow_rows", payload)
        self.assertIn("bell_status", payload)
        self.assertEqual(payload["bell_status"]["state"], "no_bells")


class ScreenApiTests(TempDataDirMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self._prev_mode = os.environ.get("GUARDSCHOOL_DEPLOYMENT_MODE")
        os.environ["GUARDSCHOOL_DEPLOYMENT_MODE"] = "local"
        os.environ.pop("GUARDSCHOOL_TV_BEARER_TOKEN", None)
        os.environ.pop("GUARDSCHOOL_LAYER_PATH", None)

    def tearDown(self) -> None:
        if self._prev_mode is None:
            os.environ.pop("GUARDSCHOOL_DEPLOYMENT_MODE", None)
        else:
            os.environ["GUARDSCHOOL_DEPLOYMENT_MODE"] = self._prev_mode
        super().tearDown()

    def test_get_screen_json_includes_schedule_and_registry(self) -> None:
        from guardschool.gs_app_config import default_screen, sanitize_config
        from guardschool.gs_ensure_dirs import ensure_dirs
        from guardschool.gs_jsonio import write_json
        from guardschool.gs_paths import CONFIG_PATH
        from guardschool.gs_app_factory import create_app

        ensure_dirs()
        screen = default_screen("TV 1", "tv-1")
        write_json(CONFIG_PATH, sanitize_config({"screens": [screen]}))

        client = TestClient(create_app())
        response = client.get("/api/screen/tv-1")
        self.assertEqual(response.status_code, 200, msg=response.text)
        body = response.json()

        self.assertEqual(body["screen"]["slug"], "tv-1")
        self.assertIn("schedule", body)
        self.assertIn("today_rows", body["schedule"])
        self.assertIsInstance(body.get("widget_types_available"), list)
        self.assertIn("time", body["widget_types_available"])


class HealthApiTests(TempDataDirMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self._prev_mode = os.environ.get("GUARDSCHOOL_DEPLOYMENT_MODE")
        os.environ["GUARDSCHOOL_DEPLOYMENT_MODE"] = "local"

    def tearDown(self) -> None:
        if self._prev_mode is None:
            os.environ.pop("GUARDSCHOOL_DEPLOYMENT_MODE", None)
        else:
            os.environ["GUARDSCHOOL_DEPLOYMENT_MODE"] = self._prev_mode
        super().tearDown()

    def test_health_reports_version_and_writable_data(self) -> None:
        from guardschool.gs_app_factory import create_app
        from guardschool.gs_paths import APP_VERSION

        client = TestClient(create_app())
        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["product"], "GuardSchool")
        self.assertEqual(body["version"], APP_VERSION)
        self.assertEqual(body["deployment_mode"], "local")
        self.assertTrue(body["data_dir_writable"])
        self.assertEqual(body["status"], "ok")


if __name__ == "__main__":
    unittest.main()
