"""Admin HTTP API (/api/admin/*). Open-core, монтируется из app.py."""
from __future__ import annotations

import io
import json
import logging
import re
import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.request import Request as UrlRequest, urlopen

from fastapi import (
    APIRouter,
    Body,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse

from . import bell_rupor_worker
from .app_try_demo import demo_exit_redirect_url as _demo_exit_redirect_url
from .capabilities import CAP_CLOUD_SYNC, get_capabilities_public
from .gs_admin_http import admin_msg, admin_ui_lang
from .gs_admin_upload import (
    read_upload_capped as _read_upload_capped,
    reject_if_saas_upload as _reject_if_saas_upload,
    saas_check_json_payload_size as _saas_check_json_payload_size,
    saas_check_quota_for_path as _saas_check_quota_for_path,
    saas_enforce_user_data_quota_after_multi_write as _saas_enforce_user_data_quota_after_multi_write,
)
from .gs_app_config import (
    _sanitize_emergency_templates_list,
    apply_emergency_template_to_screen,
    load_config,
    sanitize_audio_stream,
    sanitize_config,
)
from .gs_auth import is_demo_session_for_admin_ui, require_auth
from .gs_capability_http import require_capability
from .gs_change_log import load_change_log
from .gs_checkin import (
    confirm_all_unconfirmed_in_range,
    enrich_checkin_event_for_client,
    fetch_checkin_event_by_id,
    get_checkin_events_status_for_device,
    journal_to_csv_bytes_filtered,
    range_bounds_utc,
    sanitize_places_list,
    set_checkin_event_confirmed,
)
from .gs_checkin_screen import (
    checkin_board_payload as _checkin_board_payload,
    checkin_events_screen_slug_for_monitor as _checkin_events_screen_slug_for_monitor,
    checkin_period_normalize as _checkin_period_normalize,
    find_monitor_widget as _find_monitor_widget,
    screen_config_by_slug as _screen_config_by_slug,
)
from .gs_class_key import normalize_class
from .gs_data_loaders import (
    load_announcements,
    load_full_schedule,
    load_holidays,
    load_marquee_items,
    load_overrides,
    load_rss_news,
    load_schedule,
    load_schedule_sample,
)
from .gs_data_revision import compute_data_revision
from .gs_deploy import deployment_mode
from .gs_ensure_dirs import ensure_dirs
from .gs_excel_import import (
    parse_announcements_excel,
    parse_excel,
    parse_holidays_excel,
    parse_marquee_excel,
    parse_weekly_schedule_excel,
)
from .gs_import_bundle import (
    export_bundle_bytes,
    export_weekly_schedule_bundle_bytes,
    import_bundle_bytes,
    import_weekly_schedule_bundle_bytes,
)
from .gs_import_sample_xlsx import import_excel_sample_bytes
from .gs_import_state import load_import_state
from .gs_jsonio import write_json
from .gs_paths import (
    ANNOUNCEMENTS_PATH,
    APP_VERSION,
    AUTO_ANNOUNCEMENTS_IMPORT_PATH,
    AUTO_FULL_SCHEDULE_IMPORT_PATH,
    AUTO_HOLIDAYS_IMPORT_PATH,
    AUTO_MARQUEE_IMPORT_PATH,
    AUTO_SCHEDULE_IMPORT_PATH,
    AUTO_SCHEDULE_SAMPLE_IMPORT_PATH,
    BELL_SCHEDULES_PATH,
    BELL_SOUNDS_DIR,
    BREAK_MUSIC_DIR,
    CONFIG_PATH,
    FULL_SCHEDULE_PATH,
    FULL_SCHEDULE_SAMPLE_XLSX,
    HOLIDAYS_PATH,
    MARQUEE_PATH,
    OVERRIDES_PATH,
    SCHEDULE_PATH,
    SCHEDULE_SAMPLE_PATH,
    SCHOOL_NEWS_PATH,
    UPLOADS_DIR,
    WIDGET_IMAGES_SUBDIR,
)
from .gs_schedule_bells import (
    _norm_hex_color,
    as_lesson_number,
    audio_trigger_sec_window,
    build_bell_audio_payload,
    build_schedule_payload,
    calendar_today_for_config,
    distinct_schedule_class_names_from_sources,
    display_settings_dict,
    first_bell_sound_path,
    load_bell_schedules,
    schedule_date_iso,
)
from .gs_screen_push import (
    maybe_push_screen_content_if_data_revision_changed as _maybe_push_screen_content_if_data_revision_changed,
    notify_push_checkin_journal_bulk_confirm as _notify_push_checkin_journal_bulk_confirm,
    notify_push_checkin_journal_confirmed as _notify_push_checkin_journal_confirmed,
    notify_push_emergency_change as _notify_push_emergency_change,
)
from .gs_school_news import (
    extract_school_news_local_upload_urls as _extract_school_news_local_upload_urls,
    load_school_news,
    safe_unlink_school_news_upload_url as _safe_unlink_upload_url,
    sanitize_school_news_item,
    save_school_news_image_bytes as _save_school_news_image_bytes,
)
from .gs_screen_watch import reset_stats_counters, screen_watch_snapshot
from .gs_tv_screen_api import (
    normalize_screen_slug_for_api as _normalize_screen_slug_for_api,
    screen_api_tenant_slug as _screen_api_tenant_slug,
)
from .gs_uploads_bg import (
    list_background_images_from_uploads,
    list_background_subdirs_from_uploads,
    safe_rel_uploads_subdir,
)
from .gs_weekly_template import ensure_weekly_schedule_template_file
from .gs_saas_limits import (
    max_schedule_xlsx_bytes,
    max_school_news_image_bytes,
    max_weekly_zip_bytes,
    max_widget_image_upload_bytes,
    saas_mode,
)
from .optional_imports import cloud_sync_module
from .widget_registry import loaded_widget_types, widget_registry_public
from .widget_screen_meta import enrich_screen_widgets_meta

_log = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])


