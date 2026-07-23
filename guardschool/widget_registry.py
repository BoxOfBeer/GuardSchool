"""Реестр типов виджетов: manifest, загрузка, нормализация."""
from __future__ import annotations

import logging
import secrets
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

_LOG = logging.getLogger(__name__)

CURRENT_WIDGET_API_VERSION = 1

GRID_COLS = 32
GRID_ROWS = 26

SINGLETON_WIDGET_IDS: dict[str, str] = {
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

TYPE_ALIASES: dict[str, str] = {
    "rss_feed": "rss_news",
    "external_news": "rss_news",
}

ADMIN_PALETTE_WIDGET_TYPES: frozenset[str] = frozenset(
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
        "booking_public",
        "booking_manager",
    }
)

DEVICE_WIDGET_TAB_ORDER: tuple[str, ...] = (
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
    "booking_public",
    "booking_manager",
)

VALID_PERMISSIONS = frozenset({"filesystem", "network", "subprocess"})


class WidgetLoadStatus(str, Enum):
    loaded = "loaded"
    missing = "missing"
    error = "error"


@dataclass
class WidgetManifest:
    type: str
    title: str
    category: str = "basic"
    description: str = ""
    version: str = "1.0.0"
    api_version: int = 1
    author: str = "GuardSchool"
    official: bool = True
    singleton_id: str | None = None
    aliases: tuple[str, ...] = ()
    requires_capabilities: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    settings_schema: dict[str, Any] = field(default_factory=dict)
    mobile_supported: bool = True
    tv_supported: bool = True
    admin_supported: bool = True
    render_key: str = ""

    def __post_init__(self) -> None:
        if not self.render_key:
            self.render_key = self.type


_manifests: dict[str, WidgetManifest] = {}
_load_errors: dict[str, str] = {}
_migration_warnings: list[str] = []
_default_settings_fns: dict[str, Callable[[dict[str, Any]], None]] = {}


def _normalize_screen_slug(slug: str) -> str:
    t = unicodedata.normalize("NFKC", str(slug or "")).strip().lower()
    return t


def resolve_type(raw: str) -> str:
    wtype = str(raw or "").strip()
    return TYPE_ALIASES.get(wtype, wtype)


