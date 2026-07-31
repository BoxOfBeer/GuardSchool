"""Extract gs_screen_push, gs_data_loaders, gs_schedule_bells from app.py."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "guardschool" / "app.py"
lines = APP.read_text(encoding="utf-8").splitlines(keepends=True)


def sl(s: int, e: int) -> str:
    return "".join(lines[s - 1 : e])


def push() -> None:
    body = sl(2093, 2434)
    # Public names for routes_admin / app
    repl = [
        ("def _screen_slugs_mobile_active", "def screen_slugs_mobile_active"),
        ("def _notify_push_screen_content_refresh_for_mobile_screens", "def notify_push_screen_content_refresh_for_mobile_screens"),
        ("def _maybe_push_screen_content_if_data_revision_changed", "def maybe_push_screen_content_if_data_revision_changed"),
        ("def _checkin_monitor_screens_for_events_slug", "def checkin_monitor_screens_for_events_slug"),
        ("def _checkin_count_unconfirmed", "def checkin_count_unconfirmed"),
        ("def _checkin_push_target_slugs_for_events_screen", "def checkin_push_target_slugs_for_events_screen"),
        ("def _checkin_level_display_label", "def checkin_level_display_label"),
        ("def _checkin_monitor_widget_for_submit", "def checkin_monitor_widget_for_submit"),
        ("def _checkin_place_title_from_submit_places", "def checkin_place_title_from_submit_places"),
        ("def _checkin_place_title_from_monitor", "def checkin_place_title_from_monitor"),
        ("def _notify_push_checkin_journal_new_row", "def notify_push_checkin_journal_new_row"),
        ("def _notify_push_checkin_journal_confirmed", "def notify_push_checkin_journal_confirmed"),
        ("def _notify_push_checkin_journal_bulk_confirm", "def notify_push_checkin_journal_bulk_confirm"),
        ("def _notify_push_emergency_change", "def notify_push_emergency_change"),
    ]
    for old, new in repl:
        body = body.replace(old, new)
    # Internal calls within module
    for name in [
        "screen_slugs_mobile_active",
        "notify_push_screen_content_refresh_for_mobile_screens",
        "checkin_monitor_screens_for_events_slug",
        "checkin_push_target_slugs_for_events_screen",
        "checkin_level_display_label",
        "checkin_monitor_widget_for_submit",
        "checkin_place_title_from_submit_places",
        "checkin_place_title_from_monitor",
    ]:
        body = body.replace(f"_{name}(", f"{name}(")
    hdr = '''"""Web Push helpers: content revision, checkin journal, emergency."""
from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import quote

from fastapi import Request

from .gs_app_config import load_config
from .gs_data_revision import compute_data_revision
from .gs_tv_screen_api import normalize_screen_slug_for_api as _normalize_screen_slug_for_api
from .optional_imports import push_module
from .push_notify import notify_push_to_screen, push_enabled_on_server

_log = logging.getLogger(__name__)

'''
    # Still need helpers from app for checkin push - lazy import
    body = body.replace(
        "_screen_widgets_ordered_with_carousel_children(",
        "_widgets_ordered(",
    )
    body = body.replace(
        "_checkin_events_screen_slug_for_monitor(",
        "_events_screen_slug_for_monitor(",
    )
    helper = '''

def _widgets_ordered(screen: dict[str, Any]):
    from guardschool.gs_checkin_screen import screen_widgets_ordered_with_carousel_children
    return screen_widgets_ordered_with_carousel_children(screen)


def _events_screen_slug_for_monitor(config, mw, display_slug_key):
    from guardschool.gs_checkin_screen import checkin_events_screen_slug_for_monitor
    return checkin_events_screen_slug_for_monitor(config, mw, display_slug_key)


def _screen_api_tenant_slug(request: Request) -> str:
    from .gs_tv_screen_api import screen_api_tenant_slug
    return screen_api_tenant_slug(request)


'''
    (ROOT / "guardschool" / "gs_screen_push.py").write_text(hdr + helper + body, encoding="utf-8")
    print("gs_screen_push OK")


def data_loaders() -> None:
    body = sl(721, 744) + sl(968, 986)
    hdr = '''"""Load schedule/holidays/announcements/marquee/overrides from tenant data/."""
from __future__ import annotations

from typing import Any

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
from .gs_rss_news import load_rss_news as _load_rss_news_feed

'''
    body += sl(978, 982).replace("def load_marquee", "def load_marquee_items")
    body += '''

def load_rss_news(config: dict[str, Any] | None = None, *, force_refresh: bool = False) -> list[dict[str, Any]]:
    from .gs_app_config import load_config
    cfg = config if config is not None else load_config()
    return _load_rss_news_feed(cfg, force_refresh=force_refresh)

'''
    (ROOT / "guardschool" / "gs_data_loaders.py").write_text(hdr + body, encoding="utf-8")
    print("gs_data_loaders OK")


def schedule_bells() -> None:
    chunks = [(509, 527), (537, 576), (984, 1802)]
    body = ""
    for s, e in chunks:
        body += sl(s, e)
    hdr = '''"""Schedule rows, bell status/audio, build_schedule_payload for TV API."""
from __future__ import annotations

import copy
import logging
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from . import gs_bell_strings as _bell_i18n
from .gs_app_config import DEFAULT_BELL_TRIGGER_SEC_WINDOW, load_config
from .gs_class_key import normalize_class
from .gs_data_loaders import (
    load_announcements,
    load_full_schedule,
    load_holidays,
    load_overrides,
    load_schedule,
    load_schedule_sample,
)
from .gs_paths import BELL_SOUNDS_DIR
from .gs_jsonio import read_json
from .gs_paths import BELL_SCHEDULES_PATH

_log = logging.getLogger(__name__)
_TEMP_DISABLE_SCREEN_CLASS_FILTER = False
_ML_INDEX_CACHE: dict[tuple[Any, str], tuple[int | None, float]] = {}
_ML_INDEX_TTL_SEC = 12.0

'''
    (ROOT / "guardschool" / "gs_schedule_bells.py").write_text(hdr + body, encoding="utf-8")
    print("gs_schedule_bells OK")


if __name__ == "__main__":
    push()
    data_loaders()
    schedule_bells()
