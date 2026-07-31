"""Строки шаблона звонков, звуки, entry helpers."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from . import gs_bell_strings as _bell_i18n
from .gs_bell_schedules_io import default_bell_schedules, load_bell_schedules
from .gs_class_key import normalize_class
from .gs_ensure_dirs import ensure_dirs
from .gs_paths import BELL_SOUNDS_DIR, UPLOADS_DIR

PRE_BELL_LEAD_MINUTES = 1
PRE_BELL_FIRE_SEC_WINDOW = 12
PRE_BELL_MAX_DURATION_SEC = 52
PRE_BELL_AFADE_IN_SEC = 3.0
BREAK_ORCH_HEAD_SEC = 60
BREAK_ORCH_FADE_SEC = 120
BREAK_ORCH_SILENCE_SEC = 60
BREAK_ORCH_START_BELL_SEC = 60
MORNING_PRE_FIRST_LESSON_MIN = 30

def time_to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def minutes_phrase(n: int, locale: str = "ru") -> str:
    """Склонение для фразы «N минут» в статусе сигналов (ru/en)."""
    return _bell_i18n.minutes_phrase(n, locale)


def as_lesson_number(value: Any) -> int | None:
    """Номер урока в шаблоне / расписании может прийти строкой из JSON или Excel."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def entry_academic_num(entry: dict[str, Any]) -> int | None:
    """Только если в «Урок» одни цифры — номер для связи с расписанием Excel (Урок1…8)."""
    raw = entry.get("lesson")
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if re.fullmatch(r"\d+", s):
        return int(s)
    return None


def entry_is_academic(entry: dict[str, Any]) -> bool:
    return entry_academic_num(entry) is not None


def entry_slot_title(entry: dict[str, Any], locale: str = "ru") -> str:
    """Краткое имя интервала для строк состояния (им. падеж после «Идёт» / «Закончился»)."""
    return _bell_i18n.entry_slot_title(entry, locale, academic_num=entry_academic_num(entry))


def last_academic_lesson_ended_before(entries: list[dict[str, Any]], now_minutes: int) -> int | None:
    """Номер последнего академического урока, который уже закончился к моменту now_minutes."""
    last: int | None = None
    for e in entries:
        ln = entry_academic_num(e)
        if ln is None:
            continue
        if time_to_minutes(e["end"]) < now_minutes:
            last = ln
    return last


def next_academic_lesson_after_index(entries: list[dict[str, Any]], after_index: int) -> int | None:
    """Следующий номер академического урока среди записей с индексом > after_index."""
    for i in range(after_index + 1, len(entries)):
        ln = entry_academic_num(entries[i])
        if ln is not None:
            return ln
    return None


def display_name_for_academic_lesson_number(
    entries: list[dict[str, Any]], lesson_num: int | None, locale: str = "ru"
) -> str:
    return _bell_i18n.display_name_for_academic_lesson_number(entries, lesson_num, locale)


def get_screen_bell_entries_and_bells(
    screen: dict[str, Any], target_date: date
) -> tuple[list[dict[str, Any]], dict[str, Any], str, dict[str, Any] | None]:
    """entries, bells, имя источника, активный шаблон или разовое переопределение (для last_lesson и т.п.)."""
    bells = load_bell_schedules()
    iso_date = target_date.isoformat()
    weekday = str(target_date.weekday())
    template_id = screen.get("bell_schedule_template") or "standard"

    date_override = next((item for item in bells.get("date_overrides", []) if item.get("date") == iso_date), None)
    if date_override:
        entries = date_override.get("entries", [])
        source_name = date_override.get("name", "Разовое")
        return entries, bells, source_name, date_override
    weekday_override_id = screen.get("weekday_bell_templates", {}).get(weekday) or bells.get("weekday_overrides", {}).get(weekday)
    if weekday_override_id:
        template_id = weekday_override_id
    template = next((item for item in bells.get("templates", []) if item.get("id") == template_id), None)
    if not template:
        template = bells.get("templates", [default_bell_schedules()["templates"][0]])[0]
    entries = template.get("entries", [])
    source_name = template.get("name", "Обычное")
    return entries, bells, source_name, template


def last_lesson_cap(template: dict[str, Any] | None) -> int | None:
    """Последний номер урока, после которого звонки «начало/конец» для больших номеров отключены; None — без ограничения."""
    if not template:
        return None
    raw = template.get("last_lesson")
    if raw is None:
        return None
    if isinstance(raw, str) and not str(raw).strip():
        return None
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None
    return max(1, min(24, n))


def resolve_bell_sound_url(filename: str | None) -> str | None:
    if not filename or not str(filename).strip():
        return None
    fn = str(filename).strip()
    if fn.startswith("/"):
        return fn
    p = BELL_SOUNDS_DIR / fn
    if p.is_file():
        return f"/uploads/bells/{fn}"
    p2 = UPLOADS_DIR / fn
    if p2.is_file():
        return f"/uploads/{fn}"
    return None


def bell_audio_url_to_path(url: str | None) -> Path | None:
    """Локальный путь к файлу звонка по URL из build_bell_audio_payload (только /uploads/…)."""
    if not url:
        return None
    u = str(url).strip()
    rest: str
    base: Path
    if u.startswith("/uploads/bells/"):
        rest = u[len("/uploads/bells/") :]
        base = BELL_SOUNDS_DIR
    elif u.startswith("/uploads/"):
        rest = u[len("/uploads/") :]
        base = UPLOADS_DIR
    else:
        return None
    name = Path(rest).name
    if not name:
        return None
    p = base / name
    return p if p.is_file() else None


def pick_entry_sound(ent: dict[str, Any], key: str, default_url: str | None) -> str | None:
    if key not in ent:
        return default_url
    raw = ent.get(key)
    if raw is None:
        return default_url
    s = str(raw).strip()
    if s in ("", "-", "none", "—"):
        return None
    return resolve_bell_sound_url(s) or default_url
