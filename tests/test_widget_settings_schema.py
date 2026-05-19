"""settings_schema в реестре виджетов."""
from __future__ import annotations

import unittest

from guardschool.capabilities import reset_capabilities_for_tests
from guardschool.widget_loader import reset_widget_loader_for_tests
from guardschool.widget_registry import reset_widget_registry_for_tests


def _reset() -> None:
    reset_capabilities_for_tests()
    reset_widget_registry_for_tests()
    reset_widget_loader_for_tests()


class WidgetSettingsSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        _reset()

    def test_time_widget_has_font_schema(self) -> None:
        from guardschool.widget_loader import load_all_widgets
        from guardschool.widget_registry import widget_registry_public

        load_all_widgets()
        reg = widget_registry_public()
        time_w = next(w for w in reg["widgets"] if w["type"] == "time")
        schema = time_w.get("settings_schema") or {}
        props = schema.get("properties") or {}
        self.assertIn("fontSize", props)
        self.assertEqual(props["fontSize"].get("type"), "integer")

    def test_custom_schema_not_overwritten(self) -> None:
        from guardschool.widget_registry import register_widget, widget_registry_public

        register_widget(
            {
                "type": "custom_test_widget",
                "title": "Custom",
                "settings_schema": {"type": "object", "properties": {"foo": {"type": "string"}}},
            },
        )
        reg = widget_registry_public()
        w = next(x for x in reg["widgets"] if x["type"] == "custom_test_widget")
        self.assertIn("foo", (w.get("settings_schema") or {}).get("properties", {}))


if __name__ == "__main__":
    unittest.main()
