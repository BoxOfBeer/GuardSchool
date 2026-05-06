from __future__ import annotations

from contextlib import asynccontextmanager

import calendar
import copy
import hashlib
import hmac
import html
import io
import ipaddress
import json
import logging
import os
import re
import secrets
import shutil
import time
import unicodedata
import base64
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9 (например shared-хостинг 3.8)
    from backports.zoneinfo import ZoneInfo
from urllib.parse import quote, urlparse
from urllib.request import Request as UrlRequest, urlopen

from fastapi import Body, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from .gs_admin_http import admin_msg, admin_ui_lang, session_cookie_secure
from .gs_class_key import normalize_class
from .gs_auth import (
    create_demo_session_token,
    create_session_token,
    demo_v3_binding_from_token,
    hash_password,
    is_authenticated,
    is_demo_session_for_admin_ui,
    load_auth,
    obliterate_session_cookies,
    password_is_valid,
    require_auth,
    verify_demo_session_token,
)
from .cloud_store import hydrate_data_dir_from_database, is_cloud_database_enabled, read_revision_from_database
from .gs_deploy import deployment_mode
from .gs_saas_bootstrap import ensure_saas_bootstrap_admin
from .gs_saas_limits import (
    json_utf8_size,
    max_schedule_json_bytes,
    max_schedule_xlsx_bytes,
    max_user_data_bytes,
    max_weekly_zip_bytes,
    max_widget_image_upload_bytes,
    saas_mode,
)
from .gs_change_log import load_change_log
from .gs_data_revision import compute_data_revision
from .gs_ensure_dirs import ensure_dirs
from .gs_excel_import import (
    maybe_import_announcements_from_folder,
    maybe_import_full_schedule_from_folder,
    maybe_import_holidays_from_folder,
    maybe_import_marquee_from_folder,
    maybe_import_schedule_from_folder,
    maybe_import_schedule_sample_from_folder,
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
from .gs_import_state import load_import_state
from .gs_jsonio import read_json, write_json
from .gs_rss_news import load_rss_news as load_rss_news_feed, sanitize_rss_refresh_minutes, sanitize_rss_sources
from .gs_uploads_bg import (
    list_background_images_from_uploads,
    list_background_subdirs_from_uploads,
    safe_rel_uploads_subdir,
)
from .tenant_ctx import set_tenant_slug
from .gs_paths import (
    ANNOUNCEMENTS_PATH,
    APP_VERSION,
    AUTH_PATH,
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
    DATA_DIR,
    FULL_SCHEDULE_PATH,
    FULL_SCHEDULE_SAMPLE_XLSX,
    HOLIDAYS_PATH,
    IMPORT_DIR,
    MARQUEE_PATH,
    OVERRIDES_PATH,
    SCHOOL_NEWS_PATH,
    SCHEDULE_PATH,
    SCHEDULE_SAMPLE_PATH,
    SAAS_TENANT_COOKIE,
    SESSION_COOKIE,
    STATIC_DIR,
    SYNC_STATE_PATH,
    UPLOADS_DIR,
    WIDGET_IMAGES_SUBDIR,
    resolve_brand_logo_path,
)
from .gs_import_sample_xlsx import import_excel_sample_bytes
from .gs_weekly_template import ensure_weekly_schedule_template_file
from .gs_screen_watch import record_screen_poll, reset_stats_counters, screen_watch_snapshot
from .gs_feedback import (
    block_feedback_hash,
    can_send_feedback,
    create_feedback_message,
    ensure_feedback_tables,
    hide_feedback,
    list_feedback_messages,
    mark_feedback_read,
)
from .gs_checkin import (
    build_summary_for_places,
    build_summary_for_school_day,
    confirm_all_unconfirmed_in_range,
    enrich_checkin_event_for_client,
    ensure_checkin_tables,
    fetch_checkin_event_by_id,
    get_checkin_events_status_for_device,
    insert_event as insert_checkin_event,
    journal_to_csv_bytes,
    journal_to_csv_bytes_filtered,
    list_journal_filtered,
    list_journal_for_school_day,
    range_bounds_utc,
    sanitize_checkin_block,
    sanitize_places_list,
    school_calendar_date,
    set_checkin_event_confirmed,
)
from .gs_push import (
    delete_subscription as delete_push_subscription,
    list_subscriptions as list_push_subscriptions,
    rate_limit_decide as push_rate_limit_decide,
    upsert_subscription as upsert_push_subscription,
    vapid_application_server_key,
    vapid_private_key,
    vapid_public_key,
    vapid_subject,
)
from .gs_portal_cms import load_portal_cms_merged, sanitize_portal_cms_payload, write_portal_cms
from .saas_db import cleanup_expired_demo_sessions, ensure_public_schema, saas_db_enabled
from .saas_db import (
    connect_public,
    ensure_tenant_schema,
    license_key_hash,
    random_id,
    schema_name_for_slug,
    tv_code_hash,
    tv_device_token_hash,
    tv_pin_hash,
    utcnow,
)

GRID_COLS = 32
GRID_ROWS = 26
SINGLETON_WIDGET_IDS = {
    "date": "date",
    "time": "time",
    "text": "text",
    "bell_status": "bell_status",
    "bell_countdown": "bell_countdown",
    "schedule": "schedule",
    "holidays": "holidays",
    "announcements": "announcements",
    "school_news": "school_news",
    "rss_news": "rss_news",
    "rss_feed": "rss_news",
    "external_news": "rss_news",
    "marquee": "marquee",
    "emergency": "emergency",
    "image": "image",
}

# Типы виджетов, которые можно скрыть из списка в админке (карточки «Виджеты» и селектор добавления).
# Плюс: типы не из этого множества не попадают в палитру программы, но если виджет есть на экране — он учитывается на ТВ.
ADMIN_PALETTE_WIDGET_TYPES = frozenset(
    {
        "date",
        "time",
        "text",
        "bell_status",
        "bell_countdown",
        "schedule",
        "carousel",
        "holidays",
        "announcements",
        "school_news",
        "rss_news",
        "rss_feed",
        "external_news",
        "marquee",
        "emergency",
        "image",
        "checkin_submit",
        "checkin_monitor",
    }
)

# Порядок чекбоксов «Виджеты (по типам)» на ТВ (панель устройства); в панель не входит только emergency.
_DEVICE_WIDGET_TAB_ORDER: tuple[str, ...] = (
    "date",
    "time",
    "text",
    "bell_status",
    "bell_countdown",
    "schedule",
    "carousel",
    "holidays",
    "announcements",
    "school_news",
    "rss_news",
    "rss_feed",
    "external_news",
    "marquee",
    "image",
    "checkin_submit",
    "checkin_monitor",
)

# Не показывать в панели «Виджеты (по типам)»: только аварийный (остальные типы — по факту включённых виджетов на экране).
_TV_DEVICE_PANEL_EXCLUDED_TYPES = frozenset({"emergency"})


def device_widget_types_for_tv_device_panel(_config: dict[str, Any], widgets: list[Any]) -> list[str]:
    """
    Ключи типов для фильтра gs_mw на ТВ: есть включённый виджет этого типа на экране.
    Скрытые в программе типы (admin_palette_hidden_types) тоже показываем, если виджет на экране включён.
    Аварийный (emergency) в панель не включается.
    """
    on_screen_enabled: set[str] = set()
    if isinstance(widgets, list):
        for w in widgets:
            if not isinstance(w, dict):
                continue
            if w.get("enabled") is False:
                continue
            typ = str(w.get("type") or "").strip()
            if typ and typ != "emergency":
                on_screen_enabled.add(typ)
    out: list[str] = []
    seen: set[str] = set()
    for typ in _DEVICE_WIDGET_TAB_ORDER:
        if typ in seen or typ in _TV_DEVICE_PANEL_EXCLUDED_TYPES:
            continue
        if typ not in on_screen_enabled:
            continue
        if typ not in ADMIN_PALETTE_WIDGET_TYPES:
            continue
        out.append(typ)
        seen.add(typ)
    for typ in sorted(on_screen_enabled):
        if typ in seen or typ in _TV_DEVICE_PANEL_EXCLUDED_TYPES:
            continue
        if typ not in ADMIN_PALETTE_WIDGET_TYPES:
            continue
        out.append(typ)
        seen.add(typ)
    return out


DEFAULT_BELL_TRIGGER_SEC_WINDOW = 25
PRE_BELL_LEAD_MINUTES = 1
PRE_BELL_FIRE_SEC_WINDOW = 12
PRE_BELL_MAX_DURATION_SEC = 52
PRE_BELL_AFADE_IN_SEC = 3.0

TV_PAIR_ATTEMPT_WINDOW_SEC = 5 * 60
TV_PAIR_ATTEMPT_LIMIT = 8
TV_PAIR_BLOCK_SEC = 10
_TV_PAIR_ATTEMPTS: dict[str, list[float]] = {}
_TV_PAIR_BLOCK_UNTIL: dict[str, float] = {}


def _tv_pair_pin_bypass_env() -> bool:
    """Опционально в env (для срочного override): GUARDSCHOOL_TV_PAIR_BYPASS_PIN=1|true|yes|on."""
    v = (os.environ.get("GUARDSCHOOL_TV_PAIR_BYPASS_PIN") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _tv_pair_pin_bypass_from_tenant_config(tenant_slug: str) -> bool:
    """Флаг в config.json тенанта: tv_pair_pin_bypass (настраивается в админке)."""
    ts = (tenant_slug or "").strip()
    if not ts:
        return False
    from .tenant_ctx import set_tenant_slug

    set_tenant_slug(ts)
    try:
        return bool(load_config().get("tv_pair_pin_bypass"))
    finally:
        set_tenant_slug(None)


def _tv_pair_pin_bypass_effective(tenant_slug: str, pin_bypass_db: bool = False) -> bool:
    """Обход PIN: env ИЛИ колонка tv_access.pin_bypass (надёжно для ТВ) ИЛИ tv_pair_pin_bypass в config.json."""
    if _tv_pair_pin_bypass_env():
        return True
    if pin_bypass_db:
        return True
    return _tv_pair_pin_bypass_from_tenant_config(tenant_slug)


BREAK_ORCH_HEAD_SEC = 60
BREAK_ORCH_FADE_SEC = 120
BREAK_ORCH_SILENCE_SEC = 60
BREAK_ORCH_START_BELL_SEC = 60
MORNING_PRE_FIRST_LESSON_MIN = 30


def audio_trigger_sec_window(audio: dict[str, Any]) -> int:
    raw = audio.get("bell_trigger_sec_window", DEFAULT_BELL_TRIGGER_SEC_WINDOW)
    if raw is None:
        raw = DEFAULT_BELL_TRIGGER_SEC_WINDOW
    try:
        w = int(raw)
    except (TypeError, ValueError):
        w = DEFAULT_BELL_TRIGGER_SEC_WINDOW
    return max(5, min(55, w))


def first_bell_sound_path() -> Path | None:
    ensure_dirs()
    if not BELL_SOUNDS_DIR.exists():
        return None
    for p in sorted(BELL_SOUNDS_DIR.iterdir()):
        if p.is_file():
            return p
    return None


def default_screen(name: str, slug: str) -> dict[str, Any]:
    return {
        "id": secrets.token_hex(4),
        "name": name,
        "slug": slug,
        "ip_note": "",
        "orientation": "landscape",  # landscape|portrait
        "poll_interval_sec": 10,
        "enable_feedback": False,
        "background_image": "",
        "background_rotate_enabled": False,
        "background_rotate_interval_sec": 3600,
        "background_rotate_folder": "",
        "background_force_image": "",
        "background_rotate_cursor": 0,
        "background_rotate_epoch": 0,
        "tv_text_outline_px": 2,
        "tv_text_outline_color": "rgba(0,0,0,0.85)",
        "selected_classes": ["5", "6", "7", "8"],
        "bell_schedule_template": "standard",
        "weekday_bell_templates": {},
        "widgets": [
            {
                "id": "date",
                "type": "date",
                "title": "Дата",
                "enabled": True,
                "x": 0,
                "y": 0,
                "w": 12,
                "h": 2,
                "settings": {"fontSize": 32, "color": "#ffffff", "bold": False},
            },
            {
                "id": "time",
                "type": "time",
                "title": "Время",
                "enabled": True,
                "x": 12,
                "y": 0,
                "w": 8,
                "h": 2,
                "settings": {"fontSize": 42, "color": "#ffffff", "bold": False},
            },
            {
                "id": "text",
                "type": "text",
                "title": "Текст",
                "enabled": True,
                "x": 20,
                "y": 0,
                "w": 12,
                "h": 2,
                "settings": {
                    "text": "Добро пожаловать",
                    "fontSize": 24,
                    "color": "#ffffff",
                    "background": "rgba(0,0,0,0.35)",
                    "bold": False,
                },
            },
            {
                "id": "bell_status",
                "type": "bell_status",
                "title": "Звонки",
                "enabled": True,
                "x": 24,
                "y": 10,
                "w": 8,
                "h": 3,
                "settings": {
                    "fontSize": 18,
                    "titleFontSize": 18,
                    "color": "#ffffff",
                    "background": "rgba(15,23,42,0.55)",
                    "bold": False,
                },
            },
            {
                "id": "schedule",
                "type": "schedule",
                "title": "Расписание",
                "enabled": True,
                "x": 0,
                "y": 2,
                "w": 24,
                "h": 11,
                "settings": {
                    "showTomorrow": True,
                    "highlightColor": "#8b0000",
                    "sampleDiffColor": "#fee2e2",
                    "headerColor": "#1e3a5f",
                    "bodyColor": "rgba(255,255,255,0.9)",
                    "fontSize": 16,
                    "titleFontSize": 20,
                    "classes": ["5", "6", "7", "8"],
                    "bold": False,
                },
            },
            {
                "id": "carousel",
                "type": "carousel",
                "title": "Карусель",
                "enabled": False,
                "x": 0,
                "y": 2,
                "w": 24,
                "h": 11,
                "settings": {
                    "startDelaySec": 0,
                    "animation": "slide",
                    "childWidgetIds": ["schedule", "text"],
                    "childSlideSec": {"schedule": 60, "text": 30},
                },
            },
            {
                "id": "holidays",
                "type": "holidays",
                "title": "События",
                "enabled": False,
                "x": 24,
                "y": 2,
                "w": 8,
                "h": 5,
                "settings": {
                    "fontSize": 16,
                    "titleFontSize": 18,
                    "color": "#ffffff",
                    "background": "rgba(15,23,42,0.55)",
                    "count": 5,
                    "bold": False,
                },
            },
            {
                "id": "announcements",
                "type": "announcements",
                "title": "Объявления",
                "enabled": False,
                "x": 20,
                "y": 0,
                "w": 12,
                "h": 4,
                "settings": {
                    "items": "Собрание педагогов в 15:00\nЛинейка в понедельник\nПроверить сменную обувь",
                    "fontSize": 18,
                    "titleFontSize": 18,
                    "color": "#ffffff",
                    "background": "rgba(15,23,42,0.55)",
                    "bold": False,
                },
            },
            {
                "id": "marquee",
                "type": "marquee",
                "title": "Бегущая строка",
                "enabled": False,
                "x": 0,
                "y": 24,
                "w": 32,
                "h": 2,
                "settings": {
                    "items": "Внимание! Идет настройка экрана\nСегодня педсовет в 15:00",
                    "fontSize": 22,
                    "color": "#ffffff",
                    "background": "rgba(15,23,42,0.7)",
                    "charsPerMin": 180,
                    "speedSec": 18,
                    "bold": False,
                },
            },
            {
                "id": "school_news",
                "type": "school_news",
                "title": "Новости школы",
                "enabled": False,
                "x": 0,
                "y": 13,
                "w": 16,
                "h": 11,
                "settings": {
                    "fontSize": 18,
                    "titleFontSize": 22,
                    "color": "#ffffff",
                    "background": "rgba(15,23,42,0.55)",
                    "rotateSec": 12,
                    "bold": False,
                },
            },
            {
                "id": "rss_news",
                "type": "rss_news",
                "title": "RSS-лента",
                "enabled": False,
                "x": 24,
                "y": 14,
                "w": 8,
                "h": 10,
                "settings": {
                    "fontSize": 16,
                    "titleFontSize": 18,
                    "color": "#ffffff",
                    "background": "rgba(15,23,42,0.55)",
                    "rotateSec": 12,
                    "bold": False,
                },
            },
            {
                "id": "emergency",
                "type": "emergency",
                "title": "Аварийный",
                "enabled": False,
                "x": 0,
                "y": 0,
                "w": GRID_COLS,
                "h": GRID_ROWS,
                "settings": {
                    "text": "ВНИМАНИЕ!\nСрочное сообщение.",
                    "fontSize": 42,
                    "color": "#ffffff",
                    "background": "#b91c1c",
                    "bold": True,
                    "backdrop": False,
                    "soundEnabled": False,
                    "soundUrl": "",
                    "imageUrl": "",
                    "imageCaption": "",
                },
            },
            {
                "id": "image",
                "type": "image",
                "title": "Изображение",
                "enabled": False,
                "x": 0,
                "y": 0,
                "w": 8,
                "h": 8,
                "settings": {
                    "images": [{"name": "Эмблема", "url": ""}],
                    "imagesRotateSec": 0,
                    "opacity": 85,
                    "objectFit": "contain",
                    "backdrop": False,
                },
            },
        ],
        "template": "default_schedule",
        "is_active": True,
    }


def _default_emergency_templates() -> list[dict[str, Any]]:
    """Встроенные шаблоны аварийки (кнопка «вернуть стандарт» и первичная установка)."""
    return [
        {
            "id": "preset_fire",
            "title": "Пожар",
            "settings": {
                "text": "ПОЖАР!\nЭвакуация по сигналу. Следуйте указаниям персонала.",
                "fontSize": 44,
                "color": "#ffffff",
                "background": "#b91c1c",
                "bold": True,
                "backdrop": True,
                "soundEnabled": True,
                "soundUrl": "",
                "timer_seconds": 0,
                "byScreenName": {},
            },
        },
        {
            "id": "preset_terror",
            "title": "Антитеррор",
            "settings": {
                "text": "ВНИМАНИЕ!\nРежим повышенной готовности.\nСохраняйте спокойствие, действуйте по указаниям.",
                "fontSize": 40,
                "color": "#f8fafc",
                "background": "#1e3a8a",
                "bold": True,
                "backdrop": True,
                "soundEnabled": False,
                "soundUrl": "",
                "timer_seconds": 0,
                "byScreenName": {},
            },
        },
        {
            "id": "preset_bomb",
            "title": "Заминирование",
            "settings": {
                "text": "СООБЩЕНИЕ ОБ УГРОЗЕ\nОставайтесь на местах. Ожидайте указаний администрации.\nНе паникуйте.",
                "fontSize": 38,
                "color": "#fef3c7",
                "background": "#78350f",
                "bold": True,
                "backdrop": True,
                "soundEnabled": False,
                "soundUrl": "",
                "timer_seconds": 0,
                "byScreenName": {},
            },
        },
        {
            "id": "preset_crisis",
            "title": "Чрезвычайная ситуация",
            "settings": {
                "text": "ЧРЕЗВЫЧАЙНАЯ СИТУАЦИЯ\nСледуйте плану действий персонала школы.",
                "fontSize": 40,
                "color": "#ffffff",
                "background": "#7f1d1d",
                "bold": True,
                "backdrop": True,
                "soundEnabled": True,
                "soundUrl": "",
                "timer_seconds": 0,
                "byScreenName": {},
            },
        },
    ]


def _sanitize_emergency_by_screen_name(raw: Any) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if not isinstance(raw, dict):
        return out
    for k, v in list(raw.items())[:80]:
        key = str(k or "").strip()[:200]
        if not key:
            continue
        if not isinstance(v, dict):
            continue
        url = str(v.get("imageUrl") or v.get("url") or "").strip()[:512]
        if url and not url.startswith("/uploads/"):
            url = ""
        cap = str(v.get("caption") or v.get("imageCaption") or "").strip()[:500]
        out[key] = {"imageUrl": url, "caption": cap}
    return out


def _sanitize_emergency_templates_list(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for t in raw[:40]:
        if not isinstance(t, dict):
            continue
        tid = str(t.get("id") or "").strip()[:64]
        if not tid or not re.match(r"^[a-zA-Z0-9_-]+$", tid):
            continue
        title = str(t.get("title") or tid).strip()[:200]
        st = t.get("settings") if isinstance(t.get("settings"), dict) else {}
        try:
            fs = int(st.get("fontSize", 42))
        except (TypeError, ValueError):
            fs = 42
        fs = max(10, min(200, fs))
        bd = st.get("backdrop", True)
        if isinstance(bd, str):
            bd = bd.strip().lower() in ("true", "1", "yes", "on")
        else:
            bd = bool(bd)
        se = st.get("soundEnabled", False)
        if isinstance(se, str):
            se = se.strip().lower() in ("true", "1", "yes", "on")
        else:
            se = bool(se)
        surl = str(st.get("soundUrl") or "").strip()[:512]
        if surl and not (surl.startswith("/uploads/") or surl.startswith("http://") or surl.startswith("https://")):
            surl = ""
        try:
            timer_seconds = int(st.get("timer_seconds", st.get("timerSeconds", 0)) or 0)
        except (TypeError, ValueError):
            timer_seconds = 0
        timer_seconds = max(0, min(24 * 60 * 60, timer_seconds))
        out.append(
            {
                "id": tid,
                "title": title,
                "settings": {
                    "text": str(st.get("text", ""))[:5000],
                    "fontSize": fs,
                    "color": str(st.get("color") or "#ffffff").strip()[:64],
                    "background": str(st.get("background") or "#b91c1c").strip()[:64],
                    "bold": bool(st.get("bold", True)),
                    "backdrop": bd,
                    "soundEnabled": se,
                    "soundUrl": surl,
                    "timer_seconds": timer_seconds,
                    "byScreenName": _sanitize_emergency_by_screen_name(st.get("byScreenName")),
                },
            }
        )
    return out


def apply_emergency_template_to_screen(screen: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """
    Для ТВ/API: при включённом аварийном виджете и выбранном шаблоне подставляет настройки шаблона
    (приоритет над локальными полями виджета). Картинка/подпись — из byScreenName по имени экрана.
    """
    out = dict(screen)
    # Глубокая копия виджетов, чтобы не портить кэш load_config() в памяти при подстановке шаблона.
    widgets = copy.deepcopy(out.get("widgets") or [])
    idx = next((i for i, w in enumerate(widgets) if isinstance(w, dict) and w.get("type") == "emergency"), None)
    if idx is None:
        return out
    w = dict(widgets[idx])
    if w.get("enabled") is False:
        return out
    tid = str(config.get("emergency_active_template_id") or "").strip()
    if not tid:
        return out
    templates = config.get("emergency_templates")
    if not isinstance(templates, list):
        return out
    tpl = next((x for x in templates if isinstance(x, dict) and str(x.get("id") or "") == tid), None)
    if not tpl:
        return out
    ts = tpl.get("settings") if isinstance(tpl.get("settings"), dict) else {}
    try:
        fs = int(ts.get("fontSize", 42))
    except (TypeError, ValueError):
        fs = 42
    fs = max(10, min(200, fs))
    bd = ts.get("backdrop", True)
    if isinstance(bd, str):
        bd = bd.strip().lower() in ("true", "1", "yes", "on")
    else:
        bd = bool(bd)
    sn = str(out.get("name") or "").strip()
    byn = _sanitize_emergency_by_screen_name(ts.get("byScreenName"))
    row = byn.get(sn) or {}
    img = str(row.get("imageUrl") or "").strip()[:512]
    if img and not img.startswith("/uploads/"):
        img = ""
    cap = str(row.get("caption") or "").strip()[:500]
    surl = str(ts.get("soundUrl") or "").strip()[:512]
    if surl and not (surl.startswith("/uploads/") or surl.startswith("http://") or surl.startswith("https://")):
        surl = ""
    try:
        timer_seconds = int(ts.get("timer_seconds", ts.get("timerSeconds", 0)) or 0)
    except (TypeError, ValueError):
        timer_seconds = 0
    timer_seconds = max(0, min(24 * 60 * 60, timer_seconds))
    new_s = {
        "text": str(ts.get("text", ""))[:5000],
        "fontSize": fs,
        "color": str(ts.get("color") or "#ffffff").strip()[:64],
        "background": str(ts.get("background") or "#b91c1c").strip()[:64],
        "bold": bool(ts.get("bold", True)),
        "backdrop": bd,
        "soundEnabled": bool(ts.get("soundEnabled")),
        "soundUrl": surl,
        "timer_seconds": timer_seconds,
        "imageUrl": img,
        "imageCaption": cap,
    }
    w["settings"] = new_s
    w = normalize_widget(w)
    widgets[idx] = w
    out["widgets"] = widgets
    return out


def normalize_multicast_ip_value(raw: str | None, *, fallback: str) -> str:
    """Если в поле вставили udp://224.x...:port — вытаскиваем IPv4 группы."""
    s = (raw or "").strip()
    if not s:
        return fallback
    try:
        ip = ipaddress.ip_address(s)
        if ip.version == 4:
            return str(ip)
    except ValueError:
        pass
    m = re.search(
        r"\b(22[4-9]|23[0-9])(?:\.(?:25[0-5]|2[0-4]\d|[01]?\d?\d)){3}\b",
        s,
    )
    if m:
        try:
            ip = ipaddress.ip_address(m.group(0))
            if ip.version == 4 and ip.is_multicast:
                return str(ip)
        except ValueError:
            pass
    return fallback


def default_audio_stream_settings() -> dict[str, Any]:
    """Настройки звука на ПК (ffplay): звонки по расписанию и фон на переменах. Поля сети в JSON могут остаться от старой версии — не используются."""
    return {
        "enabled": False,
        "receiver_ip": "",
        "stream_port": 11990,
        "ping_host": "",
        "multicast_ip": "224.0.224.1",
        "multicast_ttl": 10,
        "base_port": 11990,
        "ffmpeg_path": "",
        "interface_note": "",
        "use_bell_schedule": True,
        "use_bell_sound_files": True,
        "volume_percent": 80,
        "source_screen_id": "",
        "send_via_multicast": False,
        "udp_bind_localaddr": False,
        "stream_profile": "mpegts_aac",
        "break_music_on_breaks": False,
        "break_music_volume_percent": 40,
        "bell_trigger_sec_window": DEFAULT_BELL_TRIGGER_SEC_WINDOW,
    }


def sanitize_audio_stream(raw: dict[str, Any] | None) -> dict[str, Any]:
    d = default_audio_stream_settings()
    if not isinstance(raw, dict):
        return d
    d["enabled"] = bool(raw.get("enabled"))
    recv = normalize_stream_host(str(raw.get("receiver_ip") or raw.get("ping_host") or ""))
    d["receiver_ip"] = recv
    d["ping_host"] = recv
    d["multicast_ip"] = normalize_multicast_ip_value(
        str(raw.get("multicast_ip") or ""),
        fallback=d["multicast_ip"],
    )[:45]
    d["ffmpeg_path"] = str(raw.get("ffmpeg_path") or "").strip()[:500]
    d["interface_note"] = str(raw.get("interface_note") or "").strip()[:500]
    try:
        ttl = int(raw.get("multicast_ttl", d["multicast_ttl"]))
        d["multicast_ttl"] = max(1, min(255, ttl))
    except (TypeError, ValueError):
        pass
    try:
        port = int(raw.get("stream_port", raw.get("base_port", d["stream_port"])))
        port = max(1, min(65535, port))
        d["stream_port"] = port
        d["base_port"] = port
    except (TypeError, ValueError):
        pass
    d["use_bell_schedule"] = bool(raw.get("use_bell_schedule", True))
    d["use_bell_sound_files"] = bool(raw.get("use_bell_sound_files", True))
    try:
        vol = int(raw.get("volume_percent", d["volume_percent"]))
        d["volume_percent"] = max(0, min(100, vol))
    except (TypeError, ValueError):
        pass
    try:
        ipaddress.ip_address(d["multicast_ip"])
    except ValueError:
        d["multicast_ip"] = default_audio_stream_settings()["multicast_ip"]
    if d["ffmpeg_path"]:
        p = Path(d["ffmpeg_path"])
        if not p.is_file() and not shutil.which(d["ffmpeg_path"]):
            d["ffmpeg_path"] = ""
    d["source_screen_id"] = str(raw.get("source_screen_id") or "").strip()[:80]
    d["send_via_multicast"] = bool(raw.get("send_via_multicast"))
    d["udp_bind_localaddr"] = bool(raw.get("udp_bind_localaddr"))
    prof = str(raw.get("stream_profile") or d["stream_profile"]).strip().lower()
    if prof not in ("mpegts_aac", "mpegts_copy", "mpegts_mp3"):
        prof = "mpegts_aac"
    d["stream_profile"] = prof
    d["break_music_on_breaks"] = bool(raw.get("break_music_on_breaks"))
    try:
        bv = int(raw.get("break_music_volume_percent", d["break_music_volume_percent"]))
        d["break_music_volume_percent"] = max(0, min(100, bv))
    except (TypeError, ValueError):
        pass
    try:
        bw = int(raw.get("bell_trigger_sec_window", d["bell_trigger_sec_window"]))
        d["bell_trigger_sec_window"] = max(5, min(55, bw))
    except (TypeError, ValueError):
        pass
    return d


def normalize_stream_host(raw: str) -> str:
    """
    Из поля «IP приёмника» часто вставляют URL (http://192.168.1.1/) — ping и TCP ждут голый хост.
    Убираем схему, путь, лишние слэши; при виде 192.168.1.1:порт оставляем только IP (порт задаётся отдельно).
    """
    s = str(raw or "").strip()
    if not s:
        return ""
    if re.match(r"^https?://", s, re.IGNORECASE):
        try:
            p = urlparse(s)
            h = (p.hostname or "").strip()
            if h:
                return h[:253]
        except Exception:
            pass
    s = s.split("/")[0].split("?")[0].strip()
    if s.count(":") == 1 and not s.startswith("["):
        left, _, right = s.partition(":")
        if right.isdigit():
            s = left.strip()
    return s[:253]


def default_config() -> dict[str, Any]:
    return {
        "templateSystem": {"version": 2, "templates": ["default_schedule"], "grid": {"cols": GRID_COLS, "rows": GRID_ROWS}},
        "ui_locale": "ru",
        "timezone": "Europe/Moscow",
        "clock_offset_minutes": 0,
        "admin_palette_hidden_types": [],
        "screens": [default_screen("ТВ-1", "tv-1")],
        "audio_stream": default_audio_stream_settings(),
        # Облако / гибрид (локальная админка; секреты лучше в env)
        "cloud_base_url": "",
        "cloud_sync_interval_minutes": 5,
        "cloud_sync_enabled": True,
        "cloud_sync_token": "",
        "screen_primary_base_url": "",
        "screen_fallback_base_url": "",
        "screen_fallback_enabled": False,
        "screen_poll_timeout_sec": 5,
        # SaaS: при true — PIN не проверяется; GET /t/код/экран сразу редиректит на экран с токеном в query.
        "tv_pair_pin_bypass": False,
        "emergency_templates": copy.deepcopy(_default_emergency_templates()),
        "emergency_active_template_id": "",
        "rss_sources": [],
        "rss_refresh_minutes": 45,
        "checkin": sanitize_checkin_block({}),
    }


def _reject_if_saas_upload(request: Request) -> None:
    """Тяжёлые/несущественные для SaaS загрузки (фоны, звуки, полный ZIP импорт)."""
    if not saas_mode():
        return
    loc = admin_ui_lang(request)
    raise HTTPException(
        status_code=403,
        detail=admin_msg(
            loc,
            "В режиме SaaS эта загрузка отключена (используйте расписание и правки в формах).",
            "This upload is disabled in SaaS mode (use schedule uploads and form edits).",
        ),
    )


async def _read_upload_capped(request: Request, file: UploadFile, max_bytes: int) -> bytes:
    raw = await file.read()
    if len(raw) > max_bytes:
        loc = admin_ui_lang(request)
        raise HTTPException(
            status_code=413,
            detail=admin_msg(
                loc,
                f"Файл слишком большой: {len(raw)} байт, максимум {max_bytes}.",
                f"File too large: {len(raw)} bytes, max {max_bytes}.",
            ),
        )
    return raw


def _saas_check_json_payload_size(request: Request, payload: Any, label: str) -> None:
    if not saas_mode():
        return
    n = json_utf8_size(payload)
    lim = max_schedule_json_bytes()
    if n > lim:
        loc = admin_ui_lang(request)
        raise HTTPException(
            status_code=413,
            detail=admin_msg(
                loc,
                f"{label}: после импорта JSON ≈ {n} байт (лимит {lim}). Упростите расписание.",
                f"{label}: JSON size ~{n} bytes (limit {lim}).",
            ),
        )


def _saas_check_quota_for_path(request: Request, path: Path, new_payload: Any) -> None:
    """Проверка суммарной квоты до записи JSON (замена одного файла)."""
    if not saas_mode():
        return
    new_bytes = len(json.dumps(new_payload, ensure_ascii=False, indent=2).encode("utf-8"))
    total = new_bytes
    for p in (SCHEDULE_PATH, FULL_SCHEDULE_PATH, SCHEDULE_SAMPLE_PATH, OVERRIDES_PATH, BELL_SCHEDULES_PATH):
        if p == path:
            continue
        if p.exists():
            total += p.stat().st_size
    lim = max_user_data_bytes()
    if total > lim:
        loc = admin_ui_lang(request)
        raise HTTPException(
            status_code=413,
            detail=admin_msg(
                loc,
                f"Превышена квота пользовательских данных: ~{total} байт (лимит {lim}). Упростите расписание или обратитесь к поддержке.",
                f"User data quota exceeded: ~{total} bytes (limit {lim}).",
            ),
        )


def _saas_enforce_user_data_quota_after_multi_write(request: Request) -> None:
    """После импорта ZIP или сложной записи — проверка фактического размера на диске."""
    if not saas_mode():
        return
    total = 0
    for p in (SCHEDULE_PATH, FULL_SCHEDULE_PATH, SCHEDULE_SAMPLE_PATH, OVERRIDES_PATH, BELL_SCHEDULES_PATH):
        if p.exists():
            total += p.stat().st_size
    lim = max_user_data_bytes()
    if total > lim:
        loc = admin_ui_lang(request)
        raise HTTPException(
            status_code=413,
            detail=admin_msg(
                loc,
                f"Превышена квота данных: {total} байт (лимит {lim}). Импорт отменить нельзя автоматически — удалите лишние данные вручную.",
                f"Data quota exceeded: {total} bytes (limit {lim}).",
            ),
        )


def _require_optional_tv_bearer(request: Request) -> None:
    """Если задан GUARDSCHOOL_TV_BEARER_TOKEN — /api/screen требует Authorization: Bearer …"""
    tok = (os.environ.get("GUARDSCHOOL_TV_BEARER_TOKEN") or "").strip()
    if not tok:
        return
    auth = request.headers.get("authorization") or ""
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Требуется токен ТВ (Bearer).")
    got = auth[7:].strip()
    if not hmac.compare_digest(got, tok):
        raise HTTPException(status_code=403, detail="Неверный токен ТВ.")


def _require_tv_access_for_screen(request: Request, screen_slug: str) -> None:
    """
    TV auth для /api/screen/{slug}:
    - GUARDSCHOOL_TV_BEARER_TOKEN задан: нужен Bearer; совпал с общим секретом — ок; иначе пробуем device-token.
    - секрет не задан: при Bearer в SaaS всё равно резолвим device-token → set_tenant_slug (иначе load_config()
      без cookie тенанта на school.* даёт пустое расписание).

    Device-token: тенант из tv_devices (не из cookie).
    """
    auth = (request.headers.get("authorization") or "").strip()
    got = auth[7:].strip() if auth.startswith("Bearer ") else ""
    expected = (os.environ.get("GUARDSCHOOL_TV_BEARER_TOKEN") or "").strip()

    if expected:
        if not got:
            raise HTTPException(status_code=401, detail="Требуется токен ТВ (Bearer).")
        if hmac.compare_digest(got, expected):
            return

    if deployment_mode() == "saas" and saas_db_enabled() and got:
        from .tenant_ctx import set_tenant_slug

        th = tv_device_token_hash(got)
        now = utcnow()
        with connect_public() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tenant_slug, status, expires_at FROM tv_devices
                    WHERE token_hash=%s AND lower(trim(screen_slug)) = %s
                    """,
                    (th, screen_slug),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=403, detail="Неверный токен ТВ.")
                tenant_from_device, status, expires_at = row[0], row[1], row[2]
                if status != "active":
                    raise HTTPException(status_code=403, detail="Токен ТВ отключён.")
                if expires_at is not None and expires_at <= now:
                    raise HTTPException(status_code=403, detail="Токен ТВ истёк.")
                cur.execute(
                    "UPDATE tv_devices SET last_seen_at=now() WHERE token_hash=%s AND lower(trim(screen_slug)) = %s",
                    (th, screen_slug),
                )
            conn.commit()
        slug = str(tenant_from_device or "").strip()
        if not slug:
            raise HTTPException(status_code=403, detail="Неверный токен ТВ.")
        set_tenant_slug(slug)
        try:
            from .saas_db import ensure_tenant_schema, schema_name_for_slug

            ensure_tenant_schema(schema_name_for_slug(slug))
        except Exception:
            pass
        return

    if expected:
        raise HTTPException(status_code=401, detail="Требуется токен ТВ (Bearer).")


_TV_PAIR_ZW_RE = re.compile(r"[\u200b-\u200d\ufeff]")


def _normalize_tv_pair_text(s: str) -> str:
    """NFKC + убрать ZWSP/BOM: на ТВ часто приходят полноширинные цифры и невидимые символы."""
    t = unicodedata.normalize("NFKC", str(s or ""))
    t = _TV_PAIR_ZW_RE.sub("", t).strip()
    for bad, good in (
        ("\u2010", "-"),
        ("\u2011", "-"),
        ("\u2012", "-"),
        ("\u2013", "-"),
        ("\u2014", "-"),
        ("\u2015", "-"),
        ("\u2212", "-"),
        ("\uff0d", "-"),
    ):
        t = t.replace(bad, good)
    return t


def _tv_school_code_compact(s: str) -> str:
    """Только a-z0-9 после той же нормализации, что для пары ТВ (сверка URL ↔ code_plaintext в БД)."""
    t = _normalize_tv_pair_text(str(s or "")).lower()
    return re.sub(r"[^a-z0-9]", "", t)


def _tv_path_code_segment(raw: str) -> str:
    """Сегмент кода из пути: обрезка слэшей/точек по краям (часть встроенных браузеров ТВ)."""
    return str(raw or "").strip().strip("/.").strip()


def _pin_digits_to_ascii(s: str) -> str:
    """Только цифры 0–9: ASCII и любые десятичные цифры Unicode (после NFKC — дозапас)."""
    out: list[str] = []
    for ch in s:
        if "0" <= ch <= "9":
            out.append(ch)
            continue
        if ch.isspace():
            continue
        try:
            d = unicodedata.decimal(ch)
        except (TypeError, ValueError):
            continue
        if 0 <= d <= 9:
            out.append(str(int(d)))
    return "".join(out)


def _normalize_tv_pair_pin(raw: str) -> str:
    return _pin_digits_to_ascii(_normalize_tv_pair_text(str(raw or "")))


def _normalize_screen_slug_for_api(slug: str) -> str:
    """Slug экрана в URL/API: NFKC-нормализация + нижний регистр (ТВ и конфиг часто расходятся по case)."""
    return _normalize_tv_pair_text(str(slug or "")).strip().lower()


def _tv_pair_client_key(request: Request, code: str) -> str:
    # X-Forwarded-For нужен за reverse proxy; берём только первый адрес.
    xff = str(request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    ip = xff or (request.client.host if request.client else "") or "unknown"
    return f"{ip}|{code}"


def _tv_pair_prune_attempts(key: str, now_ts: float) -> list[float]:
    arr = [ts for ts in _TV_PAIR_ATTEMPTS.get(key, []) if now_ts - ts <= TV_PAIR_ATTEMPT_WINDOW_SEC]
    if arr:
        _TV_PAIR_ATTEMPTS[key] = arr
    else:
        _TV_PAIR_ATTEMPTS.pop(key, None)
    return arr


def _tv_pair_check_rate_limit(key: str, now_ts: float) -> int:
    blocked_until = _TV_PAIR_BLOCK_UNTIL.get(key, 0.0)
    if blocked_until > now_ts:
        return max(1, int(blocked_until - now_ts))
    _TV_PAIR_BLOCK_UNTIL.pop(key, None)
    attempts = _tv_pair_prune_attempts(key, now_ts)
    if len(attempts) >= TV_PAIR_ATTEMPT_LIMIT:
        _TV_PAIR_BLOCK_UNTIL[key] = now_ts + TV_PAIR_BLOCK_SEC
        return TV_PAIR_BLOCK_SEC
    return 0


def _tv_pair_record_failure(key: str, now_ts: float) -> None:
    attempts = _tv_pair_prune_attempts(key, now_ts)
    attempts.append(now_ts)
    _TV_PAIR_ATTEMPTS[key] = attempts
    if len(attempts) >= TV_PAIR_ATTEMPT_LIMIT:
        _TV_PAIR_BLOCK_UNTIL[key] = now_ts + TV_PAIR_BLOCK_SEC


def _tv_pair_record_success(key: str) -> None:
    _TV_PAIR_ATTEMPTS.pop(key, None)
    _TV_PAIR_BLOCK_UNTIL.pop(key, None)


def _generate_tv_code() -> str:
    # Человекочитаемый короткий код: 4-4-4 символа (lower+digits), без спецсимволов.
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    raw = "".join(alphabet[secrets.randbelow(len(alphabet))] for _ in range(12))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:12]}"


def _require_sync_bearer(request: Request) -> None:
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


def _tzinfo_from_config_timezone(tzname: str):
    """Часовой пояс IANA из конфига. Без пакета tzdata (типично Windows) ZoneInfo недоступен — берём локаль ОС."""
    key = (tzname or "").strip() or "Europe/Moscow"
    for cand in (key, "Europe/Moscow"):
        try:
            return ZoneInfo(cand)
        except Exception:
            continue
    lt = datetime.now().astimezone().tzinfo
    return lt if lt is not None else timezone.utc


def _valid_iana_timezone(name: str) -> bool:
    s = (name or "").strip()
    if not s or len(s) > 80:
        return False
    try:
        ZoneInfo(s)
        return True
    except Exception:
        # Нет базы IANA (часто Windows без tzdata) — не сбрасываем пояс, если строка похожа на IANA.
        if s in ("UTC", "GMT"):
            return True
        return "/" in s and " " not in s


def calendar_today_for_config(config: dict[str, Any]) -> date:
    """«Сегодня» для расписания и звонков по часовому поясу из конфига."""
    tzname = str((config or {}).get("timezone") or "Europe/Moscow").strip()
    z = _tzinfo_from_config_timezone(tzname)
    return datetime.now(z).date()


def wall_clock_minutes_for_config(config: dict[str, Any]) -> int:
    """Минуты от полуночи в часовом поясе школы + clock_offset (согласовано с отображением времени на ТВ)."""
    tzname = str((config or {}).get("timezone") or "Europe/Moscow").strip()
    z = _tzinfo_from_config_timezone(tzname)
    try:
        off = int((config or {}).get("clock_offset_minutes") or 0)
    except (TypeError, ValueError):
        off = 0
    off = max(-720, min(720, off))
    now = datetime.now(z) + timedelta(minutes=off)
    return now.hour * 60 + now.minute


def display_settings_dict(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "timezone": str((config or {}).get("timezone") or "Europe/Moscow"),
        "clock_offset_minutes": int((config or {}).get("clock_offset_minutes") or 0),
        "ui_locale": str((config or {}).get("ui_locale") or "ru"),
    }


def default_bell_schedules() -> dict[str, Any]:
    return {
        "templates": [
            {
                "id": "standard",
                "name": "Обычное",
                "entries": [
                    {"lesson": "1", "start": "08:30", "end": "09:15"},
                    {"lesson": "2", "start": "09:25", "end": "10:10"},
                    {"lesson": "3", "start": "10:30", "end": "11:15"},
                    {"lesson": "4", "start": "11:35", "end": "12:20"},
                    {"lesson": "5", "start": "12:30", "end": "13:15"},
                    {"lesson": "6", "start": "13:25", "end": "14:10"},
                    {"lesson": "7", "start": "14:20", "end": "15:05"},
                    {"lesson": "8", "start": "15:15", "end": "16:00"},
                ],
            },
            {
                "id": "short",
                "name": "Сокращенное",
                "entries": [
                    {"lesson": "1", "start": "08:30", "end": "09:05"},
                    {"lesson": "2", "start": "09:15", "end": "09:50"},
                    {"lesson": "3", "start": "10:00", "end": "10:35"},
                    {"lesson": "4", "start": "10:45", "end": "11:20"},
                    {"lesson": "5", "start": "11:30", "end": "12:05"},
                    {"lesson": "6", "start": "12:15", "end": "12:50"},
                    {"lesson": "7", "start": "13:00", "end": "13:35"},
                    {"lesson": "8", "start": "13:45", "end": "14:20"},
                ],
            },
        ],
        "date_overrides": [],
        "weekday_overrides": {},
        "sound_defaults": {"start": None, "end": None},
    }


def normalize_widget(widget: dict[str, Any]) -> dict[str, Any]:
    wtype = str(widget.get("type") or "").strip()
    if wtype in {"rss_feed", "external_news"}:
        widget["type"] = "rss_news"
    widget["id"] = widget.get("id") or SINGLETON_WIDGET_IDS.get(widget.get("type"), secrets.token_hex(4))
    widget.setdefault("enabled", True)
    widget.setdefault("settings", {})
    if widget["type"] in {"date", "time", "text", "bell_status", "bell_countdown", "rss_news"}:
        widget["settings"].setdefault("fontSize", 24)
        widget["settings"].setdefault("color", "#ffffff")
        widget["settings"].setdefault("bold", False)
    if widget["type"] in {"holidays", "announcements", "marquee", "school_news", "rss_news"}:
        widget["settings"].setdefault("fontSize", 18)
        widget["settings"].setdefault("color", "#ffffff")
        widget["settings"].setdefault("background", "rgba(15,23,42,0.55)")
        widget["settings"].setdefault("bold", False)
    if widget["type"] in {"holidays", "announcements", "school_news", "rss_news"}:
        widget["settings"].setdefault("titleFontSize", 18)
    if widget["type"] == "text":
        widget["settings"].setdefault("background", "rgba(0,0,0,0.35)")
        widget["settings"].setdefault("text", "")
    if widget["type"] == "announcements":
        widget["settings"].setdefault("items", "")
        widget["settings"].setdefault("useManual", False)
        widget["settings"].setdefault("rotateSec", 30)
    if widget["type"] == "marquee":
        widget["settings"].setdefault("items", "")
        widget["settings"].setdefault("useManual", False)
        widget["settings"].setdefault("speedSec", 18)
    if widget["type"] in {"school_news", "rss_news"}:
        widget["settings"].setdefault("rotateSec", 12)
    if widget["type"] == "holidays":
        widget["settings"].setdefault("count", 5)
    if widget["type"] in {"bell_status", "bell_countdown"}:
        widget["settings"].setdefault("background", "rgba(15,23,42,0.55)")
        widget["settings"].setdefault("titleFontSize", 18)
    if widget["type"] == "schedule":
        widget["settings"].setdefault("highlightColor", "#8b0000")
        widget["settings"].setdefault("sampleDiffColor", "#fee2e2")
        widget["settings"].setdefault("headerColor", "#1e3a5f")
        widget["settings"].setdefault("bodyColor", "rgba(255,255,255,0.9)")
        widget["settings"].setdefault("fontSize", 16)
        widget["settings"].setdefault("titleFontSize", 20)
        widget["settings"].setdefault("classes", [])
        widget["settings"].setdefault("bold", False)
    if widget["type"] == "carousel":
        widget["settings"].setdefault("startDelaySec", 0)
        widget["settings"].setdefault("animation", "slide")
        widget["settings"].setdefault("childWidgetIds", [])
        widget["settings"].setdefault("childSlideSec", {})
    if widget["type"] == "emergency":
        widget["x"] = 0
        widget["y"] = 0
        widget["w"] = GRID_COLS
        widget["h"] = GRID_ROWS
        widget["settings"].setdefault("text", "")
        widget["settings"].setdefault("fontSize", 42)
        widget["settings"].setdefault("color", "#ffffff")
        widget["settings"].setdefault("background", "#b91c1c")
        widget["settings"].setdefault("bold", True)
        widget["settings"].setdefault("backdrop", False)
        widget["settings"].setdefault("soundEnabled", False)
        widget["settings"].setdefault("soundUrl", "")
        iu = str(widget["settings"].get("imageUrl") or "").strip()
        if iu and not iu.startswith("/uploads/"):
            iu = ""
        widget["settings"]["imageUrl"] = iu[:512]
        widget["settings"]["imageCaption"] = str(widget["settings"].get("imageCaption") or "").strip()[:500]
    if widget["type"] == "image":
        try:
            op = int(widget["settings"].get("opacity", 85))
        except (TypeError, ValueError):
            op = 85
        widget["settings"]["opacity"] = max(0, min(100, op))
        widget["settings"].setdefault("objectFit", "contain")
        widget["settings"].setdefault("backdrop", False)
        legacy_url = str(widget["settings"].get("imageUrl") or "").strip()
        raw_images = widget["settings"].get("images")
        images: list[dict[str, str]] = []
        if isinstance(raw_images, list):
            for item in raw_images:
                if not isinstance(item, dict):
                    continue
                nm = str(item.get("name") or "").strip()[:120]
                u = str(item.get("url") or "").strip()[:512]
                if not nm and not u:
                    continue
                images.append({"name": nm or "Без названия", "url": u})
        if not images and legacy_url:
            images = [{"name": "Изображение", "url": legacy_url[:512]}]
        if not images:
            images = [{"name": "Картинка 1", "url": ""}]
        widget["settings"]["images"] = images
        widget["settings"].pop("imageUrl", None)
        try:
            irs = int(widget["settings"].get("imagesRotateSec", 0))
        except (TypeError, ValueError):
            irs = 0
        widget["settings"]["imagesRotateSec"] = max(0, min(600, irs))
    if widget["type"] == "rss_news":
        widget["settings"].setdefault("titleFontSize", 18)
    if widget["type"] == "checkin_submit":
        widget["settings"].setdefault("places", [])
        widget["settings"].setdefault("monitor_widget_id", "")
        widget["settings"].setdefault("labels", {})
        widget["settings"].setdefault("pwa_icon_url", "")
        widget["settings"].setdefault("pwa_title", "")
        widget["settings"]["monitor_widget_id"] = str(widget["settings"].get("monitor_widget_id") or "").strip()[:80]
        piu = str(widget["settings"].get("pwa_icon_url") or "").strip()
        if piu and not piu.startswith("/uploads/"):
            piu = ""
        widget["settings"]["pwa_icon_url"] = piu[:512]
        widget["settings"]["pwa_title"] = str(widget["settings"].get("pwa_title") or "").strip()[:64]
        if not isinstance(widget["settings"].get("places"), list):
            widget["settings"]["places"] = []
        if not isinstance(widget["settings"].get("labels"), dict):
            widget["settings"]["labels"] = {}
    if widget["type"] == "checkin_monitor":
        widget["settings"].setdefault("places", [])
        widget["settings"].setdefault("panel_title", "Сводка мест")
        widget["settings"].setdefault("labels", {})
        widget["settings"].setdefault("events_screen_slug", "")
        widget["settings"].setdefault("pwa_icon_url", "")
        widget["settings"].setdefault("pwa_title", "")
        if not isinstance(widget["settings"].get("places"), list):
            widget["settings"]["places"] = []
        if not isinstance(widget["settings"].get("labels"), dict):
            widget["settings"]["labels"] = {}
        esc = _normalize_screen_slug_for_api(str(widget["settings"].get("events_screen_slug") or ""))
        widget["settings"]["events_screen_slug"] = esc if esc else ""
        piu = str(widget["settings"].get("pwa_icon_url") or "").strip()
        if piu and not piu.startswith("/uploads/"):
            piu = ""
        widget["settings"]["pwa_icon_url"] = piu[:512]
        widget["settings"]["pwa_title"] = str(widget["settings"].get("pwa_title") or "").strip()[:64]
    if widget["type"] in ("checkin_submit", "checkin_monitor"):
        widget["settings"].setdefault("fontSize", 0)
        widget["settings"].setdefault("bold", False)
        try:
            fs = int(widget["settings"].get("fontSize") or 0)
        except (TypeError, ValueError):
            fs = 0
        widget["settings"]["fontSize"] = max(0, min(48, fs))
        widget["settings"]["bold"] = bool(widget["settings"].get("bold"))
    widget["settings"].setdefault("backdrop", True)
    return widget


def dedupe_widgets(screen: dict[str, Any]) -> dict[str, Any]:
    seen_ids: set[str] = set()
    seen_singletons: set[str] = set()
    result: list[dict[str, Any]] = []
    for raw_widget in screen.get("widgets", []):
        widget = normalize_widget(raw_widget)
        widget_type = widget.get("type")
        widget_id = widget.get("id")
        if widget_type in SINGLETON_WIDGET_IDS:
            if widget_type in seen_singletons:
                continue
            seen_singletons.add(widget_type)
            widget["id"] = SINGLETON_WIDGET_IDS[widget_type]
            widget_id = widget["id"]
        if widget_id in seen_ids:
            continue
        seen_ids.add(widget_id)
        result.append(widget)
    screen["widgets"] = result
    return screen


def ensure_default_widgets(screen: dict[str, Any]) -> dict[str, Any]:
    existing_types = {widget.get("type") for widget in screen.get("widgets", [])}
    for template_widget in default_screen(screen.get("name", "ТВ"), screen.get("slug", "tv"))["widgets"]:
        widget_type = template_widget.get("type")
        if widget_type in SINGLETON_WIDGET_IDS and widget_type not in existing_types:
            screen.setdefault("widgets", []).append(normalize_widget(dict(template_widget)))
    return screen


def migrate_screen_layout(screen: dict[str, Any], old_cols: int, old_rows: int) -> dict[str, Any]:
    if old_cols == GRID_COLS and old_rows == GRID_ROWS:
        return screen
    default_by_type = {widget["type"]: widget for widget in default_screen(screen["name"], screen["slug"])["widgets"]}
    migrated_widgets = []
    for widget in screen.get("widgets", []):
        current = normalize_widget(widget)
        template = default_by_type.get(current["type"])
        if template:
            current["x"] = template["x"]
            current["y"] = template["y"]
            current["w"] = template["w"]
            current["h"] = template["h"]
            for key, value in template["settings"].items():
                current["settings"].setdefault(key, value)
        migrated_widgets.append(current)
    screen["widgets"] = migrated_widgets
    return screen


def load_config() -> dict[str, Any]:
    config = read_json(CONFIG_PATH, default_config())
    if not config.get("screens"):
        config["screens"] = [default_screen("ТВ-1", "tv-1")]
    grid = config.setdefault("templateSystem", {}).setdefault("grid", {"cols": GRID_COLS, "rows": GRID_ROWS})
    old_cols = int(grid.get("cols", GRID_COLS))
    old_rows = int(grid.get("rows", GRID_ROWS))
    for screen in config["screens"]:
        migrate_screen_layout(screen, old_cols, old_rows)
        dedupe_widgets(screen)
        ensure_default_widgets(screen)
        dedupe_widgets(screen)
        screen.setdefault("selected_classes", ["5", "6", "7", "8"])
        screen.setdefault("background_image", "")
        screen.setdefault("background_rotate_enabled", False)
        screen.setdefault("background_rotate_interval_sec", 3600)
        screen.setdefault("background_rotate_folder", "")
        screen.setdefault("background_force_image", "")
        screen.setdefault("background_rotate_cursor", 0)
        screen.setdefault("background_rotate_epoch", 0)
        screen.setdefault("tv_text_outline_px", 2)
        screen.setdefault("tv_text_outline_color", "rgba(0,0,0,0.85)")
        try:
            _bri = int(screen["background_rotate_interval_sec"])
        except (TypeError, ValueError):
            _bri = 3600
        screen["background_rotate_interval_sec"] = max(60, min(86400, _bri))
        screen["background_rotate_enabled"] = bool(screen.get("background_rotate_enabled"))
        screen["background_rotate_folder"] = safe_rel_uploads_subdir(screen.get("background_rotate_folder"))
        bfi = str(screen.get("background_force_image") or "").strip()
        # Разрешаем только /uploads/... (иначе можно подсунуть внешний URL)
        screen["background_force_image"] = bfi if bfi.startswith("/uploads/") else ""
        try:
            cur = int(screen.get("background_rotate_cursor", 0))
        except (TypeError, ValueError):
            cur = 0
        screen["background_rotate_cursor"] = max(0, min(1000000, cur))
        try:
            ep = int(screen.get("background_rotate_epoch", 0))
        except (TypeError, ValueError):
            ep = 0
        screen["background_rotate_epoch"] = max(0, min(4102444800, ep))  # ~2100
        try:
            _px = int(screen.get("tv_text_outline_px", 2))
        except (TypeError, ValueError):
            _px = 2
        screen["tv_text_outline_px"] = max(0, min(8, _px))
        col = screen.get("tv_text_outline_color")
        screen["tv_text_outline_color"] = str(col).strip()[:64] if col is not None else "rgba(0,0,0,0.85)"
        screen.setdefault("poll_interval_sec", 10)
        screen.setdefault("enable_feedback", False)
        screen["enable_feedback"] = bool(screen.get("enable_feedback", False))
        screen.setdefault("bell_schedule_template", "standard")
        screen.setdefault("weekday_bell_templates", {})
    config["templateSystem"]["version"] = 2
    config["templateSystem"]["grid"] = {"cols": GRID_COLS, "rows": GRID_ROWS}
    config["audio_stream"] = sanitize_audio_stream(config.get("audio_stream"))
    config.setdefault("ui_locale", "ru")
    config.setdefault("timezone", "Europe/Moscow")
    config.setdefault("clock_offset_minutes", 0)
    if str(config.get("ui_locale") or "ru").strip().lower() not in ("ru", "en"):
        config["ui_locale"] = "ru"
    tz0 = str(config.get("timezone") or "Europe/Moscow").strip()
    config["timezone"] = tz0 if _valid_iana_timezone(tz0) else "Europe/Moscow"
    try:
        _off0 = int(config.get("clock_offset_minutes", 0))
    except (TypeError, ValueError):
        _off0 = 0
    config["clock_offset_minutes"] = max(-720, min(720, _off0))
    _raw_hidden = config.get("admin_palette_hidden_types")
    if not isinstance(_raw_hidden, list):
        config["admin_palette_hidden_types"] = []
    else:
        config["admin_palette_hidden_types"] = [
            str(x).strip() for x in _raw_hidden if str(x).strip() in ADMIN_PALETTE_WIDGET_TYPES
        ]
    config.setdefault("cloud_base_url", "")
    config.setdefault("cloud_sync_interval_minutes", 5)
    config.setdefault("cloud_sync_enabled", True)
    config.setdefault("cloud_sync_token", "")
    config.setdefault("screen_primary_base_url", "")
    config.setdefault("screen_fallback_base_url", "")
    config.setdefault("screen_fallback_enabled", False)
    config.setdefault("screen_poll_timeout_sec", 5)
    try:
        _csi = int(config.get("cloud_sync_interval_minutes", 5))
    except (TypeError, ValueError):
        _csi = 5
    config["cloud_sync_interval_minutes"] = max(1, min(1440, _csi))
    try:
        _spt2 = int(config.get("screen_poll_timeout_sec", 5))
    except (TypeError, ValueError):
        _spt2 = 5
    config["screen_poll_timeout_sec"] = max(2, min(60, _spt2))
    for _k in ("cloud_base_url", "screen_primary_base_url", "screen_fallback_base_url"):
        config[_k] = str(config.get(_k) or "").strip()[:512]
    config["cloud_sync_token"] = str(config.get("cloud_sync_token") or "").strip()[:500]
    config["cloud_sync_enabled"] = bool(config.get("cloud_sync_enabled", True))
    config["screen_fallback_enabled"] = bool(config.get("screen_fallback_enabled", False))
    _et = config.get("emergency_templates")
    if _et is None:
        config["emergency_templates"] = copy.deepcopy(_default_emergency_templates())
    else:
        config["emergency_templates"] = _sanitize_emergency_templates_list(_et)
    config["emergency_active_template_id"] = str(config.get("emergency_active_template_id") or "").strip()[:64]
    config["rss_sources"] = sanitize_rss_sources(config.get("rss_sources"))
    config["rss_refresh_minutes"] = sanitize_rss_refresh_minutes(config.get("rss_refresh_minutes", 45))
    config["checkin"] = sanitize_checkin_block(config.get("checkin"))
    return config


def sanitize_config(config: dict[str, Any]) -> dict[str, Any]:
    config = config or default_config()
    template_system = config.setdefault("templateSystem", {})
    template_system["version"] = 2
    template_system["grid"] = {"cols": GRID_COLS, "rows": GRID_ROWS}

    screens = config.get("screens") or [default_screen("ТВ-1", "tv-1")]
    cleaned_screens: list[dict[str, Any]] = []
    for raw_screen in screens:
        screen = dict(raw_screen)
        screen.setdefault("selected_classes", ["5", "6", "7", "8"])
        screen["selected_classes"] = list(dict.fromkeys(screen.get("selected_classes", [])))
        # Mobile screen mode (device-friendly vertical layout).
        screen.setdefault("mobile_mode", False)
        screen.setdefault("mobile_widget_ids", [])
        screen["mobile_mode"] = bool(screen.get("mobile_mode", False))
        if not isinstance(screen.get("mobile_widget_ids"), list):
            screen["mobile_widget_ids"] = []
        else:
            screen["mobile_widget_ids"] = [str(x) for x in screen.get("mobile_widget_ids", []) if str(x)]
        screen.setdefault("background_image", "")
        screen.setdefault("background_rotate_enabled", False)
        screen.setdefault("background_rotate_interval_sec", 3600)
        screen.setdefault("background_rotate_folder", "")
        screen.setdefault("background_force_image", "")
        screen.setdefault("background_rotate_cursor", 0)
        screen.setdefault("background_rotate_epoch", 0)
        screen.setdefault("tv_text_outline_px", 2)
        screen.setdefault("tv_text_outline_color", "rgba(0,0,0,0.85)")
        ori = str(screen.get("orientation") or "landscape").strip().lower()
        screen["orientation"] = ori if ori in ("landscape", "portrait") else "landscape"
        try:
            _bri2 = int(screen["background_rotate_interval_sec"])
        except (TypeError, ValueError):
            _bri2 = 3600
        screen["background_rotate_interval_sec"] = max(60, min(86400, _bri2))
        screen["background_rotate_enabled"] = bool(screen.get("background_rotate_enabled"))
        screen["background_rotate_folder"] = safe_rel_uploads_subdir(screen.get("background_rotate_folder"))
        bfi2 = str(screen.get("background_force_image") or "").strip()
        screen["background_force_image"] = bfi2 if bfi2.startswith("/uploads/") else ""
        try:
            cur2 = int(screen.get("background_rotate_cursor", 0))
        except (TypeError, ValueError):
            cur2 = 0
        screen["background_rotate_cursor"] = max(0, min(1000000, cur2))
        try:
            ep2 = int(screen.get("background_rotate_epoch", 0))
        except (TypeError, ValueError):
            ep2 = 0
        screen["background_rotate_epoch"] = max(0, min(4102444800, ep2))
        try:
            _px2 = int(screen.get("tv_text_outline_px", 2))
        except (TypeError, ValueError):
            _px2 = 2
        screen["tv_text_outline_px"] = max(0, min(8, _px2))
        col2 = screen.get("tv_text_outline_color")
        screen["tv_text_outline_color"] = str(col2).strip()[:64] if col2 is not None else "rgba(0,0,0,0.85)"
        screen.setdefault("poll_interval_sec", 10)
        screen.setdefault("enable_feedback", False)
        screen["enable_feedback"] = bool(screen.get("enable_feedback", False))
        screen.setdefault("bell_schedule_template", "standard")
        screen.setdefault("weekday_bell_templates", {})
        dedupe_widgets(screen)
        ensure_default_widgets(screen)
        dedupe_widgets(screen)

        valid_widget_ids = {widget["id"] for widget in screen["widgets"]}
        # Keep only ids that exist in screen.widgets (order preserved).
        if isinstance(screen.get("mobile_widget_ids"), list):
            screen["mobile_widget_ids"] = [x for x in screen["mobile_widget_ids"] if x in valid_widget_ids]
        for widget in screen["widgets"]:
            if widget["type"] == "schedule":
                classes = widget["settings"].get("classes") or screen["selected_classes"]
                widget["settings"]["classes"] = list(dict.fromkeys(classes))
            if widget["type"] == "carousel":
                child_ids = widget["settings"].get("childWidgetIds", [])
                child_ids = [
                    item
                    for item in child_ids
                    if (item in valid_widget_ids or item == "__blank__") and item != widget["id"]
                ]
                widget["settings"]["childWidgetIds"] = list(dict.fromkeys(child_ids))
                cs = widget["settings"].get("childSlideSec") or {}
                if isinstance(cs, dict):
                    widget["settings"]["childSlideSec"] = {
                        k: v for k, v in cs.items() if (k in valid_widget_ids or k == "__blank__") and k != widget["id"]
                    }
            ws = widget.get("settings")
            if isinstance(ws, dict) and "backdrop" in ws:
                b = ws["backdrop"]
                if isinstance(b, str):
                    ws["backdrop"] = b.strip().lower() in ("true", "1", "yes", "on")
                elif not isinstance(b, bool):
                    ws["backdrop"] = bool(b)

        cleaned_screens.append(screen)

    config["screens"] = cleaned_screens
    config["audio_stream"] = sanitize_audio_stream(config.get("audio_stream"))
    loc = str(config.get("ui_locale") or "ru").strip().lower()
    config["ui_locale"] = loc if loc in ("ru", "en") else "ru"
    tz = str(config.get("timezone") or "Europe/Moscow").strip()
    config["timezone"] = tz if _valid_iana_timezone(tz) else "Europe/Moscow"
    try:
        off = int(config.get("clock_offset_minutes", 0))
    except (TypeError, ValueError):
        off = 0
    config["clock_offset_minutes"] = max(-720, min(720, off))
    raw_hidden = config.get("admin_palette_hidden_types")
    if not isinstance(raw_hidden, list):
        config["admin_palette_hidden_types"] = []
    else:
        config["admin_palette_hidden_types"] = [
            str(x).strip() for x in raw_hidden if str(x).strip() in ADMIN_PALETTE_WIDGET_TYPES
        ]
    config.setdefault("cloud_base_url", "")
    config.setdefault("cloud_sync_interval_minutes", 5)
    config.setdefault("cloud_sync_enabled", True)
    config.setdefault("cloud_sync_token", "")
    config.setdefault("screen_primary_base_url", "")
    config.setdefault("screen_fallback_base_url", "")
    config.setdefault("screen_fallback_enabled", False)
    config.setdefault("screen_poll_timeout_sec", 5)
    try:
        csi = int(config.get("cloud_sync_interval_minutes", 5))
    except (TypeError, ValueError):
        csi = 5
    config["cloud_sync_interval_minutes"] = max(1, min(1440, csi))
    try:
        spt = int(config.get("screen_poll_timeout_sec", 5))
    except (TypeError, ValueError):
        spt = 5
    config["screen_poll_timeout_sec"] = max(2, min(60, spt))
    for key in ("cloud_base_url", "screen_primary_base_url", "screen_fallback_base_url"):
        config[key] = str(config.get(key) or "").strip()[:512]
    for key in ("cloud_sync_token",):
        config[key] = str(config.get(key) or "").strip()[:500]
    config["cloud_sync_enabled"] = bool(config.get("cloud_sync_enabled", True))
    config["screen_fallback_enabled"] = bool(config.get("screen_fallback_enabled", False))
    config["tv_pair_pin_bypass"] = bool(config.get("tv_pair_pin_bypass", False))
    raw_et = config.get("emergency_templates")
    if raw_et is None:
        config["emergency_templates"] = copy.deepcopy(_default_emergency_templates())
    else:
        config["emergency_templates"] = _sanitize_emergency_templates_list(raw_et)
    config["emergency_active_template_id"] = str(config.get("emergency_active_template_id") or "").strip()[:64]
    config["rss_sources"] = sanitize_rss_sources(config.get("rss_sources"))
    config["rss_refresh_minutes"] = sanitize_rss_refresh_minutes(config.get("rss_refresh_minutes", 45))
    config["checkin"] = sanitize_checkin_block(config.get("checkin"))
    return config


# Фильтр классов по `screen.selected_classes` и по `?gs_classes=` (настройки устройства на ТВ/телефоне).
_TEMP_DISABLE_SCREEN_CLASS_FILTER = False


def _screen_config_by_slug(config: dict[str, Any], slug_key: str) -> dict[str, Any] | None:
    for item in config.get("screens") or []:
        if _normalize_screen_slug_for_api(str(item.get("slug") or "")) == slug_key and item.get("is_active", True):
            return item
    return None


def _screen_widgets_ordered_with_carousel_children(screen: dict[str, Any]) -> list[dict[str, Any]]:
    """Плоский порядок виджетов + дети carousel по childWidgetIds (карусель, моб. вёрстка)."""
    widgets = screen.get("widgets")
    if not isinstance(widgets, list):
        return []
    by_id: dict[str, dict[str, Any]] = {}
    for w in widgets:
        if not isinstance(w, dict):
            continue
        wid = str(w.get("id") or "").strip()
        if wid:
            by_id[wid] = w
    seq: list[dict[str, Any]] = []
    seen: set[str] = set()

    def append_widget(entry: dict[str, Any]) -> None:
        wid = str(entry.get("id") or "").strip()
        if wid:
            if wid in seen:
                return
            seen.add(wid)
        seq.append(entry)

    for w in widgets:
        if not isinstance(w, dict):
            continue
        append_widget(w)
        if str(w.get("type") or "") != "carousel":
            continue
        st_car = w.get("settings") if isinstance(w.get("settings"), dict) else {}
        for cid in st_car.get("childWidgetIds") or []:
            child = by_id.get(str(cid).strip())
            if isinstance(child, dict):
                append_widget(child)
    return seq


def _find_submit_widget(screen: dict[str, Any], widget_id: str) -> dict[str, Any] | None:
    want = str(widget_id).strip()
    for w in _screen_widgets_ordered_with_carousel_children(screen):
        if isinstance(w, dict) and str(w.get("id") or "").strip() == want and w.get("type") == "checkin_submit":
            return w
    return None


def _find_monitor_widget(screen: dict[str, Any], widget_id: str) -> dict[str, Any] | None:
    want = str(widget_id).strip()
    for w in _screen_widgets_ordered_with_carousel_children(screen):
        if isinstance(w, dict) and str(w.get("id") or "").strip() == want and w.get("type") == "checkin_monitor":
            return w
    return None


def _checkin_events_screen_slug_for_monitor(
    config: dict[str, Any], mw: dict[str, Any], display_slug_key: str
) -> str:
    """Slug экрана, с которого пишутся события в БД (форма отметки). По умолчанию — экран, где висит сводка."""
    raw = str((mw.get("settings") or {}).get("events_screen_slug") or "").strip()
    alt = _normalize_screen_slug_for_api(raw)
    if not alt:
        return display_slug_key
    if _screen_config_by_slug(config, alt):
        return alt
    return display_slug_key


def _resolve_checkin_submit_places(screen: dict[str, Any], submit_w: dict[str, Any]) -> list[dict[str, str]]:
    """Места только из виджета «Сводка» (явная ссылка или ровно одна сводка на экране)."""
    st = submit_w.get("settings") or {}
    link = str(st.get("monitor_widget_id") or "").strip()
    if link:
        mw = _find_monitor_widget(screen, link)
        if mw:
            return sanitize_places_list((mw.get("settings") or {}).get("places"))
    mons = [
        w
        for w in _screen_widgets_ordered_with_carousel_children(screen)
        if isinstance(w, dict) and w.get("type") == "checkin_monitor"
    ]
    if len(mons) == 1:
        return sanitize_places_list((mons[0].get("settings") or {}).get("places"))
    return sanitize_places_list(st.get("places"))


def _checkin_period_normalize(period: str) -> str:
    p = (period or "day").strip().lower()
    return p if p in ("day", "week", "month") else "day"


def _checkin_board_payload(
    config: dict[str, Any],
    tenant_id: str,
    slug_key: str,
    monitor_widget_id: str,
    period: str,
) -> dict[str, Any]:
    screen = _screen_config_by_slug(config, slug_key)
    if not screen:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    mw = _find_monitor_widget(screen, monitor_widget_id)
    if not mw:
        raise HTTPException(status_code=404, detail="Виджет сводки не найден.")
    places = sanitize_places_list((mw.get("settings") or {}).get("places"))
    period_n = _checkin_period_normalize(period)
    event_slug = _checkin_events_screen_slug_for_monitor(config, mw, slug_key)
    summary_label, summary_items = build_summary_for_places(
        tenant_id, config, places, period_n, event_slug
    )
    pids = {p["id"] for p in places}
    start_utc, end_utc, range_label = range_bounds_utc(config, period_n)
    journal = list_journal_filtered(tenant_id, start_utc, end_utc, pids if pids else None, event_slug)
    journal = [enrich_checkin_event_for_client(config, dict(j)) for j in journal]
    for it in summary_items:
        le = it.get("last_event")
        if isinstance(le, dict):
            it["last_event"] = enrich_checkin_event_for_client(config, dict(le))
    raw_labels = (mw.get("settings") or {}).get("labels")
    labels_out: dict[str, Any] = {}
    if isinstance(raw_labels, dict):
        labels_out = {str(k).strip()[:80]: str(v).strip()[:500] for k, v in raw_labels.items() if str(k).strip()}
    return {
        "range_label": range_label,
        "summary_title": summary_label,
        "summary": summary_items,
        "journal": journal,
        "places": places,
        "labels": labels_out,
        "period": period_n,
    }


def load_schedule() -> list[dict[str, Any]]:
    maybe_import_schedule_from_folder()
    return read_json(SCHEDULE_PATH, [])


def load_full_schedule() -> list[dict[str, Any]]:
    maybe_import_full_schedule_from_folder()
    return read_json(FULL_SCHEDULE_PATH, [])


def load_schedule_sample() -> list[dict[str, Any]]:
    maybe_import_schedule_sample_from_folder()
    return read_json(SCHEDULE_SAMPLE_PATH, [])


def load_holidays() -> list[dict[str, Any]]:
    maybe_import_holidays_from_folder()
    return read_json(HOLIDAYS_PATH, [])


def load_announcements() -> list[dict[str, Any]]:
    maybe_import_announcements_from_folder()
    return read_json(ANNOUNCEMENTS_PATH, [])


def _school_news_text_preview(raw_html: str) -> str:
    """Текст для виджета школьных новостей: без ограничения длины."""
    s = str(raw_html or "")
    # Сохраняем структуру: блоки/переносы превращаем в \n, потом чистим теги.
    s = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", s)
    s = re.sub(r"(?i)</\s*p\s*>", "\n\n", s)
    s = re.sub(r"(?i)</\s*div\s*>", "\n\n", s)
    s = re.sub(r"(?i)</\s*li\s*>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    # Нормализация: пробелы схлопываем, но переносы сохраняем.
    s = re.sub(r"[ \t\f\v]+", " ", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r" +\n", "\n", s)
    return s.strip()


def sanitize_school_news_item(item: dict[str, Any], fallback_id: str = "") -> dict[str, Any]:
    nid = str(item.get("id") or fallback_id or secrets.token_hex(6)).strip()[:64]
    tenant = ""
    try:
        from .tenant_ctx import tenant_slug as _tenant_slug

        tenant = str(_tenant_slug() or "").strip()[:64]
    except Exception:
        tenant = ""
    title = str(item.get("title") or "").strip()[:200]
    content = str(item.get("content") or "").strip()[:50000]
    # Защита от опасного встроенного JS в HTML-контенте новости.
    content = re.sub(r"(?is)<script[^>]*>.*?</script>", "", content)
    content = re.sub(r"(?is)on[a-z]+\s*=\s*\"[^\"]*\"", "", content)
    content = re.sub(r"(?is)on[a-z]+\s*=\s*'[^']*'", "", content)
    cover = str(item.get("cover_image") or "").strip()[:500]
    if cover:
        if cover.startswith("/uploads/"):
            pass
        elif re.fullmatch(r"(?i)https?://.{6,500}", cover):
            # внешняя картинка (не управляем локальным файлом)
            pass
        else:
            cover = ""
    created = schedule_date_iso(item.get("created_at")) or date.today().isoformat()
    active = bool(item.get("is_active", True))
    out = {
        "id": nid,
        "tenant_id": tenant or str(item.get("tenant_id") or "").strip()[:64],
        "title": title,
        "content": content,
        "cover_image": cover,
        "created_at": created,
        "is_active": active,
    }
    out["summary"] = _school_news_text_preview(content)
    return out


def load_school_news() -> list[dict[str, Any]]:
    raw = read_json(SCHOOL_NEWS_PATH, [])
    out: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for idx, item in enumerate(raw):
            if isinstance(item, dict):
                out.append(sanitize_school_news_item(item, fallback_id=f"news_{idx + 1}"))
    out.sort(key=lambda x: (str(x.get("created_at") or ""), str(x.get("id") or "")), reverse=True)
    return out


def _school_news_uploads_dir() -> Path:
    from .tenant_ctx import map_data_path

    return map_data_path(UPLOADS_DIR / "school_news")


def _safe_unlink_upload_url(url: str) -> None:
    """
    Удаляем только локальные файлы в data/uploads/school_news/*.
    URL должен быть вида /uploads/school_news/<name>.
    """
    u = str(url or "").strip()
    if not u.startswith("/uploads/school_news/"):
        return
    name = u.split("/uploads/school_news/", 1)[1].strip().lstrip("/").split("?", 1)[0]
    if not name or "/" in name or "\\" in name:
        return
    base = _school_news_uploads_dir()
    try:
        p = (base / name).resolve()
        if base.resolve() in p.parents and p.is_file():
            p.unlink(missing_ok=True)
    except Exception:
        return


def _extract_school_news_local_upload_urls(content_html: str) -> set[str]:
    s = str(content_html or "")
    out: set[str] = set()
    for m in re.finditer(r"(/uploads/school_news/[A-Za-z0-9._-]{1,180})", s):
        out.add(m.group(1))
    return out


def _save_school_news_image_bytes(news_id: str, data: bytes, content_type: str | None = None, source_name: str = "") -> str:
    if not data:
        raise HTTPException(status_code=400, detail="Пустой файл.")
    if len(data) > 1024 * 1024:
        raise HTTPException(status_code=413, detail="Файл слишком большой (макс. 1 МБ).")
    ensure_dirs()
    base = _school_news_uploads_dir()
    base.mkdir(parents=True, exist_ok=True)
    nid = re.sub(r"[^A-Za-z0-9_-]+", "_", str(news_id or "").strip())[:64] or secrets.token_hex(6)
    ext = ""
    ct = (content_type or "").lower().strip()
    if "png" in ct:
        ext = ".png"
    elif "jpeg" in ct or "jpg" in ct:
        ext = ".jpg"
    elif "webp" in ct:
        ext = ".webp"
    elif "gif" in ct:
        ext = ".gif"
    if not ext:
        sn = str(source_name or "").lower()
        m = re.search(r"\.(png|jpg|jpeg|webp|gif)(?:\?|$)", sn)
        if m:
            ext = ".jpg" if m.group(1) in ("jpg", "jpeg") else f".{m.group(1)}"
    if not ext:
        ext = ".jpg"
    # Максимальная совместимость с ТВ: стараемся перекодировать в baseline JPEG (без прогрессива/CMYK).
    try:
        import io

        from PIL import Image  # type: ignore

        try:
            img = Image.open(io.BytesIO(data))
            img.load()
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            elif img.mode == "L":
                img = img.convert("RGB")
            out = io.BytesIO()
            quality = 85
            best = None
            while quality >= 50:
                out.seek(0)
                out.truncate(0)
                img.save(out, format="JPEG", quality=quality, optimize=True, progressive=False)
                b = out.getvalue()
                best = b
                if len(b) <= 1024 * 1024:
                    break
                quality -= 10
            if best:
                data = best
                ext = ".jpg"
        except Exception:
            pass
    except Exception:
        pass

    fn = f"{nid}_{secrets.token_hex(4)}{ext}"
    (base / fn).write_bytes(data)
    return f"/uploads/school_news/{fn}"


def load_rss_news(config: dict[str, Any] | None = None, *, force_refresh: bool = False) -> list[dict[str, Any]]:
    """
    Обёртка совместимости для rss_news:
    - принимает старые/новые вызовы (с config и без),
    - делегирует загрузку в gs_rss_news.
    """
    cfg = config if isinstance(config, dict) else load_config()
    return load_rss_news_feed(cfg, force_refresh=force_refresh)


def load_marquee_items() -> list[str]:
    maybe_import_marquee_from_folder()
    raw = read_json(MARQUEE_PATH, [])
    return [str(x).strip() for x in raw if str(x).strip()]


def load_overrides() -> list[dict[str, Any]]:
    return read_json(OVERRIDES_PATH, [])


def schedule_date_iso(raw: Any) -> str:
    """Поле date в schedule.json / override → YYYY-MM-DD для сравнения (Excel dd.mm.yyyy, datetime-строки)."""
    if raw is None:
        return ""
    if isinstance(raw, datetime):
        return raw.date().isoformat()
    if isinstance(raw, date):
        return raw.isoformat()
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        try:
            n = int(raw)
        except (TypeError, ValueError):
            n = 0
        # Серийный номер даты Excel (часто попадает в JSON при ручном экспорте)
        if 29500 < n < 65000:
            try:
                return (date(1899, 12, 30) + timedelta(days=n)).isoformat()
            except (OverflowError, ValueError):
                return ""
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    if "T" in s:
        s = s.split("T", 1)[0].strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        head = s[:10]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", head):
            return head
    if re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{4}", s):
        try:
            return datetime.strptime(s, "%d.%m.%Y").date().isoformat()
        except ValueError:
            return ""
    return ""


def _norm_hex_color(value: Any) -> str | None:
    """Нормализация цвета (#RRGGBB) для ручной замены; None если невалидно/пусто."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if re.fullmatch(r"#[0-9a-fA-F]{6}", s):
        return s.lower()
    return None


def migrate_bell_schedules(raw: dict[str, Any]) -> dict[str, Any]:
    data = dict(raw)
    data.setdefault("sound_defaults", {"start": None, "end": None})
    sd = data.get("sound_defaults")
    if not isinstance(sd, dict):
        data["sound_defaults"] = {"start": None, "end": None}
    else:
        sd.setdefault("start", None)
        sd.setdefault("end", None)

    def fix_entries(entries: list[dict[str, Any]]) -> None:
        for ent in entries:
            if ent.get("is_lesson") is False and str(ent.get("label") or "").strip():
                if not str(ent.get("lesson") or "").strip():
                    ent["lesson"] = str(ent["label"]).strip()
            if "lesson" in ent and ent["lesson"] is not None and not isinstance(ent["lesson"], str):
                ent["lesson"] = str(ent["lesson"]).strip()

    for tpl in data.get("templates", []):
        tpl.setdefault("last_lesson", None)
        fix_entries(tpl.get("entries", []))
    for ov in data.get("date_overrides", []):
        ov.setdefault("last_lesson", None)
        fix_entries(ov.get("entries", []))
    return data


def load_bell_schedules() -> dict[str, Any]:
    return migrate_bell_schedules(read_json(BELL_SCHEDULES_PATH, default_bell_schedules()))


def class_matches_selector(class_key: str, selector: str) -> bool:
    """Только точное совпадение ключа (после normalize_class): «7» и «7а» — разные классы."""
    class_key = normalize_class(class_key)
    normalized_selector = normalize_class(selector)
    if not normalized_selector:
        return False
    return class_key == normalized_selector


def class_in_selected(class_key: str, selectors: list[str]) -> bool:
    if not selectors:
        return True
    return any(class_matches_selector(class_key, selector) for selector in selectors)


def class_sort_key(value: str) -> tuple[int, str]:
    normalized = normalize_class(value)
    match = re.match(r"^(\d+)\s*([a-zа-я]*)$", normalized)
    if match:
        return int(match.group(1)), match.group(2)
    return 10_000, normalized


def distinct_schedule_class_names_from_sources(
    dated: list[dict[str, Any]] | None,
    weekly: list[dict[str, Any]] | None,
    sample: list[dict[str, Any]] | None,
) -> list[str]:
    """Уникальные подписи классов из расписания по датам, недели и образца — для галочек в админке."""
    by_key: dict[str, str] = {}
    for source in (dated or [], weekly or [], sample or []):
        for item in source:
            raw = str(item.get("class_name") or item.get("class_key") or "").strip()
            if not raw:
                continue
            k = normalize_class(raw)
            by_key.setdefault(k, raw)
    out = list(by_key.values())
    out.sort(key=class_sort_key)
    return out


def pickable_classes_for_screen(screen_cfg: dict[str, Any]) -> list[str]:
    """Объединение выбора экрана и импорта расписания (для общей логики фильтров). Раньше тем же занимался ТВ-панель — см. pickable_classes_for_tv_device_panel."""
    if _TEMP_DISABLE_SCREEN_CLASS_FILTER:
        return distinct_schedule_class_names_from_sources(
            load_schedule(),
            load_full_schedule(),
            load_schedule_sample(),
        )
    from_import = distinct_schedule_class_names_from_sources(
        load_schedule(),
        load_full_schedule(),
        load_schedule_sample(),
    )
    raw_sel = screen_cfg.get("selected_classes")
    configured: list[str] = []
    if isinstance(raw_sel, list):
        configured = [str(x).strip() for x in raw_sel if str(x).strip()]
    if not configured:
        return from_import
    by_norm: dict[str, str] = {}
    for raw in configured + from_import:
        k = normalize_class(raw)
        if not k:
            continue
        by_norm.setdefault(k, raw)
    return sorted(by_norm.values(), key=class_sort_key)


def _first_enabled_schedule_widget_top_level(screen_cfg: dict[str, Any]) -> dict[str, Any] | None:
    """Виджет «расписание» среди виджетов экрана (не внутри карусели)."""
    for w in screen_cfg.get("widgets") or []:
        if not isinstance(w, dict):
            continue
        if str(w.get("type") or "").strip() != "schedule":
            continue
        if w.get("enabled") is False:
            continue
        return w
    return None


def pickable_classes_for_tv_device_panel(screen_cfg: dict[str, Any]) -> list[str]:
    """
    Классы для чекбоксов ТВ («Классы расписания на этом устройстве»): только если в конфиге экрана
    есть включённый виджет schedule. Чекбоксы строятся по settings.classes этого виджета
    (как в веб-редакторе); подписи нормализуются через импорт расписания.
    """
    if _TEMP_DISABLE_SCREEN_CLASS_FILTER:
        return distinct_schedule_class_names_from_sources(
            load_schedule(),
            load_full_schedule(),
            load_schedule_sample(),
        )
    sch = _first_enabled_schedule_widget_top_level(screen_cfg)
    if not sch:
        return []
    schedule_data = load_schedule()
    full_data = load_full_schedule()
    sample_data = load_schedule_sample()
    from_import = distinct_schedule_class_names_from_sources(schedule_data, full_data, sample_data)

    ws = sch.get("settings") if isinstance(sch.get("settings"), dict) else {}
    raw_wc = ws.get("classes")
    configured: list[str] = []
    if isinstance(raw_wc, list):
        configured = [str(x).strip() for x in raw_wc if str(x).strip()]
    if not configured:
        raw_sel = screen_cfg.get("selected_classes")
        if isinstance(raw_sel, list):
            configured = [str(x).strip() for x in raw_sel if str(x).strip()]
    if not configured:
        return from_import

    by_norm: dict[str, str] = {}
    for raw in from_import:
        k = normalize_class(raw)
        if k:
            by_norm.setdefault(k, raw)

    merged: list[tuple[str, str]] = []
    seen_k: set[str] = set()
    for c in configured:
        k = normalize_class(c)
        if not k or k in seen_k:
            continue
        seen_k.add(k)
        label = by_norm[k] if k in by_norm else str(c).strip()
        merged.append((k, label))

    merged.sort(key=lambda kv: class_sort_key(kv[1]))
    return [kv[1] for kv in merged]


def time_to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def minutes_phrase(n: int) -> str:
    """Склонение для фразы «N минут» в статусе звонков."""
    n = int(n)
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} минута"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} минуты"
    return f"{n} минут"


def as_lesson_number(value: Any) -> int | None:
    """Номер урока в шаблоне / расписании может прийти строкой из JSON или Excel."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def entry_academic_num(entry: dict[str, Any]) -> int | None:
    """Только если в «Урок» одни цифры — номер для связи с расписанием Excel (Урок1…8)."""
    raw = entry.get("lesson")
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if re.fullmatch(r"\d+", s):
        return int(s)
    return None


def entry_is_academic(entry: dict[str, Any]) -> bool:
    return entry_academic_num(entry) is not None


def entry_slot_title(entry: dict[str, Any]) -> str:
    """Краткое имя интервала для строк состояния (им. падеж после «Идёт» / «Закончился»)."""
    n = entry_academic_num(entry)
    if n is not None:
        return f"урок {n}"
    s = str(entry.get("lesson") or "").strip()
    return s if s else "Интервал"


def last_academic_lesson_ended_before(entries: list[dict[str, Any]], now_minutes: int) -> int | None:
    """Номер последнего академического урока, который уже закончился к моменту now_minutes."""
    last: int | None = None
    for e in entries:
        ln = entry_academic_num(e)
        if ln is None:
            continue
        if time_to_minutes(e["end"]) < now_minutes:
            last = ln
    return last


def next_academic_lesson_after_index(entries: list[dict[str, Any]], after_index: int) -> int | None:
    """Следующий номер академического урока среди записей с индексом > after_index."""
    for i in range(after_index + 1, len(entries)):
        ln = entry_academic_num(entries[i])
        if ln is not None:
            return ln
    return None


def display_name_for_academic_lesson_number(entries: list[dict[str, Any]], lesson_num: int | None) -> str:
    if lesson_num is None:
        return "следующего занятия"
    for e in entries:
        if entry_academic_num(e) == lesson_num:
            return entry_slot_title(e)
    return f"урок {lesson_num}"


def get_screen_bell_entries_and_bells(
    screen: dict[str, Any], target_date: date
) -> tuple[list[dict[str, Any]], dict[str, Any], str, dict[str, Any] | None]:
    """entries, bells, имя источника, активный шаблон или разовое переопределение (для last_lesson и т.п.)."""
    bells = load_bell_schedules()
    iso_date = target_date.isoformat()
    weekday = str(target_date.weekday())
    template_id = screen.get("bell_schedule_template") or "standard"

    date_override = next((item for item in bells.get("date_overrides", []) if item.get("date") == iso_date), None)
    if date_override:
        entries = date_override.get("entries", [])
        source_name = date_override.get("name", "Разовое")
        return entries, bells, source_name, date_override
    weekday_override_id = screen.get("weekday_bell_templates", {}).get(weekday) or bells.get("weekday_overrides", {}).get(weekday)
    if weekday_override_id:
        template_id = weekday_override_id
    template = next((item for item in bells.get("templates", []) if item.get("id") == template_id), None)
    if not template:
        template = bells.get("templates", [default_bell_schedules()["templates"][0]])[0]
    entries = template.get("entries", [])
    source_name = template.get("name", "Обычное")
    return entries, bells, source_name, template


def last_lesson_cap(template: dict[str, Any] | None) -> int | None:
    """Последний номер урока, после которого звонки «начало/конец» для больших номеров отключены; None — без ограничения."""
    if not template:
        return None
    raw = template.get("last_lesson")
    if raw is None:
        return None
    if isinstance(raw, str) and not str(raw).strip():
        return None
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None
    return max(1, min(24, n))


def resolve_bell_sound_url(filename: str | None) -> str | None:
    if not filename or not str(filename).strip():
        return None
    fn = str(filename).strip()
    if fn.startswith("/"):
        return fn
    p = BELL_SOUNDS_DIR / fn
    if p.is_file():
        return f"/uploads/bells/{fn}"
    p2 = UPLOADS_DIR / fn
    if p2.is_file():
        return f"/uploads/{fn}"
    return None


def bell_audio_url_to_path(url: str | None) -> Path | None:
    """Локальный путь к файлу звонка по URL из build_bell_audio_payload (только /uploads/…)."""
    if not url:
        return None
    u = str(url).strip()
    rest: str
    base: Path
    if u.startswith("/uploads/bells/"):
        rest = u[len("/uploads/bells/") :]
        base = BELL_SOUNDS_DIR
    elif u.startswith("/uploads/"):
        rest = u[len("/uploads/") :]
        base = UPLOADS_DIR
    else:
        return None
    name = Path(rest).name
    if not name:
        return None
    p = base / name
    return p if p.is_file() else None


def pick_entry_sound(ent: dict[str, Any], key: str, default_url: str | None) -> str | None:
    if key not in ent:
        return default_url
    raw = ent.get(key)
    if raw is None:
        return default_url
    s = str(raw).strip()
    if s in ("", "-", "none", "—"):
        return None
    return resolve_bell_sound_url(s) or default_url


def build_bell_audio_payload(
    screen: dict[str, Any],
    target_date: date,
    *,
    trigger_sec_window: int | None = None,
) -> dict[str, Any]:
    entries, bells, _, active_template = get_screen_bell_entries_and_bells(screen, target_date)
    cap_sched = compute_max_lesson_index_for_screen_day(screen, target_date)
    cap_tpl = last_lesson_cap(active_template)
    cap = cap_sched if cap_sched is not None else cap_tpl
    defaults = bells.get("sound_defaults") or {}
    d_start = resolve_bell_sound_url(defaults.get("start"))
    d_end = resolve_bell_sound_url(defaults.get("end"))
    rows = []
    for i, ent in enumerate(entries):
        n = entry_academic_num(ent)
        skip = cap is not None and n is not None and n > cap
        rows.append(
            {
                "index": i,
                "start": ent.get("start"),
                "end": ent.get("end"),
                "sound_start": None
                if skip
                else pick_entry_sound(ent, "sound_start", d_start),
                "sound_end": None if skip else pick_entry_sound(ent, "sound_end", d_end),
            }
        )
    tw = trigger_sec_window
    if tw is None:
        tw = DEFAULT_BELL_TRIGGER_SEC_WINDOW
    try:
        tw = int(tw)
    except (TypeError, ValueError):
        tw = DEFAULT_BELL_TRIGGER_SEC_WINDOW
    tw = max(5, min(55, tw))
    return {
        "defaults": {"start": d_start, "end": d_end},
        "entries": rows,
        "day": target_date.isoformat(),
        "trigger_sec_window": tw,
        "max_lesson_index_cap": cap,
        "max_lesson_index_from_schedule": cap_sched,
    }


def build_bell_status(
    screen: dict[str, Any], target_date: date, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    entries, _bells, source_name, _tpl = get_screen_bell_entries_and_bells(screen, target_date)
    cfg = config if config is not None else load_config()
    now_minutes = wall_clock_minutes_for_config(cfg)
    status = {
        "template_name": source_name,
        "entries": entries,
        "current_lesson": None,
        "next_lesson": None,
        "state": "done",
        "message": "Занятия завершены",
        "countdown_text": "Звонков нет",
        "schedule_title": "Уроки закончились",
    }

    if not entries:
        status["message"] = "Расписание звонков не задано"
        # Не "done": иначе виджет расписания на ТВ скрывает таблицу на сегодня (как после последнего звонка).
        status["state"] = "no_bells"
        status["countdown_text"] = "Звонки не настроены"
        status["schedule_title"] = "Расписание уроков"
        return status

    first_start = time_to_minutes(entries[0]["start"])
    if now_minutes < first_start:
        diff = first_start - now_minutes
        status["state"] = "before"
        first = entries[0]
        cap = entry_slot_title(first)
        status["next_lesson"] = entry_academic_num(first)
        mp = minutes_phrase(diff)
        status["message"] = f"До {cap}, {mp}"
        status["countdown_text"] = f"Осталось {mp}"
        status["schedule_title"] = f"До {cap}, {mp}"
        return status

    for index, entry in enumerate(entries):
        start = time_to_minutes(entry["start"])
        end = time_to_minutes(entry["end"])
        if start <= now_minutes <= end:
            diff = end - now_minutes
            if not entry_is_academic(entry):
                last_ac = last_academic_lesson_ended_before(entries, now_minutes)
                next_ac = next_academic_lesson_after_index(entries, index)
                label = entry_slot_title(entry)
                mp = minutes_phrase(diff)
                status["state"] = "activity"
                status["current_lesson"] = last_ac
                status["next_lesson"] = next_ac
                status["message"] = f"Идёт {label}, до конца {mp}"
                status["countdown_text"] = f"До конца — {mp}"
                status["schedule_title"] = f"Идёт {label}, до конца {mp}"
                return status
            ln = entry_academic_num(entry)
            if ln is None:
                ln = 0
            shown = entry_slot_title(entry)
            mp = minutes_phrase(diff)
            status["state"] = "lesson"
            status["current_lesson"] = ln
            line = f"Идёт {shown}, до перемены {mp}"
            status["message"] = line
            status["countdown_text"] = f"До перемены {mp}"
            status["schedule_title"] = line
            return status
        next_start = time_to_minutes(entries[index + 1]["start"]) if index + 1 < len(entries) else None
        if end < now_minutes and next_start is not None and now_minutes < next_start:
            diff = next_start - now_minutes
            last_ac = last_academic_lesson_ended_before(entries, now_minutes)
            next_ac = next_academic_lesson_after_index(entries, index)
            ended_entry = entries[index]
            ended_label = entry_slot_title(ended_entry)
            mp = minutes_phrase(diff)
            status["state"] = "break"
            status["current_lesson"] = last_ac
            status["next_lesson"] = next_ac
            line = f"Закончился {ended_label}. Перемена {mp}"
            status["message"] = line
            status["countdown_text"] = f"Перемена {mp}"
            status["schedule_title"] = line
            return status

    status["countdown_text"] = "Занятия завершены"
    status["schedule_title"] = "Уроки закончились"
    return status


def tomorrow_schedule_visible(bell_status: dict[str, Any]) -> bool:
    """Блок «следующий учебный день» на ТВ — только после окончания последнего интервала дня (звонки завершены)."""
    return bell_status.get("state") == "done"


def _norm_subject_cell(value: str) -> str:
    return str(value or "").strip().lower()


def _capitalize_subject_display(value: str) -> str:
    """Первая буква названия предмета в таблице на ТВ/в превью — заглавная; Excel и файлы данных не перезаписываются."""
    s = str(value or "").strip()
    if not s:
        return ""
    chars = list(s)
    for i, ch in enumerate(chars):
        if ch.isalpha():
            chars[i] = ch.upper()
            break
    return "".join(chars)


def _subject_at_lesson(row: dict[str, Any] | None, lesson_index: int) -> str:
    if not row:
        return ""
    for les in row.get("lessons") or []:
        try:
            if int(les.get("index")) != lesson_index:
                continue
        except (TypeError, ValueError):
            continue
        sub = les.get("subject")
        return "" if sub is None else str(sub).strip()
    return ""


def _row_by_weekday_class(rows: list[dict[str, Any]], weekday: int, class_key: str) -> dict[str, Any] | None:
    hit: dict[str, Any] | None = None
    want = normalize_class(class_key)
    for item in rows:
        try:
            wd = int(item.get("weekday"))
        except (TypeError, ValueError):
            continue
        if wd == weekday and normalize_class(str(item.get("class_key") or "")) == want:
            hit = item
    return hit


def lesson_indices_union(
    dated_row: dict[str, Any] | None,
    full_row: dict[str, Any] | None,
    sample_row: dict[str, Any] | None,
) -> list[int]:
    idxs: set[int] = set()
    for src in (dated_row, full_row, sample_row):
        if not src:
            continue
        for les in src.get("lessons") or []:
            try:
                idxs.add(int(les.get("index")))
            except (TypeError, ValueError):
                continue
    return sorted(idxs) if idxs else list(range(1, 9))


def collect_enriched_schedule_rows(
    *,
    day: date,
    marker_reference_date: date,
    schedule_data: list[dict[str, Any]],
    full_data: list[dict[str, Any]],
    sample_data: list[dict[str, Any]],
    overrides: list[dict[str, Any]],
    selectors: list[str],
    bell_status: dict[str, Any],
) -> list[dict[str, Any]]:
    """Те же строки, что таблица уроков на ТВ: объединение дат/недели/образца и override по дате."""
    wd = day.weekday()
    day_iso = day.isoformat()
    dated_by_key = {
        normalize_class(str(item["class_key"])): item
        for item in schedule_data
        if schedule_date_iso(item.get("date")) == day_iso and class_in_selected(item["class_key"], selectors)
    }
    keys_seen: set[str] = set(dated_by_key.keys())
    for item in full_data:
        try:
            if int(item.get("weekday")) != wd:
                continue
        except (TypeError, ValueError):
            continue
        if class_in_selected(item["class_key"], selectors):
            keys_seen.add(normalize_class(str(item["class_key"])))
    for item in sample_data:
        try:
            if int(item.get("weekday")) != wd:
                continue
        except (TypeError, ValueError):
            continue
        if class_in_selected(item["class_key"], selectors):
            keys_seen.add(normalize_class(str(item["class_key"])))

    display_names: dict[str, str] = {}
    for ck in keys_seen:
        dr = dated_by_key.get(ck)
        fr = _row_by_weekday_class(full_data, wd, ck)
        sr = _row_by_weekday_class(sample_data, wd, ck)
        display_names[ck] = str(
            (dr.get("class_name") if dr else None)
            or (fr.get("class_name") if fr else None)
            or (sr.get("class_name") if sr else None)
            or ck
        )

    sorted_keys = sorted(keys_seen, key=lambda k: class_sort_key(display_names[k]))
    apply_time_markers = day == marker_reference_date
    enriched: list[dict[str, Any]] = []

    for class_key in sorted_keys:
        dated_row = dated_by_key.get(class_key)
        full_row = _row_by_weekday_class(full_data, wd, class_key)
        sample_row = _row_by_weekday_class(sample_data, wd, class_key)
        indices = lesson_indices_union(dated_row, full_row, sample_row)
        lessons_out: list[dict[str, Any]] = []
        for lesson_index in indices:
            subject_full = _subject_at_lesson(full_row, lesson_index)
            subject_dated = _subject_at_lesson(dated_row, lesson_index) if dated_row else ""
            if dated_row is not None:
                base_subject = subject_dated if subject_dated != "" else subject_full
            else:
                base_subject = subject_full

            subject_sample = _subject_at_lesson(sample_row, lesson_index)
            use_sample = (
                sample_row is not None
                and subject_sample != ""
                and _norm_subject_cell(subject_sample) != _norm_subject_cell(subject_full)
            )
            if use_sample:
                cell_subject = subject_sample
                is_sample_diff = True
            else:
                cell_subject = base_subject
                is_sample_diff = False

            override = next(
                (
                    o
                    for o in overrides
                    if schedule_date_iso(o.get("date")) == day_iso
                    and normalize_class(str(o.get("class_key") or "")) == class_key
                    and int(o["lesson_index"]) == lesson_index
                ),
                None,
            )
            if override:
                final_subject = str(override["subject"]).strip()
                is_override = True
                is_sample_diff = False
                override_color = _norm_hex_color(override.get("color"))
            else:
                final_subject = cell_subject
                is_override = False
                override_color = None

            final_subject = _capitalize_subject_display(final_subject)

            cur = as_lesson_number(bell_status.get("current_lesson"))
            idx = as_lesson_number(lesson_index)
            lessons_out.append(
                {
                    "index": lesson_index,
                    "subject": final_subject,
                    "is_override": is_override,
                    "override_color": override_color,
                    "is_sample_diff": is_sample_diff,
                    "is_past": apply_time_markers and cur is not None and idx is not None and idx < cur,
                    "is_current": apply_time_markers and cur is not None and idx is not None and idx == cur,
                }
            )
        enriched.append({"class_name": display_names[class_key], "lessons": lessons_out})
    return enriched


def max_lesson_index_from_enriched_rows(today_rows: list[dict[str, Any]]) -> int | None:
    """Максимальный номер урока, для которого в сетке есть непустой предмет (по всем выбранным классам)."""
    best: int | None = None
    for row in today_rows:
        for les in row.get("lessons") or []:
            subj = str(les.get("subject") or "").strip()
            if not subj:
                continue
            try:
                ix = int(les.get("index"))
            except (TypeError, ValueError):
                continue
            best = ix if best is None else max(best, ix)
    return best


_ML_INDEX_CACHE: dict[tuple[Any, str], tuple[int | None, float]] = {}
_ML_INDEX_TTL_SEC = 12.0


def compute_max_lesson_index_for_screen_day(screen: dict[str, Any], day: date) -> int | None:
    """Последний урок дня по расписанию экрана (как в списке уроков); кэш на несколько секунд для ПК-цикла."""
    sid = screen.get("id")
    dk = day.isoformat()
    now = time.time()
    hit = _ML_INDEX_CACHE.get((sid, dk))
    if hit and now - hit[1] < _ML_INDEX_TTL_SEC:
        return hit[0]

    classes = screen.get("selected_classes", [])
    selectors = [normalize_class(item) for item in classes if normalize_class(item)]
    if _TEMP_DISABLE_SCREEN_CLASS_FILTER:
        selectors = []

    schedule_data = load_schedule()
    full_data = load_full_schedule()
    sample_data = load_schedule_sample()
    overrides = load_overrides()
    rows = collect_enriched_schedule_rows(
        day=day,
        marker_reference_date=date.min,
        schedule_data=schedule_data,
        full_data=full_data,
        sample_data=sample_data,
        overrides=overrides,
        selectors=selectors,
        bell_status={"current_lesson": None},
    )
    m = max_lesson_index_from_enriched_rows(rows)
    _ML_INDEX_CACHE[(sid, dk)] = (m, now)
    return m


def build_schedule_payload(
    screen: dict[str, Any], target_date: date, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    cfg = config if config is not None else load_config()
    schedule_data = load_schedule()
    full_data = load_full_schedule()
    sample_data = load_schedule_sample()
    overrides = load_overrides()
    bell_status = build_bell_status(screen, target_date, cfg)
    classes = screen.get("selected_classes", [])
    selectors = [normalize_class(item) for item in classes if normalize_class(item)]
    if _TEMP_DISABLE_SCREEN_CLASS_FILTER:
        selectors = []

    tgt_iso = target_date.isoformat()
    all_future_iso = sorted(
        {
            d_iso
            for item in schedule_data
            if (d_iso := schedule_date_iso(item.get("date")))
            and len(d_iso) >= 10
            and d_iso > tgt_iso
        }
    )
    filtered_future_iso = sorted(
        {
            d_iso
            for item in schedule_data
            if (d_iso := schedule_date_iso(item.get("date")))
            and len(d_iso) >= 10
            and d_iso > tgt_iso
            and class_in_selected(item["class_key"], selectors)
        }
    )
    future_pick = filtered_future_iso or all_future_iso
    next_school_date = (
        date.fromisoformat(future_pick[0][:10])
        if future_pick
        else date.fromordinal(target_date.toordinal() + 1)
    )

    # Показывать «следующий учебный день»:
    # - после завершения последнего интервала (обычное поведение),
    # - а также когда на "сегодня" нет строк расписания, но на следующий учебный день они есть
    #   (выходные/каникулы/пустой день — иначе ТВ показывает только «Нет данных»).
    show_next_day = tomorrow_schedule_visible(bell_status)

    def _collect(day: date, sel: list[str]) -> list[dict[str, Any]]:
        return collect_enriched_schedule_rows(
            day=day,
            marker_reference_date=target_date,
            schedule_data=schedule_data,
            full_data=full_data,
            sample_data=sample_data,
            overrides=overrides,
            selectors=sel,
            bell_status=bell_status,
        )

    sel_use = selectors
    today_rows = _collect(target_date, sel_use)
    tomorrow_rows = _collect(next_school_date, sel_use)
    if selectors and (not today_rows or not tomorrow_rows):
        t_all_today = _collect(target_date, [])
        t_all_tomorrow = _collect(next_school_date, [])
        if (not today_rows and t_all_today) or (not tomorrow_rows and t_all_tomorrow):
            sel_use = []
            today_rows = t_all_today
            tomorrow_rows = t_all_tomorrow
    if not show_next_day and not today_rows and tomorrow_rows:
        show_next_day = True
    max_lesson_index_today = max_lesson_index_from_enriched_rows(today_rows)

    return {
        "today": target_date.isoformat(),
        "next_school_day": next_school_date.isoformat(),
        "today_rows": today_rows,
        "tomorrow_rows": tomorrow_rows,
        "max_lesson_index_today": max_lesson_index_today,
        "tomorrow_schedule_visible": show_next_day,
        "bell_status": bell_status,
    }


ensure_dirs()
ensure_feedback_tables()
ensure_checkin_tables()

from . import bell_rupor_worker


@asynccontextmanager
async def _guard_school_lifespan(_app: FastAPI):
    if saas_db_enabled():
        try:
            ensure_public_schema()
        except Exception:
            pass
        try:
            _ensure_try_demo_sandbox_tenant_data()
        except Exception:
            pass
        try:
            cleanup_expired_demo_sessions()
        except Exception:
            pass
    ensure_saas_bootstrap_admin()
    hydrate_data_dir_from_database()
    cancel_sync = None
    demo_cleanup_task = None
    try:
        from .gs_cloud_sync import start_cloud_sync_background

        cancel_sync = start_cloud_sync_background()
    except Exception:
        cancel_sync = None
    bell_rupor_worker.start_worker()
    if saas_db_enabled() and deployment_mode() == "saas":
        import asyncio

        async def _demo_ttl_sweeper() -> None:
            while True:
                await asyncio.sleep(600)
                try:
                    cleanup_expired_demo_sessions()
                except Exception:
                    pass

        demo_cleanup_task = asyncio.create_task(_demo_ttl_sweeper())
    try:
        yield
    finally:
        if demo_cleanup_task is not None:
            import asyncio

            demo_cleanup_task.cancel()
            try:
                await demo_cleanup_task
            except asyncio.CancelledError:
                pass
        if cancel_sync is not None:
            cancel_sync()
        bell_rupor_worker.stop_worker()


_log = logging.getLogger(__name__)

app = FastAPI(title="GuardSchool", lifespan=_guard_school_lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# uploads/ зависят от школы (тенанта) в SaaS, поэтому отдаём через handler, а не StaticFiles mount.


@app.middleware("http")
async def _tenant_middleware(request: Request, call_next):
    """
    SaaS: по Host определяем школу и маппим data/ на tenants/<slug>/data.
    Примеры: foo.guarddoc.ru → slug foo.
    Если задан GUARDSCHOOL_PUBLIC_SCHOOL_HOST и Host совпадает с ним — slug берём из cookie
    gs_saas_tenant (после входа на общем school.*), а не из поддомена.
    """
    from .tenant_ctx import set_tenant_slug

    if deployment_mode() == "saas":
        host = _request_host_for_routing(request)
        slug: str | None = None
        # 1) Если cookie gs_saas_tenant уже есть — используем её для tenant routing,
        # даже при доступе по IP/локальному хосту (на ТВ часто открывают прямой адрес).
        cook_raw = request.cookies.get(SAAS_TENANT_COOKIE) or ""
        cook = _decode_saas_tenant_cookie_value(cook_raw)
        if cook and 1 <= len(cook) <= 64 and cook not in ("www", "admin"):
            slug = cook
        # 2) Если cookie нет, на публичном school.* тоже смотрим cookie (исторически).
        if not slug and _is_public_school_host(host):
            cook2_raw = request.cookies.get(SAAS_TENANT_COOKIE) or ""
            cook2 = _decode_saas_tenant_cookie_value(cook2_raw)
            if cook2 and 1 <= len(cook2) <= 64 and cook2 not in ("www", "admin"):
                slug = cook2
        # 3) Если cookie нет — subdomain tenant.
        if not slug and host.endswith(".guarddoc.ru"):
            left = host[: -len(".guarddoc.ru")]
            if left and left not in ("www", "admin"):
                slug = left
        # portal: guarddoc.ru / www.guarddoc.ru -> slug остаётся None
        bound = _demo_middleware_binding_slug(request, slug)
        if bound:
            slug = bound
        set_tenant_slug(slug)
        if slug:
            try:
                from .saas_db import ensure_tenant_schema, saas_db_enabled, schema_name_for_slug

                if saas_db_enabled():
                    ensure_tenant_schema(schema_name_for_slug(slug))
            except Exception:
                pass
    try:
        return await call_next(request)
    finally:
        if deployment_mode() == "saas":
            set_tenant_slug(None)


@app.get("/api/version")
def get_public_version() -> dict[str, str]:
    return {"product": "GuardSchool", "version": APP_VERSION}


@app.get("/api/_debug/tenant")
async def debug_tenant(request: Request) -> dict[str, Any]:
    """Диагностика SaaS tenant routing (только для провайдера)."""
    _require_provider_admin(request)
    from .tenant_ctx import tenant_slug as current_tenant
    from .tenant_ctx import map_data_path
    return {
        "host": _request_host_for_routing(request),
        "deployment_mode": deployment_mode(),
        "public_school_host": _public_school_host_normalized(),
        "tenant_slug": current_tenant(),
        "auth_path": str(map_data_path(AUTH_PATH)),
        "config_path": str(map_data_path(CONFIG_PATH)),
        "cookies": {
            "tenant": request.cookies.get(SAAS_TENANT_COOKIE),
            "session": request.cookies.get(SESSION_COOKIE),
        },
    }


PORTAL_ADM_COOKIE_NAME = "gs_portal_adm"
PORTAL_ADM_COOKIE_MAX_AGE_SEC = 7 * 24 * 3600


def _request_host_for_routing(request: Request) -> str:
    """
    Внешний host для SaaS-маршрутизации и портала.
    За nginx с proxy_pass на 127.0.0.1 иногда приходит Host=127.0.0.1 — тогда X-Forwarded-Host.
    """
    host = (request.headers.get("host") or "").split(":")[0].strip().lower()
    if host in ("127.0.0.1", "localhost", "[::1]") or host.startswith("127."):
        ff = (request.headers.get("x-forwarded-host") or "").strip()
        if ff:
            return ff.split(",")[0].strip().split(":")[0].strip().lower()
    return host


def _portal_request_host(request: Request) -> str:
    """Алиас: имя хоста для портала guarddoc.ru."""
    return _request_host_for_routing(request)


def _is_guarddoc_portal_host(host: str) -> bool:
    return host in ("guarddoc.ru", "www.guarddoc.ru")


def _is_guarddoc_portal(request: Request) -> bool:
    return _is_guarddoc_portal_host(_portal_request_host(request))


def _public_school_host_normalized() -> str | None:
    """Единый хост входа школ (school.*): без порта, нижний регистр."""
    raw = (os.environ.get("GUARDSCHOOL_PUBLIC_SCHOOL_HOST") or "").strip().lower()
    if not raw:
        return None
    return raw.split(":")[0]


def _is_public_school_host(host: str) -> bool:
    pub = _public_school_host_normalized()
    return bool(pub and host.split(":")[0].strip().lower() == pub)


def _saas_tenant_slug_cookie_ok(slug: str) -> bool:
    s = (slug or "").strip().lower()
    if not s or len(s) > 48:
        return False
    if s in ("www", "admin"):
        return False
    return all(ch.isalnum() or ch == "-" for ch in s)


def _encode_saas_tenant_cookie_value(slug: str) -> str:
    """Cookie должна быть ASCII: кодируем slug в base64url (utf-8) без паддинга."""
    raw = (slug or "").strip().lower()
    b64 = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")
    # Нужен префикс, иначе base64-строка неотличима от "обычного" ASCII slug.
    return f"b64.{b64}"


def _decode_saas_tenant_cookie_value(value: str) -> str | None:
    """Декодировать cookie gs_saas_tenant; поддерживаем и старый plain (ASCII) формат."""
    v = (value or "").strip()
    if not v:
        return None
    vv = v.strip()
    if vv.lower().startswith("b64."):
        vv = vv[4:]
        try:
            padded = vv + "=" * ((4 - (len(vv) % 4)) % 4)
            decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8").strip().lower()
            return decoded or None
        except Exception:
            return None
    # Старый формат: plain ASCII slug.
    vv_low = vv.lower()
    if all(ch.isalnum() or ch == "-" for ch in vv_low):
        return vv_low
    return None


def _screen_api_tenant_slug(request: Request) -> str:
    """
    Slug тенанта для SQLite API экрана (push и т.д.) — совпадает с отметками:
    сперва contextvar (middleware: cookie/decoded subdomain; Bearer tv_devices → set_tenant_slug),
    затем декодированное значение gs_saas_tenant. Сырую строку cookie «b64.…» в БД не кладём.
    """
    try:
        from .tenant_ctx import tenant_slug as _tg

        ctx = str(_tg() or "").strip()
        if ctx:
            return ctx
    except Exception:
        pass
    ck = _decode_saas_tenant_cookie_value(request.cookies.get(SAAS_TENANT_COOKIE) or "")
    if ck:
        return ck
    return "local"


def _pwa_manifest_resolve_tenant_slug(request: Request, screen_slug_norm: str) -> str | None:
    """Тенант для PWA-manifest: контекст/cookie, иначе ?gs_tv_token= + slug (SaaS). Non-SaaS — не None."""
    if deployment_mode() != "saas":
        return _screen_api_tenant_slug(request) or "local"
    resolved = _screen_api_tenant_slug(request)
    if resolved and resolved != "local":
        return resolved
    tok = str(request.query_params.get("gs_tv_token") or "").strip()
    if not tok or not saas_db_enabled():
        return None
    slug_key = (screen_slug_norm or "").strip().lower()
    if not slug_key:
        return None
    try:
        th = tv_device_token_hash(tok)
        now = utcnow()
        with connect_public() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tenant_slug, status, expires_at FROM tv_devices
                    WHERE token_hash=%s AND lower(trim(screen_slug))=%s
                    """,
                    (th, slug_key),
                )
                row = cur.fetchone()
        if not row:
            return None
        tenant_from_device, status, expires_at = row[0], row[1], row[2]
        if status != "active":
            return None
        if expires_at is not None and expires_at <= now:
            return None
        out = str(tenant_from_device or "").strip().lower()
        return out or None
    except Exception:
        return None


def _school_entry_url() -> str:
    scheme = (os.environ.get("GUARDSCHOOL_PUBLIC_SCHOOL_SCHEME") or "https").strip().lower().rstrip("/") or "https"
    host = _public_school_host_normalized() or "school.guarddoc.ru"
    return f"{scheme}://{host}/"


def _portal_adm_cookie_secret() -> bytes:
    raw = (
        (os.environ.get("GUARDSCHOOL_PORTAL_ADM_SECRET") or "").strip()
        or (os.environ.get("GUARDSCHOOL_PROVIDER_ADMIN_TOKEN") or "").strip()
        or (os.environ.get("GUARDSCHOOL_LICENSE_PEPPER") or "").strip()
        or "guardschool-portal-adm"
    )
    return hashlib.sha256(raw.encode("utf-8")).digest()


def _make_portal_adm_cookie_value() -> str:
    exp = int(time.time()) + PORTAL_ADM_COOKIE_MAX_AGE_SEC
    msg = str(exp).encode("utf-8")
    sig = hmac.new(_portal_adm_cookie_secret(), msg, hashlib.sha256).hexdigest()
    return f"{exp}|{sig}"


def _verify_portal_adm_cookie(request: Request) -> bool:
    raw = (request.cookies.get(PORTAL_ADM_COOKIE_NAME) or "").strip()
    if "|" not in raw:
        return False
    exp_s, sig = raw.split("|", 1)
    try:
        exp = int(exp_s)
    except ValueError:
        return False
    if exp < int(time.time()):
        return False
    msg = str(exp).encode("utf-8")
    expected = hmac.new(_portal_adm_cookie_secret(), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


def _portal_adm_credentials_configured() -> bool:
    u = (os.environ.get("GUARDSCHOOL_PORTAL_ADM_USERNAME") or "").strip()
    p = (os.environ.get("GUARDSCHOOL_PORTAL_ADM_PASSWORD") or "").strip()
    return bool(u and p)


def _provider_admin_configured() -> bool:
    if (os.environ.get("GUARDSCHOOL_PROVIDER_ADMIN_TOKEN") or "").strip():
        return True
    return _portal_adm_credentials_configured()


def _provider_admin_authorized(request: Request) -> bool:
    tok = (os.environ.get("GUARDSCHOOL_PROVIDER_ADMIN_TOKEN") or "").strip()
    auth = (request.headers.get("authorization") or "").strip()
    if tok and auth == f"Bearer {tok}":
        return True
    return _verify_portal_adm_cookie(request)


def _require_provider_admin(request: Request) -> None:
    if not _provider_admin_configured():
        raise HTTPException(status_code=501, detail="Provider admin is not configured.")
    if not _provider_admin_authorized(request):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _generate_license_key() -> str:
    # Читаемый ключ без спорных символов (MVP).
    raw = secrets.token_hex(12).upper()
    return f"GS-{raw[:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:24]}"


def _demo_token_hash(token: str) -> str:
    import hashlib

    pepper = (os.environ.get("GUARDSCHOOL_DEMO_PEPPER") or os.environ.get("GUARDSCHOOL_LICENSE_PEPPER") or "").encode("utf-8")
    raw = (token or "").strip().encode("utf-8")
    return hashlib.sha256(pepper + b"\n" + raw).hexdigest()


def _new_demo_isolated_slug() -> str:
    """Уникальный slug каталога для копии демо (не совпадает с боевыми tenant slug)."""
    return "d" + secrets.token_hex(12)


def _is_demo_isolated_slug(s: str) -> bool:
    return bool(re.fullmatch(r"d[0-9a-f]{24}", (s or "").strip().lower()))


def _rmtree_tenant_data_disk(slug: str) -> None:
    if deployment_mode() != "saas":
        return
    try:
        from .tenant_ctx import tenant_data_dir

        root = tenant_data_dir((slug or "").strip().lower())
        if root.is_dir():
            shutil.rmtree(root, ignore_errors=True)
        # tenant_data_dir = tenants/<slug>/data. Удаляем и tenants/<slug>, если он стал пустым.
        try:
            tenant_root = root.parent
            if tenant_root.is_dir() and not any(tenant_root.iterdir()):
                tenant_root.rmdir()
        except Exception:
            pass
    except Exception:
        pass


def _purge_isolated_demo_copy(iso_slug: str) -> None:
    """Удалить ephemeral-демо: схема PostgreSQL + каталог tenants/<isolated>/data."""
    s = (iso_slug or "").strip().lower()
    if not _is_demo_isolated_slug(s):
        return
    try:
        from .saas_db import drop_tenant_schema_if_exists

        drop_tenant_schema_if_exists(s)
    except Exception:
        pass
    _rmtree_tenant_data_disk(s)


def _provision_demo_isolated_snapshot(template_slug: str, isolated_slug: str) -> None:
    """Копия tenants/<template>/data → tenants/<isolated>/data + схема PostgreSQL для изолированного демо."""
    from .tenant_ctx import tenant_data_dir

    tpl = (template_slug or "").strip().lower()
    iso = (isolated_slug or "").strip().lower()
    if not tpl or not iso or not _is_demo_isolated_slug(iso):
        raise ValueError("Invalid demo snapshot slugs")
    src = tenant_data_dir(tpl)
    dst = tenant_data_dir(iso)
    if not src.is_dir():
        raise FileNotFoundError(f"Missing tenant data for template {tpl!r}")
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    skip_uploads = (os.environ.get("GUARDSCHOOL_DEMO_SNAPSHOT_SKIP_UPLOADS") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    kw: dict[str, Any] = {"symlinks": False}
    if skip_uploads:
        kw["ignore"] = lambda _src, names: [n for n in names if n == "uploads"]
    shutil.copytree(src, dst, **kw)
    ensure_tenant_schema(schema_name_for_slug(iso))


def _demo_middleware_binding_slug(request: Request, host_slug: str | None) -> str | None:
    """
    Если активна демо-сессия v3, подменяем tenant_slug на изолированную копию,
    но только когда Host/cookie указывают на тот же шаблонный тенант (защита от подстановки чужого slug).
    """
    from .tenant_ctx import tenant_data_dir

    tok = request.cookies.get(SESSION_COOKIE) or ""
    if not verify_demo_session_token(tok):
        return None
    bound = demo_v3_binding_from_token(tok)
    if not bound:
        return None
    tpl, iso = bound
    if not host_slug or tpl != host_slug:
        return None
    if not tenant_data_dir(iso).is_dir():
        return None
    return iso


def _tenant_ui_host_for_demo(tenant_slug: str) -> str:
    """Хост в ссылке на демо (API провайдера): либо единый GUARDSCHOOL_PUBLIC_SCHOOL_HOST, либо поддомен."""
    fixed = (os.environ.get("GUARDSCHOOL_PUBLIC_SCHOOL_HOST") or "").strip().lower()
    if fixed:
        return fixed
    return f"{tenant_slug}.guarddoc.ru"


def _try_demo_redirect_host(slug: str) -> str:
    """
    Хост редиректа публичного /try-demo.
    По умолчанию — поддомен песочницы (<slug>.guarddoc.ru), чтобы Host в middleware
    совпадал с тенантом и данные не смешивались с боевой школой.
    """
    explicit = (os.environ.get("GUARDSCHOOL_TRY_DEMO_REDIRECT_HOST") or "").strip().lower()
    if explicit:
        return explicit.split(":")[0]
    if (os.environ.get("GUARDSCHOOL_TRY_DEMO_USE_PUBLIC_SCHOOL_HOST") or "").strip().lower() in ("1", "true", "yes", "on"):
        fixed = (os.environ.get("GUARDSCHOOL_PUBLIC_SCHOOL_HOST") or "").strip().lower()
        if fixed:
            return fixed.split(":")[0]
    s = (slug or "demo").strip().lower()
    return f"{s}.guarddoc.ru"


def _try_demo_sandbox_slug() -> str:
    """Slug тенанта песочницы для /try-demo (Host → tenant_slug в SaaS). По умолчанию: demo."""
    return (os.environ.get("GUARDSCHOOL_DEMO_TENANT_SLUG") or "demo").strip().lower()


def _seed_try_demo_library_from_env() -> None:
    """
    Опционально: скопировать в data/ песочницы каталоги uploads и break_music из «эталонного» data
    (GUARDSCHOOL_TRY_DEMO_LIBRARY_DIR = абсолютный путь к корню data, например …/tenants/school/data).
    """
    from .tenant_ctx import map_data_path

    raw = (os.environ.get("GUARDSCHOOL_TRY_DEMO_LIBRARY_DIR") or "").strip()
    if not raw:
        return
    src_root = Path(raw).resolve()
    if not src_root.is_dir():
        return
    for sub, dest_base in (
        ("uploads", UPLOADS_DIR),
        ("break_music", BREAK_MUSIC_DIR),
    ):
        sub_path = src_root / sub
        if not sub_path.is_dir():
            continue
        dest = map_data_path(dest_base)
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(sub_path, dest, dirs_exist_ok=True)


def _ensure_try_demo_sandbox_tenant_data() -> None:
    """Создать tenants/<slug>/data с минимальным auth и дефолтным config для публичного демо."""
    if deployment_mode() != "saas" or not saas_db_enabled():
        return
    slug = _try_demo_sandbox_slug()
    if not slug:
        return
    from .tenant_ctx import set_tenant_slug, tenant_slug as _current_slug

    prev = _current_slug()
    set_tenant_slug(slug)
    try:
        ensure_tenant_schema(schema_name_for_slug(slug))
        ensure_dirs()
        try:
            _seed_try_demo_library_from_env()
        except Exception:
            pass
        if not AUTH_PATH.exists() or not load_auth():
            salt = secrets.token_hex(16)
            pwd = (os.environ.get("GUARDSCHOOL_TRY_DEMO_ADMIN_PASSWORD") or "").strip()
            if not pwd or not password_is_valid(pwd):
                pwd = secrets.token_urlsafe(14) + "Xa9"
                if not password_is_valid(pwd):
                    pwd = "TryDemoSandbox1a"
            user = (os.environ.get("GUARDSCHOOL_TRY_DEMO_ADMIN_USERNAME") or "try-demo").strip() or "try-demo"
            write_json(AUTH_PATH, {"username": user, "salt": salt, "password_hash": hash_password(pwd, salt)})
        reset_demo = (os.environ.get("GUARDSCHOOL_TRY_DEMO_RESET_ON_START") or "").strip().lower() in ("1", "true", "yes", "on")
        if reset_demo:
            write_json(CONFIG_PATH, sanitize_config(default_config()))
            write_json(SCHEDULE_PATH, [])
            write_json(FULL_SCHEDULE_PATH, [])
            write_json(SCHEDULE_SAMPLE_PATH, [])
            write_json(HOLIDAYS_PATH, [])
            write_json(ANNOUNCEMENTS_PATH, [])
            write_json(SCHOOL_NEWS_PATH, [])
            write_json(MARQUEE_PATH, [])
            write_json(OVERRIDES_PATH, [])
            write_json(BELL_SCHEDULES_PATH, default_bell_schedules())
        elif not CONFIG_PATH.exists():
            write_json(CONFIG_PATH, sanitize_config(default_config()))
    finally:
        set_tenant_slug(prev)


def _try_demo_ttl_minutes() -> int:
    try:
        n = int((os.environ.get("GUARDSCHOOL_TRY_DEMO_MINUTES") or "60").strip())
    except Exception:
        n = 60
    return max(5, min(180, n))


def _try_demo_public_enabled() -> bool:
    return (os.environ.get("GUARDSCHOOL_TRY_DEMO_DISABLE") or "").strip().lower() not in ("1", "true", "yes", "on")


def _demo_allow_any_tenant_token() -> bool:
    """Разрешить /demo/{{token}} на любом tenant_slug (выдача провайдером для «демо реальной школы»). По умолчанию выключено."""
    return (os.environ.get("GUARDSCHOOL_DEMO_ALLOW_ANY_TENANT") or "").strip().lower() in ("1", "true", "yes", "on")


def _demo_exit_redirect_url() -> str:
    """Куда вести гостя после «Выйти из демо» (главная портала, не /login на поддомене песочницы)."""
    u = (os.environ.get("GUARDSCHOOL_DEMO_EXIT_URL") or os.environ.get("GUARDSCHOOL_PORTAL_PUBLIC_URL") or "").strip()
    if u:
        return u.rstrip("/")
    return "https://guarddoc.ru"


def _license_ts_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _add_calendar_years(dt: datetime, years: int) -> datetime:
    """Добавить целое число календарных лет к моменту (UTC), с учётом 29 февраля."""
    if years <= 0:
        return _license_ts_utc(dt)
    d = _license_ts_utc(dt)
    y = d.year + years
    mo, da = d.month, d.day
    if mo == 2 and da == 29:
        da = min(da, calendar.monthrange(y, mo)[1])
    try:
        return d.replace(year=y, month=mo, day=da)
    except ValueError:
        return d.replace(year=y, month=2, day=28)


def _license_row_public(
    key_hash: str,
    license_no: Any,
    plan_id: str,
    status: str,
    issued_at: Any,
    expires_at: Any,
    notes: str,
    tenant_slug: str | None,
    owner_user_id: str | None,
    key_plaintext: Any = None,
) -> dict[str, Any]:
    iy: int | None = None
    ey: int | None = None
    try:
        if isinstance(issued_at, datetime):
            iy = _license_ts_utc(issued_at).year
    except Exception:
        pass
    try:
        if isinstance(expires_at, datetime):
            ey = _license_ts_utc(expires_at).year
    except Exception:
        pass
    return {
        "key_hash": key_hash,
        "license_no": int(license_no) if license_no is not None else None,
        # Полный ключ показываем только если он сохранён в БД (по запросу владельца).
        # Обычно клиенты видят только при выдаче; для восстановления — перевыпуск.
        "license_key": (str(key_plaintext) if isinstance(key_plaintext, str) and key_plaintext else None),
        "plan_id": plan_id,
        "status": status,
        "issued_at": issued_at.isoformat() if issued_at else None,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "issued_year": iy,
        "expires_year": ey,
        "notes": notes or "",
        "tenant_slug": tenant_slug or None,
        "owner_user_id": owner_user_id or None,
        "registered": bool(owner_user_id),
    }


_LICENSE_LIST_SQL = """
SELECT l.key_hash, l.license_no, l.key_plaintext, l.plan_id, l.status, l.issued_at, l.expires_at, l.notes,
       t.slug, u.id
FROM licenses l
LEFT JOIN users u ON u.license_key_hash = l.key_hash
LEFT JOIN tenants t ON t.owner_user_id = u.id
ORDER BY l.issued_at DESC
LIMIT 500
"""


@app.get("/api/provider/licenses")
def provider_list_licenses(request: Request) -> dict[str, Any]:
    _require_provider_admin(request)
    if not saas_db_enabled():
        return {"licenses": []}
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute(_LICENSE_LIST_SQL)
            rows = cur.fetchall() or []
    return {
        "licenses": [
            _license_row_public(
                r[0],  # key_hash
                r[1],  # license_no
                r[3],  # plan_id
                r[4],  # status
                r[5],  # issued_at
                r[6],  # expires_at
                r[7] or "",  # notes
                r[8],  # tenant_slug
                r[9],  # owner_user_id
                r[2],  # key_plaintext (optional)
            )
            for r in rows
        ]
    }


@app.get("/api/provider/licenses/{key_hash}")
def provider_get_license(key_hash: str, request: Request) -> dict[str, Any]:
    """Одна лицензия + признак регистрации и slug тенанта (если уже привязана)."""
    _require_provider_admin(request)
    if not saas_db_enabled():
        raise HTTPException(status_code=500, detail="SaaS database is not configured.")
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT l.key_hash, l.license_no, l.key_plaintext, l.plan_id, l.status, l.issued_at, l.expires_at, l.notes,
                       t.slug, u.id
                FROM licenses l
                LEFT JOIN users u ON u.license_key_hash = l.key_hash
                LEFT JOIN tenants t ON t.owner_user_id = u.id
                WHERE l.key_hash = %s
                """,
                (key_hash,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    lic = _license_row_public(
        row[0],  # key_hash
        row[1],  # license_no
        row[3],  # plan_id
        row[4],  # status
        row[5],  # issued_at
        row[6],  # expires_at
        row[7] or "",  # notes
        row[8],  # tenant_slug
        row[9],  # owner_user_id
        row[2],  # key_plaintext (optional)
    )
    return {"license": lic}


@app.post("/api/provider/licenses")
async def provider_create_license(request: Request) -> dict[str, Any]:
    _require_provider_admin(request)
    if not saas_db_enabled():
        raise HTTPException(status_code=500, detail="SaaS database is not configured.")
    body = await request.json()
    plan_id = str(body.get("plan_id") or "").strip() or "free"
    notes = str(body.get("notes") or "").strip()
    default_years: int | None = None
    raw_def = (os.environ.get("GUARDSCHOOL_LICENSE_DEFAULT_TERM_YEARS") or "").strip()
    if raw_def:
        try:
            dy = int(raw_def)
            if dy > 0:
                default_years = dy
        except ValueError:
            pass
    expires_at: datetime | None = None
    if body.get("expires_years") is not None:
        try:
            y = int(body.get("expires_years"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="expires_years must be integer.") from None
        expires_at = None if y <= 0 else _add_calendar_years(utcnow(), y)
    elif body.get("expires_days") is not None:
        try:
            d = int(body.get("expires_days"))
            if d > 0:
                expires_at = utcnow() + timedelta(days=d)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="expires_days must be integer.") from None
    elif default_years is not None:
        expires_at = _add_calendar_years(utcnow(), default_years)
    key = _generate_license_key()
    key_h = license_key_hash(key)
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM plans WHERE id=%s", (plan_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=400, detail="Unknown plan_id")
            cur.execute(
                "INSERT INTO licenses (key_hash, key_plaintext, plan_id, status, expires_at, notes) VALUES (%s,%s,%s,'active',%s,%s)",
                (key_h, key, plan_id, expires_at, notes),
            )
        conn.commit()
    # Вернём и license_no для “номера”, который можно восстановить/support.
    lic_no = None
    try:
        with connect_public() as conn2:
            with conn2.cursor() as cur2:
                cur2.execute("SELECT license_no FROM licenses WHERE key_hash=%s", (key_h,))
                r = cur2.fetchone()
                lic_no = r[0] if r else None
    except Exception:
        pass
    return {
        "status": "ok",
        "license_no": int(lic_no) if lic_no is not None else None,
        "license_key": key,
        "key_hash": key_h,
        "plan_id": plan_id,
        "expires_at": expires_at.isoformat() if expires_at else None,
    }


@app.post("/api/provider/licenses/{key_hash}/status")
async def provider_set_license_status(key_hash: str, request: Request) -> dict[str, str]:
    _require_provider_admin(request)
    if not saas_db_enabled():
        raise HTTPException(status_code=500, detail="SaaS database is not configured.")
    body = await request.json()
    status = str(body.get("status") or "").strip() or "active"
    if status not in ("active", "disabled", "revoked"):
        raise HTTPException(status_code=400, detail="Invalid status")
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE licenses SET status=%s WHERE key_hash=%s", (status, key_hash))
            if cur.rowcount <= 0:
                raise HTTPException(status_code=404, detail="Not found")
        conn.commit()
    return {"status": "ok"}


def _parse_license_expires_at_raw(raw: Any) -> datetime | None:
    """None из JSON → снять срок; ISO-строка → дата окончания (UTC)."""
    if raw is None:
        return None
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            iso = s.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid expires_at (use ISO-8601).") from None
    raise HTTPException(status_code=400, detail="Invalid expires_at type.")


@app.patch("/api/provider/licenses/{key_hash}")
async def provider_patch_license(key_hash: str, request: Request) -> dict[str, str]:
    """
    Частичное обновление: notes, plan_id, status, expires_at, expires_days,
    expires_years_from_issue (целое лет от даты выдачи лицензии; 0 = снять срок),
    expires_years_from_now (целое лет от текущего момента).
    Смена plan_id разрешена и после регистрации школы (переход между планами).
    """
    _require_provider_admin(request)
    if not saas_db_enabled():
        raise HTTPException(status_code=500, detail="SaaS database is not configured.")
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object required.")
    sets: list[str] = []
    params: list[Any] = []
    if "status" in body:
        st = str(body.get("status") or "").strip() or "active"
        if st not in ("active", "disabled", "revoked"):
            raise HTTPException(status_code=400, detail="Invalid status")
        sets.append("status=%s")
        params.append(st)
    if "notes" in body:
        sets.append("notes=%s")
        params.append(str(body.get("notes") or ""))
    if "plan_id" in body:
        pid = str(body.get("plan_id") or "").strip() or "free"
        sets.append("plan_id=%s")
        params.append(pid)
    exp_dt: datetime | None | str = "omit"
    years_from_issue: int | None = None
    if "expires_at" in body:
        exp_dt = _parse_license_expires_at_raw(body.get("expires_at"))
    elif "expires_years_from_issue" in body and body.get("expires_years_from_issue") is not None:
        try:
            ny = int(body.get("expires_years_from_issue"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="expires_years_from_issue must be integer.") from None
        if ny <= 0:
            exp_dt = None
        else:
            exp_dt = "fetch_issue"
            years_from_issue = ny
    elif "expires_years_from_now" in body and body.get("expires_years_from_now") is not None:
        try:
            ny = int(body.get("expires_years_from_now"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="expires_years_from_now must be integer.") from None
        exp_dt = None if ny <= 0 else _add_calendar_years(utcnow(), ny)
    elif "expires_days" in body and body.get("expires_days") is not None:
        try:
            d = int(body.get("expires_days"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="expires_days must be integer.")
        if d <= 0:
            exp_dt = None
        else:
            exp_dt = utcnow() + timedelta(days=d)
    if not sets and exp_dt == "omit":
        raise HTTPException(
            status_code=400,
            detail=(
                "No fields to update (status, notes, plan_id, expires_at, expires_days, "
                "expires_years_from_issue, expires_years_from_now)."
            ),
        )
    with connect_public() as conn:
        with conn.cursor() as cur:
            if exp_dt == "fetch_issue":
                if years_from_issue is None:
                    raise HTTPException(status_code=500, detail="Internal expiry resolution error.")
                cur.execute("SELECT issued_at FROM licenses WHERE key_hash=%s", (key_hash,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Not found")
                issued = row[0]
                base = issued if isinstance(issued, datetime) else utcnow()
                exp_dt = _add_calendar_years(base, years_from_issue)
            if "plan_id" in body:
                pid = str(body.get("plan_id") or "").strip() or "free"
                cur.execute("SELECT id FROM plans WHERE id=%s", (pid,))
                if not cur.fetchone():
                    raise HTTPException(status_code=400, detail="Unknown plan_id")
            if exp_dt != "omit":
                sets.append("expires_at=%s")
                params.append(exp_dt)
            if not sets:
                raise HTTPException(status_code=400, detail="No fields to update.")
            sql = f"UPDATE licenses SET {', '.join(sets)} WHERE key_hash=%s"
            params.append(key_hash)
            cur.execute(sql, tuple(params))
            if cur.rowcount <= 0:
                raise HTTPException(status_code=404, detail="Not found")
            if "plan_id" in body:
                pid_sync = str(body.get("plan_id") or "").strip() or "free"
                cur.execute(
                    "UPDATE tenants SET plan_id=%s WHERE owner_user_id IN "
                    "(SELECT id FROM users WHERE license_key_hash=%s)",
                    (pid_sync, key_hash),
                )
        conn.commit()
    return {"status": "ok"}


def _provider_purge_license_db_and_disk(key_hash: str) -> dict[str, Any]:
    """
    Удалить лицензию вместе с пользователем SaaS, строкой tenants, схемой тенанта в PostgreSQL,
    tv_* / demo_sessions по slug и каталогом tenants/<slug>/data на диске.
    """
    import psycopg2.sql as sql

    slugs: list[str] = []
    schemas: list[str] = []
    user_ids: list[str] = []
    demo_iso_slugs: list[str] = []
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM licenses WHERE key_hash=%s LIMIT 1", (key_hash,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Not found")
            cur.execute(
                "SELECT u.id, t.slug, t.schema_name FROM users u "
                "LEFT JOIN tenants t ON t.owner_user_id = u.id "
                "WHERE u.license_key_hash=%s",
                (key_hash,),
            )
            for row in cur.fetchall() or []:
                uid, slug, schema = row[0], row[1], row[2]
                if uid and str(uid) not in user_ids:
                    user_ids.append(str(uid))
                if slug:
                    s = str(slug).strip()
                    if s and s not in slugs:
                        slugs.append(s)
                if schema and str(schema) not in schemas:
                    schemas.append(str(schema))
            for sch in schemas:
                cur.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(sch)))
            if slugs:
                cur.execute(
                    "SELECT DISTINCT isolated_slug FROM demo_sessions WHERE tenant_slug = ANY(%s) AND COALESCE(isolated_slug,'')<>''",
                    (slugs,),
                )
                demo_iso_slugs = [str(r[0]).strip().lower() for r in (cur.fetchall() or []) if r and r[0]]
                cur.execute(
                    "DELETE FROM tv_devices WHERE tenant_slug = ANY(%s)",
                    (slugs,),
                )
                cur.execute(
                    "DELETE FROM tv_access WHERE tenant_slug = ANY(%s)",
                    (slugs,),
                )
                cur.execute(
                    "DELETE FROM demo_sessions WHERE tenant_slug = ANY(%s)",
                    (slugs,),
                )
            if user_ids:
                cur.execute(
                    "DELETE FROM sessions WHERE user_id = ANY(%s)",
                    (user_ids,),
                )
                cur.execute(
                    "DELETE FROM tenants WHERE owner_user_id = ANY(%s)",
                    (user_ids,),
                )
                cur.execute(
                    "DELETE FROM users WHERE license_key_hash=%s",
                    (key_hash,),
                )
            cur.execute("DELETE FROM licenses WHERE key_hash=%s", (key_hash,))
            if cur.rowcount <= 0:
                raise HTTPException(status_code=404, detail="Not found")
        conn.commit()
    if deployment_mode() == "saas":
        try:
            from .tenant_ctx import tenant_data_dir

            for iso in demo_iso_slugs:
                _purge_isolated_demo_copy(iso)
            for slug in slugs:
                root = tenant_data_dir(slug)
                if root.is_dir():
                    shutil.rmtree(root, ignore_errors=True)
        except Exception:
            pass
    return {"status": "ok", "purged": True, "tenant_slugs": slugs, "schemas_dropped": schemas}


@app.delete("/api/provider/licenses/{key_hash}")
def provider_delete_license(
    key_hash: str,
    request: Request,
    purge: bool = Query(
        False,
        description="Полное удаление: пользователь, тенант, схема PostgreSQL, tv_* и каталог tenants/<slug>.",
    ),
) -> dict[str, Any]:
    """Без purge — только неиспользованная лицензия. С purge=1 — снять тестовую/лишнюю школу вместе с данными."""
    _require_provider_admin(request)
    if not saas_db_enabled():
        raise HTTPException(status_code=500, detail="SaaS database is not configured.")
    if purge:
        return _provider_purge_license_db_and_disk(key_hash)
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE license_key_hash=%s LIMIT 1", (key_hash,))
            if cur.fetchone():
                raise HTTPException(
                    status_code=409,
                    detail="License already used for registration; use DELETE with purge=1 to remove tenant and license, or revoke/disable.",
                )
            cur.execute("DELETE FROM licenses WHERE key_hash=%s", (key_hash,))
            if cur.rowcount <= 0:
                raise HTTPException(status_code=404, detail="Not found")
        conn.commit()
    return {"status": "ok"}


def _provider_tenant_slug_param_safe(slug: str) -> str:
    s = (slug or "").strip()
    if not s or len(s) > 64 or "/" in s or "\\" in s or ".." in s:
        raise HTTPException(status_code=400, detail="Invalid tenant slug.")
    return s


def _provider_purge_tenant_by_slug(slug: str) -> dict[str, Any]:
    """
    Удалить одну школу по slug: схема PostgreSQL (Identifier), tv_*, сессии, tenants, users, licenses, каталог tenants/<slug>.
    Для «осиротевших» каталогов без строки в tenants — только rm на сервере.
    """
    import psycopg2.sql as sql

    slug_n = _provider_tenant_slug_param_safe(slug)
    schema_dropped: str | None = None
    demo_iso: list[str] = []
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT t.schema_name, t.owner_user_id, u.license_key_hash FROM tenants t "
                "INNER JOIN users u ON u.id = t.owner_user_id WHERE t.slug = %s",
                (slug_n,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Tenant not found.")
            schema_name, owner_id, lic_hash = str(row[0]), str(row[1]), str(row[2])
            schema_dropped = schema_name
            cur.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema_name)))
            cur.execute("DELETE FROM tv_devices WHERE tenant_slug=%s", (slug_n,))
            cur.execute("DELETE FROM tv_access WHERE tenant_slug=%s", (slug_n,))
            cur.execute(
                "SELECT DISTINCT isolated_slug FROM demo_sessions WHERE tenant_slug=%s AND COALESCE(isolated_slug,'')<>''",
                (slug_n,),
            )
            demo_iso = [str(r[0]).strip().lower() for r in (cur.fetchall() or []) if r and r[0]]
            cur.execute("DELETE FROM demo_sessions WHERE tenant_slug=%s", (slug_n,))
            cur.execute("DELETE FROM sessions WHERE user_id=%s", (owner_id,))
            cur.execute("DELETE FROM tenants WHERE slug=%s", (slug_n,))
            cur.execute("DELETE FROM users WHERE id=%s", (owner_id,))
            cur.execute("DELETE FROM licenses WHERE key_hash=%s", (lic_hash,))
        conn.commit()
    if deployment_mode() == "saas":
        for iso in demo_iso:
            _purge_isolated_demo_copy(iso)
        try:
            from .tenant_ctx import tenant_data_dir

            root = tenant_data_dir(slug_n)
            if root.is_dir():
                shutil.rmtree(root, ignore_errors=True)
        except Exception:
            pass
    return {"status": "ok", "purged": True, "slug": slug_n, "schema_dropped": schema_dropped}


@app.delete("/api/provider/tenants/{slug}")
def provider_delete_tenant(
    slug: str,
    request: Request,
    confirm: bool = Query(False, description="Подтверждение: confirm=1"),
) -> dict[str, Any]:
    """Полное удаление школы по slug (вместе с лицензией владельца). Нужен confirm=1."""
    _require_provider_admin(request)
    if not saas_db_enabled():
        raise HTTPException(status_code=500, detail="SaaS database is not configured.")
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Refusing to delete tenant without confirm=1 (deletes license, DB schema, and tenant data directory).",
        )
    return _provider_purge_tenant_by_slug(slug)


@app.post("/api/provider/demo")
async def provider_create_demo(request: Request) -> dict[str, Any]:
    _require_provider_admin(request)
    if deployment_mode() != "saas" or not saas_db_enabled():
        raise HTTPException(status_code=500, detail="SaaS is not configured.")
    try:
        cleanup_expired_demo_sessions()
    except Exception:
        pass
    body = await request.json()
    slug = str(body.get("tenant_slug") or "").strip().lower()
    try:
        ttl_min = int(body.get("expires_minutes") or 60)
    except Exception:
        ttl_min = 60
    ttl_min = max(5, min(180, ttl_min))
    if not slug:
        raise HTTPException(status_code=400, detail="tenant_slug required")
    from .tenant_ctx import tenant_data_dir

    if not tenant_data_dir(slug).is_dir():
        raise HTTPException(status_code=404, detail="Tenant data not found on server.")
    isolated = _new_demo_isolated_slug()
    try:
        _provision_demo_isolated_snapshot(slug, isolated)
    except Exception:
        _purge_isolated_demo_copy(isolated)
        raise HTTPException(
            status_code=503,
            detail="Could not allocate an isolated demo copy (snapshot).",
        ) from None
    token = secrets.token_urlsafe(24)
    th = _demo_token_hash(token)
    expires_at = utcnow() + timedelta(minutes=ttl_min)
    try:
        with connect_public() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO demo_sessions (token_hash, tenant_slug, isolated_slug, expires_at) VALUES (%s,%s,%s,%s)",
                    (th, slug, isolated, expires_at),
                )
            conn.commit()
    except Exception:
        _purge_isolated_demo_copy(isolated)
        raise
    return {
        "status": "ok",
        "token": token,
        "url_path": f"/demo/{token}",
        "tenant_host": _tenant_ui_host_for_demo(slug),
        "expires_at": expires_at.isoformat(),
    }


@app.get("/api/portal/cms")
def api_portal_cms_public() -> dict[str, Any]:
    """Публичный контент главной страницы портала экосистемы (без авторизации)."""
    return load_portal_cms_merged()


@app.get("/api/provider/portal-cms")
def api_provider_portal_cms_get(request: Request) -> dict[str, Any]:
    _require_provider_admin(request)
    return {"cms": load_portal_cms_merged()}


@app.put("/api/provider/portal-cms")
async def api_provider_portal_cms_put(request: Request) -> dict[str, Any]:
    _require_provider_admin(request)
    raw_body = await request.json()
    raw_cms = raw_body.get("cms") if isinstance(raw_body, dict) and "cms" in raw_body else raw_body
    if raw_cms is None:
        raise HTTPException(status_code=400, detail="Expected JSON body with a cms object.")
    try:
        dumped = json.dumps(raw_cms if isinstance(raw_cms, (dict, list)) else {}, ensure_ascii=False)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.") from None
    if len(dumped.encode("utf-8")) > 480_000:
        raise HTTPException(status_code=413, detail="CMS payload too large.")
    payload = sanitize_portal_cms_payload(raw_cms)
    write_portal_cms(payload)
    return {"status": "ok", "cms": payload}


@app.get("/demo/{token}")
def demo_login(token: str, request: Request, response: Response) -> Response:
    if deployment_mode() != "saas" or not saas_db_enabled():
        raise HTTPException(status_code=404, detail="Not found.")
    try:
        cleanup_expired_demo_sessions()
    except Exception:
        pass
    from .tenant_ctx import tenant_slug as current_tenant

    slug = current_tenant()
    if not slug:
        raise HTTPException(status_code=404, detail="Not found.")
    sandbox = _try_demo_sandbox_slug()
    if slug != sandbox and not _demo_allow_any_tenant_token():
        loc = admin_ui_lang(request)
        raise HTTPException(
            status_code=403,
            detail=admin_msg(
                loc,
                "Гостевое демо только на отдельной песочнице. Откройте «Демо» с главной страницы портала, "
                "а не адрес кабинета вашей школы.",
                "Guest demo is only on the separate sandbox. Open “Demo” from the portal home page, not your school admin URL.",
            ),
        )
    th = _demo_token_hash(token)
    now = utcnow()
    isolated_res = ""
    expires_at = None
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE demo_sessions
                SET consumed_at = now()
                WHERE token_hash=%s AND tenant_slug=%s AND expires_at > %s AND consumed_at IS NULL
                RETURNING COALESCE(isolated_slug,''), expires_at
                """,
                (th, slug, now),
            )
            row = cur.fetchone()
            if row:
                isolated_res = str(row[0] or "").strip().lower()
                expires_at = row[1]
            if not row:
                cur.execute(
                    "SELECT expires_at, consumed_at FROM demo_sessions WHERE token_hash=%s AND tenant_slug=%s",
                    (th, slug),
                )
                row2 = cur.fetchone()
                if not row2:
                    raise HTTPException(status_code=403, detail="Demo token invalid.")
                exp2, cons2 = row2[0], row2[1]
                if not exp2 or exp2 <= now:
                    raise HTTPException(status_code=403, detail="Demo token expired.")
                if cons2:
                    raise HTTPException(status_code=403, detail="Demo token already used.")
                raise HTTPException(status_code=403, detail="Demo token invalid.")
        conn.commit()

    auth = load_auth()
    if not auth:
        raise HTTPException(status_code=428, detail="Tenant is not configured.")
    try:
        exp_epoch = int(expires_at.timestamp())  # type: ignore[union-attr]
    except Exception:
        exp_epoch = int(time.time()) + 3600
    if isolated_res and _is_demo_isolated_slug(isolated_res):
        token2 = create_demo_session_token(exp_epoch, template_slug=slug, isolated_slug=isolated_res)
    else:
        token2 = create_demo_session_token(exp_epoch)
    sec = session_cookie_secure(request)
    max_age = max(60, exp_epoch - int(time.time()))
    response = RedirectResponse("/", status_code=302)
    obliterate_session_cookies(response)
    response.set_cookie(
        SESSION_COOKIE,
        token2,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=sec,
        path="/",
    )
    if isolated_res and _is_demo_isolated_slug(isolated_res):
        response.set_cookie(
            SAAS_TENANT_COOKIE,
            _encode_saas_tenant_cookie_value(isolated_res),
            max_age=max_age,
            httponly=True,
            samesite="lax",
            secure=sec,
            path="/",
        )
    return response


def _tenant_upload_local_file(full_path_under_uploads_rel: Path) -> FileResponse | None:
    """Строим FileResponse для файла под UPLOADS тенанта; None если файла нет или путь небезопасен."""
    import mimetypes

    from .tenant_ctx import map_data_path

    base = map_data_path(UPLOADS_DIR).resolve()
    rel = Path(str(full_path_under_uploads_rel or "").lstrip("/").replace("\\", "/"))
    clean_parts = [p for p in rel.parts if p not in ("..", ".", "")]
    if not clean_parts:
        return None
    full = (base / Path(*clean_parts)).resolve()
    if base not in full.parents and full != base:
        return None
    if not full.is_file():
        return None
    mt, _ = mimetypes.guess_type(str(full))
    return FileResponse(full, media_type=mt or "application/octet-stream")


@app.get("/uploads/{path:path}")
def uploads_file(request: Request, path: str) -> Response:
    """
    В SaaS /uploads/ мапится на tenants/<slug>/data/uploads.
    Иконки из manifest подгружает Chromium отдельно: иногда контекст тенанта в middleware уже сброшен,
    но cookie gs_saas_tenant ещё есть — второй раз читаем cookie и подставляем slug.
    """
    from .tenant_ctx import set_tenant_slug, tenant_slug

    resp = _tenant_upload_local_file(Path(path))
    if resp:
        return resp

    prev = tenant_slug()
    if deployment_mode() == "saas":
        ck = _decode_saas_tenant_cookie_value(request.cookies.get(SAAS_TENANT_COOKIE) or "")
        if ck and ck.strip().lower():
            try:
                set_tenant_slug(ck.strip().lower())
                resp2 = _tenant_upload_local_file(Path(path))
                if resp2:
                    return resp2
            finally:
                try:
                    set_tenant_slug(prev)
                except Exception:
                    pass
    raise HTTPException(status_code=404, detail="Not found.")


@app.get("/sw.js")
def service_worker_js() -> Response:
    # Для PWA eligibility (manifest + SW). Не кешируем: экраны часто должны обновляться сразу.
    return FileResponse(
        STATIC_DIR / "sw.js",
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.get("/api/sync/status")
def api_sync_status(request: Request) -> dict[str, Any]:
    """Проверка ревизии для локального агента (Bearer GUARDSCHOOL_SYNC_TOKEN на сервере)."""
    _require_sync_bearer(request)
    return public_revision_payload()


@app.get("/api/sync/bundle")
def api_sync_bundle(request: Request) -> StreamingResponse:
    """Полный ZIP-экспорт для подтягивания в локальную школу."""
    _require_sync_bearer(request)
    bundle = export_bundle_bytes()
    return StreamingResponse(
        io.BytesIO(bundle),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="guardschool_export.zip"'},
    )


@app.get("/", response_class=HTMLResponse)
def root(request: Request) -> Response:
    # guarddoc.ru — портал экосистемы (лендинг/регистрация), не админка школы
    if _is_guarddoc_portal(request):
        return FileResponse(STATIC_DIR / "portal.html")
    if not load_auth():
        return RedirectResponse("/setup")
    if not is_authenticated(request):
        return RedirectResponse("/login")
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


@app.get("/register", response_class=HTMLResponse)
def portal_register_page(request: Request) -> Response:
    """Публичная страница регистрации SaaS (только для guarddoc.ru)."""
    if not _is_guarddoc_portal(request):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(STATIC_DIR / "portal_register.html")


@app.get("/guardschool")
def portal_guardschool_legacy_redirect(request: Request) -> Response:
    """Старая ссылка: контент перенесён в CMS → страница /about/guardschool."""
    if not _is_guarddoc_portal(request):
        raise HTTPException(status_code=404, detail="Not found")
    return RedirectResponse("/about/guardschool", status_code=302)


@app.get("/about/{slug}", response_class=HTMLResponse)
def portal_about_cms_page(request: Request, slug: str) -> Response:
    """Публичные страницы раздела «О продукте»: контент в portal_cms.json → pages.{slug}."""
    if not _is_guarddoc_portal(request):
        raise HTTPException(status_code=404, detail="Not found")
    sk = str(slug or "").strip().lower()
    if not sk or not re.match(r"^[a-z0-9][a-z0-9-]*$", sk):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(STATIC_DIR / "about_page.html")


@app.get("/provider")
def portal_provider_redirect(request: Request) -> Response:
    """Старая ссылка: провайдерский UI перенесён на /ADM."""
    if not _is_guarddoc_portal(request):
        raise HTTPException(status_code=404, detail="Not found")
    return RedirectResponse("/ADM", status_code=302)


@app.get("/adm")
def portal_adm_redirect_lowercase() -> Response:
    """Редирект /adm → /ADM (без проверки Host: иначе за кривым прокси был бы 404 вместо редиректа)."""
    return RedirectResponse("/ADM", status_code=302)


@app.post("/api/portal-adm/login")
async def portal_adm_login(request: Request) -> Response:
    if not _is_guarddoc_portal(request):
        raise HTTPException(status_code=404, detail="Not found")
    if not _portal_adm_credentials_configured():
        raise HTTPException(status_code=501, detail="Portal ADM login is not configured.")
    body = await request.json()
    u = str(body.get("username") or "").strip()
    p = str(body.get("password") or "").strip()
    eu = (os.environ.get("GUARDSCHOOL_PORTAL_ADM_USERNAME") or "").strip()
    ep = (os.environ.get("GUARDSCHOOL_PORTAL_ADM_PASSWORD") or "").strip()
    if u != eu or p != ep:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    out = JSONResponse({"status": "ok"})
    sec = session_cookie_secure(request)
    out.set_cookie(
        PORTAL_ADM_COOKIE_NAME,
        _make_portal_adm_cookie_value(),
        max_age=PORTAL_ADM_COOKIE_MAX_AGE_SEC,
        httponly=True,
        samesite="lax",
        secure=sec,
        path="/",
    )
    return out


@app.post("/api/portal-adm/logout")
def portal_adm_logout(request: Request) -> Response:
    if not _is_guarddoc_portal(request):
        raise HTTPException(status_code=404, detail="Not found")
    out = JSONResponse({"status": "ok"})
    sec = session_cookie_secure(request)
    out.delete_cookie(PORTAL_ADM_COOKIE_NAME, path="/", secure=sec, httponly=True, samesite="lax")
    return out


@app.get("/ADM", response_class=HTMLResponse)
def portal_adm_page(request: Request) -> Response:
    """Служебная страница лицензий: логин/пароль из env или fallback на Bearer-страницу."""
    if not _is_guarddoc_portal(request):
        raise HTTPException(status_code=404, detail="Not found")
    if _portal_adm_credentials_configured():
        if _verify_portal_adm_cookie(request):
            return FileResponse(STATIC_DIR / "portal_adm.html")
        return FileResponse(STATIC_DIR / "portal_adm_login.html")
    if (os.environ.get("GUARDSCHOOL_PROVIDER_ADMIN_TOKEN") or "").strip():
        return FileResponse(STATIC_DIR / "portal_provider.html")
    return HTMLResponse(
        content=(
            "<!doctype html><html lang='ru'><head><meta charset='utf-8' /><title>ADM</title></head>"
            "<body style='font-family:system-ui;padding:24px;max-width:720px;line-height:1.5'>"
            "<h1 style='font-size:1.1rem'>ADM: лицензии не настроены</h1>"
            "<p>На сервере GuardSchool (процесс uvicorn) задайте <strong>один</strong> из вариантов:</p>"
            "<ul>"
            "<li><strong>Вход по логину/паролю</strong> в веб-форме: переменные "
            "<code>GUARDSCHOOL_PORTAL_ADM_USERNAME</code> и <code>GUARDSCHOOL_PORTAL_ADM_PASSWORD</code> "
            "(пароль ≥8 символов, буквы и цифры), затем перезапуск сервиса. Откройте "
            "<a href='/ADM'>/ADM</a> (именно заглавные ADM).</li>"
            "<li><strong>Провайдер по токену</strong> (страница с Bearer): "
            "<code>GUARDSCHOOL_PROVIDER_ADMIN_TOKEN</code> — тот же секрет вставляется в браузере на /ADM.</li>"
            "</ul>"
            "<p>Доступ к ADM включается <strong>только</strong> этими переменными в окружении процесса на сервере. "
            "Логин и пароль администратора школы (например, на поддомене <code>school.*</code>) — отдельная сущность и к выдаче лицензий не относится.</p>"
            "</body></html>"
        ),
        status_code=503,
    )


@app.get("/demo-setup", response_class=HTMLResponse)
def portal_demo_setup_page(request: Request) -> Response:
    """Страница выдачи временного демо-доступа (только guarddoc.ru)."""
    if not _is_guarddoc_portal(request):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(STATIC_DIR / "portal_demo_setup.html")


@app.get("/try-demo")
def portal_try_demo(request: Request) -> Response:
    """
    Публичный «быстрый демо» с портала: редирект на поддомен песочницы с одноразовым /demo/{token}.
    Для каждого токена создаётся копия данных песочницы (отдельный каталог тенанта); гости не делят одно дерево файлов.
    Шаблон — GUARDSCHOOL_DEMO_TENANT_SLUG (по умолчанию demo). Сессия после /demo/ — демо-cookie с привязкой к копии.
    """
    if not _is_guarddoc_portal(request):
        raise HTTPException(status_code=404, detail="Not found")
    if not _try_demo_public_enabled():
        raise HTTPException(status_code=503, detail="Try-demo is disabled.")
    if deployment_mode() != "saas" or not saas_db_enabled():
        raise HTTPException(status_code=503, detail="SaaS is not configured.")
    try:
        cleanup_expired_demo_sessions()
    except Exception:
        pass
    slug = _try_demo_sandbox_slug()
    isolated = _new_demo_isolated_slug()
    try:
        _provision_demo_isolated_snapshot(slug, isolated)
    except Exception:
        _purge_isolated_demo_copy(isolated)
        raise HTTPException(
            status_code=503,
            detail="Could not allocate an isolated demo copy (snapshot).",
        ) from None
    token = secrets.token_urlsafe(24)
    th = _demo_token_hash(token)
    ttl_min = _try_demo_ttl_minutes()
    expires_at = utcnow() + timedelta(minutes=ttl_min)
    try:
        with connect_public() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO demo_sessions (token_hash, tenant_slug, isolated_slug, expires_at) VALUES (%s,%s,%s,%s)",
                    (th, slug, isolated, expires_at),
                )
            conn.commit()
    except Exception:
        _purge_isolated_demo_copy(isolated)
        raise
    target_host = _try_demo_redirect_host(slug)
    scheme = (os.environ.get("GUARDSCHOOL_PUBLIC_SCHOOL_SCHEME") or "https").strip().lower()
    if scheme not in ("http", "https"):
        scheme = "https"
    return RedirectResponse(f"{scheme}://{target_host}/demo/{token}", status_code=302)


@app.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request) -> Response:
    # В SaaS на общем школьном хосте (school.*) первичная настройка не нужна:
    # админ = владелец лицензии, а auth.json создаётся регистрацией.
    host = _portal_request_host(request)
    if deployment_mode() == "saas" and saas_db_enabled() and _is_public_school_host(host):
        raise HTTPException(status_code=404, detail="Not found.")
    return FileResponse(STATIC_DIR / "setup.html")


@app.get("/login", response_class=HTMLResponse)
def login_page() -> Response:
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/brand-logo")
def brand_logo() -> Response:
    logo_path = resolve_brand_logo_path()
    if not logo_path:
        raise HTTPException(status_code=404, detail="Логотип не найден (положите ico.png рядом с программой или в сборку).")
    return FileResponse(logo_path)


@app.get("/favicon.ico")
def favicon_ico() -> Response:
    """Убирает 404 в консоли; при наличии ico.png в корне — тот же файл, что /brand-logo."""
    logo_path = resolve_brand_logo_path()
    if logo_path:
        return FileResponse(logo_path, media_type="image/png")
    # Минимальный прозрачный PNG 1×1 — без добавления файла в репозиторий.
    return Response(
        content=base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/aurd9kAAAAASUVORK5CYII="
        ),
        media_type="image/png",
    )


@app.get("/screen/{slug}", response_class=HTMLResponse)
def screen_page(request: Request, slug: str) -> HTMLResponse:
    """
    HTML-страница ТВ. В SaaS обложки/загрузки живут в tenants/<slug>/data, а <img> не шлёт Bearer.
    Поэтому при заходе на экран с gs_tv_token из URL выставляем cookie тенанта, чтобы /uploads/* резолвился
    в правильный tenant data/ (иначе на ТВ «битые» картинки из-за 404 на /uploads/...).
    """
    if deployment_mode() == "saas":
        try:
            # Явный tenant в URL (на случай, если ТВ открывает экран без device-token / без доступа к БД).
            explicit_tenant = str(request.query_params.get("gs_tenant") or "").strip().lower()
            if explicit_tenant and 1 <= len(explicit_tenant) <= 64 and explicit_tenant not in ("www", "admin"):
                from .tenant_ctx import set_tenant_slug

                set_tenant_slug(explicit_tenant)

            if saas_db_enabled():
                tok = str(request.query_params.get("gs_tv_token") or "").strip()
                scr = _normalize_screen_slug_for_api(slug) or str(slug or "").strip().lower()
                if tok and scr:
                    from .tenant_ctx import set_tenant_slug

                    th = tv_device_token_hash(tok)
                    now = utcnow()
                    with connect_public() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                SELECT tenant_slug, status, expires_at FROM tv_devices
                                WHERE token_hash=%s AND lower(trim(screen_slug)) = %s
                                """,
                                (th, scr),
                            )
                            row = cur.fetchone()
                    if row:
                        tenant_from_device, status, expires_at = row[0], row[1], row[2]
                        if status == "active" and (expires_at is None or expires_at > now):
                            ts = str(tenant_from_device or "").strip().lower()
                            if ts:
                                set_tenant_slug(ts)
        except Exception:
            pass

    # ТВ часто кэширует HTML и JS; подставляем версию в URL статики (плейсхолдер в screen.html).
    raw = (STATIC_DIR / "screen.html").read_text(encoding="utf-8")
    slug_for_manifest = _normalize_screen_slug_for_api(slug) or str(slug or "").strip().lower()
    manifest_line = ""
    if slug_for_manifest and re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", slug_for_manifest):
        tok_q = str(request.query_params.get("gs_tv_token") or "").strip()
        q_parts = [f"v={quote(APP_VERSION, safe='')}"]
        if tok_q:
            q_parts.insert(0, f"gs_tv_token={quote(tok_q, safe='')}")
        q = "?" + "&".join(q_parts)
        manifest_line = (
            f'<link rel="manifest" href="/pwa/screen/{quote(slug_for_manifest, safe="")}.webmanifest{q}" />\n'
        )
    html = raw.replace("__GS_ASSETS_VER__", APP_VERSION).replace("__GS_PWA_MANIFEST_LINK__", manifest_line)
    resp = HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )
    if deployment_mode() == "saas":
        try:
            from .tenant_ctx import tenant_slug as _tenant_slug

            ts2 = str(_tenant_slug() or "").strip()
            if ts2 and 1 <= len(ts2) <= 64 and ts2 not in ("www", "admin"):
                # Для TV/браузеров на устройствах чаще открывают screen по http внутри сети.
                # Secure-cookie в таком случае не сохраняется, и /uploads снова "теряет" tenant.
                sec = (getattr(request.url, "scheme", "") == "https")
                resp.set_cookie(
                    SAAS_TENANT_COOKIE,
                    _encode_saas_tenant_cookie_value(ts2),
                    max_age=3600 * 24 * 30,
                    httponly=True,
                    samesite="lax",
                    secure=sec,
                    path="/",
                )
        except Exception:
            pass
    return resp


@app.get("/screen/{slug}/menu")
def screen_menu(slug: str) -> Response:
    return RedirectResponse(f"/screen/{slug}?gs_menu=1")


@app.get("/screens", response_class=HTMLResponse)
def screens_index_page(request: Request) -> Response:
    """Страница выбора экрана. В SaaS с БД — только после входа (иначе утечка списка slug)."""
    if deployment_mode() == "saas" and saas_db_enabled() and not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=302)
    return FileResponse(
        STATIC_DIR / "screens.html",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


@app.get("/api/bootstrap")
def bootstrap_state() -> dict[str, Any]:
    return {
        "configured": bool(load_auth()),
        "saas_mode": saas_mode(),
        "deployment_mode": deployment_mode(),
    }


@app.post("/api/saas/register")
async def saas_register(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """
    SaaS: регистрация по ключу лицензии.
    Создаёт тенанта (схему) и auth.json в tenant data/.
    """
    if deployment_mode() != "saas":
        raise HTTPException(status_code=404, detail="Not found.")
    if not saas_db_enabled():
        raise HTTPException(status_code=500, detail="SaaS database is not configured.")
    lic_key = str(payload.get("license_key") or "").strip()
    password = str(payload.get("password") or "").strip()
    slug = str(payload.get("tenant_slug") or "").strip().lower()
    if not lic_key:
        raise HTTPException(status_code=400, detail="license_key is required.")
    if not password_is_valid(password):
        raise HTTPException(status_code=400, detail="Пароль: не менее 8 символов, нужны буквы и цифры.")

    # tenant_slug в SaaS — внутренний id: используем в cookie и в schema name.
    # Для публичной регистрации можно не передавать tenant_slug: сгенерируем безопасный.
    if not slug:
        slug = f"s{secrets.token_hex(6)}"  # 13 символов, латиница+цифры
    if not _saas_tenant_slug_cookie_ok(slug):
        raise HTTPException(status_code=400, detail="tenant_slug: используйте латиницу/цифры/дефис (например, s1a2b3c4d5e6f).")

    key_h = license_key_hash(lic_key)
    now = utcnow()
    schema = schema_name_for_slug(slug)

    with connect_public() as conn:
        with conn.cursor() as cur:
            # license must exist and be active
            cur.execute("SELECT plan_id, status, expires_at FROM licenses WHERE key_hash=%s", (key_h,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Лицензия не найдена.")
            plan_id, status, expires_at = row[0], row[1], row[2]
            if str(status) != "active":
                raise HTTPException(status_code=403, detail="Лицензия отключена.")
            if expires_at is not None and expires_at <= now:
                raise HTTPException(status_code=403, detail="Срок лицензии истёк.")

            # one tenant per license (MVP)
            cur.execute("SELECT id, slug FROM tenants WHERE owner_user_id IN (SELECT id FROM users WHERE license_key_hash=%s)", (key_h,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Эта лицензия уже использована.")
            cur.execute("SELECT id FROM tenants WHERE slug=%s", (slug,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Поддомен уже занят.")

            user_id = random_id("u")
            salt = secrets.token_hex(16)
            pwd_hash = hash_password(password, salt)
            cur.execute(
                "INSERT INTO users (id, license_key_hash, password_salt, password_hash) VALUES (%s,%s,%s,%s)",
                (user_id, key_h, salt, pwd_hash),
            )
            tenant_id = random_id("t")
            cur.execute(
                "INSERT INTO tenants (id, slug, schema_name, plan_id, owner_user_id) VALUES (%s,%s,%s,%s,%s)",
                (tenant_id, slug, schema, plan_id, user_id),
            )
        conn.commit()

    # create schema + snapshot table
    ensure_tenant_schema(schema)

    # create per-tenant auth.json for existing /api/login flow
    from .tenant_ctx import set_tenant_slug

    set_tenant_slug(slug)
    try:
        ensure_dirs()
        write_json(
            AUTH_PATH,
            {"username": lic_key, "salt": salt, "password_hash": pwd_hash},
        )
    finally:
        set_tenant_slug(None)

    return {
        "status": "ok",
        "tenant": {"slug": slug, "schema": schema},
        "school_entry_url": _school_entry_url(),
    }


@app.post("/api/setup")
async def setup_admin(request: Request, username: str = Form(...), password: str = Form(...)) -> dict[str, str]:
    host = _portal_request_host(request)
    if deployment_mode() == "saas" and saas_db_enabled() and _is_public_school_host(host):
        raise HTTPException(status_code=404, detail="Not found.")
    loc = admin_ui_lang(request)
    if load_auth():
        raise HTTPException(
            status_code=409,
            detail=admin_msg(loc, "Администратор уже создан.", "Administrator account already exists."),
        )
    if not password_is_valid(password):
        raise HTTPException(
            status_code=400,
            detail=admin_msg(
                loc,
                "Пароль: не менее 8 символов, нужны буквы и цифры.",
                "Password: at least 8 characters, with letters and digits.",
            ),
        )
    salt = secrets.token_hex(16)
    write_json(AUTH_PATH, {"username": username.strip(), "salt": salt, "password_hash": hash_password(password, salt)})
    return {"status": "ok"}


@app.post("/api/login")
async def login(request: Request, response: Response, username: str = Form(...), password: str = Form(...)) -> dict[str, str]:
    loc = admin_ui_lang(request)
    host = _portal_request_host(request)

    if deployment_mode() == "saas" and saas_db_enabled() and _is_public_school_host(host):
        u = username.strip()
        if not u:
            raise HTTPException(
                status_code=401,
                detail=admin_msg(loc, "Неверный логин или пароль.", "Invalid username or password."),
            )
        key_h = license_key_hash(u)
        with connect_public() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.password_salt, u.password_hash, t.slug
                    FROM users u
                    INNER JOIN tenants t ON t.owner_user_id = u.id
                    WHERE u.license_key_hash = %s
                    """,
                    (key_h,),
                )
                row = cur.fetchone()
        if not row or hash_password(password, row[0]) != row[1]:
            raise HTTPException(
                status_code=401,
                detail=admin_msg(loc, "Неверный логин или пароль.", "Invalid username or password."),
            )
        tenant_slug_val = str(row[2]).strip().lower()
        from .tenant_ctx import set_tenant_slug, tenant_slug as tenant_slug_get

        prev = tenant_slug_get()
        set_tenant_slug(tenant_slug_val)
        try:
            auth = load_auth()
            if not auth:
                raise HTTPException(
                    status_code=503,
                    detail=admin_msg(
                        loc,
                        "Данные школы не подготовлены. Обратитесь к поддержке.",
                        "School tenant data is not provisioned.",
                    ),
                )
            if str(auth.get("username") or "").strip() != u:
                raise HTTPException(
                    status_code=503,
                    detail=admin_msg(
                        loc,
                        "Несоответствие учётной записи и данных школы. Обратитесь к поддержке.",
                        "Auth data mismatch for this school.",
                    ),
                )
        finally:
            set_tenant_slug(prev)
        obliterate_session_cookies(response)
        token = create_session_token(u, auth)
        sec = session_cookie_secure(request)
        response.set_cookie(
            SESSION_COOKIE,
            token,
            httponly=True,
            samesite="lax",
            secure=sec,
            path="/",
        )
        response.set_cookie(
            SAAS_TENANT_COOKIE,
            _encode_saas_tenant_cookie_value(tenant_slug_val),
            httponly=True,
            samesite="lax",
            secure=sec,
            path="/",
        )
        return {"status": "ok"}

    auth = load_auth()
    if not auth:
        raise HTTPException(
            status_code=428,
            detail=admin_msg(loc, "Сначала создайте администратора.", "Create the administrator account first."),
        )
    if username.strip() != auth["username"] or hash_password(password, auth["salt"]) != auth["password_hash"]:
        raise HTTPException(
            status_code=401,
            detail=admin_msg(loc, "Неверный логин или пароль.", "Invalid username or password."),
        )
    sec = session_cookie_secure(request)
    obliterate_session_cookies(response)
    token = create_session_token(username.strip(), auth)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=sec,
        path="/",
    )
    return {"status": "ok"}


@app.post("/api/logout")
def logout(request: Request, response: Response) -> dict[str, str]:
    """Снимает обычную и демо-сессию (cookie `SESSION_COOKIE`, оба варианта Secure)."""
    obliterate_session_cookies(response)
    return {"status": "ok"}


@app.get("/api/admin/config")
async def get_admin_config(request: Request) -> Response:
    require_auth(request)
    cfg = load_config()
    # Метаданные, которые нужны UI, но не должны сохраняться в config.json.
    cfg["_meta"] = {
        "saas_mode": saas_mode(),
        "deployment_mode": deployment_mode(),
        "app_version": APP_VERSION,
        "demo_session": is_demo_session_for_admin_ui(request),
        "demo_exit_url": _demo_exit_redirect_url(),
    }
    return JSONResponse(cfg, headers={"Cache-Control": "no-store"})


@app.post("/api/admin/rss-news/refresh")
def post_admin_rss_news_refresh(request: Request) -> dict[str, Any]:
    require_auth(request)
    cfg = load_config()
    items = load_rss_news(cfg, force_refresh=True)
    return {"items": items, "count": len(items)}


@app.post("/api/admin/config")
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
    return {"status": "ok"}


@app.get("/api/admin/sync-status")
def get_admin_sync_status(request: Request) -> dict[str, Any]:
    require_auth(request)
    if deployment_mode() == "saas":
        raise HTTPException(status_code=404, detail="Not found.")
    from .gs_jsonio import read_json

    return {
        "sync_state": read_json(SYNC_STATE_PATH, {}),
        "data_revision": compute_data_revision(),
        "cloud_revision": read_revision_from_database(),
    }


@app.post("/api/admin/sync-now")
async def post_admin_sync_now(request: Request) -> dict[str, Any]:
    require_auth(request)
    if deployment_mode() == "saas":
        raise HTTPException(status_code=404, detail="Not found.")
    from .gs_cloud_sync import run_cloud_sync_once

    return await run_cloud_sync_once()


@app.get("/api/admin/background-gallery")
def admin_background_gallery(request: Request, folder: str = "") -> dict[str, Any]:
    require_auth(request)
    f = safe_rel_uploads_subdir(folder)
    return {
        "folder": f,
        "folders": list_background_subdirs_from_uploads(),
        "images": list_background_images_from_uploads(f),
    }


@app.post("/api/admin/screen-bg-next")
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
                detail="В uploads/bells нет файлов. Загрузите звук в разделе «Звонки».",
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


@app.post("/api/admin/audio-stream-test-send")
async def post_audio_stream_test_send(request: Request) -> dict[str, str]:
    """Совместимость со старыми клиентами; предпочтительно /api/admin/pc-audio-test-play."""
    return await _handle_pc_audio_test_play(request)


@app.post("/api/admin/pc-audio-test-play")
async def post_pc_audio_test_play(request: Request) -> dict[str, str]:
    """Тест Рупор из сайдбара (есть только в актуальном сервере — иначе в браузере будет 404)."""
    return await _handle_pc_audio_test_play(request)


@app.get("/api/admin/audio-stream-last-send")
def get_audio_stream_last_send(request: Request) -> dict[str, Any]:
    """Последний сеанс ffplay (команда и stderr)."""
    require_auth(request)
    return {"last": bell_rupor_worker.get_last_ffmpeg_send()}


@app.get("/api/admin/audio-stream-status")
def get_audio_stream_status(request: Request) -> dict[str, Any]:
    """Процесс ffplay и последний результат — для панели админки."""
    require_auth(request)
    return bell_rupor_worker.get_ffmpeg_status()


@app.post("/api/admin/audio-stream-stop")
def post_audio_stream_stop(request: Request) -> dict[str, Any]:
    """Остановить текущее воспроизведение (ffplay)."""
    require_auth(request)
    return bell_rupor_worker.stop_current_stream()


@app.get("/api/admin/break-music-files")
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


@app.post("/api/admin/break-music-preview")
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


@app.post("/api/admin/upload-background")
async def upload_background(request: Request, file: UploadFile = File(...)) -> dict[str, str]:
    require_auth(request)
    _reject_if_saas_upload(request)
    suffix = Path(file.filename or "background").suffix or ".jpg"
    target = UPLOADS_DIR / f"{secrets.token_hex(8)}{suffix}"
    target.write_bytes(await file.read())
    return {"path": f"/uploads/{target.name}"}


@app.post("/api/admin/upload-widget-image")
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


@app.post("/api/admin/upload-holidays")
async def upload_holidays(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
    require_auth(request)
    _reject_if_saas_upload(request)
    lang = admin_ui_lang(request)
    suffix = Path(file.filename or "holidays.xlsx").suffix or ".xlsx"
    temp = UPLOADS_DIR / f"holidays_import{suffix}"
    temp.write_bytes(await file.read())
    parsed = parse_holidays_excel(temp, lang=lang)
    write_json(HOLIDAYS_PATH, parsed)
    return {"status": "ok", "rows": len(parsed)}


@app.post("/api/admin/upload-announcements")
async def upload_announcements(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
    require_auth(request)
    _reject_if_saas_upload(request)
    lang = admin_ui_lang(request)
    suffix = Path(file.filename or "announcements.xlsx").suffix or ".xlsx"
    temp = UPLOADS_DIR / f"announcements_import{suffix}"
    temp.write_bytes(await file.read())
    parsed = parse_announcements_excel(temp, lang=lang)
    write_json(ANNOUNCEMENTS_PATH, parsed)
    return {"status": "ok", "rows": len(parsed)}


@app.post("/api/admin/upload-marquee")
async def upload_marquee(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
    require_auth(request)
    _reject_if_saas_upload(request)
    lang = admin_ui_lang(request)
    suffix = Path(file.filename or "marquee.xlsx").suffix or ".xlsx"
    temp = UPLOADS_DIR / f"marquee_import{suffix}"
    temp.write_bytes(await file.read())
    parsed = parse_marquee_excel(temp, lang=lang)
    write_json(MARQUEE_PATH, parsed)
    return {"status": "ok", "rows": len(parsed)}


@app.post("/api/admin/upload-schedule")
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
    return {"status": "ok", "rows": len(parsed)}


@app.post("/api/admin/upload-full-schedule")
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
    return {"status": "ok", "rows": len(parsed)}


@app.post("/api/admin/upload-schedule-sample")
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
    return {"status": "ok", "rows": len(parsed)}


@app.post("/api/admin/upload-bell-sound")
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


@app.post("/api/admin/upload-emergency-sound")
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


@app.post("/api/admin/school-news/cover-upload")
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


@app.post("/api/admin/school-news/cover-fetch")
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
            data = resp.read(1024 * 1024 + 1)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Не удалось загрузить картинку: {e}")
    url = _save_school_news_image_bytes(nid, data, content_type=ct, source_name=url_raw)
    return {"status": "ok", "news_id": nid, "url": url}


@app.get("/api/admin/bell-sounds")
def list_bell_sounds(request: Request) -> dict[str, Any]:
    require_auth(request)
    ensure_dirs()
    files = []
    if BELL_SOUNDS_DIR.exists():
        for p in sorted(BELL_SOUNDS_DIR.iterdir()):
            if p.is_file():
                files.append({"filename": p.name, "url": f"/uploads/bells/{p.name}"})
    return {"files": files}


@app.get("/api/admin/schedule")
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


@app.get("/api/admin/history")
def get_change_history(request: Request) -> dict[str, Any]:
    require_auth(request)
    return {"history": load_change_log(), "app_version": APP_VERSION}


@app.get("/api/admin/school-news")
def get_admin_school_news(request: Request) -> dict[str, Any]:
    require_auth(request)
    return {"items": load_school_news()}


@app.post("/api/admin/school-news")
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


@app.delete("/api/admin/school-news/{news_id}")
def delete_admin_school_news(request: Request, news_id: str) -> dict[str, Any]:
    require_auth(request)
    nid = str(news_id or "").strip()
    if not nid:
        raise HTTPException(status_code=400, detail="Не указан id новости.")
    existing = load_school_news()
    deleted = next((x for x in existing if str(x.get("id") or "") == nid), None)
    rows = [item for item in existing if str(item.get("id") or "") != nid]
    write_json(SCHOOL_NEWS_PATH, rows)
    # Удаляем локальные картинки новости (обложка и ссылки из HTML)
    try:
        if deleted:
            _safe_unlink_upload_url(str(deleted.get("cover_image") or ""))
            for u in _extract_school_news_local_upload_urls(str(deleted.get("content") or "")):
                _safe_unlink_upload_url(u)
    except Exception:
        pass
    return {"status": "ok", "items": rows}


@app.get("/api/school-news")
def get_public_school_news(limit: int = Query(default=3, ge=1, le=30)) -> dict[str, Any]:
    rows = [item for item in load_school_news() if item.get("is_active", True)]
    return {"items": rows[:limit]}


@app.get("/api/school-news/{news_id}")
def get_public_school_news_item(news_id: str) -> dict[str, Any]:
    nid = str(news_id or "").strip()
    row = next(
        (
            item
            for item in load_school_news()
            if str(item.get("id") or "") == nid and item.get("is_active", True)
        ),
        None,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Новость не найдена.")
    return {"item": row}


@app.get("/school-news/{news_id}", response_class=HTMLResponse)
def school_news_page(news_id: str) -> HTMLResponse:
    nid = str(news_id or "").strip()
    row = next((item for item in load_school_news() if str(item.get("id") or "") == nid and item.get("is_active", True)), None)
    if not row:
        return HTMLResponse("<h1>Новость не найдена</h1>", status_code=404)
    title = html.escape(str(row.get("title") or "Новость школы"))
    content = str(row.get("content") or "")
    # Делает ссылки кликабельными/безопаснее в выдаче страницы новости.
    # (TinyMCE сам генерит <a>, но target/rel полезны на телефонах.)
    try:
        content = re.sub(
            r'(?is)<a\s+(?![^>]*\btarget=)([^>]*href\s*=\s*["\'][^"\']+["\'][^>]*)>',
            r'<a target="_blank" rel="noopener" \1>',
            content,
        )
    except Exception:
        pass
    cover = str(row.get("cover_image") or "").strip()
    cover_html = f'<img src="{html.escape(cover)}" alt="" style="max-width:100%;border-radius:14px;margin:0 0 16px;">' if cover else ""
    dt = html.escape(str(row.get("created_at") or ""))
    body = (
        "<!doctype html><html lang=\"ru\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{title}</title><style>body{{margin:0;background:#0b1220;color:#e2e8f0;font:16px/1.5 Arial,sans-serif}}main{{max-width:900px;margin:0 auto;padding:20px}}h1{{margin:0 0 8px}}.meta{{opacity:.8;margin:0 0 12px}}a{{color:#38bdf8}}a:visited{{color:#60a5fa}}</style></head>"
        f"<body><main><h1>{title}</h1><p class=\"meta\">{dt}</p>{cover_html}<article>{content}</article></main></body></html>"
    )
    return HTMLResponse(body)


@app.post("/api/admin/overrides")
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
    return {"status": "ok"}


@app.post("/api/admin/bells")
async def save_bells(request: Request) -> dict[str, str]:
    require_auth(request)
    payload = await request.json()
    _saas_check_quota_for_path(request, BELL_SCHEDULES_PATH, payload)
    write_json(BELL_SCHEDULES_PATH, payload)
    return {"status": "ok"}


@app.get("/api/admin/export")
def export_admin_bundle(request: Request) -> StreamingResponse:
    require_auth(request)
    bundle = export_bundle_bytes()
    filename = f'gorniitv_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
    return StreamingResponse(
        io.BytesIO(bundle),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/admin/export-weekly-schedule")
def export_weekly_schedule_bundle(request: Request) -> StreamingResponse:
    require_auth(request)
    bundle = export_weekly_schedule_bundle_bytes()
    filename = f'guardschool_weekly_schedule_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
    return StreamingResponse(
        io.BytesIO(bundle),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/admin/weekly-schedule-template.xlsx")
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


@app.get("/api/admin/import-excel-sample.xlsx")
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


@app.post("/api/admin/import")
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


@app.post("/api/admin/import-weekly-schedule")
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
    return {
        "status": "ok",
        "full_schedule_rows": len(load_full_schedule()),
        "schedule_sample_rows": len(load_schedule_sample()),
    }


@app.post("/api/admin/preview-payload")
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
    screen_eff = apply_emergency_template_to_screen(dict(screen), cfg)
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
    }
    return JSONResponse(content=body)


@app.get("/api/screens-index")
def get_screens_index(request: Request) -> dict[str, Any]:
    """Список экранов для /screens. В SaaS с БД — только для авторизованной сессии."""
    if deployment_mode() == "saas" and saas_db_enabled():
        require_auth(request)
    config = load_config()
    items = []
    for item in config.get("screens") or []:
        if item.get("is_active") is False:
            continue
        sl = str(item.get("slug") or "").strip()
        if not sl:
            continue
        items.append(
            {
                "name": item.get("name") or sl,
                "slug": sl,
                "path": f"/screen/{sl}",
            }
        )
    return {"screens": items}


@app.get("/api/screen/{slug}")
def get_screen(request: Request, slug: str) -> JSONResponse:
    slug_key = _normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    _require_tv_access_for_screen(request, slug_key)
    config = load_config()
    screen0 = next(
        (
            item
            for item in (config.get("screens") or [])
            if _normalize_screen_slug_for_api(str(item.get("slug") or "")) == slug_key and item.get("is_active", True)
        ),
        None,
    )
    screen = screen0
    if not screen:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    pickable = pickable_classes_for_tv_device_panel(screen0)
    qp = request.query_params
    # Фильтр gs_classes только в мобильном режиме экрана; иначе игнорируем (ТВ/сетка = только конфиг).
    raw_classes = str(qp.get("gs_classes") or "").strip()
    if (
        not _TEMP_DISABLE_SCREEN_CLASS_FILTER
        and raw_classes
        and bool(screen0.get("mobile_mode"))
    ):
        parts = [p.strip() for p in raw_classes.split(",") if p.strip()]
        parts = parts[:12]
        if parts:
            # shallow copy: не мутируем config.json в памяти
            screen = dict(screen0)
            screen["selected_classes"] = parts
    record_screen_poll(
        request,
        str(screen0.get("slug") or slug_key),
        str(qp.get("gs_client") or "").strip(),
        str(qp.get("gs_label") or "").strip(),
        str(qp.get("gs_device") or "").strip(),
        str(screen.get("name") or slug_key).strip(),
    )
    today = calendar_today_for_config(config)
    audio = sanitize_audio_stream(config.get("audio_stream"))
    sched_body = build_schedule_payload(screen, today, config)
    tr = len((sched_body.get("today_rows") or [])) if isinstance(sched_body, dict) else 0
    screen_out = apply_emergency_template_to_screen(screen, config)
    payload = {
        "screen": screen_out,
        "device_widget_types": device_widget_types_for_tv_device_panel(config, screen_out.get("widgets") or []),
        "pickable_classes": pickable,
        "serverTime": datetime.now().isoformat(),
        "schedule": sched_body,
        "holidays": load_holidays(),
        "announcements": load_announcements(),
        "school_news": load_school_news(),
        "marquee": load_marquee_items(),
        "rss_news": load_rss_news(config),
        "background_gallery": list_background_images_from_uploads(screen.get("background_rotate_folder")),
        "bell_audio": build_bell_audio_payload(
            screen,
            today,
            trigger_sec_window=audio_trigger_sec_window(audio),
        ),
        "display": display_settings_dict(config),
        "revision": compute_data_revision(),
        "app_version": APP_VERSION,
    }
    return JSONResponse(
        content=payload,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Guardschool-App-Version": APP_VERSION,
            "X-GS-Schedule-Today-Rows": str(tr),
            "X-GS-Schedule-Cal-Day": today.isoformat(),
        },
    )


@app.post("/api/screen/{slug}/feedback")
async def post_screen_feedback(request: Request, slug: str) -> dict[str, Any]:
    slug_key = _normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    _require_tv_access_for_screen(request, slug_key)
    config = load_config()
    screen = next(
        (
            item
            for item in (config.get("screens") or [])
            if _normalize_screen_slug_for_api(str(item.get("slug") or "")) == slug_key and item.get("is_active", True)
        ),
        None,
    )
    if not screen:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    if not bool(screen.get("enable_feedback")):
        raise HTTPException(status_code=403, detail="Обратная связь отключена для этого экрана.")
    body = await request.json()
    device_hash = str(body.get("device_hash") or "").strip()[:128]
    message = str(body.get("message") or "").strip()
    if not device_hash:
        raise HTTPException(status_code=400, detail="Не передан device_hash.")
    if len(message) < 2:
        raise HTTPException(status_code=400, detail="Сообщение слишком короткое.")
    if len(message) > 2000:
        message = message[:2000]
    if not can_send_feedback(device_hash, cooldown_minutes=5):
        raise HTTPException(status_code=429, detail="Можно отправлять не чаще 1 сообщения в 5 минут.")
    saved = create_feedback_message(
        tenant_id=_screen_api_tenant_slug(request), device_hash=device_hash, message=message
    )
    return {"status": "ok", **saved}


@app.get("/api/admin/feedback")
def admin_feedback_list(request: Request, include_hidden: bool = Query(False)) -> dict[str, Any]:
    require_auth(request)
    return {"items": list_feedback_messages(limit=500, include_hidden=bool(include_hidden))}


@app.post("/api/admin/feedback/{message_id}/read")
def admin_feedback_mark_read(message_id: int, request: Request) -> dict[str, Any]:
    require_auth(request)
    mark_feedback_read(message_id)
    return {"status": "ok"}


@app.post("/api/admin/feedback/{message_id}/hide")
def admin_feedback_hide(message_id: int, request: Request) -> dict[str, Any]:
    require_auth(request)
    hide_feedback(message_id)
    return {"status": "ok"}


@app.post("/api/admin/feedback/block-hash")
async def admin_feedback_block_hash(request: Request) -> dict[str, Any]:
    require_auth(request)
    body = await request.json()
    h = str(body.get("device_hash") or "").strip()[:128]
    if not h:
        raise HTTPException(status_code=400, detail="Пустой device_hash.")
    block_feedback_hash(h)
    return {"status": "ok"}


@app.post("/api/checkin/event")
async def api_checkin_post_event(request: Request) -> dict[str, Any]:
    """Отметка с экрана: нужны slug экрана и id виджета «Отметка» (checkin_submit). Данные привязаны к токену клиента."""
    body = await request.json()
    screen_slug_raw = str(body.get("screen_slug") or "").strip()
    submit_widget_id = str(body.get("submit_widget_id") or "").strip()
    slug_key = _normalize_screen_slug_for_api(screen_slug_raw)
    if not slug_key or not submit_widget_id:
        raise HTTPException(status_code=400, detail="Укажите screen_slug и submit_widget_id.")
    cfg = load_config()
    screen = _screen_config_by_slug(cfg, slug_key)
    if not screen:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    submit_w = _find_submit_widget(screen, submit_widget_id)
    if not submit_w or submit_w.get("enabled") is False:
        raise HTTPException(status_code=404, detail="Виджет отметки не найден или выключен.")
    places = _resolve_checkin_submit_places(screen, submit_w)
    allowed_ids = {p["id"] for p in places}
    if not allowed_ids:
        raise HTTPException(status_code=400, detail="Не заданы места: укажите места у виджета или привяжите виджет сводки.")
    place_id = str(body.get("place_id") or "").strip()
    level = str(body.get("level") or "").strip().lower()
    comment = str(body.get("comment") or "").strip()
    device_name = str(body.get("device_name") or "").strip()
    device_hash = str(body.get("device_hash") or "").strip()
    if place_id not in allowed_ids:
        raise HTTPException(status_code=400, detail="Неизвестное место для этого экрана.")
    auth = (request.headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        _require_tv_access_for_screen(request, slug_key)
    tenant_id = _screen_api_tenant_slug(request)
    try:
        saved = insert_checkin_event(
            tenant_id,
            device_hash,
            device_name,
            place_id,
            level,
            comment,
            screen_slug=slug_key,
            submit_widget_id=submit_widget_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    _en = enrich_checkin_event_for_client(cfg, {"created_at": saved.get("created_at"), "confirmed_at": ""})
    try:
        _notify_push_checkin_journal_new_row(
            cfg=cfg,
            tenant_id=tenant_id,
            screen=screen,
            submit_w=submit_w,
            events_screen_slug=slug_key,
            saved=saved,
            place_id=place_id,
            level=level,
            device_name=device_name,
            comment=comment,
        )
    except Exception:
        pass
    return {
        "status": "ok",
        **saved,
        "created_date": _en.get("created_date") or "",
        "created_time": _en.get("created_time") or "",
    }


@app.get("/api/screen/{slug}/checkin/board")
def api_screen_checkin_board(
    request: Request,
    slug: str,
    monitor_widget_id: str = Query(...),
    period: str = Query("day", alias="range"),
) -> dict[str, Any]:
    """Сводка и журнал для виджета «Сводка отметок» на ТВ (по токену доступа к экрану)."""
    slug_key = _normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    _require_tv_access_for_screen(request, slug_key)
    cfg = load_config()
    tenant_id = _checkin_tenant_from_request(request)
    return _checkin_board_payload(cfg, tenant_id, slug_key, monitor_widget_id, period)


@app.get("/api/screen/{slug}/checkin/export.csv")
def api_screen_checkin_export_csv(
    request: Request,
    slug: str,
    monitor_widget_id: str = Query(...),
    period: str = Query("day", alias="range"),
) -> Response:
    slug_key = _normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    _require_tv_access_for_screen(request, slug_key)
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
    tenant_id = _checkin_tenant_from_request(request)
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


@app.get("/api/admin/checkin/board")
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


@app.get("/api/admin/checkin/export.csv")
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


def _checkin_tenant_from_request(request: Request) -> str:
    return _screen_api_tenant_slug(request)


@app.post("/api/screen/{slug}/checkin/confirm")
async def api_screen_checkin_confirm(request: Request, slug: str) -> dict[str, Any]:
    slug_key = _normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    _require_tv_access_for_screen(request, slug_key)
    body = await request.json()
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


@app.post("/api/screen/{slug}/checkin/confirm-all")
async def api_screen_checkin_confirm_all(request: Request, slug: str) -> dict[str, Any]:
    slug_key = _normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    _require_tv_access_for_screen(request, slug_key)
    body = await request.json()
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


@app.get("/api/screen/{slug}/checkin/events-status")
def api_screen_checkin_events_status(
    request: Request,
    slug: str,
    submit_widget_id: str = Query(...),
    device_hash: str = Query(...),
    ids: str = Query("", description="Список id через запятую"),
) -> dict[str, Any]:
    slug_key = _normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    _require_tv_access_for_screen(request, slug_key)
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


@app.post("/api/admin/checkin/confirm")
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


@app.post("/api/admin/checkin/confirm-all")
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


@app.get("/api/admin/checkin/events-status")
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


@app.get("/api/screen/{slug}/push/vapid-public-key")
def api_push_vapid_public_key(request: Request, slug: str) -> dict[str, Any]:
    slug_key = _normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    _require_tv_access_for_screen(request, slug_key)
    return {
        "status": "ok",
        "public_key": vapid_public_key(),
        "application_server_key": vapid_application_server_key(),
        "enabled": _push_enabled_on_server(),
    }


@app.get("/api/screen/{slug}/tv-pair-link")
def api_screen_tv_pair_link(request: Request, slug: str) -> dict[str, Any]:
    """
    Для уже подключённых /screen/{slug}?gs_tv_token=... устройств:
    вернуть публичную SaaS-ссылку вида /t/<code>/<slug>, чтобы можно было установить PWA-ярлык без переподключения.
    """
    slug_key = _normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    _require_tv_access_for_screen(request, slug_key)  # в SaaS выставит tenant_ctx.set_tenant_slug(...)
    if deployment_mode() != "saas" or not saas_db_enabled():
        raise HTTPException(status_code=404, detail="Not found.")
    try:
        from .tenant_ctx import tenant_slug as current_tenant

        ts = str(current_tenant() or "").strip()
    except Exception:
        ts = ""
    if not ts:
        raise HTTPException(status_code=404, detail="Tenant not resolved.")
    code_plain = ""
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT code_plaintext FROM tv_access WHERE tenant_slug=%s", (ts,))
            row = cur.fetchone()
            code_plain = str(row[0] or "").strip() if row else ""
    if not code_plain:
        raise HTTPException(status_code=404, detail="TV code is not configured.")
    return {
        "status": "ok",
        "code": code_plain,
        "url": f"/t/{code_plain}/{slug_key}",
    }


@app.post("/api/screen/{slug}/push/subscribe")
async def api_push_subscribe(request: Request, slug: str) -> dict[str, Any]:
    slug_key = _normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    _require_tv_access_for_screen(request, slug_key)
    body = await request.json()
    sub = body.get("subscription") if isinstance(body, dict) else None
    if not isinstance(sub, dict):
        raise HTTPException(status_code=400, detail="subscription required")
    endpoint = str(sub.get("endpoint") or "").strip()
    keys = sub.get("keys") if isinstance(sub.get("keys"), dict) else {}
    p256dh = str(keys.get("p256dh") or "").strip()
    auth = str(keys.get("auth") or "").strip()
    if not endpoint or not p256dh or not auth:
        raise HTTPException(status_code=400, detail="Invalid subscription")
    topics = body.get("topics") if isinstance(body, dict) else {}
    try:
        min_interval_sec = int(body.get("min_interval_sec") or 300) if isinstance(body, dict) else 300
    except (TypeError, ValueError):
        min_interval_sec = 300
    tenant_id = _screen_api_tenant_slug(request)
    upsert_push_subscription(
        tenant_id=tenant_id,
        screen_slug=slug_key,
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth,
        topics=topics if isinstance(topics, dict) else {},
        min_interval_sec=min_interval_sec,
        enabled=True,
    )
    return {"status": "ok"}


@app.post("/api/screen/{slug}/push/unsubscribe")
async def api_push_unsubscribe(request: Request, slug: str) -> dict[str, Any]:
    slug_key = _normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    _require_tv_access_for_screen(request, slug_key)
    body = await request.json()
    endpoint = str((body or {}).get("endpoint") or "").strip() if isinstance(body, dict) else ""
    if not endpoint:
        raise HTTPException(status_code=400, detail="endpoint required")
    tenant_id = _screen_api_tenant_slug(request)
    n = delete_push_subscription(tenant_id=tenant_id, screen_slug=slug_key, endpoint=endpoint)
    return {"status": "ok", "deleted": n}


@app.post("/api/screen/{slug}/push/test")
def api_push_test(request: Request, slug: str) -> dict[str, Any]:
    """Проверка Web Push без телефона: доставка на все подписки экрана (обходит rate-limit)."""
    slug_key = _normalize_screen_slug_for_api(slug)
    if not slug_key:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    _require_tv_access_for_screen(request, slug_key)
    if not _push_enabled_on_server():
        raise HTTPException(status_code=503, detail="Push на сервере не настроен (VAPID).")
    tenant_id = _screen_api_tenant_slug(request)
    subs = list_push_subscriptions(tenant_id=tenant_id, screen_slug=slug_key, topic=None)
    if not subs:
        raise HTTPException(
            status_code=400,
            detail="Нет подписки на этот экран — сначала нажмите «Включить уведомления».",
        )
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    _notify_push_to_screen(
        tenant_id=tenant_id,
        screen_slug=slug_key,
        topic="test",
        title="GuardSchool — тест push",
        body=(
            f"Сервер отправил в {now}. Если нет баннера: «Не беспокоить», настройки сайта в Windows, "
            f"или смотрите консоль SW (F12 → Application → Service Workers → Inspect)."
        ),
        url=f"/screen/{quote(slug_key, safe='')}",
        all_subscribers=True,
        skip_rate_limit=True,
    )
    return {"status": "ok", "targets": len(subs)}


def _tv_pair_pin_entry_file_response() -> FileResponse:
    """Страница ввода PIN без кеша (иначе после включения обхода браузер долго держит старый HTML)."""
    return FileResponse(
        STATIC_DIR / "tv_pair.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


def _push_enabled_on_server() -> bool:
    return bool(
        vapid_public_key() and vapid_private_key() and vapid_application_server_key(),
    )


def _notify_push_to_screen(
    *,
    tenant_id: str,
    screen_slug: str,
    topic: str,
    title: str,
    body: str,
    url: str,
    all_subscribers: bool = False,
    skip_rate_limit: bool = False,
    notification_tag: str | None = None,
) -> None:
    if not _push_enabled_on_server():
        return
    list_topic = "" if all_subscribers else topic
    subs = list_push_subscriptions(tenant_id=tenant_id, screen_slug=screen_slug, topic=list_topic)
    if not subs:
        return
    mi = 300
    try:
        mi = int(subs[0].get("min_interval_sec") or 300)
    except Exception:
        mi = 300
    if not skip_rate_limit:
        dec = push_rate_limit_decide(tenant_id=tenant_id, screen_slug=screen_slug, topic=topic, min_interval_sec=mi)
        if not dec.should_send:
            return
    tag_out = (notification_tag or "").strip() or f"{screen_slug}:{topic}"
    payload = json.dumps(
        {"title": title, "body": body, "url": url, "tag": tag_out},
        ensure_ascii=False,
    )
    try:
        from pywebpush import webpush
    except Exception:
        return
    for s in subs:
        try:
            webpush(
                subscription_info={"endpoint": s["endpoint"], "keys": s["keys"]},
                data=payload,
                vapid_private_key=vapid_private_key(),
                vapid_claims={"sub": vapid_subject()},
            )
        except Exception:
            continue


def _checkin_monitor_screens_for_events_slug(cfg: dict[str, Any], events_slug: str) -> list[str]:
    """
    Возвращает slug экранов, где есть checkin_monitor, который смотрит на events_slug.
    Нужен кейс: отметки создаются на tv-1, а сводка/уведомления — на tv-2.
    """
    want = (events_slug or "").strip().lower()
    if not want:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for sc in (cfg.get("screens") or []) if isinstance(cfg, dict) else []:
        if not isinstance(sc, dict) or sc.get("is_active", True) is False:
            continue
        disp_slug = _normalize_screen_slug_for_api(str(sc.get("slug") or ""))
        if not disp_slug or disp_slug in seen:
            continue
        for w in _screen_widgets_ordered_with_carousel_children(sc):
            if not isinstance(w, dict) or w.get("enabled") is False:
                continue
            if str(w.get("type") or "") != "checkin_monitor":
                continue
            event_slug = _checkin_events_screen_slug_for_monitor(cfg, w, disp_slug)
            if (event_slug or "").strip().lower() == want:
                out.append(disp_slug)
                seen.add(disp_slug)
                break
    return out


def _checkin_count_unconfirmed(*, tenant_id: str, events_screen_slug: str) -> int:
    try:
        import sqlite3

        from .gs_paths import DATA_DIR
        from .tenant_ctx import map_data_path

        db_path = map_data_path(DATA_DIR) / "checkin.sqlite3"
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.execute(
                """
                SELECT COUNT(1) AS n
                FROM checkin_events
                WHERE tenant_id=? AND lower(trim(screen_slug))=?
                  AND (confirmed_at IS NULL OR trim(confirmed_at) = '')
                """,
                ((tenant_id or "local").strip() or "local", (events_screen_slug or "").strip().lower()),
            )
            row = cur.fetchone()
            return int(row[0] or 0) if row else 0
        finally:
            conn.close()
    except Exception:
        return 0


def _checkin_push_target_slugs_for_events_screen(cfg: dict[str, Any], events_screen_slug: str) -> list[str]:
    """Экран записи событий + все экраны со сводкой, смотрящие на этот slug."""
    root = (events_screen_slug or "").strip().lower()
    if not root:
        return []
    out: list[str] = [root]
    for m in _checkin_monitor_screens_for_events_slug(cfg, root):
        if m and m not in out:
            out.append(m)
    return out


def _checkin_level_display_label(cfg: dict[str, Any], mw: dict[str, Any] | None, level: str) -> str:
    lv = (level or "").strip().lower()
    merged: dict[str, str] = {}
    ch = (cfg.get("checkin") or {}) if isinstance(cfg, dict) else {}
    raw = ch.get("labels") if isinstance(ch.get("labels"), dict) else {}
    for k, v in raw.items():
        key = str(k).strip().lower()
        if key:
            merged[key] = str(v).strip()
    if isinstance(mw, dict):
        raw2 = (mw.get("settings") or {}).get("labels")
        if isinstance(raw2, dict):
            for k, v in raw2.items():
                key = str(k).strip().lower()
                if key:
                    merged[key] = str(v).strip()
    return merged.get(lv) or {"ok": "Норма", "warn": "Внимание", "alert": "Проблема"}.get(lv, lv or "—")


def _checkin_monitor_widget_for_submit(screen: dict[str, Any], submit_w: dict[str, Any]) -> dict[str, Any] | None:
    st = submit_w.get("settings") or {}
    link = str(st.get("monitor_widget_id") or "").strip()
    if link:
        mw = _find_monitor_widget(screen, link)
        if mw:
            return mw
    mons = [
        w
        for w in _screen_widgets_ordered_with_carousel_children(screen)
        if isinstance(w, dict) and w.get("type") == "checkin_monitor"
    ]
    return mons[0] if len(mons) == 1 else None


def _checkin_place_title_from_submit_places(places: list[dict[str, str]], place_id: str) -> str:
    for p in places or []:
        if str(p.get("id") or "") == str(place_id):
            t = str(p.get("title") or "").strip()
            return t or str(place_id)
    return str(place_id)


def _checkin_place_title_from_monitor(mw: dict[str, Any], place_id: str) -> str:
    for p in sanitize_places_list((mw.get("settings") or {}).get("places")):
        if str(p.get("id") or "") == str(place_id):
            t = str(p.get("title") or "").strip()
            return t or str(place_id)
    return str(place_id)


def _notify_push_checkin_journal_new_row(
    *,
    cfg: dict[str, Any],
    tenant_id: str,
    screen: dict[str, Any],
    submit_w: dict[str, Any],
    events_screen_slug: str,
    saved: dict[str, Any],
    place_id: str,
    level: str,
    device_name: str,
    comment: str,
) -> None:
    """Пуш при новой строке журнала сводки (тема «Новые отметки» в подписке)."""
    places = _resolve_checkin_submit_places(screen, submit_w)
    place_title = _checkin_place_title_from_submit_places(places, place_id)
    mw = _checkin_monitor_widget_for_submit(screen, submit_w)
    lvl = _checkin_level_display_label(cfg, mw, level)
    parts = [place_title, lvl]
    dn = (device_name or "").strip()
    if dn:
        parts.append(dn)
    body = " · ".join(parts)
    cm = (comment or "").strip()
    if cm:
        body += " — " + cm[:180]
    try:
        eid = int(saved.get("id") or 0)
    except (TypeError, ValueError):
        eid = 0
    n_unc = _checkin_count_unconfirmed(tenant_id=tenant_id, events_screen_slug=events_screen_slug)
    if n_unc > 1:
        body += f" (неподтверждённых: {n_unc})"
    title = "Сводка: новая отметка"
    for disp in _checkin_push_target_slugs_for_events_screen(cfg, events_screen_slug):
        if not disp:
            continue
        url = f"/screen/{quote(str(disp).strip().lower(), safe='')}"
        tag = f"{disp}:checkin:new:{eid}" if eid else f"{disp}:checkin:new:{int(time.time())}"
        _notify_push_to_screen(
            tenant_id=tenant_id,
            screen_slug=disp,
            topic="checkin",
            title=title,
            body=body,
            url=url,
            notification_tag=tag,
            skip_rate_limit=True,
        )


def _notify_push_checkin_journal_confirmed(
    *,
    cfg: dict[str, Any],
    tenant_id: str,
    mw: dict[str, Any],
    events_screen_slug: str,
    row: dict[str, Any],
) -> None:
    pid = str(row.get("place_id") or "")
    place_title = _checkin_place_title_from_monitor(mw, pid)
    lvl = _checkin_level_display_label(cfg, mw, str(row.get("level") or ""))
    dn = str(row.get("device_name") or "").strip()
    parts = [place_title, lvl]
    if dn:
        parts.append(dn)
    body = " · ".join(parts)
    title = "Сводка: отметка подтверждена"
    try:
        eid = int(row.get("id") or 0)
    except (TypeError, ValueError):
        eid = 0
    root = (events_screen_slug or "").strip().lower()
    if not root:
        return
    for disp in _checkin_push_target_slugs_for_events_screen(cfg, root):
        if not disp:
            continue
        url = f"/screen/{quote(str(disp).strip().lower(), safe='')}"
        tag = f"{disp}:checkin:ok:{eid}" if eid else f"{disp}:checkin:ok:{int(time.time())}"
        _notify_push_to_screen(
            tenant_id=tenant_id,
            screen_slug=disp,
            topic="checkin",
            title=title,
            body=body,
            url=url,
            notification_tag=tag,
            skip_rate_limit=True,
        )


def _notify_push_checkin_journal_bulk_confirm(
    *, cfg: dict[str, Any], tenant_id: str, events_screen_slug: str, count: int
) -> None:
    if count <= 0:
        return
    title = "Сводка: журнал"
    body = f"Подтверждено записей: {count}"
    ts = int(time.time())
    root = (events_screen_slug or "").strip().lower()
    if not root:
        return
    for disp in _checkin_push_target_slugs_for_events_screen(cfg, root):
        if not disp:
            continue
        url = f"/screen/{quote(str(disp).strip().lower(), safe='')}"
        tag = f"{disp}:checkin:bulk:{ts}:{count}"
        _notify_push_to_screen(
            tenant_id=tenant_id,
            screen_slug=disp,
            topic="checkin",
            title=title,
            body=body,
            url=url,
            notification_tag=tag,
            skip_rate_limit=True,
        )


def _notify_push_emergency_change(*, tenant_id: str, cfg: dict[str, Any], prev_tid: str, new_tid: str) -> None:
    """
    Пуш по смене аварийного режима: prev_tid -> new_tid.
    new_tid == '' означает «выключено».
    """
    prev = str(prev_tid or "").strip()
    new = str(new_tid or "").strip()
    if prev == new:
        return
    # Найти title шаблона для текста уведомления.
    tname = ""
    try:
        templates = cfg.get("emergency_templates") if isinstance(cfg, dict) else None
        if isinstance(templates, list) and new:
            tpl = next((x for x in templates if isinstance(x, dict) and str(x.get("id") or "") == new), None)
            if isinstance(tpl, dict):
                tname = str(tpl.get("title") or tpl.get("name") or "").strip()[:120]
    except Exception:
        tname = ""
    title = "Аварийный режим" if new else "Аварийный режим выключен"
    body = (tname and f"Шаблон: {tname}") or ("Включён" if new else "Выключен")
    for sc in (cfg.get("screens") or []) if isinstance(cfg, dict) else []:
        if not isinstance(sc, dict) or sc.get("is_active", True) is False:
            continue
        slug = _normalize_screen_slug_for_api(str(sc.get("slug") or ""))
        if not slug:
            continue
        url = f"/screen/{quote(slug, safe='')}"
        _notify_push_to_screen(
            tenant_id=tenant_id,
            screen_slug=slug,
            topic="emergency",
            title=title,
            body=body,
            url=url,
        )


def _tv_pair_gate_notice_html(*, title: str, message: str, status: int = 404) -> HTMLResponse:
    """Текст без формы PIN и без URL админки — для ТВ при неверной ссылке или когда PIN не используется."""
    t = html.escape(title)
    m = html.escape(message, quote=False)
    doc = (
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'/>"
        "<meta http-equiv='Cache-Control' content='no-store'/>"
        f"<title>{t}</title></head>"
        "<body style='margin:0;font-family:system-ui;background:#0f172a;color:#e2e8f0;padding:28px;max-width:560px'>"
        f"<h1 style='font-size:20px;margin:0 0 12px'>{t}</h1>"
        f"<p style='margin:0;line-height:1.5;font-size:16px;color:#cbd5e1'>{m}</p>"
        "</body></html>"
    )
    return HTMLResponse(
        content=doc,
        status_code=status,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache"},
    )


_TV_SCHOOL_CODE_TRIPLET = re.compile(r"^[a-z2-9]{4}-[a-z2-9]{4}-[a-z2-9]{4}$")
_TV_SCHOOL_CODE_TRIPLET_LOOSE = re.compile(r"^[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}$")


def _canonical_tv_school_code(normalized_lower: str) -> str | None:
    """
    Код из URL/тела: строго xxx-xxx-xxx или те же 12 символов без дефисов (часть ТВ режет дефисы в пути).
    Допускаются старые коды с 0/1 в триплетах (loose).
    """
    s = (normalized_lower or "").strip()
    if _TV_SCHOOL_CODE_TRIPLET.fullmatch(s):
        return s
    letters = _tv_school_code_compact(s)
    if len(letters) != 12:
        return None
    cand = f"{letters[:4]}-{letters[4:8]}-{letters[8:12]}"
    if _TV_SCHOOL_CODE_TRIPLET.fullmatch(cand):
        return cand
    if _TV_SCHOOL_CODE_TRIPLET_LOOSE.fullmatch(cand):
        return cand
    return None


_TV_ACCESS_BY_CODE_SQL = (
    "SELECT tenant_slug, pin_salt, pin_hash, COALESCE(pin_bypass, false) FROM tv_access "
    "WHERE code_hash=%s "
    "OR lower(trim(coalesce(code_plaintext, '')))=%s "
    "OR regexp_replace(lower(trim(coalesce(code_plaintext, ''))), '[^a-z0-9]', '', 'g')=%s "
    "LIMIT 1"
)


def _normalize_pwa_upload_icon_path(raw: object) -> str | None:
    """
    Поле pwa_icon_url в виджете: нужен путь вида /uploads/..., либо полный URL с таким же путём
    (копируют из браузера). Иначе иконку в manifest не ставим — Chromium не любит произвольные URL.
    """
    cand = str(raw or "").strip()
    if not cand:
        return None
    if cand.startswith("/uploads/"):
        return cand.split("?", 1)[0][:512]
    low = cand.lower()
    if low.startswith(("http://", "https://")):
        try:
            path = urlparse(cand).path or ""
            path = path.split("?", 1)[0]
            if path.startswith("/uploads/"):
                return path[:512]
        except Exception:
            return None
    return None


def _pwa_manifest_icon_src_public(request: Request, rel_path: str) -> str:
    """Абсолютный URL иконки: часть клиентов криво резолвит относительные пути к /pwa/*.webmanifest."""
    rp = str(rel_path or "").strip()
    if not rp.startswith("/"):
        return rp
    try:
        return str(request.base_url).rstrip("/") + rp
    except Exception:
        return rp


_PWA_DEFAULT_ICON_REL_512 = "/static/pwa/icon_default.png"
_PWA_DEFAULT_ICON_REL_192 = "/static/pwa/icon_default_192.png"
_WIDGET_PWA_ICON_FILENAME_RE = re.compile(r"^[a-zA-Z0-9._-]{1,220}$")
_PWA_DERIVED_192_MARKER = "_gs_pwa192"
# Если нигде не задан «Название ярлыка (PWA)», всё равно нужен непустой name в manifest (Chrome).
_PWA_MANIFEST_DEFAULT_TITLE = "Приложение"


def _pwa_path_inside_dir_relaxed(base_dir: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(base_dir.resolve())
        return True
    except ValueError:
        return False


def _pwa_widget_uploads_icon_filename(icon_rel_no_query: str) -> str | None:
    """Имя файла в uploads/widget_images/… или None (path traversal отсекаем).

    Допускаем и автокопию «…_gs_pwa192.png» — её иногда подставляют вручную в pwa_icon_url.
    """
    cand = icon_rel_no_query.strip()
    if not cand.startswith("/"):
        cand = "/" + cand
    prefix = f"/uploads/{WIDGET_IMAGES_SUBDIR}/"
    if cand[: len(prefix)].lower() != prefix.lower():
        return None
    name = cand[len(prefix) :].lstrip("/")
    if not name or "/" in name:
        return None
    if not _WIDGET_PWA_ICON_FILENAME_RE.fullmatch(name):
        return None
    return name


def _pwa_neighbor_original_upload_name(fs_dir: Path, derivative_nm: str) -> str | None:
    """Для имени вида foo_gs_pwa192.png находит файл оригинала foo.{png,jpg,...} рядом в каталоге."""
    p = Path(derivative_nm)
    sl = p.stem.lower()
    if not sl.endswith(_PWA_DERIVED_192_MARKER):
        return None
    base_stem = p.stem[: -len(_PWA_DERIVED_192_MARKER)]
    if not base_stem.strip():
        return None
    # Один активный файл с этим префиксом (.png предпочитаем — как после «Загрузить»).
    matches = [
        cand
        for cand in fs_dir.glob(f"{base_stem}.*")
        if cand.is_file() and not cand.stem.lower().endswith(_PWA_DERIVED_192_MARKER)
    ]
    matches.sort(key=lambda c: (c.suffix.lower() != ".png", c.name.lower()))
    return matches[0].name if matches else None


def _pwa_pil_image_size(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image

        with Image.open(path) as im:
            w, h = im.size
            if isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0:
                return (w, h)
    except Exception:
        pass
    return None


def _pwa_write_png_192_from_raster(src: Path, dst: Path) -> bool:
    """Ровно 192×192 PNG — под manifest sizes:«192x192» (intrinsic должны совпадать с объявлением)."""
    try:
        from PIL import Image

        with Image.open(src) as im:
            conv = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
            if conv.mode != "RGBA":
                conv = conv.convert("RGBA")
            sm = conv.resize((192, 192), Image.Resampling.LANCZOS)
        dst.parent.mkdir(parents=True, exist_ok=True)
        sm.save(dst, format="PNG", optimize=True)
        return True
    except Exception:
        try:
            if dst.exists():
                dst.unlink()
        except Exception:
            pass
        return False


def _pwa_ensure_manifest_192_upload_rel(request: Request, icon_rel_clean: str) -> str | None:
    """Копия 192×192 рядом с пользовательским файлом `<stem>_gs_pwa192.png` (обновление при более новой оригинале)."""
    nm = _pwa_widget_uploads_icon_filename(icon_rel_clean)
    if not nm:
        return None
    try:
        from .tenant_ctx import map_data_path

        fs_dir = map_data_path(UPLOADS_DIR / WIDGET_IMAGES_SUBDIR).resolve()
    except Exception:
        return None
    stem_low = Path(nm).stem.lower()
    if stem_low.endswith(_PWA_DERIVED_192_MARKER):
        dst = (fs_dir / nm).resolve()
        if _pwa_path_inside_dir_relaxed(fs_dir, dst) and dst.is_file():
            return f"/uploads/{WIDGET_IMAGES_SUBDIR}/{nm}"
        return None
    src = (fs_dir / nm).resolve()
    if not _pwa_path_inside_dir_relaxed(fs_dir, src) or not src.is_file():
        return None
    dst_nm = f"{src.stem}{_PWA_DERIVED_192_MARKER}.png"
    dst = (fs_dir / dst_nm).resolve()
    if not _pwa_path_inside_dir_relaxed(fs_dir, dst):
        return None
    need = True
    if dst.is_file():
        try:
            need = src.stat().st_mtime > dst.stat().st_mtime
        except OSError:
            need = True
    if need and not _pwa_write_png_192_from_raster(src, dst):
        return None
    return f"/uploads/{WIDGET_IMAGES_SUBDIR}/{dst_nm}"


def _pwa_manifest_mime_for_upload_suffix(filename: str) -> str:
    low = filename.lower()
    if low.endswith(".webp"):
        return "image/webp"
    if low.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    return "image/png"


def _pwa_manifest_raster_icons(
    request: Request | None,
    *,
    icon_rel_clean: str,
    mime: str,
) -> list[dict[str, str]]:
    """
    Chromium: каждая запись icons[] — заявленные пиксели должны совпадать с фактическим размером
    файла по src. Поэтому 192×192 — отдельный URL (копия), а не второй маркёр на файл 512×512.
    """
    if request is None:
        return [
            {"src": icon_rel_clean, "sizes": "any", "type": mime, "purpose": "any"},
        ]
    src_main_pub = _pwa_manifest_icon_src_public(request, icon_rel_clean)
    base_low = icon_rel_clean.lower()
    # Встроенный fallback без загрузки: два статических файла с разными intrinsic.
    if base_low.endswith(_PWA_DEFAULT_ICON_REL_512):
        pub192 = _pwa_manifest_icon_src_public(request, _PWA_DEFAULT_ICON_REL_192)
        pub512 = _pwa_manifest_icon_src_public(request, _PWA_DEFAULT_ICON_REL_512)
        return [
            {"src": pub192, "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": pub512, "sizes": "512x512", "type": "image/png", "purpose": "any"},
        ]

    icons: list[dict[str, str]] = []

    fs_dir: Path | None = None
    try:
        from .tenant_ctx import map_data_path

        fs_dir = map_data_path(UPLOADS_DIR / WIDGET_IMAGES_SUBDIR).resolve()
    except Exception:
        fs_dir = None

    nm = _pwa_widget_uploads_icon_filename(icon_rel_clean)
    path_512: Path | None = None
    path_192: Path | None = None

    if fs_dir and nm:
        path_user = (fs_dir / nm).resolve()
        if _pwa_path_inside_dir_relaxed(fs_dir, path_user) and path_user.is_file():
            stem_low = Path(nm).stem.lower()
            if stem_low.endswith(_PWA_DERIVED_192_MARKER):
                path_192 = path_user
                nm512 = _pwa_neighbor_original_upload_name(fs_dir, nm)
                if nm512:
                    cand512 = (fs_dir / nm512).resolve()
                    if _pwa_path_inside_dir_relaxed(fs_dir, cand512) and cand512.is_file():
                        path_512 = cand512
            else:
                path_512 = path_user
                rel_gen = _pwa_ensure_manifest_192_upload_rel(request, icon_rel_clean)
                if rel_gen:
                    nm192 = rel_gen.rstrip("/").rsplit("/", 1)[-1]
                    cand192 = (fs_dir / nm192).resolve()
                    if _pwa_path_inside_dir_relaxed(fs_dir, cand192) and cand192.is_file():
                        path_192 = cand192

    if path_192:
        nm192_final = path_192.name
        rel_192 = f"/uploads/{WIDGET_IMAGES_SUBDIR}/{nm192_final}"
        icons.append(
            {
                "src": _pwa_manifest_icon_src_public(request, rel_192),
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            }
        )

    if path_512:
        nm512_final = path_512.name
        sz = _pwa_pil_image_size(path_512)
        if sz:
            w, h = sz
            mime512 = _pwa_manifest_mime_for_upload_suffix(nm512_final)
            rel_512 = f"/uploads/{WIDGET_IMAGES_SUBDIR}/{nm512_final}"
            icons.append(
                {
                    "src": _pwa_manifest_icon_src_public(request, rel_512),
                    "sizes": f"{w}x{h}",
                    "type": mime512,
                    "purpose": "any",
                }
            )

    if icons:
        return icons

    icons.append({"src": src_main_pub, "sizes": "any", "type": mime, "purpose": "any"})
    return icons


def _pwa_manifest_icon_specs(
    icon_rel: str,
    *,
    request: Request | None = None,
) -> tuple[list[dict[str, str]], str]:
    """
    Кортеж: список записей icons[] для manifest, MIME первой записи (для логики не обязательно).

    ICO/SVG — только sizes:any. Для PNG/WebP/JPEG см. _pwa_manifest_raster_icons (раздельный 192px URL).
    """
    icon_rel_clean = (icon_rel or "").split("?", 1)[0].strip()
    src = (
        _pwa_manifest_icon_src_public(request, icon_rel_clean)
        if request is not None
        else str(icon_rel_clean or "")
    )
    base_low = icon_rel_clean.lower()
    if base_low.endswith(".ico"):
        return (
            [{"src": src, "sizes": "any", "type": "image/x-icon", "purpose": "any"}],
            "image/x-icon",
        )
    if base_low.endswith(".svg") or base_low.endswith(".svgz"):
        return (
            [{"src": src, "sizes": "any", "type": "image/svg+xml", "purpose": "any"}],
            "image/svg+xml",
        )
    if base_low.endswith(".webp"):
        mime = "image/webp"
    elif base_low.endswith(".jpg") or base_low.endswith(".jpeg"):
        mime = "image/jpeg"
    else:
        mime = "image/png"
    icons_raster = _pwa_manifest_raster_icons(request, icon_rel_clean=icon_rel_clean, mime=mime)
    return (icons_raster, mime)


def _pwa_manifest_screenshots_entries(request: Request | None) -> list[dict[str, str]]:
    """Скрины для расширенного UI установки: wide (десктоп) и narrow (мобилки). Файлы в /static/pwa/."""
    if request is None:
        return []
    wide = _pwa_manifest_icon_src_public(request, "/static/pwa/screenshot_wide.png")
    narrow = _pwa_manifest_icon_src_public(request, "/static/pwa/screenshot_narrow.png")
    return [
        {
            "src": wide,
            "sizes": "1280x720",
            "type": "image/png",
            "form_factor": "wide",
            "label": "Экран",
        },
        {
            "src": narrow,
            "sizes": "540x720",
            "type": "image/png",
            "form_factor": "narrow",
            "label": "Экран",
        },
    ]


def _pwa_fallback_pwa_fields_from_widgets(
    visit_all: list[dict[str, Any]],
    *,
    have_title: bool,
    have_icon: bool,
) -> tuple[str, str]:
    """Берём pwa_title / pwa_icon_url из любого виджета (админ мог заполнить не у checkin)."""
    if have_title and have_icon:
        return "", ""
    t_out = ""
    i_out = ""
    for w in visit_all:
        # enabled не фильтруем: поля ярлыка остаются в конфиге и для выключенного виджета.
        if not isinstance(w, dict):
            continue
        st = w.get("settings") if isinstance(w.get("settings"), dict) else {}
        if not have_title and not t_out:
            pt = str(st.get("pwa_title") or "").strip()[:64]
            if pt:
                t_out = pt
        if not have_icon and not i_out:
            ip = _normalize_pwa_upload_icon_path(st.get("pwa_icon_url"))
            if ip:
                i_out = ip
        if (have_title or t_out) and (have_icon or i_out):
            break
    return t_out, i_out


def _pwa_widget_title_icon_for_slug(cfg: dict[str, Any], slug_n: str) -> tuple[str, str]:
    """Имя и иконка в webmanifest: только поля «Название ярлыка (PWA)» / «Иконка ярлыка» в виджетах (по приоритету ниже)."""
    # Дефолт-иконка из статики (всегда 200), не из uploads/ тенанта — иначе 404 и пустой ярлык.
    icon_url = "/static/pwa/icon_default.png"
    slug_key = slug_n.strip().lower()
    screens = cfg.get("screens") if isinstance(cfg, dict) else None
    if not isinstance(screens, list):
        return _PWA_MANIFEST_DEFAULT_TITLE[:64], icon_url
    sc = next(
        (
            s
            for s in screens
            if isinstance(s, dict) and str(s.get("slug") or "").strip().lower() == slug_key
        ),
        None,
    )
    if not isinstance(sc, dict):
        return _PWA_MANIFEST_DEFAULT_TITLE[:64], icon_url
    visit_all = _screen_widgets_ordered_with_carousel_children(sc)
    checkin_ordered: list[dict[str, Any]] = []
    for w in visit_all:
        if not isinstance(w, dict):
            continue
        if str(w.get("type") or "") not in ("checkin_submit", "checkin_monitor"):
            continue
        checkin_ordered.append(w)
    submits = [w for w in checkin_ordered if str(w.get("type") or "") == "checkin_submit"]
    monitors = [w for w in checkin_ordered if str(w.get("type") or "") == "checkin_monitor"]
    visit = submits + monitors
    if not visit:
        fb_t, fb_i = _pwa_fallback_pwa_fields_from_widgets(visit_all, have_title=False, have_icon=False)
        chosen0 = (fb_t or _PWA_MANIFEST_DEFAULT_TITLE)[:64]
        return chosen0, fb_i if fb_i else icon_url
    pwa_title_submit = ""
    pwa_title_monitor = ""
    icon_submit = ""
    icon_monitor = ""
    for w in visit:
        st_w = w.get("settings") if isinstance(w.get("settings"), dict) else {}
        wt = str(w.get("type") or "")
        ip = _normalize_pwa_upload_icon_path(st_w.get("pwa_icon_url"))
        pt = str(st_w.get("pwa_title") or "").strip()[:64]
        if wt == "checkin_submit":
            if ip and not icon_submit:
                icon_submit = ip
            if pt and not pwa_title_submit:
                pwa_title_submit = pt
        elif wt == "checkin_monitor":
            if ip and not icon_monitor:
                icon_monitor = ip
            if pt and not pwa_title_monitor:
                pwa_title_monitor = pt
    pwa_title_pick = pwa_title_submit or pwa_title_monitor
    icon_pick = icon_submit or icon_monitor
    fb_t, fb_i = _pwa_fallback_pwa_fields_from_widgets(
        visit_all,
        have_title=bool(pwa_title_pick),
        have_icon=bool(icon_pick),
    )
    if not pwa_title_pick and fb_t:
        pwa_title_pick = fb_t
    if not icon_pick and fb_i:
        icon_pick = fb_i
    chosen = (pwa_title_pick or _PWA_MANIFEST_DEFAULT_TITLE)[:64]
    final_icon = icon_pick if icon_pick else icon_url
    return chosen, final_icon


def _pwa_manifest_for_tv_pair(
    *,
    request: Request,
    tenant_slug: str,
    code_canon: str,
    screen_slug: str,
    app_title: str,
    icon_url: str,
) -> JSONResponse:
    """
    SaaS: PWA manifest для ссылки /t/{code}/{screen_slug}.

    Ключевые требования:
    - start_url должен содержать code (чтобы “ярлык” вёл на брендированную ссылку);
    - icon должен быть tenant-scoped (через /uploads/*, который резолвится по cookie тенанта).
    """
    icon_entries, _mime = _pwa_manifest_icon_specs(icon_url, request=request)
    start_url = f"/t/{quote(code_canon, safe='')}/{quote(screen_slug, safe='')}?pwa=1"
    manifest = {
        "name": app_title,
        "short_name": app_title[:24],
        "id": f"/pwa/t/{code_canon}/{screen_slug}",
        "start_url": start_url,
        "scope": "/",
        "display": "standalone",
        "background_color": "#0f172a",
        "theme_color": "#0f172a",
        "icons": icon_entries,
        "screenshots": _pwa_manifest_screenshots_entries(request),
    }
    resp = JSONResponse(
        content=manifest,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )
    # Чтобы /uploads/* для icon_url отдался из data/ конкретного тенанта (map_data_path).
    sec = session_cookie_secure(request)
    resp.set_cookie(
        SAAS_TENANT_COOKIE,
        _encode_saas_tenant_cookie_value(tenant_slug),
        max_age=3600 * 24 * 365,
        httponly=True,
        samesite="lax",
        secure=sec,
        path="/",
    )
    return resp


@app.get("/pwa/t/{code}/{screen_slug}.webmanifest", response_class=JSONResponse)
def pwa_manifest_for_tv_pair(request: Request, code: str, screen_slug: str) -> JSONResponse:
    """
    SaaS: webmanifest для установки ярлыка с tenant-кодом и экраном (tv-1/tv-2).
    Иконка берётся из /uploads/..., т.е. из data/uploads конкретного тенанта.
    """
    if deployment_mode() != "saas" or not saas_db_enabled():
        raise HTTPException(status_code=404, detail="Not found.")
    code_raw = _normalize_tv_pair_text(_tv_path_code_segment(code)).lower()
    code_canon = _canonical_tv_school_code(code_raw)
    if not code_canon:
        raise HTTPException(status_code=404, detail="Not found.")
    slug_n = _normalize_screen_slug_for_api(str(screen_slug or ""))
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", slug_n):
        raise HTTPException(status_code=404, detail="Not found.")
    with connect_public() as conn:
        with conn.cursor() as cur:
            row = _tv_access_lookup_row(cur, code_canon=code_canon)
            if not row:
                raise HTTPException(status_code=404, detail="Not found.")
            tenant_slug = str(row[0] or "").strip()
    prev_tenant = None
    try:
        from .tenant_ctx import tenant_slug as _tenant_slug_get

        prev_tenant = _tenant_slug_get()
    except Exception:
        prev_tenant = None
    try:
        set_tenant_slug(tenant_slug)
        cfg = load_config()
        title, icon_url = _pwa_widget_title_icon_for_slug(cfg, slug_n)
    except Exception:
        _log.exception(
            "PWA /pwa/t manifest: ошибка load_config или разбора pwa_* slug=%r tenant=%r",
            slug_n,
            tenant_slug,
        )
        title, icon_url = _pwa_widget_title_icon_for_slug({}, slug_n)
    finally:
        try:
            set_tenant_slug(prev_tenant)
        except Exception:
            set_tenant_slug(None)
    return _pwa_manifest_for_tv_pair(
        request=request,
        tenant_slug=tenant_slug,
        code_canon=code_canon,
        screen_slug=slug_n,
        app_title=title,
        icon_url=icon_url,
    )


@app.get("/pwa/screen/{screen_slug}.webmanifest", response_class=JSONResponse)
def pwa_manifest_for_screen_standalone(request: Request, screen_slug: str) -> JSONResponse:
    """
    Manifest для /screen/<slug>: tenant из middleware (cookie), из декодированной cookie,
    либо из ?gs_tv_token= (совпадает со slug экрана) — когда cookie ещё не успела сохраниться.
    """
    slug_n = _normalize_screen_slug_for_api(str(screen_slug or ""))
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", slug_n):
        raise HTTPException(status_code=404, detail="Not found.")
    if deployment_mode() == "saas":
        tenant_slug = _pwa_manifest_resolve_tenant_slug(request, slug_n)
        if not tenant_slug:
            raise HTTPException(
                status_code=404,
                detail="Откройте экран с ?gs_tv_token=… или войдите в школу; обновите страницу (нужна привязка к школе).",
            )
    else:
        tenant_slug = _pwa_manifest_resolve_tenant_slug(request, slug_n) or "local"
    prev_tenant = None
    try:
        from .tenant_ctx import tenant_slug as _tenant_slug_get

        prev_tenant = _tenant_slug_get()
    except Exception:
        prev_tenant = None
    try:
        set_tenant_slug(tenant_slug)
        cfg = load_config()
        title, icon_url = _pwa_widget_title_icon_for_slug(cfg, slug_n)
    except Exception:
        _log.exception(
            "PWA /pwa/screen manifest: ошибка load_config или разбора pwa_* slug=%r tenant=%r",
            slug_n,
            tenant_slug,
        )
        title, icon_url = _pwa_widget_title_icon_for_slug({}, slug_n)
    finally:
        try:
            set_tenant_slug(prev_tenant)
        except Exception:
            set_tenant_slug(None)

    icon_entries_sc, _mime_sc = _pwa_manifest_icon_specs(icon_url, request=request)
    start_url = f"/screen/{quote(slug_n, safe='')}?pwa=1"
    manifest = {
        "name": title,
        "short_name": title[:24],
        "id": f"/pwa/screen/{tenant_slug}/{slug_n}",
        "start_url": start_url,
        "scope": "/",
        "display": "standalone",
        "background_color": "#0f172a",
        "theme_color": "#0f172a",
        "icons": icon_entries_sc,
        "screenshots": _pwa_manifest_screenshots_entries(request),
    }
    resp = JSONResponse(
        content=manifest,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )
    sec = session_cookie_secure(request)
    resp.set_cookie(
        SAAS_TENANT_COOKIE,
        _encode_saas_tenant_cookie_value(tenant_slug),
        max_age=3600 * 24 * 365,
        httponly=True,
        samesite="lax",
        secure=sec,
        path="/",
    )
    return resp


def _tv_access_lookup_row(cur: Any, *, code_canon: str) -> tuple[Any, Any, Any, Any] | None:
    """Поиск tv_access по хешу/SQL и резервно по компактному коду (ZWSP/дефисы Unicode в БД или в URL ТВ)."""
    ch = tv_code_hash(code_canon)
    code_digits_only = re.sub(r"[^a-z0-9]", "", code_canon)
    cur.execute(_TV_ACCESS_BY_CODE_SQL, (ch, code_canon, code_digits_only))
    row = cur.fetchone()
    if row:
        return row
    want = _tv_school_code_compact(code_canon)
    if len(want) != 12:
        return None
    cur.execute(
        "SELECT tenant_slug, pin_salt, pin_hash, COALESCE(pin_bypass, false), coalesce(code_plaintext,'') FROM tv_access"
    )
    for r in cur.fetchall() or []:
        if _tv_school_code_compact(str(r[4] or "")) == want:
            return (r[0], r[1], r[2], r[3])
    return None


@app.get("/t/{code}/{screen_slug}", response_class=HTMLResponse)
def tv_pair_page(request: Request, code: str, screen_slug: str) -> Response:
    """
    Вход по ссылке /t/…: при обходе PIN — сразу экран с токеном; при обычном режиме — только тогда
    отдаём страницу ввода PIN (никогда не подставляем форму PIN «вслепую» при неверном коде или обходе).
    """
    if deployment_mode() != "saas" or not saas_db_enabled():
        return _tv_pair_gate_notice_html(
            title="ТВ-подключение",
            message="В этой конфигурации сервера автоматическое подключение телевизора недоступно.",
            status=503,
        )
    code_raw = _normalize_tv_pair_text(_tv_path_code_segment(code)).lower()
    code_canon = _canonical_tv_school_code(code_raw)
    if not code_canon:
        return _tv_pair_gate_notice_html(
            title="Неверная ссылка",
            message="Формат кода в адресе не распознан. Попросите администратора школы прислать ссылку для этого телевизора ещё раз.",
        )
    slug_n = _normalize_screen_slug_for_api(str(screen_slug or ""))
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", slug_n):
        return _tv_pair_gate_notice_html(
            title="Неверная ссылка",
            message="Имя экрана в адресе не распознано. Попросите администратора школы прислать ссылку ещё раз.",
        )
    now_ts = time.time()
    pair_key = _tv_pair_client_key(request, code_canon)
    retry_after = _tv_pair_check_rate_limit(pair_key, now_ts)
    if retry_after > 0:
        return HTMLResponse(
            "<!doctype html><html lang='ru'><head><meta charset='utf-8' /><title>GuardSchool</title></head>"
            f"<body style='font-family:system-ui;padding:24px'>Слишком много попыток. Подождите {retry_after} с.</body></html>",
            status_code=429,
            headers={"Cache-Control": "no-store"},
        )
    with connect_public() as conn:
        with conn.cursor() as cur:
            row = _tv_access_lookup_row(cur, code_canon=code_canon)
            if not row:
                _tv_pair_record_failure(pair_key, now_ts)
                return _tv_pair_gate_notice_html(
                    title="Ссылка недействительна",
                    message="Код школы в ссылке не найден или был обновлён. Попросите администратора школы в программе снова сгенерировать код для телевизора и прислать новую ссылку.",
                )
            tenant_slug, _pin_salt, _pin_hash, pin_bypass_db = row[0], row[1], row[2], bool(row[3])
            ts = str(tenant_slug or "").strip()
            if not _tv_pair_pin_bypass_effective(ts, pin_bypass_db):
                return _tv_pair_pin_entry_file_response()
            # Установка ярлыка (PWA): если приложение уже установлено, нельзя каждый запуск создавать новый device-token.
            # В режиме pwa=1 сначала пытаемся взять сохранённый токен из localStorage и перейти на /screen/{slug}?gs_tv_token=...
            if str(request.query_params.get("pwa") or "").strip() in ("1", "true", "yes"):
                # Manifest иконки/тенант-uploads требует cookie тенанта.
                sec = session_cookie_secure(request)
                resp = HTMLResponse(
                    content=(
                        "<!doctype html><html lang='ru'><head><meta charset='utf-8'/>"
                        "<meta name='viewport' content='width=device-width, initial-scale=1'/>"
                        "<meta http-equiv='Cache-Control' content='no-store'/>"
                        "<title>GuardSchool</title>"
                        f"<link rel='manifest' href='/pwa/t/{html.escape(code_canon, quote=True)}/{html.escape(slug_n, quote=True)}.webmanifest'/>"
                        "</head><body style='margin:0;font-family:system-ui;background:#0f172a;color:#e2e8f0'>"
                        "<div style='padding:24px;font-size:18px'>Запуск экрана…</div>"
                        "<script>(function(){try{"
                        f"var code={json.dumps(code_canon)}; var slug={json.dumps(slug_n)};"
                        "var k='gs_pwa_tv_token__'+code+'__'+slug;"
                        "var tok=localStorage.getItem(k)||'';"
                        "if(tok&&tok.length>10){location.replace('/screen/'+encodeURIComponent(slug)+'?gs_tv_token='+encodeURIComponent(tok));return;}"
                        "location.replace('/t/'+encodeURIComponent(code)+'/'+encodeURIComponent(slug)+'?pwa_pair=1');"
                        "}catch(e){location.replace('/t/"+ html.escape(code_canon, quote=True) + "/" + html.escape(slug_n, quote=True) + "?pwa_pair=1');}})();</script>"
                        "</body></html>"
                    ),
                    status_code=200,
                    headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache"},
                )
                resp.set_cookie(
                    SAAS_TENANT_COOKIE,
                    _encode_saas_tenant_cookie_value(ts),
                    max_age=3600 * 24 * 365,
                    httponly=True,
                    samesite="lax",
                    secure=sec,
                    path="/",
                )
                return resp
            lab = str(request.query_params.get("gs_label") or "").strip()[:120]
            _tv_pair_record_success(pair_key)
            token = secrets.token_urlsafe(24)
            th = tv_device_token_hash(token)
            cur.execute(
                """
                INSERT INTO tv_devices (token_hash, tenant_slug, screen_slug, label, status)
                VALUES (%s,%s,%s,%s,'active')
                ON CONFLICT (token_hash) DO NOTHING
                """,
                (th, ts, slug_n, lab),
            )
        conn.commit()
    loc = f"/screen/{quote(slug_n, safe='')}?gs_tv_token={quote(token, safe='')}"
    # Часть ТВ-WebView даёт пустой экран на HTTP 302 с длинным Location — отдаём HTML и делаем переход из JS.
    loc_js = json.dumps(loc, ensure_ascii=False)
    loc_attr = html.escape(loc, quote=True)
    # Для PWA: сохранить токен 1 раз (если пришли из pwa_pair=1), чтобы последующие запуски ярлыка не плодили tv_devices.
    store_js = ""
    if str(request.query_params.get("pwa_pair") or "").strip() in ("1", "true", "yes"):
        store_js = (
            "<script>(function(){try{"
            f"var k='gs_pwa_tv_token__'+{json.dumps(code_canon)}+'__'+{json.dumps(slug_n)};"
            f"localStorage.setItem(k,{json.dumps(token)});"
            f"localStorage.setItem('gs_pwa_tv_code__'+{json.dumps(slug_n)},{json.dumps(code_canon)});"
            "}catch(e){}})();</script>"
        )
    jump_html = (
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'/>"
        "<meta http-equiv='Cache-Control' content='no-store'/>"
        f"<link rel='manifest' href='/pwa/t/{html.escape(code_canon, quote=True)}/{html.escape(slug_n, quote=True)}.webmanifest'/>"
        f"<meta http-equiv='refresh' content='0;url={loc_attr}'/>"
        "<title>GuardSchool — подключение ТВ</title></head>"
        "<body style='margin:0;font-family:system-ui;background:#0f172a;color:#e2e8f0'>"
        "<div style='padding:24px;font-size:18px'>Переход на экран…</div>"
        f"{store_js}"
        f"<script>location.replace({loc_js});</script>"
        f"<noscript><div style='padding:24px'><a href='{loc_attr}' style='color:#38bdf8'>Открыть экран</a></div>"
        f"<meta http-equiv='refresh' content='0;url={loc_attr}'/></noscript></body></html>"
    )
    resp2 = HTMLResponse(
        content=jump_html,
        status_code=200,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache"},
    )
    sec = session_cookie_secure(request)
    resp2.set_cookie(
        SAAS_TENANT_COOKIE,
        _encode_saas_tenant_cookie_value(ts),
        max_age=3600 * 24 * 365,
        httponly=True,
        samesite="lax",
        secure=sec,
        path="/",
    )
    return resp2


@app.post("/api/tv/pair")
async def tv_pair(request: Request) -> dict[str, Any]:
    """
    Pairing ТВ по короткому коду школы + PIN.
    Возвращает device-token (Bearer) и URL для перехода на /screen/{slug}.
    """
    if deployment_mode() != "saas" or not saas_db_enabled():
        raise HTTPException(status_code=404, detail="Not found.")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    code_raw = _normalize_tv_pair_text(str(body.get("code") or "")).lower()
    code = _canonical_tv_school_code(code_raw) or ""
    screen_slug = _normalize_screen_slug_for_api(str(body.get("screen_slug") or ""))
    label = str(body.get("label") or "").strip()[:120]
    if not code_raw or not screen_slug:
        raise HTTPException(status_code=400, detail="code, pin, screen_slug required")
    if not code:
        raise HTTPException(status_code=400, detail="Invalid code format")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", screen_slug):
        raise HTTPException(status_code=400, detail="Invalid screen_slug")
    now_ts = time.time()
    pair_key = _tv_pair_client_key(request, code)
    retry_after = _tv_pair_check_rate_limit(pair_key, now_ts)
    if retry_after > 0:
        raise HTTPException(status_code=429, detail=f"Too many attempts. Retry after {retry_after}s")

    with connect_public() as conn:
        with conn.cursor() as cur:
            row = _tv_access_lookup_row(cur, code_canon=code)
            if not row:
                _tv_pair_record_failure(pair_key, now_ts)
                raise HTTPException(status_code=403, detail="Invalid code or PIN")
            tenant_slug, pin_salt, pin_hash_db, pin_bypass_db = row[0], row[1], row[2], bool(row[3])
            ts = str(tenant_slug or "").strip()
            pin_bypass = _tv_pair_pin_bypass_effective(ts, pin_bypass_db)
            if pin_bypass:
                pin = _normalize_tv_pair_text(str(body.get("pin") or "")).strip()
                if len(pin) > 48:
                    raise HTTPException(status_code=400, detail="PIN too long (bypass mode)")
                if not pin:
                    pin = "."
            else:
                pin = _normalize_tv_pair_pin(str(body.get("pin") or ""))
                if not re.fullmatch(r"[0-9]{4,12}", pin):
                    raise HTTPException(status_code=400, detail="PIN must be 4..12 digits")
            if not pin_bypass:
                got = tv_pin_hash(pin, pin_salt)
                if not hmac.compare_digest(got, str(pin_hash_db or "")):
                    _tv_pair_record_failure(pair_key, now_ts)
                    raise HTTPException(status_code=403, detail="Invalid code or PIN")

            _tv_pair_record_success(pair_key)
            token = secrets.token_urlsafe(24)
            th = tv_device_token_hash(token)
            cur.execute(
                """
                INSERT INTO tv_devices (token_hash, tenant_slug, screen_slug, label, status)
                VALUES (%s,%s,%s,%s,'active')
                ON CONFLICT (token_hash) DO NOTHING
                """,
                (th, tenant_slug, screen_slug, label),
            )
        conn.commit()
    screen_path = f"/screen/{quote(screen_slug, safe='')}?gs_tv_token={quote(token, safe='')}"
    return {
        "status": "ok",
        "token": token,
        "tenant_slug": tenant_slug,
        "screen_slug": screen_slug,
        "screen_path": screen_path,
    }


@app.get("/api/admin/tv-access")
def admin_tv_access_get(request: Request) -> dict[str, Any]:
    require_auth(request)
    if deployment_mode() != "saas" or not saas_db_enabled():
        raise HTTPException(status_code=404, detail="Not found.")
    from .tenant_ctx import tenant_slug as current_tenant

    slug = current_tenant()
    if not slug:
        raise HTTPException(status_code=400, detail="Tenant is not resolved.")
    pin_db = False
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT code_plaintext, COALESCE(pin_bypass, false) FROM tv_access WHERE tenant_slug=%s",
                (slug,),
            )
            row = cur.fetchone()
            ok = bool(row)
            code = str(row[0] or "").strip() if row else ""
            pin_db = bool(row[1]) if row else False
        conn.commit()
    cfg = load_config()
    pin_cfg = bool(cfg.get("tv_pair_pin_bypass"))
    pin_env = _tv_pair_pin_bypass_env()
    return {
        "status": "ok",
        "tenant_slug": slug,
        "configured": ok,
        "code": code,
        "pin_bypass_from_db": pin_db,
        "pin_bypass_from_config": pin_cfg,
        "pin_bypass_from_env": pin_env,
        "pin_bypass_effective": pin_env or pin_db or pin_cfg,
    }


@app.post("/api/admin/tv-access/rotate-code")
async def admin_tv_access_rotate_code(request: Request) -> dict[str, Any]:
    require_auth(request)
    if deployment_mode() != "saas" or not saas_db_enabled():
        raise HTTPException(status_code=404, detail="Not found.")
    from .tenant_ctx import tenant_slug as current_tenant

    slug = current_tenant()
    if not slug:
        raise HTTPException(status_code=400, detail="Tenant is not resolved.")
    # При первой записи задаём случайный PIN (не 0000) и возвращаем его один раз в ответе.
    code = _generate_tv_code()
    ch = tv_code_hash(code)
    initial_pin: str | None = None
    pin_hint = "PIN не изменён."
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pin_salt, pin_hash FROM tv_access WHERE tenant_slug=%s", (slug,))
            row = cur.fetchone()
            if not row:
                pin_salt = secrets.token_hex(8)
                initial_pin = f"{secrets.randbelow(900_000) + 100_000:06d}"
                pin_hash_db = tv_pin_hash(initial_pin, pin_salt)
                pin_bypass_init = bool(load_config().get("tv_pair_pin_bypass"))
                cur.execute(
                    """
                    INSERT INTO tv_access (tenant_slug, code_plaintext, code_hash, pin_salt, pin_hash, pin_bypass, created_at, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,now(),now())
                    """,
                    (slug, code, ch, pin_salt, pin_hash_db, pin_bypass_init),
                )
                pin_hint = "Сохраните PIN — он показан один раз. При необходимости смените в настройках."
            else:
                pin_salt, pin_hash_db = row[0], row[1]
                cur.execute(
                    "UPDATE tv_access SET code_plaintext=%s, code_hash=%s, updated_at=now() WHERE tenant_slug=%s",
                    (code, ch, slug),
                )
        conn.commit()
    out: dict[str, Any] = {
        "status": "ok",
        "tenant_slug": slug,
        "code": code,
        "pin_hint": pin_hint,
    }
    if initial_pin is not None:
        out["initial_pin"] = initial_pin
    return out


@app.post("/api/admin/tv-access/set-pin")
async def admin_tv_access_set_pin(request: Request) -> dict[str, Any]:
    require_auth(request)
    if deployment_mode() != "saas" or not saas_db_enabled():
        raise HTTPException(status_code=404, detail="Not found.")
    from .tenant_ctx import tenant_slug as current_tenant

    slug = current_tenant()
    if not slug:
        raise HTTPException(status_code=400, detail="Tenant is not resolved.")
    body = await request.json()
    pin = _normalize_tv_pair_pin(str(body.get("pin") or ""))
    if not re.fullmatch(r"[0-9]{4,12}", pin):
        raise HTTPException(status_code=400, detail="PIN must be 4..12 digits")
    pin_salt = secrets.token_hex(8)
    ph = tv_pin_hash(pin, pin_salt)
    with connect_public() as conn:
        with conn.cursor() as cur:
            # Требуем, чтобы код уже был сгенерен (иначе админ сначала rotate-code).
            cur.execute("SELECT code_hash FROM tv_access WHERE tenant_slug=%s", (slug,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=409, detail="TV code is not generated yet.")
            cur.execute(
                "UPDATE tv_access SET pin_salt=%s, pin_hash=%s, updated_at=now() WHERE tenant_slug=%s",
                (pin_salt, ph, slug),
            )
        conn.commit()
    return {"status": "ok"}


@app.post("/api/admin/tv-access/pin-bypass")
async def admin_tv_access_pin_bypass(request: Request) -> dict[str, Any]:
    """Включить/выключить обход PIN: tv_access.pin_bypass (источник для /t/…) + tv_pair_pin_bypass в config.json."""
    require_auth(request)
    if deployment_mode() != "saas" or not saas_db_enabled():
        raise HTTPException(status_code=404, detail="Not found.")
    from .tenant_ctx import tenant_slug as current_tenant

    slug = current_tenant()
    if not slug:
        raise HTTPException(status_code=400, detail="Tenant is not resolved.")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    if "enabled" not in body:
        raise HTTPException(status_code=400, detail="enabled required")
    enabled = bool(body.get("enabled"))
    db_written = False
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tv_access SET pin_bypass=%s, updated_at=now() WHERE tenant_slug=%s",
                (enabled, slug),
            )
            db_written = int(cur.rowcount or 0) > 0
        conn.commit()
    cfg = load_config()
    cfg["tv_pair_pin_bypass"] = enabled
    write_json(CONFIG_PATH, sanitize_config(cfg))
    return {
        "status": "ok",
        "pin_bypass_from_db": enabled if db_written else False,
        "pin_bypass_from_config": enabled,
    }


@app.get("/api/admin/screen-watch")
def get_admin_screen_watch(request: Request) -> dict[str, Any]:
    require_auth(request)
    config = load_config()
    return screen_watch_snapshot(list(config.get("screens") or []))


@app.post("/api/admin/screen-watch/reset-counters")
def admin_reset_screen_watch_counters(request: Request) -> dict[str, Any]:
    require_auth(request)
    return {"status": "ok", "visits": reset_stats_counters()}
