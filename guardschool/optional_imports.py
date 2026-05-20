"""Ленивые импорты опциональных SaaS-модулей (open-core: core не тянет их при local-only)."""
from __future__ import annotations

from typing import Any

from .capabilities import (
    CAP_CLOUD_SYNC,
    CAP_PUSH_NOTIFICATIONS,
    CAP_TENANT_FEEDBACK,
    has_capability,
)


def push_module() -> Any:
    if not has_capability(CAP_PUSH_NOTIFICATIONS):
        return None
    from .private_modules import import_optional_module

    return import_optional_module("gs_push")


def cloud_sync_module() -> Any:
    if not has_capability(CAP_CLOUD_SYNC):
        return None
    from .private_modules import import_optional_module

    return import_optional_module("gs_cloud_sync")


def feedback_module() -> Any:
    if not has_capability(CAP_TENANT_FEEDBACK):
        return None
    from .private_modules import import_optional_module

    return import_optional_module("gs_feedback")


def ensure_feedback_tables_if_needed() -> None:
  mod = feedback_module()
  if mod is None:
    return
  mod.ensure_feedback_tables()


def create_feedback_message(**kwargs: Any) -> dict[str, Any]:
  mod = feedback_module()
  if mod is None:
    raise RuntimeError("tenant_feedback capability is not available")
  return mod.create_feedback_message(**kwargs)


def list_feedback_messages(**kwargs: Any) -> list[dict[str, Any]]:
  mod = feedback_module()
  if mod is None:
    return []
  return mod.list_feedback_messages(**kwargs)


def count_unread_feedback_messages() -> int:
  mod = feedback_module()
  if mod is None:
    return 0
  return int(mod.count_unread_feedback_messages())


def mark_feedback_read(message_id: int) -> None:
  mod = feedback_module()
  if mod is None:
    return
  mod.mark_feedback_read(message_id)


def hide_feedback(message_id: int) -> None:
  mod = feedback_module()
  if mod is None:
    return
  mod.hide_feedback(message_id)


def block_feedback_hash(device_hash: str) -> None:
  mod = feedback_module()
  if mod is None:
    return
  mod.block_feedback_hash(device_hash)


def can_send_feedback(device_hash: str, *, cooldown_minutes: int = 5) -> bool:
  mod = feedback_module()
  if mod is None:
    return False
  return mod.can_send_feedback(device_hash, cooldown_minutes=cooldown_minutes)