def register_widget(
    manifest: WidgetManifest | dict[str, Any],
    *,
    default_settings_fn: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    if isinstance(manifest, dict):
        from .widget_settings_schemas import apply_default_schema

        manifest = apply_default_schema(manifest)
        perms = manifest.get("permissions") or ()
        manifest = WidgetManifest(
            type=str(manifest["type"]),
            title=str(manifest.get("title") or manifest["type"]),
            category=str(manifest.get("category") or "basic"),
            description=str(manifest.get("description") or ""),
            version=str(manifest.get("version") or "1.0.0"),
            api_version=int(manifest.get("api_version", 1)),
            author=str(manifest.get("author") or "GuardSchool"),
            official=bool(manifest.get("official", True)),
            singleton_id=manifest.get("singleton_id"),
            aliases=tuple(manifest.get("aliases") or ()),
            requires_capabilities=tuple(manifest.get("requires_capabilities") or manifest.get("requires") or ()),
            permissions=tuple(p for p in perms if p in VALID_PERMISSIONS),
            settings_schema=dict(manifest.get("settings_schema") or {}),
            mobile_supported=bool(manifest.get("mobile_supported", True)),
            tv_supported=bool(manifest.get("tv_supported", True)),
            admin_supported=bool(manifest.get("admin_supported", True)),
            render_key=str(manifest.get("render_key") or manifest["type"]),
        )
    wtype = resolve_type(manifest.type)
    manifest.type = wtype
    if manifest.requires_capabilities:
        from .capabilities import has_capability

        for cap in manifest.requires_capabilities:
            if not has_capability(cap):
                _load_errors[wtype] = f"Виджет требует capability «{cap}», которая недоступна."
                _LOG.warning("Widget %s missing capability %s", wtype, cap)
                return
    if manifest.api_version > CURRENT_WIDGET_API_VERSION:
        _load_errors[wtype] = (
            f"Виджет требует API v{manifest.api_version}, установлена v{CURRENT_WIDGET_API_VERSION}."
        )
        _LOG.warning("Widget %s api_version too new: %s", wtype, manifest.api_version)
        return
    if manifest.api_version < CURRENT_WIDGET_API_VERSION:
        _migration_warnings.append(
            f"Виджет {wtype} объявлен для API v{manifest.api_version}; текущая v{CURRENT_WIDGET_API_VERSION}."
        )
    _manifests[wtype] = manifest
    if default_settings_fn:
        _default_settings_fns[wtype] = default_settings_fn
    for alias in manifest.aliases:
        TYPE_ALIASES[alias] = wtype
        if manifest.singleton_id:
            SINGLETON_WIDGET_IDS[alias] = manifest.singleton_id


def get_widget(wtype: str) -> WidgetManifest | None:
    return _manifests.get(resolve_type(wtype))


def list_widgets(*, official_only: bool = False, for_saas: bool = False) -> list[WidgetManifest]:
    out = list(_manifests.values())
    if official_only or for_saas:
        out = [m for m in out if m.official]
    return sorted(out, key=lambda m: m.type)


def widget_status(wtype: str) -> WidgetLoadStatus:
    resolved = resolve_type(wtype)
    if resolved in _load_errors:
        return WidgetLoadStatus.error
    if resolved in _manifests:
        return WidgetLoadStatus.loaded
    return WidgetLoadStatus.missing


def explain_widget_status(wtype: str) -> str:
    resolved = resolve_type(wtype)
    st = widget_status(resolved)
    if st == WidgetLoadStatus.loaded:
        m = get_widget(resolved)
        if m and not m.official:
            return "Сторонний локальный виджет. Используется на ответственность администратора установки."
        return ""
    if st == WidgetLoadStatus.error:
        err = _load_errors.get(resolved, "")
        return err or f"Не удалось загрузить виджет {resolved}."
    return (
        f"Не могу загрузить виджет {resolved}: модуль отсутствует в папке widgets. "
        f"Верните файл widgets/{resolved}.py или удалите виджет с экрана."
    )


def loaded_widget_types() -> list[str]:
    from .widget_loader import load_all_widgets

    load_all_widgets()
    return sorted(_manifests.keys())


def _apply_type_defaults(widget: dict[str, Any]) -> None:
    wtype = widget.get("type")
    fn = _default_settings_fns.get(wtype)
    if fn:
        fn(widget)
        return
    _apply_builtin_type_defaults(widget)


def _apply_builtin_type_defaults(widget: dict[str, Any]) -> None:
    """Defaults для встроенных типов (до переноса в widgets/*.py)."""
    wtype = widget.get("type")
    widget.setdefault("settings", {})
    if wtype in {"date", "time", "text", "bell_status", "bell_countdown", "rss_news"}:
        widget["settings"].setdefault("fontSize", 24)
        widget["settings"].setdefault("color", "#ffffff")
        widget["settings"].setdefault("bold", False)
    if wtype in {"holidays", "announcements", "marquee", "school_news", "rss_news"}:
        widget["settings"].setdefault("fontSize", 18)
        widget["settings"].setdefault("color", "#ffffff")
        widget["settings"].setdefault("background", "rgba(15,23,42,0.55)")
        widget["settings"].setdefault("bold", False)
    if wtype in {"holidays", "announcements", "school_news", "rss_news"}:
        widget["settings"].setdefault("titleFontSize", 18)
    if wtype == "text":
        widget["settings"].setdefault("background", "rgba(0,0,0,0.35)")
        widget["settings"].setdefault("text", "")
    if wtype == "announcements":
        widget["settings"].setdefault("items", "")
        widget["settings"].setdefault("useManual", False)
        widget["settings"].setdefault("rotateSec", 30)
    if wtype == "marquee":
        widget["settings"].setdefault("items", "")
        widget["settings"].setdefault("useManual", False)
        widget["settings"].setdefault("speedSec", 18)
    if wtype in {"school_news", "rss_news"}:
        widget["settings"].setdefault("rotateSec", 12)
        try:
            legacy_fs = int(widget["settings"].get("fontSize") or 18)
        except (TypeError, ValueError):
            legacy_fs = 18
        try:
            body_fs = int(widget["settings"].get("bodyFontSize") or legacy_fs)
        except (TypeError, ValueError):
            body_fs = legacy_fs
        body_fs = max(8, min(96, body_fs))
        widget["settings"]["bodyFontSize"] = body_fs
        widget["settings"]["fontSize"] = body_fs
    if wtype == "holidays":
        widget["settings"].setdefault("count", 5)
    if wtype in {"bell_status", "bell_countdown"}:
        widget["settings"].setdefault("background", "rgba(15,23,42,0.55)")
        widget["settings"].setdefault("titleFontSize", 18)
    if wtype == "schedule":
        widget["settings"].setdefault("highlightColor", "#8b0000")
        widget["settings"].setdefault("sampleDiffColor", "#fee2e2")
        widget["settings"].setdefault("headerColor", "#1e3a5f")
        widget["settings"].setdefault("bodyColor", "rgba(255,255,255,0.9)")
        widget["settings"].setdefault("fontSize", 16)
        widget["settings"].setdefault("titleFontSize", 20)
        widget["settings"].setdefault("classes", [])
        widget["settings"].setdefault("bold", False)
    if wtype == "carousel":
        widget["settings"].setdefault("startDelaySec", 0)
        widget["settings"].setdefault("animation", "slide")
        widget["settings"].setdefault("childWidgetIds", [])
        widget["settings"].setdefault("childSlideSec", {})
    if wtype == "emergency":
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
    if wtype == "image":
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
    if wtype == "rss_news":
        widget["settings"].setdefault("titleFontSize", 18)
    if wtype == "checkin_submit":
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
    if wtype == "checkin_monitor":
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
        esc = _normalize_screen_slug(str(widget["settings"].get("events_screen_slug") or ""))
        widget["settings"]["events_screen_slug"] = esc if esc else ""
        piu = str(widget["settings"].get("pwa_icon_url") or "").strip()
        if piu and not piu.startswith("/uploads/"):
            piu = ""
        widget["settings"]["pwa_icon_url"] = piu[:512]
        widget["settings"]["pwa_title"] = str(widget["settings"].get("pwa_title") or "").strip()[:64]
    if wtype in ("checkin_submit", "checkin_monitor"):
        widget["settings"].setdefault("fontSize", 0)
        widget["settings"].setdefault("bold", False)
        try:
            fs = int(widget["settings"].get("fontSize") or 0)
        except (TypeError, ValueError):
            fs = 0
        widget["settings"]["fontSize"] = max(0, min(48, fs))
        widget["settings"]["bold"] = bool(widget["settings"].get("bold"))
    if wtype in ("booking_public", "booking_manager"):
        widget["settings"].setdefault("module_id", "booking-main")
        widget["settings"].setdefault("heading", "Запись" if wtype == "booking_public" else "Управление записями")
        widget["settings"].setdefault("pwa_icon_url", "")
        widget["settings"].setdefault("pwa_title", "")
        mid = "".join(ch for ch in str(widget["settings"].get("module_id") or "booking-main").lower() if ch.isalnum() or ch in "-_")
        widget["settings"]["module_id"] = (mid or "booking-main")[:80]
        widget["settings"]["heading"] = str(widget["settings"].get("heading") or "").strip()[:100]
        piu = str(widget["settings"].get("pwa_icon_url") or "").strip()
        if piu and not piu.startswith("/uploads/"):
            piu = ""
        widget["settings"]["pwa_icon_url"] = piu[:512]
        widget["settings"]["pwa_title"] = str(widget["settings"].get("pwa_title") or "").strip()[:64]
        if wtype == "booking_manager":
            color_defaults = {
                "public_action_color": "#2563eb",
                "public_action_text_color": "#ffffff",
                "public_free_color": "#16a34a",
                "public_booked_color": "#b91c1c",
                "public_cancel_color": "#ca8a04",
            }
            for key, fallback in color_defaults.items():
                value = str(widget["settings"].get(key) or "").strip().lower()
                valid = (
                    len(value) == 7
                    and value.startswith("#")
                    and all(ch in "0123456789abcdef" for ch in value[1:])
                )
                widget["settings"][key] = value if valid else fallback
            manager_color_defaults = {
                "manager_action_color": widget["settings"]["public_action_color"],
                "manager_action_text_color": widget["settings"]["public_action_text_color"],
            }
            for key, fallback in manager_color_defaults.items():
                value = str(widget["settings"].get(key) or "").strip().lower()
                valid = (
                    len(value) == 7
                    and value.startswith("#")
                    and all(ch in "0123456789abcdef" for ch in value[1:])
                )
                widget["settings"][key] = value if valid else fallback
    widget["settings"].setdefault("backdrop", True)


def normalize_widget(widget: dict[str, Any]) -> dict[str, Any]:
    wtype = str(widget.get("type") or "").strip()
    if wtype in TYPE_ALIASES:
        widget["type"] = TYPE_ALIASES[wtype]
        wtype = widget["type"]
    widget["id"] = widget.get("id") or SINGLETON_WIDGET_IDS.get(widget.get("type"), secrets.token_hex(4))
    widget.setdefault("enabled", True)
    widget.setdefault("settings", {})
    if widget_status(wtype) == WidgetLoadStatus.loaded or wtype in _manifests:
        _apply_type_defaults(widget)
    else:
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


def manifest_to_public(m: WidgetManifest) -> dict[str, Any]:
    st = widget_status(m.type)
    return {
        "type": m.type,
        "title": m.title,
        "category": m.category,
        "description": m.description,
        "version": m.version,
        "api_version": m.api_version,
        "author": m.author,
        "official": m.official,
        "singleton_id": m.singleton_id,
        "aliases": list(m.aliases),
        "requires_capabilities": list(m.requires_capabilities),
        "permissions": list(m.permissions),
        "mobile_supported": m.mobile_supported,
        "tv_supported": m.tv_supported,
        "admin_supported": m.admin_supported,
        "render_key": m.render_key,
        "settings_schema": dict(m.settings_schema) if m.settings_schema else {},
        "status": st.value,
        "status_message": explain_widget_status(m.type),
    }


def _widget_usable_in_palette(m: WidgetManifest) -> bool:
    if not m.admin_supported:
        return False
    if m.requires_capabilities:
        from .capabilities import has_capability

        return all(has_capability(c) for c in m.requires_capabilities)
    return True


def widget_registry_public(*, official_only: bool = False, for_saas: bool = False) -> dict[str, Any]:
    from .widget_loader import load_all_widgets

    load_all_widgets()
    manifests = list_widgets(official_only=official_only, for_saas=for_saas)
    widgets = [manifest_to_public(m) for m in manifests]
    palette = [m.type for m in manifests if _widget_usable_in_palette(m)]
    order = [t for t in DEVICE_WIDGET_TAB_ORDER if t in palette or t in _manifests]
    for t in palette:
        if t not in order:
            order.append(t)
    return {
        "api_version": CURRENT_WIDGET_API_VERSION,
        "widgets": widgets,
        "palette_order": order,
        "singleton_ids": {k: v for k, v in SINGLETON_WIDGET_IDS.items() if k in _manifests or k in TYPE_ALIASES},
        "migration_warnings": list(_migration_warnings),
    }


_INITIAL_TYPE_ALIASES = dict(TYPE_ALIASES)
_INITIAL_SINGLETON_WIDGET_IDS = dict(SINGLETON_WIDGET_IDS)


def reset_widget_registry_for_tests() -> None:
    """Сброс реестра виджетов (только для unit-тестов)."""
    _manifests.clear()
    _load_errors.clear()
    _migration_warnings.clear()
    _default_settings_fns.clear()
    TYPE_ALIASES.clear()
    TYPE_ALIASES.update(_INITIAL_TYPE_ALIASES)
    SINGLETON_WIDGET_IDS.clear()
    SINGLETON_WIDGET_IDS.update(_INITIAL_SINGLETON_WIDGET_IDS)
