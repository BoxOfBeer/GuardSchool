"""School config.json: load, sanitize, defaults, emergency templates."""
from __future__ import annotations

import copy
from typing import Any

from .gs_checkin import sanitize_checkin_block
from .gs_jsonio import read_json
from .gs_paths import CONFIG_PATH
from .gs_rss_news import sanitize_rss_refresh_minutes, sanitize_rss_sources
from .gs_uploads_bg import safe_rel_uploads_subdir
from .widget_registry import (
    ADMIN_PALETTE_WIDGET_TYPES,
    GRID_COLS,
    GRID_ROWS,
    dedupe_widgets,
    loaded_widget_types,
)

from .gs_app_config_audio import (  # noqa: F401
    DEFAULT_BELL_TRIGGER_SEC_WINDOW,
    default_audio_stream_settings,
    normalize_multicast_ip_value,
    sanitize_audio_stream,
)
from .gs_app_config_defaults import (  # noqa: F401
    _default_emergency_templates,
    _sanitize_emergency_templates_list,
    apply_emergency_template_to_screen,
    default_config,
    default_screen,
    ensure_default_widgets,
    migrate_screen_layout,
    _valid_iana_timezone,
)

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
