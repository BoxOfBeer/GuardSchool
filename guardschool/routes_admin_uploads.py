"""Admin API: загрузка файлов (фоны, Excel, звуки)."""
from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from .gs_admin_http import admin_msg, admin_ui_lang
from .gs_admin_upload import (
    read_upload_capped as _read_upload_capped,
    reject_if_saas_upload as _reject_if_saas_upload,
    saas_check_json_payload_size as _saas_check_json_payload_size,
    saas_check_quota_for_path as _saas_check_quota_for_path,
)
from .gs_auth import require_auth
from .gs_ensure_dirs import ensure_dirs
from .gs_excel_import import (
    parse_announcements_excel,
    parse_excel,
    parse_holidays_excel,
    parse_marquee_excel,
    parse_weekly_schedule_excel,
)
from .gs_jsonio import write_json
from .gs_paths import (
    ANNOUNCEMENTS_PATH,
    BELL_SOUNDS_DIR,
    FULL_SCHEDULE_PATH,
    HOLIDAYS_PATH,
    MARQUEE_PATH,
    SCHEDULE_PATH,
    SCHEDULE_SAMPLE_PATH,
    UPLOADS_DIR,
    WIDGET_IMAGES_SUBDIR,
)
from .gs_saas_limits import max_schedule_xlsx_bytes, max_widget_image_upload_bytes, saas_mode
from .gs_screen_push import (
    maybe_push_screen_content_if_data_revision_changed as _maybe_push_screen_content_if_data_revision_changed,
)

router = APIRouter(tags=["admin"])


@router.post("/api/admin/upload-background")
async def upload_background(request: Request, file: UploadFile = File(...)) -> dict[str, str]:
    require_auth(request)
    _reject_if_saas_upload(request)
    suffix = Path(file.filename or "background").suffix or ".jpg"
    target = UPLOADS_DIR / f"{secrets.token_hex(8)}{suffix}"
    target.write_bytes(await file.read())
    return {"path": f"/uploads/{target.name}"}


@router.post("/api/admin/upload-widget-image")
async def upload_widget_image(request: Request, file: UploadFile = File(...)) -> dict[str, str]:
    require_auth(request)
    # В SaaS раньше вызывали _reject_if_saas_upload — файл не попадал в tenants/<slug>/data/uploads/…,
    # а форма всё равно могла содержать «адрес» из ручного ввода или старого конфига → 404 по URL.
    lim = max_widget_image_upload_bytes()
    raw = await _read_upload_capped(request, file, lim)
    from .tenant_ctx import map_data_path

    ensure_dirs()
    sub = map_data_path(UPLOADS_DIR / WIDGET_IMAGES_SUBDIR)
    sub.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "image").suffix or ".jpg"
    target = sub / f"{secrets.token_hex(8)}{suffix}"
    target.write_bytes(raw)
    return {"path": f"/uploads/{WIDGET_IMAGES_SUBDIR}/{target.name}"}


