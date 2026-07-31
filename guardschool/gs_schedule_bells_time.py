"""Часовой пояс и «сегодня» для расписания/звонков."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

def _tzinfo_from_config_timezone(tzname: str):
    key = (tzname or "").strip() or "Europe/Moscow"
    for cand in (key, "Europe/Moscow"):
        try:
            return ZoneInfo(cand)
        except Exception:
            continue
    lt = datetime.now().astimezone().tzinfo
    return lt if lt is not None else timezone.utc


def display_settings_dict(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "timezone": str((config or {}).get("timezone") or "Europe/Moscow"),
        "clock_offset_minutes": int((config or {}).get("clock_offset_minutes") or 0),
        "ui_locale": str((config or {}).get("ui_locale") or "ru"),
    }


def calendar_today_for_config(config: dict[str, Any]) -> date:
    """«Сегодня» для расписания и звонков по часовому поясу из конфига."""
    tzname = str((config or {}).get("timezone") or "Europe/Moscow").strip()
    z = _tzinfo_from_config_timezone(tzname)
    return datetime.now(z).date()


def wall_clock_minutes_for_config(config: dict[str, Any]) -> int:
    """Минуты от полуночи в часовом поясе школы + clock_offset (согласовано с отображением времени на ТВ)."""
    tzname = str((config or {}).get("timezone") or "Europe/Moscow").strip()
    z = _tzinfo_from_config_timezone(tzname)
    try:
        off = int((config or {}).get("clock_offset_minutes") or 0)
    except (TypeError, ValueError):
        off = 0
    off = max(-720, min(720, off))
    now = datetime.now(z) + timedelta(minutes=off)
    return now.hour * 60 + now.minute
