"""Background delivery of appointment reminders and morning summaries."""
from __future__ import annotations

import asyncio
import logging

from .gs_booking import claim_scheduled_notifications
from .gs_booking_push import notify_morning, notify_reminder
from .gs_deploy import deployment_mode
from .tenant_ctx import set_tenant_slug, tenant_data_root, tenant_slug

_log = logging.getLogger(__name__)


def _tenant_ids() -> list[str | None]:
    if deployment_mode() != "saas":
        return [None]
    root = tenant_data_root()
    return [p.name for p in root.iterdir() if p.is_dir() and (p / "data").is_dir()] if root.exists() else []


def _run_once_sync() -> None:
    previous = tenant_slug()
    try:
        for slug in _tenant_ids():
            set_tenant_slug(slug)
            claimed = claim_scheduled_notifications()
            tenant_id = slug or "local"
            for row in claimed["reminders"]:
                notify_reminder(tenant_id=tenant_id, row=row)
            for summary in claimed["summaries"]:
                notify_morning(tenant_id=tenant_id, summary=summary)
    finally:
        set_tenant_slug(previous)


async def run() -> None:
    while True:
        try:
            await asyncio.to_thread(_run_once_sync)
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception("booking notification worker failed")
        await asyncio.sleep(60)


def start() -> asyncio.Task:
    return asyncio.create_task(run(), name="booking-notifications")
