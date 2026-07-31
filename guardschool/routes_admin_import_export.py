"""Admin API: экспорт/импорт ZIP и образцы Excel."""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from .gs_admin_http import admin_msg, admin_ui_lang
from .gs_admin_upload import (
    read_upload_capped as _read_upload_capped,
    reject_if_saas_upload as _reject_if_saas_upload,
    saas_enforce_user_data_quota_after_multi_write as _saas_enforce_user_data_quota_after_multi_write,
)
from .gs_auth import require_auth
from .gs_data_loaders import load_full_schedule, load_schedule_sample
from .gs_ensure_dirs import ensure_dirs
from .gs_import_bundle import (
    export_bundle_bytes,
    export_weekly_schedule_bundle_bytes,
    import_bundle_bytes,
    import_weekly_schedule_bundle_bytes,
)
from .gs_import_sample_xlsx import import_excel_sample_bytes
from .gs_paths import FULL_SCHEDULE_SAMPLE_XLSX
from .gs_saas_limits import max_weekly_zip_bytes, saas_mode
from .gs_screen_push import (
    maybe_push_screen_content_if_data_revision_changed as _maybe_push_screen_content_if_data_revision_changed,
)
from .gs_weekly_template import ensure_weekly_schedule_template_file

router = APIRouter(tags=["admin"])


@router.get("/api/admin/export")
def export_admin_bundle(request: Request) -> StreamingResponse:
    require_auth(request)
    bundle = export_bundle_bytes()
    filename = f'gorniitv_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
    return StreamingResponse(
        io.BytesIO(bundle),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/admin/export-weekly-schedule")
def export_weekly_schedule_bundle(request: Request) -> StreamingResponse:
    require_auth(request)
    bundle = export_weekly_schedule_bundle_bytes()
    filename = f'guardschool_weekly_schedule_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
    return StreamingResponse(
        io.BytesIO(bundle),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/admin/weekly-schedule-template.xlsx")
def download_weekly_schedule_template_xlsx(request: Request) -> FileResponse:
    require_auth(request)
    ensure_dirs()
    ensure_weekly_schedule_template_file()
    if not FULL_SCHEDULE_SAMPLE_XLSX.is_file():
        raise HTTPException(
            status_code=404,
            detail=admin_msg(admin_ui_lang(request), "Не удалось создать шаблон.", "Could not create template."),
        )
    return FileResponse(
        FULL_SCHEDULE_SAMPLE_XLSX,
        filename="full_schedule_sample.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/api/admin/import-excel-sample.xlsx")
def download_import_excel_sample(request: Request, kind: str = Query(...)) -> Response:
    """Образцы Excel для блока «Импорт из Excel» (kind=dated|full|sample|holidays|announcements|marquee)."""
    require_auth(request)
    lang = admin_ui_lang(request)
    body, filename = import_excel_sample_bytes(kind=kind, lang=lang)
    return Response(
        content=body,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/api/admin/import")
async def import_admin_bundle(request: Request, file: UploadFile = File(...)) -> dict[str, str]:
    require_auth(request)
    _reject_if_saas_upload(request)
    lang = admin_ui_lang(request)
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(
            status_code=400,
            detail=admin_msg(lang, "Нужен ZIP-архив экспорта.", "Expected an export ZIP archive."),
        )
    import_bundle_bytes(await file.read(), lang=lang)
    return {"status": "ok"}


@router.post("/api/admin/import-weekly-schedule")
async def import_weekly_schedule_bundle(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
    require_auth(request)
    lang = admin_ui_lang(request)
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(
            status_code=400,
            detail=admin_msg(
                lang,
                "Нужен ZIP с full_schedule.xlsx и schedule_sample.xlsx.",
                "Expected a ZIP with full_schedule.xlsx and schedule_sample.xlsx.",
            ),
        )
    raw = await _read_upload_capped(request, file, max_weekly_zip_bytes()) if saas_mode() else await file.read()
    import_weekly_schedule_bundle_bytes(raw, lang=lang)
    _saas_enforce_user_data_quota_after_multi_write(request)
    _maybe_push_screen_content_if_data_revision_changed(request)
    return {
        "status": "ok",
        "full_schedule_rows": len(load_full_schedule()),
        "schedule_sample_rows": len(load_schedule_sample()),
    }
