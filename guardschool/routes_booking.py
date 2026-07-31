"""Public and authenticated HTTP API for generic appointment widgets."""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Query, Request

from .gs_app_config import load_config
from .gs_booking import admin_action, admin_state, availability, create_booking, device_hash, request_cancel, save_config
from .gs_booking_push import notify_change, subscribe
from .gs_tv_screen_api import normalize_screen_slug_for_api, require_tv_access_for_screen, screen_api_tenant_slug

router = APIRouter(tags=["booking"])


def _screen_widget(request: Request, slug: str, module_id: str, allowed_types: tuple[str, ...]) -> None:
    key = normalize_screen_slug_for_api(slug)
    require_tv_access_for_screen(request, key)
    screen = next((s for s in load_config().get("screens", []) if normalize_screen_slug_for_api(s.get("slug", "")) == key and s.get("is_active", True)), None)
    if not screen:
        raise HTTPException(404, "Экран не найден.")
    found = any(w.get("type") in allowed_types and w.get("enabled", True) and str((w.get("settings") or {}).get("module_id") or "booking-main") == module_id for w in screen.get("widgets", []))
    if not found:
        raise HTTPException(404, "Модуль записи не найден.")


def _bad(exc: ValueError) -> None:
    raise HTTPException(400, str(exc)) from None


@router.get("/api/screen/{slug}/booking/{module_id}")
def public_state(request: Request, slug: str, module_id: str, service_id: str = Query("basic"), week: str = Query(""), device_id: str = Query("")) -> dict[str, Any]:
    _screen_widget(request, slug, module_id, ("booking_public",))
    try: return availability(module_id, week or None, service_id, device_id)
    except ValueError as exc: _bad(exc)


@router.post("/api/screen/{slug}/booking/{module_id}")
async def public_create(request: Request, slug: str, module_id: str) -> dict[str, Any]:
    _screen_widget(request, slug, module_id, ("booking_public",))
    try:
        data = await request.json()
        data["screen_slug"] = slug
        row = create_booking(module_id, data)
        notify_change(tenant_id=screen_api_tenant_slug(request), module_id=module_id, row=dict(row), event="created")
        return {"booking": {"id": row["id"], "start_at": row["start_at"], "end_at": row["end_at"], "status": row["status"]}}
    except ValueError as exc: _bad(exc)


@router.post("/api/screen/{slug}/booking/{module_id}/{booking_id}/cancel-request")
async def public_cancel(request: Request, slug: str, module_id: str, booking_id: int) -> dict[str, Any]:
    _screen_widget(request, slug, module_id, ("booking_public",))
    body = await request.json()
    try:
        row = request_cancel(module_id, booking_id, str(body.get("device_id") or ""))
        notify_change(tenant_id=screen_api_tenant_slug(request), module_id=module_id, row=row, event="cancel_requested")
        return {"status": row["status"]}
    except ValueError as exc: _bad(exc)


@router.post("/api/screen/{slug}/booking/{module_id}/push/subscribe")
async def booking_push_subscribe(request: Request, slug: str, module_id: str) -> dict[str, Any]:
    body = await request.json()
    audience = str(body.get("audience") or "device")
    if audience == "admin":
        _screen_widget(request, slug, module_id, ("booking_manager",))
        dh = ""
    else:
        audience = "device"
        _screen_widget(request, slug, module_id, ("booking_public",))
        try: dh = device_hash(str(body.get("device_id") or ""))
        except ValueError as exc: _bad(exc)
    try:
        subscribe(tenant_id=screen_api_tenant_slug(request), module_id=module_id, audience=audience, device_hash=dh, subscription=body.get("subscription") or {})
        return {"status": "ok"}
    except ValueError as exc: _bad(exc)


@router.get("/api/screen/{slug}/booking-admin/{module_id}")
def get_admin_booking(request: Request, slug: str, module_id: str, week: str = Query("")) -> dict[str, Any]:
    _screen_widget(request, slug, module_id, ("booking_manager",))
    try: return admin_state(module_id, week or None)
    except ValueError as exc: _bad(exc)


@router.put("/api/screen/{slug}/booking-admin/{module_id}/config")
async def put_admin_booking_config(request: Request, slug: str, module_id: str) -> dict[str, Any]:
    _screen_widget(request, slug, module_id, ("booking_manager",))
    try: return {"config": save_config(module_id, await request.json())}
    except (ValueError, TypeError) as exc: _bad(ValueError(str(exc)))


@router.post("/api/screen/{slug}/booking-admin/{module_id}")
async def post_admin_booking(request: Request, slug: str, module_id: str) -> dict[str, Any]:
    _screen_widget(request, slug, module_id, ("booking_manager",))
    try:
        row = create_booking(module_id, await request.json(), actor="admin")
        notify_change(tenant_id=screen_api_tenant_slug(request), module_id=module_id, row=row, event="created")
        return {"booking": row}
    except ValueError as exc: _bad(exc)


@router.post("/api/screen/{slug}/booking-admin/{module_id}/{booking_id}/{action}")
async def post_admin_booking_action(request: Request, slug: str, module_id: str, booking_id: int, action: str) -> dict[str, Any]:
    _screen_widget(request, slug, module_id, ("booking_manager",))
    try:
        row = admin_action(module_id, booking_id, action, await request.json())
        notify_change(tenant_id=screen_api_tenant_slug(request), module_id=module_id, row=row, event=action)
        return {"booking": row}
    except ValueError as exc: _bad(exc)