@router.post("/api/admin/upload-holidays")
async def upload_holidays(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
    require_auth(request)
    _reject_if_saas_upload(request)
    lang = admin_ui_lang(request)
    suffix = Path(file.filename or "holidays.xlsx").suffix or ".xlsx"
    temp = UPLOADS_DIR / f"holidays_import{suffix}"
    temp.write_bytes(await file.read())
    parsed = parse_holidays_excel(temp, lang=lang)
    write_json(HOLIDAYS_PATH, parsed)
    _maybe_push_screen_content_if_data_revision_changed(request)
    return {"status": "ok", "rows": len(parsed)}


@router.post("/api/admin/upload-announcements")
async def upload_announcements(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
    require_auth(request)
    _reject_if_saas_upload(request)
    lang = admin_ui_lang(request)
    suffix = Path(file.filename or "announcements.xlsx").suffix or ".xlsx"
    temp = UPLOADS_DIR / f"announcements_import{suffix}"
    temp.write_bytes(await file.read())
    parsed = parse_announcements_excel(temp, lang=lang)
    write_json(ANNOUNCEMENTS_PATH, parsed)
    _maybe_push_screen_content_if_data_revision_changed(request)
    return {"status": "ok", "rows": len(parsed)}


@router.post("/api/admin/upload-marquee")
async def upload_marquee(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
    require_auth(request)
    _reject_if_saas_upload(request)
    lang = admin_ui_lang(request)
    suffix = Path(file.filename or "marquee.xlsx").suffix or ".xlsx"
    temp = UPLOADS_DIR / f"marquee_import{suffix}"
    temp.write_bytes(await file.read())
    parsed = parse_marquee_excel(temp, lang=lang)
    write_json(MARQUEE_PATH, parsed)
    _maybe_push_screen_content_if_data_revision_changed(request)
    return {"status": "ok", "rows": len(parsed)}


@router.post("/api/admin/upload-schedule")
async def upload_schedule(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
    require_auth(request)
    lang = admin_ui_lang(request)
    suffix = Path(file.filename or "schedule.xlsx").suffix or ".xlsx"
    temp = UPLOADS_DIR / f"schedule_import{suffix}"
    raw = await _read_upload_capped(request, file, max_schedule_xlsx_bytes()) if saas_mode() else await file.read()
    temp.write_bytes(raw)
    parsed = parse_excel(temp, lang=lang)
    _saas_check_json_payload_size(request, parsed, "schedule.json")
    _saas_check_quota_for_path(request, SCHEDULE_PATH, parsed)
    write_json(SCHEDULE_PATH, parsed)
    _maybe_push_screen_content_if_data_revision_changed(request)
    return {"status": "ok", "rows": len(parsed)}


@router.post("/api/admin/upload-full-schedule")
async def upload_full_schedule(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
    require_auth(request)
    lang = admin_ui_lang(request)
    suffix = Path(file.filename or "full_schedule.xlsx").suffix or ".xlsx"
    temp = UPLOADS_DIR / f"full_schedule_import{suffix}"
    raw = await _read_upload_capped(request, file, max_schedule_xlsx_bytes()) if saas_mode() else await file.read()
    temp.write_bytes(raw)
    parsed = parse_weekly_schedule_excel(temp, lang=lang)
    _saas_check_json_payload_size(request, parsed, "full_schedule.json")
    _saas_check_quota_for_path(request, FULL_SCHEDULE_PATH, parsed)
    write_json(FULL_SCHEDULE_PATH, parsed)
    _maybe_push_screen_content_if_data_revision_changed(request)
    return {"status": "ok", "rows": len(parsed)}


@router.post("/api/admin/upload-schedule-sample")
async def upload_schedule_sample(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
    require_auth(request)
    lang = admin_ui_lang(request)
    suffix = Path(file.filename or "schedule_sample.xlsx").suffix or ".xlsx"
    temp = UPLOADS_DIR / f"schedule_sample_import{suffix}"
    raw = await _read_upload_capped(request, file, max_schedule_xlsx_bytes()) if saas_mode() else await file.read()
    temp.write_bytes(raw)
    parsed = parse_weekly_schedule_excel(temp, lang=lang)
    _saas_check_json_payload_size(request, parsed, "schedule_sample.json")
    _saas_check_quota_for_path(request, SCHEDULE_SAMPLE_PATH, parsed)
    write_json(SCHEDULE_SAMPLE_PATH, parsed)
    _maybe_push_screen_content_if_data_revision_changed(request)
    return {"status": "ok", "rows": len(parsed)}


@router.post("/api/admin/upload-bell-sound")
async def upload_bell_sound(request: Request, file: UploadFile = File(...)) -> dict[str, str]:
    require_auth(request)
    _reject_if_saas_upload(request)
    lang = admin_ui_lang(request)
    suffix = (Path(file.filename or "sound").suffix or ".mp3").lower()
    if suffix not in {".mp3", ".wav", ".ogg", ".m4a", ".aac"}:
        raise HTTPException(
            status_code=400,
            detail=admin_msg(lang, "Допустимы: mp3, wav, ogg, m4a, aac.", "Allowed: mp3, wav, ogg, m4a, aac."),
        )
    name = f"{secrets.token_hex(6)}{suffix}"
    target = BELL_SOUNDS_DIR / name
    target.write_bytes(await file.read())
    return {"filename": name, "url": f"/uploads/bells/{name}"}


@router.post("/api/admin/upload-emergency-sound")
async def upload_emergency_sound(request: Request, file: UploadFile = File(...)) -> dict[str, str]:
    require_auth(request)
    _reject_if_saas_upload(request)
    lang = admin_ui_lang(request)
    ensure_dirs()
    suffix = (Path(file.filename or "sound").suffix or ".mp3").lower()
    if suffix not in {".mp3", ".wav", ".ogg", ".m4a", ".aac"}:
        raise HTTPException(
            status_code=400,
            detail=admin_msg(lang, "Допустимы: mp3, wav, ogg, m4a, aac.", "Allowed: mp3, wav, ogg, m4a, aac."),
        )
    sub = UPLOADS_DIR / "emergency_sounds"
    sub.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_hex(6)}{suffix}"
    target = sub / name
    target.write_bytes(await file.read())
    return {"filename": name, "url": f"/uploads/emergency_sounds/{name}"}


@router.get("/api/admin/bell-sounds")
def list_bell_sounds(request: Request) -> dict[str, Any]:
    require_auth(request)
    ensure_dirs()
    files = []
    if BELL_SOUNDS_DIR.exists():
        for p in sorted(BELL_SOUNDS_DIR.iterdir()):
            if p.is_file():
                files.append({"filename": p.name, "url": f"/uploads/bells/{p.name}"})
    return {"files": files}
