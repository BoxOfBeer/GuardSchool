"""Demo-seed при первой настройке и проверка PyInstaller spec."""
from __future__ import annotations

import importlib
import os
import re
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
_REQUIRED_SPEC_DATAS = ("static", "widgets", "change_log_seed.json")


def _reload_data_path_modules() -> None:
    import guardschool.gs_paths as gs_paths

    importlib.reload(gs_paths)
    for name in (
        "guardschool.gs_jsonio",
        "guardschool.gs_ensure_dirs",
        "guardschool.gs_app_config",
        "guardschool.gs_community_seed",
        "guardschool.gs_auth",
        "guardschool.routes_auth",
    ):
        mod = importlib.import_module(name)
        importlib.reload(mod)


class CommunitySeedTests(unittest.TestCase):
    def setUp(self) -> None:
        self._prev_data_dir = os.environ.get("GUARDSCHOOL_DATA_DIR")
        self._prev_mode = os.environ.get("GUARDSCHOOL_DEPLOYMENT_MODE")
        self._prev_skip = os.environ.get("GUARDSCHOOL_SKIP_DEMO_SEED")
        os.environ.pop("GUARDSCHOOL_SKIP_DEMO_SEED", None)
        os.environ["GUARDSCHOOL_DEPLOYMENT_MODE"] = "local"
        self._td = tempfile.TemporaryDirectory()
        os.environ["GUARDSCHOOL_DATA_DIR"] = self._td.name
        _reload_data_path_modules()
        from guardschool.capabilities import reset_capabilities_for_tests
        from guardschool.widget_loader import load_all_widgets, reset_widget_loader_for_tests
        from guardschool.widget_registry import reset_widget_registry_for_tests

        reset_capabilities_for_tests()
        reset_widget_registry_for_tests()
        reset_widget_loader_for_tests()
        load_all_widgets()

    def tearDown(self) -> None:
        self._td.cleanup()
        for key, val in (
            ("GUARDSCHOOL_DATA_DIR", self._prev_data_dir),
            ("GUARDSCHOOL_DEPLOYMENT_MODE", self._prev_mode),
            ("GUARDSCHOOL_SKIP_DEMO_SEED", self._prev_skip),
        ):
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        _reload_data_path_modules()

    def test_seed_writes_config_and_schedule(self) -> None:
        from guardschool.gs_community_seed import seed_community_demo_data_if_empty
        from guardschool.gs_jsonio import read_json
        from guardschool.gs_paths import ANNOUNCEMENTS_PATH, CONFIG_PATH, FULL_SCHEDULE_PATH

        self.assertTrue(seed_community_demo_data_if_empty())
        self.assertFalse(seed_community_demo_data_if_empty())
        self.assertTrue(CONFIG_PATH.is_file())
        rows = read_json(FULL_SCHEDULE_PATH, [])
        self.assertGreaterEqual(len(rows), 5)
        announcements = read_json(ANNOUNCEMENTS_PATH, [])
        self.assertGreaterEqual(len(announcements), 1)

    def test_setup_admin_triggers_seed(self) -> None:
        import guardschool.gs_auth as gs_auth
        import guardschool.routes_auth as routes_auth

        importlib.reload(gs_auth)
        importlib.reload(routes_auth)
        from guardschool.gs_app_factory import create_app
        from guardschool.gs_paths import CONFIG_PATH, FULL_SCHEDULE_PATH

        client = TestClient(create_app())
        r = client.post("/api/setup", data={"username": "admin", "password": "Secret1a"})
        self.assertEqual(r.status_code, 200, msg=r.text)
        self.assertTrue(CONFIG_PATH.is_file())
        self.assertTrue(FULL_SCHEDULE_PATH.is_file())


class PyInstallerSpecTests(unittest.TestCase):
    def _datas_from_spec(self, path: Path) -> list[str]:
        text = path.read_text(encoding="utf-8")
        found: list[str] = []
        for entry in re.findall(r"_datas\s*=\s*\[(.*?)\]", text, re.S):
            for item in re.findall(r"\('([^']+)'", entry):
                found.append(item)
            for item in re.findall(r'\("([^"]+)"', entry):
                found.append(item)
        return found

    def test_specs_include_runtime_assets(self) -> None:
        for name in ("GuardSchool.spec", "GuardSchool_full.spec"):
            spec = ROOT / name
            self.assertTrue(spec.is_file(), msg=f"missing {name}")
            datas = self._datas_from_spec(spec)
            for required in _REQUIRED_SPEC_DATAS:
                self.assertIn(required, datas, msg=f"{name} missing datas entry {required!r}")


if __name__ == "__main__":
    unittest.main()