def register_admin_routes(app) -> None:
    app.include_router(router)


def _checkin_tenant_from_request(request: Request) -> str:
    return _screen_api_tenant_slug(request)


@router.get("/api/admin/config")
async def get_admin_config(request: Request) -> Response:
    require_auth(request)
    cfg = load_config()
    # Метаданные, которые нужны UI, но не должны сохраняться в config.json.
    cfg["_meta"] = {
        "saas_mode": saas_mode(),
        "deployment_mode": deployment_mode(),
        "app_version": APP_VERSION,
        "demo_session": is_demo_session_for_admin_ui(request),
        "demo_exit_url": _demo_exit_redirect_url,
        "capabilities": get_capabilities_public(),
        "widget_registry": widget_registry_public(),
    }
    return JSONResponse(cfg, headers={"Cache-Control": "no-store"})


@router.post("/api/admin/rss-news/refresh")
def post_admin_rss_news_refresh(request: Request) -> dict[str, Any]:
    require_auth(request)
    cfg = load_config()
    items = load_rss_news(cfg, force_refresh=True)
    return {"items": items, "count": len(items)}


@router.post("/api/admin/config")
async def save_admin_config(request: Request) -> dict[str, str]:
    require_auth(request)
    payload = await request.json()
    # Важно: аварийный режим включается/выключается через emergency_active_template_id.
    # Чтобы пушить только на смене режима, сравниваем старое и новое значения.
    prev_cfg = {}
    try:
        prev_cfg = load_config()
    except Exception:
        prev_cfg = {}
    prev_tid = str((prev_cfg or {}).get("emergency_active_template_id") or "").strip()
    new_cfg = sanitize_config(payload)
    new_tid = str((new_cfg or {}).get("emergency_active_template_id") or "").strip()
    write_json(CONFIG_PATH, new_cfg)
    try:
        if prev_tid != new_tid:
            _notify_push_emergency_change(
                tenant_id=_screen_api_tenant_slug(request), cfg=new_cfg, prev_tid=prev_tid, new_tid=new_tid
            )
    except Exception:
        pass
    _maybe_push_screen_content_if_data_revision_changed(request)
    return {"status": "ok"}


