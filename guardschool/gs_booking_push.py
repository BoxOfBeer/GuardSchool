"""Targeted Web Push helpers for appointment modules."""
from __future__ import annotations

import hashlib
from typing import Any

from .optional_imports import push_module
from .push_notify import notify_push_to_screen, push_enabled_on_server


def _module_key(module_id: str) -> str:
    return hashlib.sha256(str(module_id).encode("utf-8")).hexdigest()[:12]


def subscription_key(module_id: str, audience: str, device_hash: str = "") -> str:
    if audience == "admin":
        return f"booking-{_module_key(module_id)}-admin"
    return f"booking-{_module_key(module_id)}-{str(device_hash)[:32]}"


def subscribe(*, tenant_id: str, module_id: str, audience: str, device_hash: str, subscription: dict[str, Any]) -> None:
    push = push_module()
    if push is None or not push_enabled_on_server():
        raise ValueError("Push-уведомления на сервере не настроены.")
    endpoint = str(subscription.get("endpoint") or "").strip()
    keys = subscription.get("keys") if isinstance(subscription.get("keys"), dict) else {}
    p256dh, auth = str(keys.get("p256dh") or "").strip(), str(keys.get("auth") or "").strip()
    if not endpoint or not p256dh or not auth:
        raise ValueError("Некорректная push-подписка.")
    push.upsert_subscription(tenant_id=tenant_id, screen_slug=subscription_key(module_id, audience, device_hash), endpoint=endpoint, p256dh=p256dh, auth=auth, topics={"booking": True}, min_interval_sec=30, enabled=True)


def notify_change(*, tenant_id: str, module_id: str, row: dict[str, Any], event: str) -> None:
    url = f"/screen/{row.get('screen_slug') or ''}"
    labels = {"created": "Создана новая запись", "cancel_requested": "Запрошена отмена", "confirm_cancel": "Отмена подтверждена", "reject_cancel": "Отмена отклонена", "cancel": "Запись отменена", "move": "Время записи изменено"}
    body = f"{row.get('service_title', '')}: {str(row.get('start_at', ''))[:16].replace('T', ' ')}"
    notify_push_to_screen(tenant_id=tenant_id, screen_slug=subscription_key(module_id, "admin"), topic="booking", title=labels.get(event, "Изменение записи"), body=body, url=url, skip_rate_limit=True, notification_tag=f"booking-admin-{row.get('id')}")
    dh = str(row.get("device_hash") or "")
    if dh and event != "created":
        notify_push_to_screen(tenant_id=tenant_id, screen_slug=subscription_key(module_id, "device", dh), topic="booking", title=labels.get(event, "Изменение записи"), body=body, url=url, skip_rate_limit=True, notification_tag=f"booking-device-{row.get('id')}")


def notify_reminder(*, tenant_id: str, row: dict[str, Any]) -> None:
    dh = str(row.get("device_hash") or "")
    if not dh:
        return
    notify_push_to_screen(tenant_id=tenant_id, screen_slug=subscription_key(str(row["module_id"]), "device", dh), topic="booking", title="Напоминание о записи", body=f"Через 2 часа: {row.get('service_title', '')}", url=f"/screen/{row.get('screen_slug') or ''}", skip_rate_limit=True, notification_tag=f"booking-reminder-{row.get('id')}")


def notify_morning(*, tenant_id: str, summary: dict[str, Any]) -> None:
    first = str(summary.get("first_at") or "")
    notify_push_to_screen(tenant_id=tenant_id, screen_slug=subscription_key(str(summary["module_id"]), "admin"), topic="booking", title="Записи на сегодня", body=f"Всего: {summary['count']}. Первая: {first[11:16]}", url=f"/screen/{summary.get('screen_slug') or ''}", skip_rate_limit=True, notification_tag=f"booking-morning-{first[:10]}")
