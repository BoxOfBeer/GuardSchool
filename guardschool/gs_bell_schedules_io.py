"""Загрузка bell_schedules.json, миграция, нормализация дат и цветов."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from .gs_jsonio import read_json
from .gs_paths import BELL_SCHEDULES_PATH

def default_bell_schedules() -> dict[str, Any]:
    return {
        "templates": [
            {
                "id": "standard",
                "name": "Обычное",
                "entries": [
                    {"lesson": "1", "start": "08:30", "end": "09:15"},
                    {"lesson": "2", "start": "09:25", "end": "10:10"},
                    {"lesson": "3", "start": "10:30", "end": "11:15"},
                    {"lesson": "4", "start": "11:35", "end": "12:20"},
                    {"lesson": "5", "start": "12:30", "end": "13:15"},
                    {"lesson": "6", "start": "13:25", "end": "14:10"},
                    {"lesson": "7", "start": "14:20", "end": "15:05"},
                    {"lesson": "8", "start": "15:15", "end": "16:00"},
                ],
            },
            {
                "id": "short",
                "name": "Сокращенное",
                "entries": [
                    {"lesson": "1", "start": "08:30", "end": "09:05"},
                    {"lesson": "2", "start": "09:15", "end": "09:50"},
                    {"lesson": "3", "start": "10:00", "end": "10:35"},
                    {"lesson": "4", "start": "10:45", "end": "11:20"},
                    {"lesson": "5", "start": "11:30", "end": "12:05"},
                    {"lesson": "6", "start": "12:15", "end": "12:50"},
                    {"lesson": "7", "start": "13:00", "end": "13:35"},
                    {"lesson": "8", "start": "13:45", "end": "14:20"},
                ],
            },
        ],
        "date_overrides": [],
        "weekday_overrides": {},
        "sound_defaults": {"start": None, "end": None},
    }


def schedule_date_iso(raw: Any) -> str:
    """Поле date в schedule.json / override → YYYY-MM-DD для сравнения (Excel dd.mm.yyyy, datetime-строки)."""
    if raw is None:
        return ""
    if isinstance(raw, datetime):
        return raw.date().isoformat()
    if isinstance(raw, date):
        return raw.isoformat()
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        try:
            n = int(raw)
        except (TypeError, ValueError):
            n = 0
        # Серийный номер даты Excel (часто попадает в JSON при ручном экспорте)
        if 29500 < n < 65000:
            try:
                return (date(1899, 12, 30) + timedelta(days=n)).isoformat()
            except (OverflowError, ValueError):
                return ""
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    if "T" in s:
        s = s.split("T", 1)[0].strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        head = s[:10]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", head):
            return head
    if re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{4}", s):
        try:
            return datetime.strptime(s, "%d.%m.%Y").date().isoformat()
        except ValueError:
            return ""
    return ""


def _norm_hex_color(value: Any) -> str | None:
    """Нормализация цвета (#RRGGBB) для ручной замены; None если невалидно/пусто."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if re.fullmatch(r"#[0-9a-fA-F]{6}", s):
        return s.lower()
    return None


def migrate_bell_schedules(raw: dict[str, Any]) -> dict[str, Any]:
    data = dict(raw)
    data.setdefault("sound_defaults", {"start": None, "end": None})
    sd = data.get("sound_defaults")
    if not isinstance(sd, dict):
        data["sound_defaults"] = {"start": None, "end": None}
    else:
        sd.setdefault("start", None)
        sd.setdefault("end", None)

    def fix_entries(entries: list[dict[str, Any]]) -> None:
        for ent in entries:
            if ent.get("is_lesson") is False and str(ent.get("label") or "").strip():
                if not str(ent.get("lesson") or "").strip():
                    ent["lesson"] = str(ent["label"]).strip()
            if "lesson" in ent and ent["lesson"] is not None and not isinstance(ent["lesson"], str):
                ent["lesson"] = str(ent["lesson"]).strip()

    for tpl in data.get("templates", []):
        tpl.setdefault("last_lesson", None)
        fix_entries(tpl.get("entries", []))
    for ov in data.get("date_overrides", []):
        ov.setdefault("last_lesson", None)
        fix_entries(ov.get("entries", []))
    return data


def load_bell_schedules() -> dict[str, Any]:
    return migrate_bell_schedules(read_json(BELL_SCHEDULES_PATH, default_bell_schedules()))
