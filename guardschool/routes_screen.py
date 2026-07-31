"""Screen/TV JSON API and check-in routes. Open-core."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from .gs_app_config import (
    apply_emergency_template_to_screen,
    load_config,
    sanitize_audio_stream,
)
from .gs_auth import require_auth
from .gs_checkin import (
    confirm_all_unconfirmed_in_range,
    enrich_checkin_event_for_client,
    fetch_checkin_event_by_id,
    get_checkin_events_status_for_device,
    insert_event as insert_checkin_event,
    journal_to_csv_bytes_filtered,
    range_bounds_utc,
    sanitize_places_list,
    set_checkin_event_confirmed,
)
from .gs_checkin_screen import (
    checkin_board_payload as _checkin_board_payload,
    checkin_events_screen_slug_for_monitor as _checkin_events_screen_slug_for_monitor,
    checkin_period_normalize as _checkin_period_normalize,
    device_widget_types_for_tv_device_panel,
    find_monitor_widget as _find_monitor_widget,
    find_submit_widget as _find_submit_widget,
    resolve_checkin_submit_places as _resolve_checkin_submit_places,
    screen_config_by_slug as _screen_config_by_slug,
)
from .gs_data_loaders import load_announcements, load_holidays, load_marquee_items, load_rss_news
from .gs_data_revision import compute_data_revision
from .gs_deploy import deployment_mode
from .gs_paths import APP_VERSION
from .gs_schedule_bells import (
    _TEMP_DISABLE_SCREEN_CLASS_FILTER,
    audio_trigger_sec_window,
    build_bell_audio_payload,
    build_schedule_payload,
    calendar_today_for_config,
    display_settings_dict,
    pickable_classes_for_tv_device_panel,
)
from .gs_school_news import load_school_news
from .gs_screen_push import (
    notify_push_checkin_journal_bulk_confirm as _notify_push_checkin_journal_bulk_confirm,
    notify_push_checkin_journal_confirmed as _notify_push_checkin_journal_confirmed,
    notify_push_checkin_journal_new_row as _notify_push_checkin_journal_new_row,
)
from .gs_screen_watch import record_screen_poll
from .gs_tv_screen_api import (
    normalize_screen_slug_for_api as _normalize_screen_slug_for_api,
    require_tv_access_for_screen as _require_tv_access_for_screen,
    screen_api_tenant_slug as _screen_api_tenant_slug,
)
from .gs_uploads_bg import list_background_images_from_uploads
from .saas_db import saas_db_enabled
from .widget_registry import loaded_widget_types
from .widget_screen_meta import enrich_screen_widgets_meta

_log = logging.getLogger(__name__)
router = APIRouter(tags=["screen"])


def register_screen_routes(app) -> None:
    app.include_router(router)


@router.get("/api/screens-index")
def get_screens_index(request: Request) -> dict[str, Any]:
    """Список экранов для /screens. В SaaS с БД — только для авторизованной сессии."""
    if deployment_mode() == "saas" and saas_db_enabled():
        require_auth(request)
    config = load_config()
    items = []
    for item in config.get("screens") or []:
        if item.get("is_active") is False:
            continue
        sl = str(item.get("slug") or "").strip()
        if not sl:
            continue
        items.append(
            {
                "name": item.get("name") or sl,
                "slug": sl,
                "path": f"/screen/{sl}",
            }
        )
    return {"screens": items}


@router.get("/api/screen/{slug}")
def get_screen(request: Request, slug: str) -> JSONResponse:
    slug_key = _normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    _require_tv_access_for_screen(request, slug_key)
    config = load_config()
    screen0 = next(
        (
            item
            for item in (config.get("screens") or [])
            if _normalize_screen_slug_for_api(str(item.get("slug") or "")) == slug_key and item.get("is_active", True)
        ),
        None,
    )
    screen = screen0
    if not screen:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    pickable = pickable_classes_for_tv_device_panel(screen0)
    qp = request.query_params
    # Фильтр gs_classes только в мобильном режиме экрана; иначе игнорируем (ТВ/сетка = только конфиг).
    raw_classes = str(qp.get("gs_classes") or "").strip()
    if (
        not _TEMP_DISABLE_SCREEN_CLASS_FILTER
        and raw_classes
        and bool(screen0.get("mobile_mode"))
    ):
        parts = [p.strip() for p in raw_classes.split(",") if p.strip()]
        parts = parts[:12]
        if parts:
            # shallow copy: не мутируем config.json в памяти
            screen = dict(screen0)
            screen["selected_classes"] = parts
    record_screen_poll(
        request,
        str(screen0.get("slug") or slug_key),
        str(qp.get("gs_client") or "").strip(),
        str(qp.get("gs_label") or "").strip(),
        str(qp.get("gs_device") or "").strip(),
        str(screen.get("name") or slug_key).strip(),
    )
    today = calendar_today_for_config(config)
    audio = sanitize_audio_stream(config.get("audio_stream"))
    sched_body = build_schedule_payload(screen, today, config)
    tr = len((sched_body.get("today_rows") or [])) if isinstance(sched_body, dict) else 0
    screen_out = enrich_screen_widgets_meta(apply_emergency_template_to_screen(screen, config))
    payload = {
        "screen": screen_out,
        "widget_types_available": loaded_widget_types(),
        "device_widget_types": device_widget_types_for_tv_device_panel(config, screen_out.get("widgets") or []),
        "pickable_classes": pickable,
        "serverTime": datetime.now().isoformat(),
        "schedule": sched_body,
        "holidays": load_holidays(),
        "announcements": load_announcements(),
        "school_news": load_school_news(),
        "marquee": load_marquee_items(),
        "rss_news": load_rss_news(config),
        "background_gallery": list_background_images_from_uploads(screen.get("background_rotate_folder")),
        "bell_audio": build_bell_audio_payload(
            screen,
            today,
            trigger_sec_window=audio_trigger_sec_window(audio),
        ),
        "display": display_settings_dict(config),
        "revision": compute_data_revision(),
        "app_version": APP_VERSION,
    }
    return JSONResponse(
        content=payload,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Guardschool-App-Version": APP_VERSION,
            "X-GS-Schedule-Today-Rows": str(tr),
            "X-GS-Schedule-Cal-Day": today.isoformat(),
        },
    )


@router.post("/api/checkin/event")
async def api_checkin_post_event(request: Request) -> dict[str, Any]:
    """Отметка с экрана: нужны slug экрана и id виджета «Отметка» (checkin_submit). Данные привязаны к токену клиента."""
    body = await request.json()
    screen_slug_raw = str(body.get("screen_slug") or "").strip()
    submit_widget_id = str(body.get("submit_widget_id") or "").strip()
    slug_key = _normalize_screen_slug_for_api(screen_slug_raw)
    if not slug_key or not submit_widget_id:
        raise HTTPException(status_code=400, detail="Укажите screen_slug и submit_widget_id.")
    cfg = load_config()
    screen = _screen_config_by_slug(cfg, slug_key)
    if not screen:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    submit_w = _find_submit_widget(screen, submit_widget_id)
    if not submit_w or submit_w.get("enabled") is False:
        raise HTTPException(status_code=404, detail="Виджет отметки не найден или выключен.")
    places = _resolve_checkin_submit_places(screen, submit_w)
    allowed_ids = {p["id"] for p in places}
    if not allowed_ids:
        raise HTTPException(status_code=400, detail="Не заданы места: укажите места у виджета или привяжите виджет сводки.")
    place_id = str(body.get("place_id") or "").strip()
    level = str(body.get("level") or "").strip().lower()
    comment = str(body.get("comment") or "").strip()
    device_name = str(body.get("device_name") or "").strip()
    device_hash = str(body.get("device_hash") or "").strip()
    if place_id not in allowed_ids:
        raise HTTPException(status_code=400, detail="Неизвестное место для этого экрана.")
    auth = (request.headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        _require_tv_access_for_screen(request, slug_key)
    tenant_id = _screen_api_tenant_slug(request)
    try:
        saved = insert_checkin_event(
            tenant_id,
            device_hash,
            device_name,
            place_id,
            level,
            comment,
            screen_slug=slug_key,
            submit_widget_id=submit_widget_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    _en = enrich_checkin_event_for_client(cfg, {"created_at": saved.get("created_at"), "confirmed_at": ""})
    try:
        _notify_push_checkin_journal_new_row(
            cfg=cfg,
            tenant_id=tenant_id,
            screen=screen,
            submit_w=submit_w,
            events_screen_slug=slug_key,
            saved=saved,
            place_id=place_id,
            level=level,
            device_name=device_name,
            comment=comment,
        )
    except Exception:
        _log.exception("push checkin new_row failed slug=%s event_id=%s", slug_key, saved.get("id"))
    return {
        "status": "ok",
        **saved,
        "created_date": _en.get("created_date") or "",
        "created_time": _en.get("created_time") or "",
    }


@router.get("/api/screen/{slug}/checkin/board")
def api_screen_checkin_board(
    request: Request,
    slug: str,
    monitor_widget_id: str = Query(...),
    period: str = Query("day", alias="range"),
) -> dict[str, Any]:
    """Сводка и журнал для виджета «Сводка отметок» на ТВ (по токену доступа к экрану)."""
    slug_key = _normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    _require_tv_access_for_screen(request, slug_key)
    cfg = load_config()
    tenant_id = _checkin_tenant_from_request(request)
    return _checkin_board_payload(cfg, tenant_id, slug_key, monitor_widget_id, period)


@router.get("/api/screen/{slug}/checkin/export.csv")
def api_screen_checkin_export_csv(
    request: Request,
    slug: str,
    monitor_widget_id: str = Query(...),
    period: str = Query("day", alias="range"),
) -> Response:
    slug_key = _normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    _require_tv_access_for_screen(request, slug_key)
    cfg = load_config()
    screen = _screen_config_by_slug(cfg, slug_key)
    if not screen:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    mw = _find_monitor_widget(screen, monitor_widget_id)
    if not mw:
        raise HTTPException(status_code=404, detail="Виджет сводки не найден.")
    places = sanitize_places_list((mw.get("settings") or {}).get("places"))
    place_titles = {p["id"]: p["title"] for p in places}
    pids = {p["id"] for p in places}
    tenant_id = _checkin_tenant_from_request(request)
    period_n = _checkin_period_normalize(period)
    event_slug = _checkin_events_screen_slug_for_monitor(cfg, mw, slug_key)
    raw = journal_to_csv_bytes_filtered(
        tenant_id, cfg, period_n, pids if pids else None, event_slug, place_titles
    )
    rl = range_bounds_utc(cfg, period_n)[2]
    return Response(
        content=raw,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="checkin_{slug_key}_{monitor_widget_id}_{rl}.csv"'
        },
    )


def _checkin_tenant_from_request(request: Request) -> str:
    return _screen_api_tenant_slug(request)


@router.post("/api/screen/{slug}/checkin/confirm")
async def api_screen_checkin_confirm(request: Request, slug: str) -> dict[str, Any]:
    slug_key = _normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    _require_tv_access_for_screen(request, slug_key)
    body = await request.json()
    monitor_widget_id = str(body.get("monitor_widget_id") or "").strip()
    try:
        event_id = int(body.get("event_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Укажите event_id.") from None
    if not monitor_widget_id:
        raise HTTPException(status_code=400, detail="Укажите monitor_widget_id.")
    cfg = load_config()
    screen = _screen_config_by_slug(cfg, slug_key)
    if not screen:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    mw = _find_monitor_widget(screen, monitor_widget_id)
    if not mw:
        raise HTTPException(status_code=404, detail="Виджет сводки не найден.")
    places = sanitize_places_list((mw.get("settings") or {}).get("places"))
    allowed = {p["id"] for p in places}
    tenant_id = _checkin_tenant_from_request(request)
    event_slug = _checkin_events_screen_slug_for_monitor(cfg, mw, slug_key)
    ts, newly = set_checkin_event_confirmed(
        tenant_id, event_id, screen_slug=event_slug, allowed_place_ids=allowed
    )
    if ts is None:
        raise HTTPException(status_code=404, detail="Событие не найдено или недоступно.")
    if newly:
        try:
            erow = fetch_checkin_event_by_id(tenant_id, event_id)
            if erow:
                _notify_push_checkin_journal_confirmed(
                    cfg=cfg,
                    tenant_id=tenant_id,
                    mw=mw,
                    events_screen_slug=event_slug,
                    row=erow,
                )
        except Exception:
            pass
    return {"status": "ok", "confirmed_at": ts}


@router.post("/api/screen/{slug}/checkin/confirm-all")
async def api_screen_checkin_confirm_all(request: Request, slug: str) -> dict[str, Any]:
    slug_key = _normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    _require_tv_access_for_screen(request, slug_key)
    body = await request.json()
    monitor_widget_id = str(body.get("monitor_widget_id") or "").strip()
    period = str(body.get("range") or body.get("period") or "day").strip()
    if not monitor_widget_id:
        raise HTTPException(status_code=400, detail="Укажите monitor_widget_id.")
    cfg = load_config()
    screen = _screen_config_by_slug(cfg, slug_key)
    if not screen:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    mw = _find_monitor_widget(screen, monitor_widget_id)
    if not mw:
        raise HTTPException(status_code=404, detail="Виджет сводки не найден.")
    places = sanitize_places_list((mw.get("settings") or {}).get("places"))
    pids = {p["id"] for p in places}
    period_n = _checkin_period_normalize(period)
    tenant_id = _checkin_tenant_from_request(request)
    event_slug = _checkin_events_screen_slug_for_monitor(cfg, mw, slug_key)
    n = confirm_all_unconfirmed_in_range(tenant_id, cfg, event_slug, pids, period_n)
    if n > 0:
        try:
            _notify_push_checkin_journal_bulk_confirm(
                cfg=cfg, tenant_id=tenant_id, events_screen_slug=event_slug, count=n
            )
        except Exception:
            pass
    return {"status": "ok", "confirmed_count": n}


@router.get("/api/screen/{slug}/checkin/events-status")
def api_screen_checkin_events_status(
    request: Request,
    slug: str,
    submit_widget_id: str = Query(...),
    device_hash: str = Query(...),
    ids: str = Query("", description="Список id через запятую"),
) -> dict[str, Any]:
    slug_key = _normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    _require_tv_access_for_screen(request, slug_key)
    sw = str(submit_widget_id or "").strip()
    if not sw:
        raise HTTPException(status_code=400, detail="Укажите submit_widget_id.")
    id_parts = [x.strip() for x in (ids or "").split(",") if x.strip()]
    id_list: list[int] = []
    for x in id_parts:
        try:
            id_list.append(int(x))
        except ValueError:
            continue
    tenant_id = _checkin_tenant_from_request(request)
    rows = get_checkin_events_status_for_device(tenant_id, slug_key, sw, device_hash, id_list)
    cfg = load_config()
    enriched = []
    for r in rows:
        e = dict(r)
        ca = e.get("confirmed_at") or ""
        ed = enrich_checkin_event_for_client(
            cfg,
            {"created_at": "", "confirmed_at": ca},
        )
        e["confirmed_date"] = ed.get("confirmed_date") or ""
        e["confirmed_time"] = ed.get("confirmed_time") or ""
        enriched.append(e)
    return {"status": "ok", "items": enriched}
