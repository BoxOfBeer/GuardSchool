"""Community: без SaaS lifecycle."""
from __future__ import annotations

import asyncio
from typing import Callable


def saas_startup_sync() -> None:
    return


def start_cloud_sync_cancel() -> Callable[[], None] | None:
    return None


def start_demo_cleanup_task() -> asyncio.Task | None:
    return None


async def shutdown_demo_task(task: asyncio.Task | None) -> None:
    return
