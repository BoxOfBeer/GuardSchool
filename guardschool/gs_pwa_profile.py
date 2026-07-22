"""Resolve effective PWA title and icon for a configured screen."""
from __future__ import annotations

from typing import Any
import unicodedata
from urllib.parse import urlparse

PWA_DEFAULT_TITLE = "GuardSchool"
PWA_DEFAULT_ICON = "/static/pwa/icon_default.png"
PWA_PROFILE_WIDGET_TYPES = ("booking_manager", "booking_public", "checkin_monitor", "checkin_submit")


def _normalize_screen_slug(raw: object) -> str:
    value = unicodedata.normalize("NFKC", str(raw or ""))
    return value.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "").replace("\ufeff", "").strip().lower()


def pwa_widget_types_from_value(raw: object) -> tuple[str, ...]:
    """Sanitize the device widget filter used to select a per-widget PWA profile."""
    allowed = set(PWA_PROFILE_WIDGET_TYPES)
    result: list[str] = []
    for part in str(raw or "").split(","):
        widget_type = part.strip().lower()
        if widget_type in allowed and widget_type not in result:
            result.append(widget_type)
    return tuple(result)


def normalize_pwa_upload_icon_path(raw: object) -> str:
    """Return a safe tenant upload path or an empty string."""
    candidate = str(raw or "").strip()
    if not candidate:
        return ""
    low = candidate.lower()
    if low.startswith("uploads/"):
        candidate = "/" + candidate
    if candidate.startswith("/uploads/"):
        return candidate.split("?", 1)[0][:512]
    if low.startswith(("http://", "https://")):
        try:
            path = (urlparse(candidate).path or "").split("?", 1)[0]
        except Exception:
            return ""
        if path.startswith("/uploads/"):
            return path[:512]
    return ""


def _settings(widget: dict[str, Any]) -> dict[str, Any]:
    raw = widget.get("settings")
    return raw if isinstance(raw, dict) else {}


def _screen_widgets_ordered(screen: dict[str, Any]) -> list[dict[str, Any]]:
    """Flat screen order plus carousel children, without importing HTTP modules."""
    raw_widgets = screen.get("widgets")
    if not isinstance(raw_widgets, list):
        return []
    widgets = [widget for widget in raw_widgets if isinstance(widget, dict)]
    by_id = {str(widget.get("id") or "").strip(): widget for widget in widgets if str(widget.get("id") or "").strip()}
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for widget in widgets:
        widget_id = str(widget.get("id") or "").strip()
        if not widget_id or widget_id not in seen:
            result.append(widget)
            if widget_id:
                seen.add(widget_id)
        if str(widget.get("type") or "") != "carousel":
            continue
        for child_id in _settings(widget).get("childWidgetIds") or []:
            child = by_id.get(str(child_id).strip())
            child_key = str(child.get("id") or "").strip() if child else ""
            if child and child_key not in seen:
                result.append(child)
                if child_key:
                    seen.add(child_key)
    return result


def _first_widget_pwa(widgets: list[dict[str, Any]], widget_types: tuple[str, ...]) -> tuple[str, str]:
    title = ""
    icon = ""
    for widget_type in widget_types:
        for widget in widgets:
            if str(widget.get("type") or "") != widget_type:
                continue
            st = _settings(widget)
            if not title:
                title = str(st.get("pwa_title") or "").strip()[:64]
            if not icon:
                icon = normalize_pwa_upload_icon_path(st.get("pwa_icon_url"))
        if title and icon:
            break
    return title, icon


def resolve_pwa_profile(
    config: dict[str, Any],
    screen_slug: str,
    preferred_widget_types: tuple[str, ...] | list[str] = (),
) -> tuple[str, str]:
    """Widget-specific values override general PWA values and technical defaults."""
    cfg = config if isinstance(config, dict) else {}
    general = cfg.get("pwa") if isinstance(cfg.get("pwa"), dict) else {}
    general_title = str(general.get("title") or "").strip()[:64]
    general_icon = normalize_pwa_upload_icon_path(general.get("icon_url"))

    slug_key = _normalize_screen_slug(screen_slug)
    screens = cfg.get("screens") if isinstance(cfg.get("screens"), list) else []
    screen = next(
        (
            item
            for item in screens
            if isinstance(item, dict)
            and _normalize_screen_slug(item.get("slug")) == slug_key
        ),
        None,
    )
    if not isinstance(screen, dict):
        return general_title or PWA_DEFAULT_TITLE, general_icon or PWA_DEFAULT_ICON

    widgets = [
        widget
        for widget in _screen_widgets_ordered(screen)
        if isinstance(widget, dict) and widget.get("enabled") is not False
    ]
    available_types = {str(widget.get("type") or "") for widget in widgets}
    preferred = tuple(
        widget_type
        for widget_type in pwa_widget_types_from_value(",".join(preferred_widget_types))
        if widget_type in available_types
    )
    selected_type = preferred[0] if preferred else ""
    booking_order = (selected_type,) if selected_type in ("booking_public", "booking_manager") else ("booking_manager", "booking_public")
    checkin_order = (selected_type,) if selected_type in ("checkin_submit", "checkin_monitor") else ("checkin_monitor", "checkin_submit")
    booking_title, booking_icon = _first_widget_pwa(widgets, booking_order)
    checkin_title, checkin_icon = _first_widget_pwa(widgets, checkin_order)

    # A booking screen uses its booking profile; otherwise retain the established
    # check-in monitor-over-submit priority. Empty fields inherit independently.
    has_booking = bool(available_types & {"booking_public", "booking_manager"})
    if selected_type in ("checkin_submit", "checkin_monitor"):
        specific_title, specific_icon = checkin_title, checkin_icon
    elif has_booking:
        specific_title, specific_icon = booking_title, booking_icon
    else:
        specific_title, specific_icon = checkin_title, checkin_icon

    title = specific_title or general_title
    icon = specific_icon or general_icon
    if not title:
        # A semantic fallback must stay inside the selected widget family.
        # Otherwise an old check-in title can brand a booking-only device.
        if selected_type in ("booking_public", "booking_manager") or has_booking:
            fallback_types = booking_order
            fallback_key = "heading"
        else:
            fallback_types = checkin_order
            fallback_key = "panel_title"
        for widget_type in fallback_types:
            for widget in widgets:
                if str(widget.get("type") or "") != widget_type:
                    continue
                title = str(_settings(widget).get(fallback_key) or "").strip()[:64]
                if title:
                    break
            if title:
                break
    return title or PWA_DEFAULT_TITLE, icon or PWA_DEFAULT_ICON
