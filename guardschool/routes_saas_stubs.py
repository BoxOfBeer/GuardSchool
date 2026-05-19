"""Заглушки SaaS HTTP: те же пути, ответ 503 если capability missing (community local)."""
from __future__ import annotations

from fastapi import APIRouter, Request

from .capabilities import (
    CAP_CLOUD_STATUS,
    CAP_CLOUD_SYNC,
    CAP_PUSH_NOTIFICATIONS,
    CAP_REMOTE_TV_PAIRING,
    CAP_TENANT_FEEDBACK,
)
from .gs_capability_http import require_capability

router = APIRouter(tags=["saas-stubs"])


@router.post("/api/screen/{slug}/feedback")
async def stub_post_screen_feedback(request: Request, slug: str) -> None:
    require_capability(CAP_TENANT_FEEDBACK)


@router.get("/api/admin/feedback")
def stub_admin_feedback_list(request: Request) -> None:
    require_capability(CAP_TENANT_FEEDBACK)


@router.post("/api/admin/feedback/{message_id}/read")
def stub_admin_feedback_mark_read(message_id: int, request: Request) -> None:
    require_capability(CAP_TENANT_FEEDBACK)


@router.post("/api/admin/feedback/{message_id}/hide")
def stub_admin_feedback_hide(message_id: int, request: Request) -> None:
    require_capability(CAP_TENANT_FEEDBACK)


@router.post("/api/admin/feedback/block-hash")
async def stub_admin_feedback_block_hash(request: Request) -> None:
    require_capability(CAP_TENANT_FEEDBACK)


@router.get("/api/sync/status")
def stub_api_sync_status(request: Request) -> None:
    require_capability(CAP_CLOUD_SYNC)


@router.get("/api/sync/bundle")
def stub_api_sync_bundle(request: Request) -> None:
    require_capability(CAP_CLOUD_SYNC)


@router.get("/api/admin/sync-status")
def stub_admin_sync_status(request: Request) -> None:
    require_capability(CAP_CLOUD_STATUS)


@router.get("/api/screen/{slug}/push/vapid-public-key")
def stub_push_vapid(request: Request, slug: str) -> None:
    require_capability(CAP_PUSH_NOTIFICATIONS)


@router.get("/api/screen/{slug}/tv-pair-link")
def stub_tv_pair_link(request: Request, slug: str) -> None:
    require_capability(CAP_REMOTE_TV_PAIRING)


@router.post("/api/screen/{slug}/push/subscribe")
async def stub_push_subscribe(request: Request, slug: str) -> None:
    require_capability(CAP_PUSH_NOTIFICATIONS)


@router.post("/api/screen/{slug}/push/unsubscribe")
async def stub_push_unsubscribe(request: Request, slug: str) -> None:
    require_capability(CAP_PUSH_NOTIFICATIONS)


@router.post("/api/screen/{slug}/push/test")
def stub_push_test(request: Request, slug: str) -> None:
    require_capability(CAP_PUSH_NOTIFICATIONS)


@router.get("/t/{code}/{screen_slug}")
def stub_tv_pair_page(request: Request, code: str, screen_slug: str) -> None:
    require_capability(CAP_REMOTE_TV_PAIRING)


@router.post("/api/tv/pair")
async def stub_tv_pair(request: Request) -> None:
    require_capability(CAP_REMOTE_TV_PAIRING)


@router.get("/api/admin/tv-access")
def stub_admin_tv_access_get(request: Request) -> None:
    require_capability(CAP_REMOTE_TV_PAIRING)


@router.post("/api/admin/tv-access/rotate-code")
async def stub_admin_tv_access_rotate_code(request: Request) -> None:
    require_capability(CAP_REMOTE_TV_PAIRING)


@router.post("/api/admin/tv-access/set-pin")
async def stub_admin_tv_access_set_pin(request: Request) -> None:
    require_capability(CAP_REMOTE_TV_PAIRING)


@router.post("/api/admin/tv-access/pin-bypass")
async def stub_admin_tv_access_pin_bypass(request: Request) -> None:
    require_capability(CAP_REMOTE_TV_PAIRING)
