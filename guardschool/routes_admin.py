"""Admin HTTP API (/api/admin/*). Open-core, монтируется из app.py."""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from .app_try_demo import demo_exit_redirect_url as _demo_exit_redirect_url
from .capabilities import CAP_CLOUD_SYNC, get_capabilities_public, resolve_capabilities_audience
from .license_capability_provider import resolve_effective_plan_id
from .gs_admin_upload import saas_check_quota_for_path as _saas_check_quota_for_path
from .gs_app_config import (
    _sanitize_emergency_templates_list,
    apply_emergency_template_to_screen,
    load_config,
    sanitize_audio_stream,
    sanitize_config,
)
from .gs_auth import is_demo_session_for_admin_ui, require_auth
from .gs_capability_http import require_capability
from .gs_change_log import load_change_log
from .gs_class_key import normalize_class
from .gs_data_loaders import (
    load_announcements,
    load_full_schedule,
    load_holidays,
    load_marquee_items,
    load_overrides,
    load_rss_news,
    load_schedule,
    load_schedule_sample,
)
from .gs_data_revision import compute_data_revision
from .gs_deploy import deployment_mode
from .gs_import_state import load_import_state
from .gs_jsonio import write_json
from .gs_paths import (
    APP_VERSION,
    AUTO_ANNOUNCEMENTS_IMPORT_PATH,
    AUTO_FULL_SCHEDULE_IMPORT_PATH,
    AUTO_HOLIDAYS_IMPORT_PATH,
    AUTO_MARQUEE_IMPORT_PATH,
    AUTO_SCHEDULE_IMPORT_PATH,
    AUTO_SCHEDULE_SAMPLE_IMPORT_PATH,
    BELL_SCHEDULES_PATH,
    CONFIG_PATH,
    OVERRIDES_PATH,
)
from .gs_schedule_bells import (
    _norm_hex_color,
    as_lesson_number,
    audio_trigger_sec_window,
    build_bell_audio_payload,
    build_schedule_payload,
    calendar_today_for_config,
    distinct_schedule_class_names_from_sources,
    display_settings_dict,
    load_bell_schedules,
    schedule_date_iso,
)
from .gs_screen_push import (
    maybe_push_screen_content_if_data_revision_changed as _maybe_push_screen_content_if_data_revision_changed,
    notify_push_emergency_change as _notify_push_emergency_change,
)
from .gs_school_news import load_school_news
from .gs_screen_watch import reset_stats_counters, screen_watch_snapshot
from .gs_tv_screen_api import screen_api_tenant_slug as _screen_api_tenant_slug
from .gs_uploads_bg import (
    list_background_images_from_uploads,
    list_background_subdirs_from_uploads,
    safe_rel_uploads_subdir,
)
from .gs_saas_limits import saas_mode
from .optional_imports import cloud_sync_module
from .widget_registry import loaded_widget_types, widget_registry_public
from .widget_screen_meta import enrich_screen_widgets_meta

_log = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])


def register_admin_routes(app) -> None:
    from .routes_admin_audio import router as admin_audio_router
    from .routes_admin_checkin import router as admin_checkin_router
    from .routes_admin_import_export import router as admin_import_export_router
    from .routes_admin_school_news import router as admin_school_news_router
    from .routes_admin_uploads import router as admin_uploads_router

    app.include_router(router)
    app.include_router(admin_audio_router)
    app.include_router(admin_checkin_router)
    app.include_router(admin_uploads_router)
    app.include_router(admin_school_news_router)
    app.include_router(admin_import_export_router)


@router.get("/api/admin/config")
async def get_admin_config(request: Request) -> Response:
    require_auth(request)
    cfg = load_config()
    # Метаданные, которые нужны UI, но не должны сохраняться в config.json.
    cap_audience = resolve_capabilities_audience(request)
    cfg["_meta"] = {
        "saas_mode": saas_mode(),
        "deployment_mode": deployment_mode(),
        "app_version": APP_VERSION,
        "demo_session": is_demo_session_for_admin_ui(request),
        "demo_exit_url": _demo_exit_redirect_url(),
        "capabilities": get_capabilities_public(audience=cap_audience),
        "capabilities_audience": cap_audience,
        "effective_plan_id": resolve_effective_plan_id(),
        "widget_registry": widget_registry_public(),
    }
    return JSONResponse(cfg, headers={"Cache-Control": "no-store"})


