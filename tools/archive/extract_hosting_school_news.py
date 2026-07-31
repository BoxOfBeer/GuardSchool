"""Extract gs_school_news, gs_checkin_screen, gs_admin_upload, app_hosting from app.py."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
lines = (ROOT / "guardschool" / "app.py").read_text(encoding="utf-8").splitlines(keepends=True)


def sl(s: int, e: int) -> str:
    return "".join(lines[s - 1 : e])


def school_news() -> None:
    body = sl(674, 893)
    repl = [
        ("_sanitize_school_news_display_html", "sanitize_school_news_display_html"),
        ("_school_news_text_preview", "school_news_text_preview"),
        ("_school_news_uploads_dir", "school_news_uploads_dir"),
        ("_safe_unlink_upload_url", "safe_unlink_school_news_upload_url"),
        ("_sanitize_one_news_image_url", "sanitize_one_news_image_url"),
        ("_sanitize_gallery_images", "sanitize_gallery_images"),
        ("_extract_school_news_local_upload_urls", "extract_school_news_local_upload_urls"),
        ("_save_school_news_image_bytes", "save_school_news_image_bytes"),
    ]
    for old, new in repl:
        body = body.replace(old, new)
    hdr = '''"""School news: load/sanitize, image uploads under /uploads/school_news/."""
from __future__ import annotations

import re
import secrets
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .gs_ensure_dirs import ensure_dirs
from .gs_jsonio import read_json
from .gs_paths import SCHOOL_NEWS_PATH, UPLOADS_DIR
from .gs_saas_limits import max_school_news_image_bytes
from .gs_schedule_bells import schedule_date_iso

SCHOOL_NEWS_GALLERY_MAX = 4

'''
    (ROOT / "guardschool" / "gs_school_news.py").write_text(hdr + body, encoding="utf-8")
    print("gs_school_news OK")


def checkin_screen() -> None:
    body = sl(302, 336) + sl(535, 670)
    repl = [
        ("_screen_config_by_slug", "screen_config_by_slug"),
        ("_screen_widgets_ordered_with_carousel_children", "screen_widgets_ordered_with_carousel_children"),
        ("_find_submit_widget", "find_submit_widget"),
        ("_find_monitor_widget", "find_monitor_widget"),
        ("_checkin_events_screen_slug_for_monitor", "checkin_events_screen_slug_for_monitor"),
        ("_resolve_checkin_submit_places", "resolve_checkin_submit_places"),
        ("_checkin_period_normalize", "checkin_period_normalize"),
        ("_checkin_board_payload", "checkin_board_payload"),
    ]
    for old, new in repl:
        body = body.replace(old, new)
    hdr = '''"""Screen lookup, widget traversal, check-in board payload."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from .gs_checkin import (
    build_summary_for_places,
    enrich_checkin_event_for_client,
    list_journal_filtered,
    range_bounds_utc,
    sanitize_places_list,
)
from .gs_tv_screen_api import normalize_screen_slug_for_api as _normalize_screen_slug_for_api
from .widget_registry import (
    ADMIN_PALETTE_WIDGET_TYPES,
    DEVICE_WIDGET_TAB_ORDER,
)

_TV_DEVICE_PANEL_EXCLUDED_TYPES = frozenset({"emergency"})

'''
    (ROOT / "guardschool" / "gs_checkin_screen.py").write_text(hdr + body, encoding="utf-8")
    print("gs_checkin_screen OK")


def admin_upload() -> None:
    body = sl(406, 495)
    repl = [
        ("_reject_if_saas_upload", "reject_if_saas_upload"),
        ("_read_upload_capped", "read_upload_capped"),
        ("_saas_check_json_payload_size", "saas_check_json_payload_size"),
        ("_saas_check_quota_for_path", "saas_check_quota_for_path"),
        ("_saas_enforce_user_data_quota_after_multi_write", "saas_enforce_user_data_quota_after_multi_write"),
    ]
    for old, new in repl:
        body = body.replace(old, new)
    hdr = '''"""SaaS upload limits and quota checks for admin imports."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile, Request

from .gs_admin_http import admin_msg, admin_ui_lang
from .gs_paths import BELL_SCHEDULES_PATH, FULL_SCHEDULE_PATH, OVERRIDES_PATH, SCHEDULE_PATH, SCHEDULE_SAMPLE_PATH
from .gs_saas_limits import json_utf8_size, max_schedule_json_bytes, max_user_data_bytes, saas_mode

'''
    (ROOT / "guardschool" / "gs_admin_upload.py").write_text(hdr + body, encoding="utf-8")
    print("gs_admin_upload OK")


def hosting() -> None:
    mid = sl(918, 977)
    demo = sl(990, 1008)
    body = demo + "\n" + mid
    body = body.replace("def _demo_middleware_binding_slug", "def demo_middleware_binding_slug")
    body = body.replace("async def _tenant_middleware", "async def tenant_middleware")
    body = body.replace("_demo_middleware_binding_slug(", "demo_middleware_binding_slug(")
    hdr = '''"""FastAPI SaaS tenant middleware (cookie/host → tenant_ctx)."""
from __future__ import annotations

from fastapi import FastAPI, Request

from .app_host_routing import (
    is_public_school_host,
    request_host_for_routing,
)
from .gs_auth import verify_demo_session_token
from .app_try_demo import demo_v3_binding_from_token
from .gs_deploy import deployment_mode
from .gs_paths import SAAS_TENANT_COOKIE, SESSION_COOKIE
from .gs_tv_screen_api import decode_saas_tenant_cookie_value


def register_hosting_middleware(app: FastAPI) -> None:
    app.middleware("http")(tenant_middleware)


'''
    (ROOT / "guardschool" / "app_hosting.py").write_text(hdr + body, encoding="utf-8")
    print("app_hosting OK")


if __name__ == "__main__":
    school_news()
    checkin_screen()
    admin_upload()
    hosting()
