"""School config.json: load, sanitize, defaults, emergency templates."""
from __future__ import annotations

import copy
import ipaddress
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
from .gs_net_utils import normalize_stream_host
from .gs_jsonio import read_json
from .gs_paths import CONFIG_PATH
from .gs_rss_news import sanitize_rss_refresh_minutes, sanitize_rss_sources
from .gs_uploads_bg import safe_rel_uploads_subdir
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

DEFAULT_BELL_TRIGGER_SEC_WINDOW = 25

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
        _palette_ok = ADMIN_PALETTE_WIDGET_TYPES | set(loaded_widget_types())
        config["admin_palette_hidden_types"] = [
            str(x).strip() for x in _raw_hidden if str(x).strip() in _palette_ok
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
        palette_ok = ADMIN_PALETTE_WIDGET_TYPES | set(loaded_widget_types())
        config["admin_palette_hidden_types"] = [
            str(x).strip() for x in raw_hidden if str(x).strip() in palette_ok
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

