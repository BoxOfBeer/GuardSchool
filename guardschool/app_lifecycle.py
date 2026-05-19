"""FastAPI lifespan GuardSchool (open-core + SaaS hooks)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import bell_rupor_worker
from .app_saas_lifecycle import (
    saas_startup_sync,
    shutdown_demo_task,
    start_cloud_sync_cancel,
    start_demo_cleanup_task,
)
from .capabilities import ensure_capabilities_initialized
from .cloud_store import hydrate_data_dir_from_database
from .gs_ensure_dirs import ensure_dirs
from .gs_saas_bootstrap import ensure_saas_bootstrap_admin
from .optional_imports import ensure_feedback_tables_if_needed
from .gs_checkin import ensure_checkin_tables


@asynccontextmanager
async def guard_school_lifespan(_app: FastAPI):
    saas_startup_sync()
    ensure_saas_bootstrap_admin()
    ensure_dirs()
    ensure_feedback_tables_if_needed()
    ensure_checkin_tables()
    hydrate_data_dir_from_database()
    from .widget_loader import load_all_widgets

    ensure_capabilities_initialized()
    load_all_widgets()
    cancel_sync = start_cloud_sync_cancel()
    demo_cleanup_task = start_demo_cleanup_task()
    bell_rupor_worker.start_worker()
    try:
        yield
    finally:
        await shutdown_demo_task(demo_cleanup_task)
        if cancel_sync is not None:
            cancel_sync()
        bell_rupor_worker.stop_worker()