@router.post("/api/admin/rss-news/refresh")
def post_admin_rss_news_refresh(request: Request) -> dict[str, Any]:
    require_auth(request)
    cfg = load_config()
    items = load_rss_news(cfg, force_refresh=True)
    return {"items": items, "count": len(items)}


@router.post("/api/admin/config")
async def save_admin_config(request: Request) -> dict[str, str]:
    require_auth(request)
    payload = await request.json()
    # Важно: аварийный режим включается/выключается через emergency_active_template_id.
    # Чтобы пушить только на смене режима, сравниваем старое и новое значения.
    prev_cfg = {}
    try:
        prev_cfg = load_config()
    except Exception:
        prev_cfg = {}
    prev_tid = str((prev_cfg or {}).get("emergency_active_template_id") or "").strip()
    new_cfg = sanitize_config(payload)
    new_tid = str((new_cfg or {}).get("emergency_active_template_id") or "").strip()
    write_json(CONFIG_PATH, new_cfg)
    try:
        if prev_tid != new_tid:
            _notify_push_emergency_change(
                tenant_id=_screen_api_tenant_slug(request), cfg=new_cfg, prev_tid=prev_tid, new_tid=new_tid
            )
    except Exception:
        pass
    _maybe_push_screen_content_if_data_revision_changed(request)
    return {"status": "ok"}


@router.post("/api/admin/sync-now")
async def post_admin_sync_now(request: Request) -> dict[str, Any]:
    require_auth(request)
    if deployment_mode() == "saas":
        raise HTTPException(status_code=404, detail="Not found.")
    require_capability(CAP_CLOUD_SYNC)
    sync_mod = cloud_sync_module()
    if sync_mod is None:
        raise HTTPException(status_code=503, detail="Cloud sync module is not available.")
    return await sync_mod.run_cloud_sync_once()


@router.get("/api/admin/background-gallery")
def admin_background_gallery(request: Request, folder: str = "") -> dict[str, Any]:
    require_auth(request)
    f = safe_rel_uploads_subdir(folder)
    return {
        "folder": f,
        "folders": list_background_subdirs_from_uploads(),
        "images": list_background_images_from_uploads(f),
    }


@router.post("/api/admin/screen-bg-next")
async def admin_screen_bg_next(request: Request) -> dict[str, Any]:
    require_auth(request)
    body = await request.json()
    sid = str(body.get("screen_id") or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="Нужен screen_id.")
    config = load_config()
    screen = next((s for s in config.get("screens") or [] if str(s.get("id")) == sid), None)
    if not screen:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    # сбрасываем «фиксированный» фон, если был
    screen["background_force_image"] = ""
    screen["background_rotate_enabled"] = True
    try:
        cur = int(screen.get("background_rotate_cursor", 0))
    except (TypeError, ValueError):
        cur = 0
    screen["background_rotate_cursor"] = max(0, cur) + 1
    screen["background_rotate_epoch"] = int(time.time())
    write_json(CONFIG_PATH, sanitize_config(config))
    _maybe_push_screen_content_if_data_revision_changed(request)
    return {"status": "ok", "screen_id": sid}




@router.get("/api/admin/schedule")
async def get_schedule_snapshot(request: Request) -> dict[str, Any]:
    require_auth(request)
    cfg = load_config()
    schedule_rows = load_schedule()
    full_rows = load_full_schedule()
    sample_rows = load_schedule_sample()
    return {
        "schedule": schedule_rows,
        "holidays": load_holidays(),
        "announcements": load_announcements(),
        "school_news": load_school_news()[:20],
        "rss_news": load_rss_news(cfg),
        "marquee": load_marquee_items(),
        "overrides": load_overrides(),
        "bells": load_bell_schedules(),
        "history": load_change_log(),
        "full_schedule_rows": len(full_rows),
        "schedule_sample_rows": len(sample_rows),
        "schedule_class_options": distinct_schedule_class_names_from_sources(
            schedule_rows, full_rows, sample_rows
        ),
        "imports": {
            "schedule_path": str(AUTO_SCHEDULE_IMPORT_PATH),
            "full_schedule_path": str(AUTO_FULL_SCHEDULE_IMPORT_PATH),
            "schedule_sample_path": str(AUTO_SCHEDULE_SAMPLE_IMPORT_PATH),
            "holidays_path": str(AUTO_HOLIDAYS_IMPORT_PATH),
            "announcements_path": str(AUTO_ANNOUNCEMENTS_IMPORT_PATH),
            "marquee_path": str(AUTO_MARQUEE_IMPORT_PATH),
            "state": load_import_state(),
        },
        "app_version": APP_VERSION,
    }


