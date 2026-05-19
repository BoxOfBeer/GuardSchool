"""Паритет ключей static/locales/ru.json и en.json."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

LOCALES = Path(__file__).resolve().parent.parent / "static" / "locales"


class LocalesParityTests(unittest.TestCase):
    def test_ru_en_keys_match(self) -> None:
        ru = json.loads((LOCALES / "ru.json").read_text(encoding="utf-8"))
        en = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
        self.assertEqual(set(ru), set(en), f"ru-only={set(ru)-set(en)} en-only={set(en)-set(ru)}")
        self.assertGreaterEqual(len(ru), 500)
