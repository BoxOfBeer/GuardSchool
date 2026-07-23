"""Unit-тесты реестра виджетов (open-core test plan)."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


def _reset_widget_state() -> None:
    from guardschool.capabilities import reset_capabilities_for_tests
    from guardschool.widget_loader import reset_widget_loader_for_tests
    from guardschool.widget_registry import reset_widget_registry_for_tests

    reset_capabilities_for_tests()
    reset_widget_registry_for_tests()
    reset_widget_loader_for_tests()


class WidgetRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        _reset_widget_state()
        os.environ["GUARDSCHOOL_DEPLOYMENT_MODE"] = "local"

    def tearDown(self) -> None:
        _reset_widget_state()

    def test_missing_widget_status(self) -> None:
        from guardschool.widget_registry import WidgetLoadStatus, explain_widget_status, widget_status

        self.assertEqual(widget_status("nonexistent_type_xyz"), WidgetLoadStatus.missing)
        msg = explain_widget_status("nonexistent_type_xyz")
        self.assertIn("nonexistent_type_xyz", msg)

    def test_api_version_too_new_not_registered(self) -> None:
        from guardschool.widget_registry import WidgetLoadStatus, get_widget, register_widget, widget_status

        register_widget({"type": "future_widget", "title": "Future", "api_version": 99})
        self.assertIsNone(get_widget("future_widget"))
        self.assertEqual(widget_status("future_widget"), WidgetLoadStatus.error)

    def test_api_version_old_registers_with_migration_warning(self) -> None:
        from guardschool.widget_registry import (
            CURRENT_WIDGET_API_VERSION,
            get_widget,
            register_widget,
            widget_registry_public,
        )

        if CURRENT_WIDGET_API_VERSION <= 1:
            old_ver = 0
        else:
            old_ver = CURRENT_WIDGET_API_VERSION - 1
        register_widget({"type": "legacy_widget", "title": "Legacy", "api_version": old_ver})
        self.assertIsNotNone(get_widget("legacy_widget"))
        reg = widget_registry_public()
        warnings = reg.get("migration_warnings") or []
        self.assertTrue(any("legacy_widget" in w for w in warnings))

    def test_broken_widget_file_sets_error(self) -> None:
        from guardschool.widget_loader import _load_py_modules_from_dir
        from guardschool.widget_registry import WidgetLoadStatus, explain_widget_status, widget_status

        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "broken_widget.py"
            bad.write_text("def syntax_error(:\n", encoding="utf-8")
            _load_py_modules_from_dir(Path(td), official=True)
            self.assertEqual(widget_status("broken_widget"), WidgetLoadStatus.error)
            self.assertTrue(explain_widget_status("broken_widget"))

    def test_valid_widget_module_loads(self) -> None:
        from guardschool.widget_loader import _load_py_modules_from_dir
        from guardschool.widget_registry import WidgetLoadStatus, get_widget, widget_status

        with tempfile.TemporaryDirectory() as td:
            good = Path(td) / "hello_test.py"
            good.write_text(
                'from guardschool.widget_registry import register_widget\n'
                'register_widget({"type": "hello_test", "title": "Hello", "api_version": 1, "official": False})\n',
                encoding="utf-8",
            )
            _load_py_modules_from_dir(Path(td), official=False)
            self.assertEqual(widget_status("hello_test"), WidgetLoadStatus.loaded)
            self.assertIsNotNone(get_widget("hello_test"))

    def test_time_widget_present_in_official_widgets_dir(self) -> None:
        """Регрессия: widgets/time.py должен быть в репозитории и грузиться."""
        from guardschool.widget_loader import load_all_widgets
        from guardschool.widget_registry import WidgetLoadStatus, widget_status

        load_all_widgets()
        self.assertEqual(widget_status("time"), WidgetLoadStatus.loaded)

    def test_booking_widget_keeps_valid_pwa_override(self) -> None:
        from guardschool.widget_loader import load_all_widgets
        from guardschool.widget_registry import normalize_widget

        load_all_widgets()
        widget = normalize_widget(
            {
                "id": "booking-test",
                "type": "booking_public",
                "settings": {
                    "pwa_title": "  Запись онлайн  ",
                    "pwa_icon_url": "/uploads/widget_images/booking.png",
                },
            }
        )
        self.assertEqual(widget["settings"]["pwa_title"], "Запись онлайн")
        self.assertEqual(widget["settings"]["pwa_icon_url"], "/uploads/widget_images/booking.png")

    def test_booking_widget_rejects_external_pwa_icon(self) -> None:
        from guardschool.widget_loader import load_all_widgets
        from guardschool.widget_registry import normalize_widget

        load_all_widgets()
        widget = normalize_widget(
            {"id": "booking-test", "type": "booking_manager", "settings": {"pwa_icon_url": "https://bad.test/x.png"}}
        )
        self.assertEqual(widget["settings"]["pwa_icon_url"], "")

    def test_booking_manager_sanitizes_public_button_colors(self) -> None:
        from guardschool.widget_loader import load_all_widgets
        from guardschool.widget_registry import normalize_widget

        load_all_widgets()
        widget = normalize_widget(
            {
                "id": "booking-test",
                "type": "booking_manager",
                "settings": {
                    "public_action_color": "#ABCDEF",
                    "public_free_color": "red",
                },
            }
        )
        self.assertEqual(widget["settings"]["public_action_color"], "#abcdef")
        self.assertEqual(widget["settings"]["public_free_color"], "#16a34a")
        self.assertEqual(widget["settings"]["public_booked_color"], "#b91c1c")


class CapabilitiesLocalTests(unittest.TestCase):
    def setUp(self) -> None:
        _reset_widget_state()
        os.environ["GUARDSCHOOL_DEPLOYMENT_MODE"] = "local"
        os.environ.pop("GUARDSCHOOL_LAYER_PATH", None)

    def tearDown(self) -> None:
        _reset_widget_state()

    def test_local_saas_capabilities_missing(self) -> None:
        from guardschool.capabilities import (
            CAP_CLOUD_SYNC,
            CAP_PUSH_NOTIFICATIONS,
            CapabilityStatus,
            get_capabilities,
        )

        caps = get_capabilities()
        self.assertEqual(caps[CAP_CLOUD_SYNC].status, CapabilityStatus.missing)
        self.assertEqual(caps[CAP_PUSH_NOTIFICATIONS].status, CapabilityStatus.missing)

    def test_local_core_widgets_available(self) -> None:
        from guardschool.capabilities import CAP_CUSTOM_WIDGETS, CAP_LOCAL_WIDGETS, CapabilityStatus, get_capabilities

        caps = get_capabilities()
        self.assertEqual(caps[CAP_LOCAL_WIDGETS].status, CapabilityStatus.available)
        self.assertEqual(caps[CAP_CUSTOM_WIDGETS].status, CapabilityStatus.available)


if __name__ == "__main__":
    unittest.main()
