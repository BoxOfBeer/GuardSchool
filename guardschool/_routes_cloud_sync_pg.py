"""Роуты синхронизации с облаком (core; layer может подключить свой router поверх)."""
from __future__ import annotations

import io

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .capabilities import CAP_CLOUD_SYNC
from .gs_capability_http import require_capability
from .gs_import_bundle import export_bundle_bytes
from .gs_sync_http import public_revision_payload, require_sync_bearer

router = APIRouter(tags=["cloud-sync"])


@router.get("/api/sync/status")
def api_sync_status(request: Request) -> dict:
    """Проверка ревизии для локального агента (Bearer GUARDSCHOOL_SYNC_TOKEN на сервере)."""
    require_capability(CAP_CLOUD_SYNC)
    require_sync_bearer(request)
    return public_revision_payload()


@router.get("/api/sync/bundle")
def api_sync_bundle(request: Request) -> StreamingResponse:
    """Полный ZIP-экспорт для подтягивания в локальную школу."""
    require_capability(CAP_CLOUD_SYNC)
    require_sync_bearer(request)
    bundle = export_bundle_bytes()
    return StreamingResponse(
        io.BytesIO(bundle),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="guardschool_export.zip"'},
    )
