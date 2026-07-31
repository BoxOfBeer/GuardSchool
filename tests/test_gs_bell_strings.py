"""Локализация строк bell status."""
from __future__ import annotations

import unittest

from guardschool.gs_bell_strings import (
    bell_status_before,
    bell_status_no_entries,
    entry_slot_title,
    minutes_phrase,
    ui_locale_from_config,
)


class BellStringsTests(unittest.TestCase):
    def test_ui_locale_from_config(self) -> None:
        self.assertEqual(ui_locale_from_config({"ui_locale": "en"}), "en")
        self.assertEqual(ui_locale_from_config({"ui_locale": "RU"}), "ru")
        self.assertEqual(ui_locale_from_config({"ui_locale": "de"}), "ru")

    def test_minutes_phrase_ru(self) -> None:
        self.assertEqual(minutes_phrase(1, "ru"), "1 минута")
        self.assertEqual(minutes_phrase(3, "ru"), "3 минуты")
        self.assertEqual(minutes_phrase(5, "ru"), "5 минут")

    def test_minutes_phrase_en(self) -> None:
        self.assertEqual(minutes_phrase(1, "en"), "1 minute")
        self.assertEqual(minutes_phrase(5, "en"), "5 minutes")

    def test_entry_slot_title(self) -> None:
        self.assertEqual(entry_slot_title({"lesson": "3"}, "ru"), "слот 3")
        self.assertEqual(entry_slot_title({"lesson": "3"}, "en"), "slot 3")
        self.assertEqual(entry_slot_title({"lesson": "Line-up"}, "en"), "Line-up")

    def test_no_entries_en(self) -> None:
        d = bell_status_no_entries("en")
        self.assertIn("not configured", d["countdown_text"].lower())

    def test_before_en(self) -> None:
        d = bell_status_before("slot 1", "5 minutes", "en")
        self.assertIn("Until slot 1", d["message"])


if __name__ == "__main__":
    unittest.main()
