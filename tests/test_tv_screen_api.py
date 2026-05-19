"""Тесты gs_tv_screen_api (slug, school code)."""
from __future__ import annotations

import unittest

from guardschool.gs_tv_screen_api import (
    canonical_tv_school_code,
    normalize_screen_slug_for_api,
    normalize_tv_pair_text,
    tv_school_code_compact,
)


class TvScreenApiTests(unittest.TestCase):
    def test_normalize_screen_slug_nfkc(self) -> None:
        self.assertEqual(normalize_screen_slug_for_api("TV-1"), "tv-1")

    def test_canonical_code_with_dashes(self) -> None:
        raw = normalize_tv_pair_text("abcd-efgh-jkmn").lower()
        self.assertEqual(canonical_tv_school_code(raw), "abcd-efgh-jkmn")

    def test_compact_twelve_chars(self) -> None:
        letters = tv_school_code_compact("abcd-efgh-jkmn")
        self.assertEqual(len(letters), 12)


if __name__ == "__main__":
    unittest.main()