@router.get("/api/admin/history")
def get_change_history(request: Request) -> dict[str, Any]:
    require_auth(request)
    return {"history": load_change_log(), "app_version": APP_VERSION}


@router.post("/api/admin/overrides")
async def save_overrides(request: Request) -> dict[str, str]:
    require_auth(request)
    raw = await request.json()
    payload: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            date_s = str(item.get("date") or "").strip()
            class_name = str(item.get("class_name") or "").strip()
            class_key = normalize_class(item.get("class_key") or class_name)
            lesson_index = as_lesson_number(item.get("lesson_index"))
            subject = str(item.get("subject") or "").strip()
            date_norm = schedule_date_iso(date_s) or date_s
            if not (date_norm and class_name and class_key and lesson_index and subject):
                continue
            out = {
                "date": date_norm,
                "class_name": class_name,
                "class_key": class_key,
                "lesson_index": lesson_index,
                "subject": subject,
            }
            c = _norm_hex_color(item.get("color"))
            if c:
                out["color"] = c
            payload.append(out)
    _saas_check_quota_for_path(request, OVERRIDES_PATH, payload)
    write_json(OVERRIDES_PATH, payload)
    _maybe_push_screen_content_if_data_revision_changed(request)
    return {"status": "ok"}


@router.post("/api/admin/bells")
async def save_bells(request: Request) -> dict[str, str]:
    require_auth(request)
    payload = await request.json()
    _saas_check_quota_for_path(request, BELL_SCHEDULES_PATH, payload)
    write_json(BELL_SCHEDULES_PATH, payload)
    _maybe_push_screen_content_if_data_revision_changed(request)
    return {"status": "ok"}


@router.post("/api/admin/preview-payload")
def post_preview_payload(request: Request, payload: dict[str, Any] = Body(...)) -> JSONResponse:
    require_auth(request)
    screen = payload.get("screen")
    if not isinstance(screen, dict):
        raise HTTPException(status_code=400, detail="Нужен объект screen.")
    screen.setdefault("selected_classes", [])
    screen.setdefault("bell_schedule_template", "standard")
    screen.setdefault("weekday_bell_templates", {})
    screen.setdefault("widgets", [])
    cfg = load_config()
    if isinstance(payload.get("emergency_templates"), list):
        cfg = dict(cfg)
        cfg["emergency_templates"] = _sanitize_emergency_templates_list(payload.get("emergency_templates"))
    if payload.get("emergency_active_template_id") is not None:
        cfg = dict(cfg)
        cfg["emergency_active_template_id"] = str(payload.get("emergency_active_template_id") or "").strip()[:64]
    screen_eff = enrich_screen_widgets_meta(apply_emergency_template_to_screen(dict(screen), cfg))
    today = calendar_today_for_config(cfg)
    audio = sanitize_audio_stream(cfg.get("audio_stream"))
    from . import local_audio_worker

    body = {
        "schedule": build_schedule_payload(screen, today, cfg),
        "holidays": load_holidays(),
        "announcements": load_announcements(),
        "school_news": load_school_news()[:20],
        "marquee": load_marquee_items(),
        "rss_news": load_rss_news(cfg),
        "background_gallery": list_background_images_from_uploads(screen.get("background_rotate_folder")),
        "bell_audio": build_bell_audio_payload(
            screen,
            today,
            trigger_sec_window=audio_trigger_sec_window(audio),
        ),
        "pc_audio_preview": local_audio_worker.describe_pc_audio_preview(
            screen,
            cfg.get("audio_stream"),
        ),
        "display": display_settings_dict(cfg),
        "revision": compute_data_revision(),
        "app_version": APP_VERSION,
        "screen": screen_eff,
        "widget_types_available": loaded_widget_types(),
    }
    return JSONResponse(content=body)

@router.get("/api/admin/screen-watch")
def get_admin_screen_watch(request: Request) -> dict[str, Any]:
    require_auth(request)
    config = load_config()
    return screen_watch_snapshot(list(config.get("screens") or []))


@router.post("/api/admin/screen-watch/reset-counters")
def admin_reset_screen_watch_counters(request: Request) -> dict[str, Any]:
    require_auth(request)
    return {"status": "ok", "visits": reset_stats_counters()}

