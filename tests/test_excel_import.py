"""Тесты парсинга Excel (образцы из gs_import_sample_xlsx)."""
from __future__ import annotations

import tempfile
import unittest
from datetime import date
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook

from guardschool.gs_excel_import import (
    parse_announcements_excel,
    parse_excel,
    parse_holidays_excel,
    parse_marquee_excel,
    parse_weekly_schedule_excel,
)
from guardschool.gs_import_sample_xlsx import import_excel_sample_bytes


def _write_sample(kind: str, lang: str = "ru") -> Path:
    raw, _ = import_excel_sample_bytes(kind=kind, lang=lang)
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    path = Path(tmp.name)
    tmp.write(raw)
    tmp.close()
    return path


def _write_xlsx_bytes(save_fn) -> Path:
    buf = BytesIO()
    save_fn(buf)
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    path = Path(tmp.name)
    path.write_bytes(buf.getvalue())
    return path


class ExcelImportTests(unittest.TestCase):
    def test_parse_dated_schedule_sample(self) -> None:
        path = _write_sample("dated")
        try:
            rows = parse_excel(path, lang="ru")
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["date"], "2025-09-01")
            self.assertEqual(row["class_key"], "5а")
            subjects = [les["subject"] for les in row["lessons"] if les.get("subject")]
            self.assertIn("Математика", subjects)
        finally:
            path.unlink(missing_ok=True)

    def test_parse_weekly_schedule_sample(self) -> None:
        path = _write_sample("weekly")
        try:
            rows = parse_weekly_schedule_excel(path, lang="en")
            self.assertGreaterEqual(len(rows), 3)
            monday = next(r for r in rows if r["weekday"] == 0 and r["class_key"] == "5а")
            lesson1 = next(l for l in monday["lessons"] if l["index"] == 1)
            self.assertEqual(lesson1["subject"], "Математика")
        finally:
            path.unlink(missing_ok=True)

    def test_parse_holidays_sample(self) -> None:
        path = _write_sample("holidays")
        try:
            rows = parse_holidays_excel(path, lang="ru")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["name"], "День Победы")
            self.assertEqual(rows[0]["date"], "2025-05-09")
        finally:
            path.unlink(missing_ok=True)

    def test_parse_announcements_sample(self) -> None:
        path = _write_sample("announcements")
        try:
            rows = parse_announcements_excel(path, lang="ru")
            self.assertGreaterEqual(len(rows), 1)
            combined = "\n".join(r["text"] for r in rows).lower()
            self.assertIn("педсовет", combined)
        finally:
            path.unlink(missing_ok=True)

    def test_parse_marquee_sample(self) -> None:
        path = _write_sample("marquee")
        try:
            lines = parse_marquee_excel(path, lang="ru")
            self.assertEqual(len(lines), 1)
            self.assertIn("экрана", lines[0].lower())
        finally:
            path.unlink(missing_ok=True)

    def test_parse_dated_schedule_neutral_column_headers(self) -> None:
        def _build(buf: BytesIO) -> None:
            wb = Workbook()
            ws = wb.active
            ws.append(["Date", "Group", "Slot1", "Slot2"])
            ws.append([date(2025, 9, 1), "5A", "Math", "English"])
            wb.save(buf)

        path = _write_xlsx_bytes(_build)
        try:
            rows = parse_excel(path, lang="en")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["date"], "2025-09-01")
            subjects = [les["subject"] for les in rows[0]["lessons"]]
            self.assertIn("Math", subjects)
        finally:
            path.unlink(missing_ok=True)

    def test_parse_weekly_schedule_neutral_column_headers(self) -> None:
        def _build(buf: BytesIO) -> None:
            wb = Workbook()
            ws = wb.active
            ws.append(["Weekday", "Group", "Slot1", "Slot2"])
            ws.append(["Monday", "5A", "Math", "English"])
            wb.save(buf)

        path = _write_xlsx_bytes(_build)
        try:
            rows = parse_weekly_schedule_excel(path, lang="en")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["weekday"], 0)
            self.assertEqual(rows[0]["class_name"], "5A")
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
