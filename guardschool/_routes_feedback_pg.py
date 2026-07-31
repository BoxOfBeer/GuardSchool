"""Роуты обратной связи с ТВ (админка + экран)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from .capabilities import CAP_TENANT_FEEDBACK
from .gs_auth import require_auth
from .gs_capability_http import require_capability
from .gs_tv_screen_api import (
    find_active_screen,
    normalize_screen_slug_for_api,
    require_tv_access_for_screen,
    screen_api_tenant_slug,
)
from .optional_imports import (
    block_feedback_hash,
    can_send_feedback,
    count_unread_feedback_messages,
    create_feedback_message,
    hide_feedback,
    list_feedback_messages,
    mark_feedback_read,
)

router = APIRouter(tags=["feedback"])


@router.post("/api/screen/{slug}/feedback")
async def post_screen_feedback(request: Request, slug: str) -> dict[str, Any]:
    require_capability(CAP_TENANT_FEEDBACK)
    slug_key = normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    require_tv_access_for_screen(request, slug_key)
    screen = find_active_screen(slug)
    if not screen:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    if not bool(screen.get("enable_feedback")):
        raise HTTPException(status_code=403, detail="Обратная связь отключена для этого экрана.")
    body = await request.json()
    device_hash = str(body.get("device_hash") or "").strip()[:128]
    message = str(body.get("message") or "").strip()
    if not device_hash:
        raise HTTPException(status_code=400, detail="Не передан device_hash.")
    if len(message) < 2:
        raise HTTPException(status_code=400, detail="Сообщение слишком короткое.")
    if len(message) > 2000:
        message = message[:2000]
    if not can_send_feedback(device_hash, cooldown_minutes=5):
        raise HTTPException(status_code=429, detail="Можно отправлять не чаще 1 сообщения в 5 минут.")
    saved = create_feedback_message(
        tenant_id=screen_api_tenant_slug(request),
        device_hash=device_hash,
        message=message,
    )
    return {"status": "ok", **saved}


@router.get("/api/admin/feedback")
def admin_feedback_list(request: Request, include_hidden: bool = Query(False)) -> dict[str, Any]:
    require_capability(CAP_TENANT_FEEDBACK)
    require_auth(request)
    return {"items": list_feedback_messages(limit=500, include_hidden=bool(include_hidden))}


@router.get("/api/admin/feedback/unread-count")
def admin_feedback_unread_count(request: Request) -> dict[str, int]:
    require_capability(CAP_TENANT_FEEDBACK)
    require_auth(request)
    return {"count": count_unread_feedback_messages()}


@router.post("/api/admin/feedback/{message_id}/read")
def admin_feedback_mark_read(message_id: int, request: Request) -> dict[str, Any]:
    require_capability(CAP_TENANT_FEEDBACK)
    require_auth(request)
    mark_feedback_read(message_id)
    return {"status": "ok"}


@router.post("/api/admin/feedback/{message_id}/hide")
def admin_feedback_hide(message_id: int, request: Request) -> dict[str, Any]:
    require_capability(CAP_TENANT_FEEDBACK)
    require_auth(request)
    hide_feedback(message_id)
    return {"status": "ok"}


@router.post("/api/admin/feedback/block-hash")
async def admin_feedback_block_hash(request: Request) -> dict[str, Any]:
    require_capability(CAP_TENANT_FEEDBACK)
    require_auth(request)
    body = await request.json()
    h = str(body.get("device_hash") or "").strip()[:128]
    if not h:
        raise HTTPException(status_code=400, detail="Пустой device_hash.")
    block_feedback_hash(h)
    return {"status": "ok"}
