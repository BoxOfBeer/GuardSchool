"""Community stub: Web Push notify — no-op."""
from __future__ import annotations


def push_enabled_on_server() -> bool:
    return False


def notify_push_to_screen(**kwargs) -> None:
    return
