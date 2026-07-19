"""Admin API: журнал отметок (check-in)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, Response

from .gs_app_config import load_config
from .gs_auth import require_auth
from .gs_checkin import (
    confirm_all_unconfirmed_in_range,
    enrich_checkin_event_for_client,
    fetch_checkin_event_by_id,
    get_checkin_events_status_for_device,
    journal_to_csv_bytes_filtered,
    range_bounds_utc,
    sanitize_places_list,
    set_checkin_event_confirmed,
)
from .gs_checkin_screen import (
    checkin_board_payload as _checkin_board_payload,
    checkin_events_screen_slug_for_monitor as _checkin_events_screen_slug_for_monitor,
    checkin_period_normalize as _checkin_period_normalize,
    find_monitor_widget as _find_monitor_widget,
    screen_config_by_slug as _screen_config_by_slug,
)
from .gs_screen_push import (
    notify_push_checkin_journal_bulk_confirm as _notify_push_checkin_journal_bulk_confirm,
    notify_push_checkin_journal_confirmed as _notify_push_checkin_journal_confirmed,
)
from .gs_tv_screen_api import (
    normalize_screen_slug_for_api as _normalize_screen_slug_for_api,
    screen_api_tenant_slug as _screen_api_tenant_slug,
)

router = APIRouter(tags=["admin"])


def _checkin_tenant_from_request(request: Request) -> str:
    return _screen_api_tenant_slug(request)


@router.get("/api/admin/checkin/board")
def api_admin_checkin_board(
    request: Request,
    screen_slug: str = Query(...),
    monitor_widget_id: str = Query(...),
    period: str = Query("day", alias="range"),
) -> dict[str, object]:
    require_auth(request)
    slug_key = _normalize_screen_slug_for_api(screen_slug)
    if not slug_key:
        raise HTTPException(status_code=400, detail="Укажите screen_slug.")
    cfg = load_config()
    return _checkin_board_payload(cfg, _screen_api_tenant_slug(request), slug_key, monitor_widget_id, period)


@router.get("/api/admin/checkin/export.csv")
def api_admin_checkin_export_csv(
    request: Request,
    screen_slug: str = Query(...),
    monitor_widget_id: str = Query(...),
    period: str = Query("day", alias="range"),
) -> Response:
    require_auth(request)
    slug_key = _normalize_screen_slug_for_api(screen_slug)
    if not slug_key:
        raise HTTPException(status_code=400, detail="Укажите screen_slug.")
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
    tenant_id = _screen_api_tenant_slug(request)
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


@router.post("/api/admin/checkin/confirm")
async def api_admin_checkin_confirm(request: Request) -> dict[str, object]:
    require_auth(request)
    body = await request.json()
    screen_slug_raw = str(body.get("screen_slug") or "").strip()
    slug_key = _normalize_screen_slug_for_api(screen_slug_raw)
    if not slug_key:
        raise HTTPException(status_code=400, detail="Укажите screen_slug.")
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


@router.post("/api/admin/checkin/confirm-all")
async def api_admin_checkin_confirm_all(request: Request) -> dict[str, object]:
    require_auth(request)
    body = await request.json()
    screen_slug_raw = str(body.get("screen_slug") or "").strip()
    slug_key = _normalize_screen_slug_for_api(screen_slug_raw)
    if not slug_key:
        raise HTTPException(status_code=400, detail="Укажите screen_slug.")
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


@router.get("/api/admin/checkin/events-status")
def api_admin_checkin_events_status(
    request: Request,
    screen_slug: str = Query(...),
    submit_widget_id: str = Query(...),
    device_hash: str = Query(...),
    ids: str = Query(""),
) -> dict[str, object]:
    require_auth(request)
    slug_key = _normalize_screen_slug_for_api(screen_slug)
    if not slug_key:
        raise HTTPException(status_code=400, detail="Укажите screen_slug.")
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
