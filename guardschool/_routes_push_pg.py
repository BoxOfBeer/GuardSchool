"""Роуты Web Push и TV pair link (SaaS; capability gates)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request

from .capabilities import CAP_PUSH_NOTIFICATIONS, CAP_REMOTE_TV_PAIRING
from .gs_capability_http import require_capability
from .gs_deploy import deployment_mode
from .gs_tv_screen_api import (
    canonical_tv_school_code,
    normalize_screen_slug_for_api,
    normalize_tv_pair_text,
    require_tv_access_for_screen,
    screen_api_tenant_slug,
    tv_pwa_screen_url,
)
from .optional_imports import push_module
from .push_notify import notify_push_to_screen, push_enabled_on_server
from .saas_db import connect_public, saas_db_enabled

router = APIRouter(tags=["push"])


@router.get("/api/screen/{slug}/push/vapid-public-key")
def api_push_vapid_public_key(request: Request, slug: str) -> dict[str, Any]:
    require_capability(CAP_PUSH_NOTIFICATIONS)
    push = push_module()
    if push is None:
        raise HTTPException(status_code=503, detail="Push недоступен.")
    slug_key = normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    require_tv_access_for_screen(request, slug_key)
    return {
        "status": "ok",
        "public_key": push.vapid_public_key(),
        "application_server_key": push.vapid_application_server_key(),
        "enabled": push_enabled_on_server(),
    }


@router.get("/api/screen/{slug}/tv-pair-link")
def api_screen_tv_pair_link(request: Request, slug: str) -> dict[str, Any]:
    """
    Для уже подключённых /screen/{slug}?gs_tv_token=... устройств:
    вернуть публичную SaaS-ссылку вида /t/<code>/<slug>, чтобы можно было установить PWA-ярлык без переподключения.
    """
    require_capability(CAP_REMOTE_TV_PAIRING)
    slug_key = normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    require_tv_access_for_screen(request, slug_key)
    if deployment_mode() != "saas" or not saas_db_enabled():
        raise HTTPException(status_code=404, detail="Not found.")
    try:
        from .tenant_ctx import tenant_slug as current_tenant

        ts = str(current_tenant() or "").strip()
    except Exception:
        ts = ""
    if not ts:
        raise HTTPException(status_code=404, detail="Tenant not resolved.")
    code_plain = ""
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT code_plaintext FROM tv_access WHERE tenant_slug=%s", (ts,))
            row = cur.fetchone()
            code_plain = str(row[0] or "").strip() if row else ""
    if not code_plain:
        raise HTTPException(status_code=404, detail="TV code is not configured.")
    code_canon = canonical_tv_school_code(normalize_tv_pair_text(code_plain)) or code_plain
    return {
        "status": "ok",
        "code": code_plain,
        "url": tv_pwa_screen_url(code_canon, slug_key, "", pwa=True),
    }


@router.post("/api/screen/{slug}/push/subscribe")
async def api_push_subscribe(request: Request, slug: str) -> dict[str, Any]:
    require_capability(CAP_PUSH_NOTIFICATIONS)
    slug_key = normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    require_tv_access_for_screen(request, slug_key)
    body = await request.json()
    sub = body.get("subscription") if isinstance(body, dict) else None
    if not isinstance(sub, dict):
        raise HTTPException(status_code=400, detail="subscription required")
    endpoint = str(sub.get("endpoint") or "").strip()
    keys = sub.get("keys") if isinstance(sub.get("keys"), dict) else {}
    p256dh = str(keys.get("p256dh") or "").strip()
    auth = str(keys.get("auth") or "").strip()
    if not endpoint or not p256dh or not auth:
        raise HTTPException(status_code=400, detail="Invalid subscription")
    topics = body.get("topics") if isinstance(body, dict) else {}
    try:
        min_interval_sec = int(body.get("min_interval_sec") or 300) if isinstance(body, dict) else 300
    except (TypeError, ValueError):
        min_interval_sec = 300
    push = push_module()
    if push is None:
        raise HTTPException(status_code=503, detail="Push недоступен.")
    tenant_id = screen_api_tenant_slug(request)
    push.upsert_subscription(
        tenant_id=tenant_id,
        screen_slug=slug_key,
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth,
        topics=topics if isinstance(topics, dict) else {},
        min_interval_sec=min_interval_sec,
        enabled=True,
    )
    return {"status": "ok"}


@router.post("/api/screen/{slug}/push/unsubscribe")
async def api_push_unsubscribe(request: Request, slug: str) -> dict[str, Any]:
    require_capability(CAP_PUSH_NOTIFICATIONS)
    slug_key = normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    require_tv_access_for_screen(request, slug_key)
    body = await request.json()
    endpoint = str((body or {}).get("endpoint") or "").strip() if isinstance(body, dict) else ""
    if not endpoint:
        raise HTTPException(status_code=400, detail="endpoint required")
    push = push_module()
    if push is None:
        raise HTTPException(status_code=503, detail="Push недоступен.")
    tenant_id = screen_api_tenant_slug(request)
    n = push.delete_subscription(tenant_id=tenant_id, screen_slug=slug_key, endpoint=endpoint)
    return {"status": "ok", "deleted": n}


@router.post("/api/screen/{slug}/push/test")
def api_push_test(
    request: Request,
    slug: str,
    topic: str = Query("", description="Пусто — все подписки; checkin|emergency|content|test — как у реальных событий"),
) -> dict[str, Any]:
    """Проверка Web Push: без topic — все подписки; с topic — только с включённой темой (как боевые события)."""
    require_capability(CAP_PUSH_NOTIFICATIONS)
    slug_key = normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    require_tv_access_for_screen(request, slug_key)
    if not push_enabled_on_server():
        raise HTTPException(status_code=503, detail="Push на сервере не настроен (VAPID).")
    push = push_module()
    if push is None:
        raise HTTPException(status_code=503, detail="Push недоступен.")
    tenant_id = screen_api_tenant_slug(request)
    topic_key = (topic or "").strip().lower()
    if topic_key and topic_key not in ("checkin", "emergency", "content", "test"):
        raise HTTPException(status_code=400, detail="topic: checkin, emergency, content или пусто.")
    if topic_key:
        subs = push.list_subscriptions(tenant_id=tenant_id, screen_slug=slug_key, topic=topic_key)
        all_subs = False
        topic_send = topic_key
        title = f"GuardSchool — тест ({topic_key})"
    else:
        subs = push.list_subscriptions(tenant_id=tenant_id, screen_slug=slug_key, topic=None)
        all_subs = True
        topic_send = "test"
        title = "GuardSchool — тест push"
    if not subs:
        hint = (
            "Нет подписки с темой «журнал сводки» на этот экран."
            if topic_key == "checkin"
            else "Нет подписки с темой «обновления экрана» на этот экран."
            if topic_key == "content"
            else "Нет подписки на этот экран — сначала нажмите «Включить уведомления»."
        )
        raise HTTPException(status_code=400, detail=hint)
    now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    notify_push_to_screen(
        tenant_id=tenant_id,
        screen_slug=slug_key,
        topic=topic_send,
        title=title,
        body=(
            f"Сервер отправил в {now}. Если нет баннера: «Не беспокоить», настройки сайта в Windows, "
            f"или смотрите консоль SW (F12 → Application → Service Workers → Inspect)."
        ),
        url=f"/screen/{quote(slug_key, safe='')}",
        all_subscribers=all_subs,
        skip_rate_limit=True,
    )
    return {"status": "ok", "targets": len(subs), "topic": topic_key or "all"}
