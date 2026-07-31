"""Web Push: отправка уведомлений (open-core — импорт gs_push только через push_module)."""
from __future__ import annotations

import json
import logging
from typing import Any

from .optional_imports import push_module

_LOG = logging.getLogger(__name__)


def push_enabled_on_server() -> bool:
    push = push_module()
    if push is None:
        return False
    return bool(
        push.vapid_public_key() and push.vapid_private_key() and push.vapid_application_server_key(),
    )


def notify_push_to_screen(
    *,
    tenant_id: str,
    screen_slug: str,
    topic: str,
    title: str,
    body: str,
    url: str,
    all_subscribers: bool = False,
    skip_rate_limit: bool = False,
    notification_tag: str | None = None,
) -> None:
    push = push_module()
    if push is None or not push_enabled_on_server():
        return
    list_topic = "" if all_subscribers else topic
    subs = push.list_subscriptions(tenant_id=tenant_id, screen_slug=screen_slug, topic=list_topic)
    if not subs:
        return
    mi = 300
    try:
        mi = int(subs[0].get("min_interval_sec") or 300)
    except Exception:
        mi = 300
    if not skip_rate_limit:
        dec = push.rate_limit_decide(tenant_id=tenant_id, screen_slug=screen_slug, topic=topic, min_interval_sec=mi)
        if not dec.should_send:
            return
    tag_out = (notification_tag or "").strip() or f"{screen_slug}:{topic}"
    payload = json.dumps(
        {"title": title, "body": body, "url": url, "tag": tag_out},
        ensure_ascii=False,
    )
    try:
        from pywebpush import webpush
    except Exception:
        return
    sent = 0
    for s in subs:
        try:
            webpush(
                subscription_info={"endpoint": s["endpoint"], "keys": s["keys"]},
                data=payload,
                vapid_private_key=push.vapid_private_key_for_webpush(),
                vapid_claims={"sub": push.vapid_subject()},
            )
            sent += 1
        except Exception as exc:
            ep_short = str(s.get("endpoint") or "")[:72]
            full_ep = str(s.get("endpoint") or "").strip()
            if push.webpush_subscription_stale(exc) and full_ep:
                n = push.delete_subscription(
                    tenant_id=tenant_id,
                    screen_slug=screen_slug,
                    endpoint=full_ep,
                )
                _LOG.info(
                    "webpush stale subscription removed screen=%s topic=%s endpoint=%s deleted=%s",
                    screen_slug,
                    topic,
                    ep_short,
                    n,
                )
            else:
                _LOG.warning(
                    "webpush failed screen=%s topic=%s endpoint=%s: %s",
                    screen_slug,
                    topic,
                    ep_short,
                    exc,
                )
            continue
    if subs and sent == 0:
        _LOG.warning(
            "webpush: 0/%d доставлено screen=%s topic=%s tenant=%s",
            len(subs),
            screen_slug,
            topic,
            tenant_id,
        )
