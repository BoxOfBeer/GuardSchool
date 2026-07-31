"""HTTP-вспомогательные функции синхронизации с облаком (Bearer token)."""
from __future__ import annotations

import hmac
import os
from typing import Any

from fastapi import HTTPException, Request

from .cloud_store import is_cloud_database_enabled, read_revision_from_database
from .gs_data_revision import compute_data_revision
from .gs_paths import APP_VERSION


def require_sync_bearer(request: Request) -> None:
    expected = (os.environ.get("GUARDSCHOOL_SYNC_TOKEN") or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Синхронизация не настроена (GUARDSCHOOL_SYNC_TOKEN).")
    auth = request.headers.get("authorization") or ""
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Требуется токен синхронизации.")
    got = auth[7:].strip()
    if not hmac.compare_digest(got, expected):
        raise HTTPException(status_code=403, detail="Неверный токен синхронизации.")


def public_revision_payload() -> dict[str, Any]:
    dr = compute_data_revision()
    db_rev = read_revision_from_database()
    return {
        "data_revision": dr,
        "revision": int(db_rev) if db_rev is not None else None,
        "app_version": APP_VERSION,
        "cloud_db": is_cloud_database_enabled(),
    }
