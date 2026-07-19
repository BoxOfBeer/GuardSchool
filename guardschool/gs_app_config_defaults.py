"""Дефолты config.json: экраны, emergency, migrate layout."""
from __future__ import annotations

import copy
import re
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from .gs_checkin import sanitize_checkin_block
from .gs_app_config_audio import default_audio_stream_settings
from .widget_registry import (
    ADMIN_PALETTE_WIDGET_TYPES,
    GRID_COLS,
    GRID_ROWS,
    SINGLETON_WIDGET_IDS,
    WidgetLoadStatus,
    dedupe_widgets,
    loaded_widget_types,
    normalize_widget,
    widget_status,
)

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
                "title": "Сигналы",
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
                "title": "Новости",
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
                "text": "ЧРЕЗВЫЧАЙНАЯ СИТУАЦИЯ\nСледуйте плану действий персонала.",
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

def ensure_default_widgets(screen: dict[str, Any]) -> dict[str, Any]:
    existing_types = {widget.get("type") for widget in screen.get("widgets", [])}
    for template_widget in default_screen(screen.get("name", "ТВ"), screen.get("slug", "tv"))["widgets"]:
        widget_type = template_widget.get("type")
        if widget_type in SINGLETON_WIDGET_IDS and widget_type not in existing_types:
            if widget_status(str(widget_type)) != WidgetLoadStatus.loaded:
                continue
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
