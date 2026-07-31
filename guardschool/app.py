"""GuardSchool FastAPI entry point (`uvicorn app:app` via repo-root shim)."""
from __future__ import annotations

import logging

from .gs_app_factory import create_app

_log = logging.getLogger(__name__)

app = create_app()

# uploads/ зависят от школы (тенанта) в SaaS — отдаём через routes_pages, не StaticFiles mount.
