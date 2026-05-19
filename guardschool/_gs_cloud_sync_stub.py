"""Community stub: фоновая cloud sync отключена."""
from __future__ import annotations

from typing import Any, Callable


async def run_cloud_sync_once() -> dict[str, Any]:
    return {"skipped": True, "reason": "cloud_sync not available"}


def start_cloud_sync_background() -> Callable[[], None]:
    def _cancel() -> None:
        return

    return _cancel