@router.post("/api/admin/sync-now")
async def post_admin_sync_now(request: Request) -> dict[str, Any]:
    require_auth(request)
    if deployment_mode() == "saas":
        raise HTTPException(status_code=404, detail="Not found.")
    require_capability(CAP_CLOUD_SYNC)
    sync_mod = cloud_sync_module()
    if sync_mod is None:
        raise HTTPException(status_code=503, detail="Cloud sync module is not available.")
    return await sync_mod.run_cloud_sync_once()


@router.get("/api/admin/background-gallery")
def admin_background_gallery(request: Request, folder: str = "") -> dict[str, Any]:
    require_auth(request)
    f = safe_rel_uploads_subdir(folder)
    return {
        "folder": f,
        "folders": list_background_subdirs_from_uploads(),
        "images": list_background_images_from_uploads(f),
    }


@router.post("/api/admin/screen-bg-next")
async def admin_screen_bg_next(request: Request) -> dict[str, Any]:
    require_auth(request)
    body = await request.json()
    sid = str(body.get("screen_id") or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="Нужен screen_id.")
    config = load_config()
    screen = next((s for s in config.get("screens") or [] if str(s.get("id")) == sid), None)
    if not screen:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    # сбрасываем «фиксированный» фон, если был
    screen["background_force_image"] = ""
    screen["background_rotate_enabled"] = True
    try:
        cur = int(screen.get("background_rotate_cursor", 0))
    except (TypeError, ValueError):
        cur = 0
    screen["background_rotate_cursor"] = max(0, cur) + 1
    screen["background_rotate_epoch"] = int(time.time())
    write_json(CONFIG_PATH, sanitize_config(config))
    _maybe_push_screen_content_if_data_revision_changed(request)
    return {"status": "ok", "screen_id": sid}


async def _handle_pc_audio_test_play(request: Request) -> dict[str, str]:
    """Тест колонок с ПК: первый файл из uploads/bells или явный filename в JSON."""
    require_auth(request)
    body: dict[str, Any] = {}
    raw = await request.body()
    if raw.strip():
        try:
            parsed = json.loads(raw.decode("utf-8-sig"))
            if isinstance(parsed, dict):
                body = parsed
        except (json.JSONDecodeError, UnicodeError, TypeError):
            body = {}
    use_first = request.query_params.get("use_first") in ("1", "true", "yes")
    raw_fn = body.get("filename")
    if raw_fn in (None, "", False):
        raw_fn = body.get("file")
    if use_first or raw_fn in (None, "", False):
        fn = ""
    else:
        fn = str(raw_fn).strip()
    if fn:
        safe = Path(fn).name
        path = BELL_SOUNDS_DIR / safe
        if not path.is_file():
            path = UPLOADS_DIR / safe
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Файл не найден в каталогах uploads/bells или uploads.")
    else:
        first = first_bell_sound_path()
        if not first:
            raise HTTPException(
                status_code=400,
                detail="В uploads/bells нет файлов. Загрузите звук в разделе «Сигналы».",
            )
        path = first
        safe = path.name
    audio = dict(sanitize_audio_stream(load_config().get("audio_stream")))
    vol = body.get("volume_percent")
    if vol is not None:
        try:
            audio["volume_percent"] = max(0, min(100, int(vol)))
        except (TypeError, ValueError):
            pass
    ok, err = bell_rupor_worker.stream_file_to_rupor(path, audio)
    if not ok:
        raise HTTPException(status_code=400, detail=err or "Не удалось запустить отправку.")
    return {
        "status": "ok",
        "detail": f"Файл «{safe}»: воспроизведение на ПК в фоне (если ffmpeg с muxer wasapi — через него; иначе ffplay в той же папке). Ниже — stderr.",
    }


@router.post("/api/admin/audio-stream-test-send")
async def post_audio_stream_test_send(request: Request) -> dict[str, str]:
    """Совместимость со старыми клиентами; предпочтительно /api/admin/pc-audio-test-play."""
    return await _handle_pc_audio_test_play(request)


@router.post("/api/admin/pc-audio-test-play")
async def post_pc_audio_test_play(request: Request) -> dict[str, str]:
    """Тест Рупор из сайдбара (есть только в актуальном сервере — иначе в браузере будет 404)."""
    return await _handle_pc_audio_test_play(request)


