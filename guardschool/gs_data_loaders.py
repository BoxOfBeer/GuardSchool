"""Load schedule/holidays/announcements/marquee/overrides from tenant data/."""
from __future__ import annotations

from typing import Any

from .gs_app_config import load_config
from .gs_excel_import import (
    maybe_import_announcements_from_folder,
    maybe_import_full_schedule_from_folder,
    maybe_import_holidays_from_folder,
    maybe_import_marquee_from_folder,
    maybe_import_schedule_from_folder,
    maybe_import_schedule_sample_from_folder,
)
from .gs_jsonio import read_json
from .gs_paths import (
    ANNOUNCEMENTS_PATH,
    FULL_SCHEDULE_PATH,
    HOLIDAYS_PATH,
    MARQUEE_PATH,
    OVERRIDES_PATH,
    SCHEDULE_PATH,
    SCHEDULE_SAMPLE_PATH,
)
from .gs_rss_news import load_rss_news as load_rss_news_feed


def load_schedule() -> list[dict[str, Any]]:
    maybe_import_schedule_from_folder()
    return read_json(SCHEDULE_PATH, [])


def load_full_schedule() -> list[dict[str, Any]]:
    maybe_import_full_schedule_from_folder()
    return read_json(FULL_SCHEDULE_PATH, [])


def load_schedule_sample() -> list[dict[str, Any]]:
    maybe_import_schedule_sample_from_folder()
    return read_json(SCHEDULE_SAMPLE_PATH, [])


def load_holidays() -> list[dict[str, Any]]:
    maybe_import_holidays_from_folder()
    return read_json(HOLIDAYS_PATH, [])


def load_announcements() -> list[dict[str, Any]]:
    maybe_import_announcements_from_folder()
    return read_json(ANNOUNCEMENTS_PATH, [])


def load_marquee_items() -> list[str]:
    maybe_import_marquee_from_folder()
    raw = read_json(MARQUEE_PATH, [])
    return [str(x).strip() for x in raw if str(x).strip()]


def load_overrides() -> list[dict[str, Any]]:
    return read_json(OVERRIDES_PATH, [])


def load_rss_news(config: dict[str, Any] | None = None, *, force_refresh: bool = False) -> list[dict[str, Any]]:
    cfg = config if config is not None else load_config()
    return load_rss_news_feed(cfg, force_refresh=force_refresh)
