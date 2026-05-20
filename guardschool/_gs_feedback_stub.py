"""Community stub: обратная связь с ТВ отключена."""
from __future__ import annotations

from typing import Any


def ensure_feedback_tables() -> None:
    return


def is_feedback_blocked(device_hash: str) -> bool:
    return False


def can_send_feedback(device_hash: str, cooldown_minutes: int = 5) -> bool:
    return False


def create_feedback_message(tenant_id: str, device_hash: str, message: str) -> dict[str, Any]:
    raise RuntimeError("tenant_feedback capability is not available")


def list_feedback_messages(limit: int = 300, include_hidden: bool = False) -> list[dict[str, Any]]:
    return []


def count_unread_feedback_messages() -> int:
    return 0


def mark_feedback_read(message_id: int) -> None:
    return


def hide_feedback(message_id: int) -> None:
    return


def block_feedback_hash(device_hash: str) -> None:
    return