@router.get("/api/admin/audio-stream-last-send")
def get_audio_stream_last_send(request: Request) -> dict[str, Any]:
    """Последний сеанс ffplay (команда и stderr)."""
    require_auth(request)
    return {"last": bell_rupor_worker.get_last_ffmpeg_send()}


@router.get("/api/admin/audio-stream-status")
def get_audio_stream_status(request: Request) -> dict[str, Any]:
    """Процесс ffplay и последний результат — для панели админки."""
    require_auth(request)
    return bell_rupor_worker.get_ffmpeg_status()


@router.post("/api/admin/audio-stream-stop")
def post_audio_stream_stop(request: Request) -> dict[str, Any]:
    """Остановить текущее воспроизведение (ffplay)."""
    require_auth(request)
    return bell_rupor_worker.stop_current_stream()


@router.get("/api/admin/break-music-files")
def list_break_music_files(request: Request) -> dict[str, Any]:
    """Файлы в data/break_music + порядок воспроизведения и громкости для админки."""
    require_auth(request)
    ensure_dirs()
    files = []
    if BREAK_MUSIC_DIR.exists():
        for p in sorted(BREAK_MUSIC_DIR.iterdir()):
            if p.is_file():
                files.append({"filename": p.name})
    from . import local_audio_worker

    return {
        "files": files,
        "directory": str(BREAK_MUSIC_DIR),
        "playback": local_audio_worker.get_break_music_playback_info(),
    }


@router.post("/api/admin/break-music-preview")
async def post_break_music_preview(request: Request) -> dict[str, str]:
    """Прослушать файл из data/break_music на ПК с громкостью «перемена» (как в оркестрации)."""
    require_auth(request)
    body: dict[str, Any] = {}
    raw = await request.body()
    if raw.strip():
        try:
            parsed = json.loads(raw.decode("utf-8-sig"))
            if isinstance(parsed, dict):
                body = parsed
        except (json.JSONDecodeError, UnicodeError, TypeError):
            body = {}
    fn = Path(str(body.get("filename") or "")).name
    if not fn:
        raise HTTPException(status_code=400, detail="Укажите filename (имя файла в data/break_music).")
    path = BREAK_MUSIC_DIR / fn
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден в data/break_music.")
    from . import local_audio_worker

    audio = sanitize_audio_stream(load_config().get("audio_stream"))
    vol = body.get("volume_percent")
    if vol is not None:
        try:
            audio = {**audio, "break_music_volume_percent": max(0, min(100, int(vol)))}
        except (TypeError, ValueError):
            pass
    local_audio_worker.stop_playback_hard()
    time.sleep(0.08)
    ok, err = local_audio_worker.play_break_music_preview(path, audio)
    if not ok:
        raise HTTPException(status_code=400, detail=err or "Не удалось воспроизвести.")
    v = int(audio.get("break_music_volume_percent") or 40)
    return {
        "status": "ok",
        "detail": f"«{fn}» — громкость перемены {v}% (ffmpeg af volume={v/100.0:.2f}).",
    }


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


@router.post("/api/admin/school-news/cover-upload")
async def admin_school_news_cover_upload(
    request: Request,
    file: UploadFile = File(...),
    news_id: str = Form(default=""),
) -> dict[str, Any]:
    require_auth(request)
    nid = str(news_id or "").strip()[:64] or secrets.token_hex(6)
    raw = await file.read()
    url = _save_school_news_image_bytes(
        nid,
        raw,
        content_type=file.content_type,
        source_name=file.filename or "",
    )
    return {"status": "ok", "news_id": nid, "url": url}


