"""Community: revision payload для локального core; Bearer sync — только в полной сборке."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from .cloud_store import is_cloud_database_enabled, read_revision_from_database
from .gs_data_revision import compute_data_revision
from .gs_paths import APP_VERSION


def require_sync_bearer(request: Request) -> None:
    raise HTTPException(status_code=503, detail="Синхронизация не доступна (community edition).")


def public_revision_payload() -> dict[str, Any]:
    dr = compute_data_revision()
    db_rev = read_revision_from_database()
    return {
        "data_revision": dr,
        "revision": int(db_rev) if db_rev is not None else None,
        "app_version": APP_VERSION,
        "cloud_db": is_cloud_database_enabled(),
    }
