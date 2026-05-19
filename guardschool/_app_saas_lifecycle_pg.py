"""SaaS: startup/shutdown хуков (schema, demo cleanup, cloud sync background)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from .app_try_demo import ensure_try_demo_sandbox_tenant_data
from .gs_deploy import deployment_mode
from .optional_imports import cloud_sync_module
from .saas_db import cleanup_expired_demo_sessions, ensure_public_schema, saas_db_enabled

_LOG = logging.getLogger(__name__)


async def _demo_ttl_sweeper() -> None:
    while True:
        await asyncio.sleep(600)
        try:
            cleanup_expired_demo_sessions()
        except Exception:
            pass


def saas_startup_sync() -> None:
    if not saas_db_enabled():
        return
    try:
        ensure_public_schema()
    except Exception:
        pass
    try:
        ensure_try_demo_sandbox_tenant_data()
    except Exception:
        pass
    try:
        cleanup_expired_demo_sessions()
    except Exception:
        pass


def start_cloud_sync_cancel() -> Callable[[], None] | None:
    sync_mod = cloud_sync_module()
    if sync_mod is None:
        return None
    try:
        return sync_mod.start_cloud_sync_background()
    except Exception:
        return None


def start_demo_cleanup_task() -> asyncio.Task | None:
    if not saas_db_enabled() or deployment_mode() != "saas":
        return None
    return asyncio.create_task(_demo_ttl_sweeper())


async def shutdown_demo_task(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
