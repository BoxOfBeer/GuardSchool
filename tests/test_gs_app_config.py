"""Unit-тесты sanitize_config, migrate_screen_layout, load_config."""
from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path

from guardschool.gs_app_config import (
    GRID_COLS,
    GRID_ROWS,
    default_config,
    load_config,
    migrate_screen_layout,
    sanitize_config,
)
from guardschool.widget_loader import load_all_widgets

_PATH_MODULES = (
    "guardschool.gs_paths",
    "guardschool.gs_jsonio",
    "guardschool.gs_app_config",
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
        os.environ["GUARDSCHOOL_DEPLOYMENT_MODE"] = "local"
        _reload_data_path_modules()
        from guardschool.capabilities import reset_capabilities_for_tests
        from guardschool.widget_loader import reset_widget_loader_for_tests
        from guardschool.widget_registry import reset_widget_registry_for_tests

        reset_capabilities_for_tests()
        reset_widget_registry_for_tests()
        reset_widget_loader_for_tests()
        load_all_widgets()

    def tearDown(self) -> None:
        self._td.cleanup()
        if self._prev_data_dir is None:
            os.environ.pop("GUARDSCHOOL_DATA_DIR", None)
        else:
            os.environ["GUARDSCHOOL_DATA_DIR"] = self._prev_data_dir
        _reload_data_path_modules()


class SanitizeConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        load_all_widgets()

    def test_sanitize_sets_template_grid_version(self) -> None:
        out = sanitize_config({})
        self.assertEqual(out["templateSystem"]["version"], 2)
        self.assertEqual(out["templateSystem"]["grid"], {"cols": GRID_COLS, "rows": GRID_ROWS})

    def test_sanitize_invalid_timezone_falls_back(self) -> None:
        cfg = default_config()
        cfg["timezone"] = "TotallyInvalid"
        out = sanitize_config(cfg)
        self.assertEqual(out["timezone"], "Europe/Moscow")

    def test_sanitize_invalid_ui_locale_falls_back_ru(self) -> None:
        cfg = default_config()
        cfg["ui_locale"] = "de"
        out = sanitize_config(cfg)
        self.assertEqual(out["ui_locale"], "ru")

    def test_sanitize_pwa_profile_and_legacy_default(self) -> None:
        self.assertEqual(sanitize_config({})["pwa"], {"title": "", "icon_url": ""})
        cfg = default_config()
        cfg["pwa"] = {"title": "  Моя организация  ", "icon_url": "/uploads/widget_images/app.png"}
        out = sanitize_config(cfg)
        self.assertEqual(out["pwa"]["title"], "Моя организация")
        self.assertEqual(out["pwa"]["icon_url"], "/uploads/widget_images/app.png")

    def test_sanitize_pwa_rejects_external_icon(self) -> None:
        cfg = default_config()
        cfg["pwa"] = {"title": "Приложение", "icon_url": "https://example.test/icon.png"}
        self.assertEqual(sanitize_config(cfg)["pwa"]["icon_url"], "")

    def test_sanitize_carousel_drops_orphan_child_ids(self) -> None:
        cfg = default_config()
        screen = cfg["screens"][0]
        screen["widgets"].append(
            {
                "id": "carousel1",
                "type": "carousel",
                "title": "Карусель",
                "enabled": True,
                "x": 0,
                "y": 10,
                "w": 32,
                "h": 8,
                "settings": {"childWidgetIds": ["missing_widget", "date"], "childSlideSec": {"missing_widget": 5}},
            }
        )
        out = sanitize_config(cfg)
        carousel = next(w for w in out["screens"][0]["widgets"] if w["type"] == "carousel")
        child_ids = carousel["settings"]["childWidgetIds"]
        self.assertNotIn("missing_widget", child_ids)
        self.assertNotIn("missing_widget", carousel["settings"]["childSlideSec"])
        self.assertTrue(child_ids)

    def test_migrate_screen_layout_from_legacy_grid(self) -> None:
        screen = default_config()["screens"][0]
        screen["widgets"] = [{"id": "time", "type": "time", "x": 99, "y": 99, "w": 1, "h": 1, "settings": {}}]
        migrated = migrate_screen_layout(screen, old_cols=16, old_rows=20)
        time_w = next(w for w in migrated["widgets"] if w["type"] == "time")
        default_time = next(w for w in default_config()["screens"][0]["widgets"] if w["type"] == "time")
        self.assertEqual(time_w["x"], default_time["x"])
        self.assertEqual(time_w["w"], default_time["w"])


class LoadConfigPersistenceTests(TempDataDirMixin, unittest.TestCase):
    def test_load_config_migrates_legacy_grid_in_memory(self) -> None:
        from guardschool.gs_jsonio import write_json
        from guardschool.gs_paths import CONFIG_PATH

        legacy = default_config()
        legacy["templateSystem"] = {"version": 1, "grid": {"cols": 16, "rows": 20}}
        write_json(CONFIG_PATH, legacy)

        cfg = load_config()
        self.assertEqual(cfg["templateSystem"]["grid"], {"cols": GRID_COLS, "rows": GRID_ROWS})
        time_w = next(w for w in cfg["screens"][0]["widgets"] if w["type"] == "time")
        default_time = next(w for w in default_config()["screens"][0]["widgets"] if w["type"] == "time")
        self.assertEqual(time_w["x"], default_time["x"])


if __name__ == "__main__":
    unittest.main()
