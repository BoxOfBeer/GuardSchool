"""Локализованные строки статуса сигналов (ТВ / preview) — ru/en из config.ui_locale."""
from __future__ import annotations

import re
from typing import Any


def ui_locale_from_config(config: dict[str, Any] | None) -> str:
    loc = str((config or {}).get("ui_locale") or "ru").strip().lower()
    return loc if loc in ("en", "ru") else "ru"


def minutes_phrase(n: int, locale: str = "ru") -> str:
    n = int(n)
    if locale == "en":
        return f"{n} minute" if n == 1 else f"{n} minutes"
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} минута"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} минуты"
    return f"{n} минут"


def entry_slot_title(entry: dict[str, Any], locale: str = "ru", *, academic_num: int | None = None) -> str:
    """Краткое имя интервала (им. падеж после «Идёт» / «Закончился»)."""
    n = academic_num
    if n is None:
        raw = entry.get("lesson")
        if raw is not None:
            s = str(raw).strip()
            if s and re.fullmatch(r"\d+", s):
                n = int(s)
    if n is not None:
        return f"slot {n}" if locale == "en" else f"слот {n}"
    s = str(entry.get("lesson") or "").strip()
    if s:
        return s
    return "Interval" if locale == "en" else "Интервал"


def display_name_for_academic_lesson_number(
    entries: list[dict[str, Any]],
    lesson_num: int | None,
    locale: str = "ru",
) -> str:
    if lesson_num is None:
        return "next activity" if locale == "en" else "следующего занятия"
    for e in entries:
        raw = e.get("lesson")
        if raw is not None and str(raw).strip() == str(lesson_num):
            return entry_slot_title(e, locale, academic_num=lesson_num)
    return entry_slot_title({}, locale, academic_num=lesson_num)


def bell_status_idle_defaults(locale: str) -> dict[str, str]:
    if locale == "en":
        return {
            "message": "Activities finished",
            "countdown_text": "No signals",
            "schedule_title": "Slots finished",
        }
    return {
        "message": "Занятия завершены",
        "countdown_text": "Сигналов нет",
        "schedule_title": "Слоты закончились",
    }


def bell_status_no_entries(locale: str) -> dict[str, str]:
    if locale == "en":
        return {
            "message": "Signal schedule not set",
            "countdown_text": "Signals not configured",
            "schedule_title": "Schedule not set",
        }
    return {
        "message": "Расписание сигналов не задано",
        "countdown_text": "Сигналы не настроены",
        "schedule_title": "Расписание не задано",
    }


def bell_status_before(cap: str, mp: str, locale: str) -> dict[str, str]:
    if locale == "en":
        line = f"Until {cap}, {mp}"
        return {"message": line, "countdown_text": f"Remaining {mp}", "schedule_title": line}
    line = f"До {cap}, {mp}"
    return {"message": line, "countdown_text": f"Осталось {mp}", "schedule_title": line}


def bell_status_activity(label: str, mp: str, locale: str) -> dict[str, str]:
    if locale == "en":
        line = f"In progress: {label}, until end {mp}"
        return {"message": line, "countdown_text": f"Until end — {mp}", "schedule_title": line}
    line = f"Идёт {label}, до конца {mp}"
    return {"message": line, "countdown_text": f"До конца — {mp}", "schedule_title": line}


def bell_status_lesson(shown: str, mp: str, locale: str) -> dict[str, str]:
    if locale == "en":
        line = f"In progress: {shown}, until break {mp}"
        return {"message": line, "countdown_text": f"Until break {mp}", "schedule_title": line}
    line = f"Идёт {shown}, до перемены {mp}"
    return {"message": line, "countdown_text": f"До перемены {mp}", "schedule_title": line}


def bell_status_break(ended_label: str, mp: str, locale: str) -> dict[str, str]:
    if locale == "en":
        line = f"Ended {ended_label}. Break {mp}"
        return {"message": line, "countdown_text": f"Break {mp}", "schedule_title": line}
    line = f"Закончился {ended_label}. Перемена {mp}"
    return {"message": line, "countdown_text": f"Перемена {mp}", "schedule_title": line}


def bell_status_day_done(locale: str) -> dict[str, str]:
    if locale == "en":
        return {"countdown_text": "Activities finished", "schedule_title": "Slots finished"}
    return {"countdown_text": "Занятия завершены", "schedule_title": "Слоты закончились"}
