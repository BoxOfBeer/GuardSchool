"""Статус звонков на сегодня (build_bell_status)."""
from __future__ import annotations

from datetime import date
from typing import Any

from . import gs_bell_strings as _bell_i18n
from .gs_app_config import load_config
from .gs_bell_entries import (
    entry_academic_num,
    entry_is_academic,
    entry_slot_title,
    last_academic_lesson_ended_before,
    minutes_phrase,
    next_academic_lesson_after_index,
    time_to_minutes,
)


def build_bell_status(
    screen: dict[str, Any], target_date: date, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    # Через фасад — чтобы unittest.mock.patch на gs_schedule_bells.* работал.
    from . import gs_schedule_bells as _facade

    entries, _bells, source_name, _tpl = _facade.get_screen_bell_entries_and_bells(screen, target_date)
    cfg = config if config is not None else load_config()
    loc = _bell_i18n.ui_locale_from_config(cfg)
    now_minutes = _facade.wall_clock_minutes_for_config(cfg)
    status = {
        "template_name": source_name,
        "entries": entries,
        "current_lesson": None,
        "next_lesson": None,
        "state": "done",
        **_bell_i18n.bell_status_idle_defaults(loc),
    }

    if not entries:
        # Не "done": иначе виджет расписания на ТВ скрывает таблицу на сегодня (как после последнего сигнала).
        status["state"] = "no_bells"
        status.update(_bell_i18n.bell_status_no_entries(loc))
        return status

    first_start = time_to_minutes(entries[0]["start"])
    if now_minutes < first_start:
        diff = first_start - now_minutes
        status["state"] = "before"
        first = entries[0]
        cap = entry_slot_title(first, loc)
        status["next_lesson"] = entry_academic_num(first)
        mp = minutes_phrase(diff, loc)
        status.update(_bell_i18n.bell_status_before(cap, mp, loc))
        return status

    for index, entry in enumerate(entries):
        start = time_to_minutes(entry["start"])
        end = time_to_minutes(entry["end"])
        if start <= now_minutes <= end:
            diff = end - now_minutes
            if not entry_is_academic(entry):
                last_ac = last_academic_lesson_ended_before(entries, now_minutes)
                next_ac = next_academic_lesson_after_index(entries, index)
                label = entry_slot_title(entry, loc)
                mp = minutes_phrase(diff, loc)
                status["state"] = "activity"
                status["current_lesson"] = last_ac
                status["next_lesson"] = next_ac
                status.update(_bell_i18n.bell_status_activity(label, mp, loc))
                return status
            ln = entry_academic_num(entry)
            if ln is None:
                ln = 0
            shown = entry_slot_title(entry, loc)
            mp = minutes_phrase(diff, loc)
            status["state"] = "lesson"
            status["current_lesson"] = ln
            status.update(_bell_i18n.bell_status_lesson(shown, mp, loc))
            return status
        next_start = time_to_minutes(entries[index + 1]["start"]) if index + 1 < len(entries) else None
        if end < now_minutes and next_start is not None and now_minutes < next_start:
            diff = next_start - now_minutes
            last_ac = last_academic_lesson_ended_before(entries, now_minutes)
            next_ac = next_academic_lesson_after_index(entries, index)
            ended_entry = entries[index]
            ended_label = entry_slot_title(ended_entry, loc)
            mp = minutes_phrase(diff, loc)
            status["state"] = "break"
            status["current_lesson"] = last_ac
            status["next_lesson"] = next_ac
            status.update(_bell_i18n.bell_status_break(ended_label, mp, loc))
            return status

    status.update(_bell_i18n.bell_status_day_done(loc))
    return status


def tomorrow_schedule_visible(bell_status: dict[str, Any]) -> bool:
    """Блок «следующий рабочий день» на ТВ — только после окончания последнего интервала дня (сигналы завершены)."""
    return bell_status.get("state") == "done"
