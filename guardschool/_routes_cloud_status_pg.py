"""Админка: статус синхронизации с облаком (SaaS capability cloud_status)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from .capabilities import CAP_CLOUD_STATUS
from .cloud_store import read_revision_from_database
from .gs_auth import require_auth
from .gs_capability_http import require_capability
from .gs_data_revision import compute_data_revision
from .gs_deploy import deployment_mode
from .gs_jsonio import read_json
from .gs_paths import SYNC_STATE_PATH

router = APIRouter(tags=["cloud-status"])


@router.get("/api/admin/sync-status")
def get_admin_sync_status(request: Request) -> dict[str, Any]:
    require_capability(CAP_CLOUD_STATUS)
    require_auth(request)
    if deployment_mode() == "saas":
        cr: int | None = None
        try:
            cr = read_revision_from_database()
        except Exception:
            cr = None
        return {
            "sync_state": {},
            "data_revision": compute_data_revision(),
            "cloud_revision": cr,
            "saas_no_file_sync": True,
        }

    return {
        "sync_state": read_json(SYNC_STATE_PATH, {}),
        "data_revision": compute_data_revision(),
        "cloud_revision": read_revision_from_database(),
    }