@router.post("/api/admin/school-news/cover-fetch")
async def admin_school_news_cover_fetch(
    request: Request,
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    require_auth(request)
    url_raw = str(payload.get("url") or "").strip()
    if not re.fullmatch(r"(?i)https?://.{6,500}", url_raw):
        raise HTTPException(status_code=400, detail="Неверный URL (нужен http/https).")
    nid = str(payload.get("news_id") or "").strip()[:64] or secrets.token_hex(6)
    try:
        req = UrlRequest(url_raw, headers={"User-Agent": "GuardSchool/1.0"})
        with urlopen(req, timeout=8) as resp:
            ct = str(resp.headers.get("Content-Type") or "").strip()
            data = resp.read(max_school_news_image_bytes() + 1)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Не удалось загрузить картинку: {e}")
    url = _save_school_news_image_bytes(nid, data, content_type=ct, source_name=url_raw)
    return {"status": "ok", "news_id": nid, "url": url}


@router.post("/api/admin/school-news/gallery-upload")
async def admin_school_news_gallery_upload(
    request: Request,
    file: UploadFile = File(...),
    news_id: str = Form(default=""),
) -> dict[str, Any]:
    """То же хранение, что обложка; URL подставляется в нужный слот галереи на клиенте."""
    require_auth(request)
    nid = str(news_id or "").strip()[:64] or secrets.token_hex(6)
    raw = await file.read()
    url = _save_school_news_image_bytes(
        nid,
        raw,
        content_type=file.content_type,
        source_name=file.filename or "",
    )
    return {"status": "ok", "news_id": nid, "url": url}


@router.post("/api/admin/school-news/gallery-fetch")
async def admin_school_news_gallery_fetch(
    request: Request,
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    require_auth(request)
    url_raw = str(payload.get("url") or "").strip()
    if not re.fullmatch(r"(?i)https?://.{6,500}", url_raw):
        raise HTTPException(status_code=400, detail="Неверный URL (нужен http/https).")
    nid = str(payload.get("news_id") or "").strip()[:64] or secrets.token_hex(6)
    try:
        req = UrlRequest(url_raw, headers={"User-Agent": "GuardSchool/1.0"})
        with urlopen(req, timeout=8) as resp:
            ct = str(resp.headers.get("Content-Type") or "").strip()
            data = resp.read(max_school_news_image_bytes() + 1)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Не удалось загрузить картинку: {e}")
    url = _save_school_news_image_bytes(nid, data, content_type=ct, source_name=url_raw)
    return {"status": "ok", "news_id": nid, "url": url}


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


@router.get("/api/admin/schedule")
async def get_schedule_snapshot(request: Request) -> dict[str, Any]:
    require_auth(request)
    cfg = load_config()
    schedule_rows = load_schedule()
    full_rows = load_full_schedule()
    sample_rows = load_schedule_sample()
    return {
        "schedule": schedule_rows,
        "holidays": load_holidays(),
        "announcements": load_announcements(),
        "school_news": load_school_news()[:20],
        "rss_news": load_rss_news(cfg),
        "marquee": load_marquee_items(),
        "overrides": load_overrides(),
        "bells": load_bell_schedules(),
        "history": load_change_log(),
        "full_schedule_rows": len(full_rows),
        "schedule_sample_rows": len(sample_rows),
        "schedule_class_options": distinct_schedule_class_names_from_sources(
            schedule_rows, full_rows, sample_rows
        ),
        "imports": {
            "schedule_path": str(AUTO_SCHEDULE_IMPORT_PATH),
            "full_schedule_path": str(AUTO_FULL_SCHEDULE_IMPORT_PATH),
            "schedule_sample_path": str(AUTO_SCHEDULE_SAMPLE_IMPORT_PATH),
            "holidays_path": str(AUTO_HOLIDAYS_IMPORT_PATH),
            "announcements_path": str(AUTO_ANNOUNCEMENTS_IMPORT_PATH),
            "marquee_path": str(AUTO_MARQUEE_IMPORT_PATH),
            "state": load_import_state(),
        },
        "app_version": APP_VERSION,
    }


@router.get("/api/admin/history")
def get_change_history(request: Request) -> dict[str, Any]:
    require_auth(request)
    return {"history": load_change_log(), "app_version": APP_VERSION}


@router.get("/api/admin/school-news")
def get_admin_school_news(request: Request) -> dict[str, Any]:
    require_auth(request)
    return {"items": load_school_news()}


@router.post("/api/admin/school-news")
async def save_admin_school_news(request: Request, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    require_auth(request)
    rows = load_school_news()
    nid = str(payload.get("id") or "").strip()
    item = sanitize_school_news_item(payload, fallback_id=nid or secrets.token_hex(6))
    replaced = False
    if nid:
        for i, row in enumerate(rows):
            if str(row.get("id") or "") == nid:
                rows[i] = item
                replaced = True
                break
    if not replaced:
        rows.append(item)
    rows.sort(key=lambda x: (str(x.get("created_at") or ""), str(x.get("id") or "")), reverse=True)
    write_json(SCHOOL_NEWS_PATH, rows)
    return {"status": "ok", "item": item, "items": rows}


@router.delete("/api/admin/school-news/{news_id}")
def delete_admin_school_news(request: Request, news_id: str) -> dict[str, Any]:
    require_auth(request)
    nid = str(news_id or "").strip()
    if not nid:
        raise HTTPException(status_code=400, detail="Не указан id новости.")
    existing = load_school_news()
    deleted = next((x for x in existing if str(x.get("id") or "") == nid), None)
    rows = [item for item in existing if str(item.get("id") or "") != nid]
    write_json(SCHOOL_NEWS_PATH, rows)
    try:
        if deleted:
            _safe_unlink_upload_url(str(deleted.get("cover_image") or ""))
            for u in deleted.get("gallery_images") or []:
                _safe_unlink_upload_url(str(u))
            for u in _extract_school_news_local_upload_urls(str(deleted.get("content") or "")):
                _safe_unlink_upload_url(u)
    except Exception:
        pass
    return {"status": "ok", "items": rows}


@router.post("/api/admin/overrides")
async def save_overrides(request: Request) -> dict[str, str]:
    require_auth(request)
    raw = await request.json()
    payload: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            date_s = str(item.get("date") or "").strip()
            class_name = str(item.get("class_name") or "").strip()
            class_key = normalize_class(item.get("class_key") or class_name)
            lesson_index = as_lesson_number(item.get("lesson_index"))
            subject = str(item.get("subject") or "").strip()
            date_norm = schedule_date_iso(date_s) or date_s
            if not (date_norm and class_name and class_key and lesson_index and subject):
                continue
            out = {
                "date": date_norm,
                "class_name": class_name,
                "class_key": class_key,
                "lesson_index": lesson_index,
                "subject": subject,
            }
            c = _norm_hex_color(item.get("color"))
            if c:
                out["color"] = c
            payload.append(out)
    _saas_check_quota_for_path(request, OVERRIDES_PATH, payload)
    write_json(OVERRIDES_PATH, payload)
    _maybe_push_screen_content_if_data_revision_changed(request)
    return {"status": "ok"}


@router.post("/api/admin/bells")
async def save_bells(request: Request) -> dict[str, str]:
    require_auth(request)
    payload = await request.json()
    _saas_check_quota_for_path(request, BELL_SCHEDULES_PATH, payload)
    write_json(BELL_SCHEDULES_PATH, payload)
    _maybe_push_screen_content_if_data_revision_changed(request)
    return {"status": "ok"}


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
                "Нужен ZIP с full_schedule.json и/или schedule_sample.json.",
                "Expected a ZIP with full_schedule.json and/or schedule_sample.json.",
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


@router.post("/api/admin/preview-payload")
def post_preview_payload(request: Request, payload: dict[str, Any] = Body(...)) -> JSONResponse:
    require_auth(request)
    screen = payload.get("screen")
    if not isinstance(screen, dict):
        raise HTTPException(status_code=400, detail="Нужен объект screen.")
    screen.setdefault("selected_classes", [])
    screen.setdefault("bell_schedule_template", "standard")
    screen.setdefault("weekday_bell_templates", {})
    screen.setdefault("widgets", [])
    cfg = load_config()
    if isinstance(payload.get("emergency_templates"), list):
        cfg = dict(cfg)
        cfg["emergency_templates"] = _sanitize_emergency_templates_list(payload.get("emergency_templates"))
    if payload.get("emergency_active_template_id") is not None:
        cfg = dict(cfg)
        cfg["emergency_active_template_id"] = str(payload.get("emergency_active_template_id") or "").strip()[:64]
    screen_eff = enrich_screen_widgets_meta(apply_emergency_template_to_screen(dict(screen), cfg))
    today = calendar_today_for_config(cfg)
    audio = sanitize_audio_stream(cfg.get("audio_stream"))
    from . import local_audio_worker

    body = {
        "schedule": build_schedule_payload(screen, today, cfg),
        "holidays": load_holidays(),
        "announcements": load_announcements(),
        "school_news": load_school_news()[:20],
        "marquee": load_marquee_items(),
        "rss_news": load_rss_news(cfg),
        "background_gallery": list_background_images_from_uploads(screen.get("background_rotate_folder")),
        "bell_audio": build_bell_audio_payload(
            screen,
            today,
            trigger_sec_window=audio_trigger_sec_window(audio),
        ),
        "pc_audio_preview": local_audio_worker.describe_pc_audio_preview(
            screen,
            cfg.get("audio_stream"),
        ),
        "display": display_settings_dict(cfg),
        "revision": compute_data_revision(),
        "app_version": APP_VERSION,
        "screen": screen_eff,
        "widget_types_available": loaded_widget_types(),
    }
    return JSONResponse(content=body)

@router.get("/api/admin/checkin/board")
def api_admin_checkin_board(
    request: Request,
    screen_slug: str = Query(...),
    monitor_widget_id: str = Query(...),
    period: str = Query("day", alias="range"),
) -> dict[str, Any]:
    require_auth(request)
    slug_key = _normalize_screen_slug_for_api(screen_slug)
    if not slug_key:
        raise HTTPException(status_code=400, detail="Укажите screen_slug.")
    cfg = load_config()
    return _checkin_board_payload(cfg, _screen_api_tenant_slug(request), slug_key, monitor_widget_id, period)


@router.get("/api/admin/checkin/export.csv")
def api_admin_checkin_export_csv(
    request: Request,
    screen_slug: str = Query(...),
    monitor_widget_id: str = Query(...),
    period: str = Query("day", alias="range"),
) -> Response:
    require_auth(request)
    slug_key = _normalize_screen_slug_for_api(screen_slug)
    if not slug_key:
        raise HTTPException(status_code=400, detail="Укажите screen_slug.")
    cfg = load_config()
    screen = _screen_config_by_slug(cfg, slug_key)
    if not screen:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    mw = _find_monitor_widget(screen, monitor_widget_id)
    if not mw:
        raise HTTPException(status_code=404, detail="Виджет сводки не найден.")
    places = sanitize_places_list((mw.get("settings") or {}).get("places"))
    place_titles = {p["id"]: p["title"] for p in places}
    pids = {p["id"] for p in places}
    tenant_id = _screen_api_tenant_slug(request)
    period_n = _checkin_period_normalize(period)
    event_slug = _checkin_events_screen_slug_for_monitor(cfg, mw, slug_key)
    raw = journal_to_csv_bytes_filtered(
        tenant_id, cfg, period_n, pids if pids else None, event_slug, place_titles
    )
    rl = range_bounds_utc(cfg, period_n)[2]
    return Response(
        content=raw,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="checkin_{slug_key}_{monitor_widget_id}_{rl}.csv"'
        },
    )


@router.post("/api/admin/checkin/confirm")
async def api_admin_checkin_confirm(request: Request) -> dict[str, Any]:
    require_auth(request)
    body = await request.json()
    screen_slug_raw = str(body.get("screen_slug") or "").strip()
    slug_key = _normalize_screen_slug_for_api(screen_slug_raw)
    if not slug_key:
        raise HTTPException(status_code=400, detail="Укажите screen_slug.")
    monitor_widget_id = str(body.get("monitor_widget_id") or "").strip()
    try:
        event_id = int(body.get("event_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Укажите event_id.") from None
    if not monitor_widget_id:
        raise HTTPException(status_code=400, detail="Укажите monitor_widget_id.")
    cfg = load_config()
    screen = _screen_config_by_slug(cfg, slug_key)
    if not screen:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    mw = _find_monitor_widget(screen, monitor_widget_id)
    if not mw:
        raise HTTPException(status_code=404, detail="Виджет сводки не найден.")
    places = sanitize_places_list((mw.get("settings") or {}).get("places"))
    allowed = {p["id"] for p in places}
    tenant_id = _checkin_tenant_from_request(request)
    event_slug = _checkin_events_screen_slug_for_monitor(cfg, mw, slug_key)
    ts, newly = set_checkin_event_confirmed(
        tenant_id, event_id, screen_slug=event_slug, allowed_place_ids=allowed
    )
    if ts is None:
        raise HTTPException(status_code=404, detail="Событие не найдено или недоступно.")
    if newly:
        try:
            erow = fetch_checkin_event_by_id(tenant_id, event_id)
            if erow:
                _notify_push_checkin_journal_confirmed(
                    cfg=cfg,
                    tenant_id=tenant_id,
                    mw=mw,
                    events_screen_slug=event_slug,
                    row=erow,
                )
        except Exception:
            pass
    return {"status": "ok", "confirmed_at": ts}


@router.post("/api/admin/checkin/confirm-all")
async def api_admin_checkin_confirm_all(request: Request) -> dict[str, Any]:
    require_auth(request)
    body = await request.json()
    screen_slug_raw = str(body.get("screen_slug") or "").strip()
    slug_key = _normalize_screen_slug_for_api(screen_slug_raw)
    if not slug_key:
        raise HTTPException(status_code=400, detail="Укажите screen_slug.")
    monitor_widget_id = str(body.get("monitor_widget_id") or "").strip()
    period = str(body.get("range") or body.get("period") or "day").strip()
    if not monitor_widget_id:
        raise HTTPException(status_code=400, detail="Укажите monitor_widget_id.")
    cfg = load_config()
    screen = _screen_config_by_slug(cfg, slug_key)
    if not screen:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    mw = _find_monitor_widget(screen, monitor_widget_id)
    if not mw:
        raise HTTPException(status_code=404, detail="Виджет сводки не найден.")
    places = sanitize_places_list((mw.get("settings") or {}).get("places"))
    pids = {p["id"] for p in places}
    period_n = _checkin_period_normalize(period)
    tenant_id = _checkin_tenant_from_request(request)
    event_slug = _checkin_events_screen_slug_for_monitor(cfg, mw, slug_key)
    n = confirm_all_unconfirmed_in_range(tenant_id, cfg, event_slug, pids, period_n)
    if n > 0:
        try:
            _notify_push_checkin_journal_bulk_confirm(
                cfg=cfg, tenant_id=tenant_id, events_screen_slug=event_slug, count=n
            )
        except Exception:
            pass
    return {"status": "ok", "confirmed_count": n}


@router.get("/api/admin/checkin/events-status")
def api_admin_checkin_events_status(
    request: Request,
    screen_slug: str = Query(...),
    submit_widget_id: str = Query(...),
    device_hash: str = Query(...),
    ids: str = Query(""),
) -> dict[str, Any]:
    require_auth(request)
    slug_key = _normalize_screen_slug_for_api(screen_slug)
    if not slug_key:
        raise HTTPException(status_code=400, detail="Укажите screen_slug.")
    sw = str(submit_widget_id or "").strip()
    if not sw:
        raise HTTPException(status_code=400, detail="Укажите submit_widget_id.")
    id_parts = [x.strip() for x in (ids or "").split(",") if x.strip()]
    id_list: list[int] = []
    for x in id_parts:
        try:
            id_list.append(int(x))
        except ValueError:
            continue
    tenant_id = _checkin_tenant_from_request(request)
    rows = get_checkin_events_status_for_device(tenant_id, slug_key, sw, device_hash, id_list)
    cfg = load_config()
    enriched = []
    for r in rows:
        e = dict(r)
        ca = e.get("confirmed_at") or ""
        ed = enrich_checkin_event_for_client(
            cfg,
            {"created_at": "", "confirmed_at": ca},
        )
        e["confirmed_date"] = ed.get("confirmed_date") or ""
        e["confirmed_time"] = ed.get("confirmed_time") or ""
        enriched.append(e)
    return {"status": "ok", "items": enriched}


@router.get("/api/admin/screen-watch")
def get_admin_screen_watch(request: Request) -> dict[str, Any]:
    require_auth(request)
    config = load_config()
    return screen_watch_snapshot(list(config.get("screens") or []))


@router.post("/api/admin/screen-watch/reset-counters")
def admin_reset_screen_watch_counters(request: Request) -> dict[str, Any]:
    require_auth(request)
    return {"status": "ok", "visits": reset_stats_counters()}

