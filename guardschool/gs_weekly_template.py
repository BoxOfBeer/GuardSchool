"""Шаблон Excel для недельного расписания (full_schedule_sample.xlsx)."""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from .gs_paths import FULL_SCHEDULE_SAMPLE_XLSX, IMPORT_DIR


def write_weekly_schedule_template_excel(path: Path) -> None:
    """Шаблон Excel: «День недели», «Класс», Урок1…Урок8 (как parse_weekly_schedule_excel)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Расписание"
    headers = ["День недели", "Класс"] + [f"Урок{i}" for i in range(1, 9)]
    ws.append(headers)
    for row in (
        ("Понедельник", "5А", "Математика", "Русский язык", "Литература", "Окр. мир", "", "", "", ""),
        ("Вторник", "5А", "История", "Английский язык", "Физическая культура", "", "", "", "", ""),
        ("Среда", "5А", "Математика", "Русский язык", "Технология", "Музыка", "", "", "", ""),
    ):
        ws.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(path))


def ensure_weekly_schedule_template_file() -> None:
    if FULL_SCHEDULE_SAMPLE_XLSX.exists():
        return
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        write_weekly_schedule_template_excel(FULL_SCHEDULE_SAMPLE_XLSX)
    except OSError:
        pass
