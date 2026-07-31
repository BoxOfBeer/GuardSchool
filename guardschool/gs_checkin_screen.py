"""Screen lookup, widget traversal, check-in board payload."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from .gs_checkin import (
    build_summary_for_places,
    enrich_checkin_event_for_client,
    list_journal_filtered,
    range_bounds_utc,
    sanitize_places_list,
)
from .gs_tv_screen_api import normalize_screen_slug_for_api as _normalize_screen_slug_for_api
from .widget_registry import (
    ADMIN_PALETTE_WIDGET_TYPES,
    DEVICE_WIDGET_TAB_ORDER,
)

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
    for typ in DEVICE_WIDGET_TAB_ORDER:
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


def screen_config_by_slug(config: dict[str, Any], slug_key: str) -> dict[str, Any] | None:
    for item in config.get("screens") or []:
        if _normalize_screen_slug_for_api(str(item.get("slug") or "")) == slug_key and item.get("is_active", True):
            return item
    return None


def screen_widgets_ordered_with_carousel_children(screen: dict[str, Any]) -> list[dict[str, Any]]:
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


def find_submit_widget(screen: dict[str, Any], widget_id: str) -> dict[str, Any] | None:
    want = str(widget_id).strip()
    for w in screen_widgets_ordered_with_carousel_children(screen):
        if isinstance(w, dict) and str(w.get("id") or "").strip() == want and w.get("type") == "checkin_submit":
            return w
    return None


def find_monitor_widget(screen: dict[str, Any], widget_id: str) -> dict[str, Any] | None:
    want = str(widget_id).strip()
    for w in screen_widgets_ordered_with_carousel_children(screen):
        if isinstance(w, dict) and str(w.get("id") or "").strip() == want and w.get("type") == "checkin_monitor":
            return w
    return None


def checkin_events_screen_slug_for_monitor(
    config: dict[str, Any], mw: dict[str, Any], display_slug_key: str
) -> str:
    """Slug экрана, с которого пишутся события в БД (форма отметки). По умолчанию — экран, где висит сводка."""
    raw = str((mw.get("settings") or {}).get("events_screen_slug") or "").strip()
    alt = _normalize_screen_slug_for_api(raw)
    if not alt:
        return display_slug_key
    if screen_config_by_slug(config, alt):
        return alt
    return display_slug_key


def resolve_checkin_submit_places(screen: dict[str, Any], submit_w: dict[str, Any]) -> list[dict[str, str]]:
    """Места только из виджета «Сводка» (явная ссылка или ровно одна сводка на экране)."""
    st = submit_w.get("settings") or {}
    link = str(st.get("monitor_widget_id") or "").strip()
    if link:
        mw = find_monitor_widget(screen, link)
        if mw:
            return sanitize_places_list((mw.get("settings") or {}).get("places"))
    mons = [
        w
        for w in screen_widgets_ordered_with_carousel_children(screen)
        if isinstance(w, dict) and w.get("type") == "checkin_monitor"
    ]
    if len(mons) == 1:
        return sanitize_places_list((mons[0].get("settings") or {}).get("places"))
    return sanitize_places_list(st.get("places"))


def checkin_period_normalize(period: str) -> str:
    p = (period or "day").strip().lower()
    return p if p in ("day", "week", "month") else "day"


def checkin_board_payload(
    config: dict[str, Any],
    tenant_id: str,
    slug_key: str,
    monitor_widget_id: str,
    period: str,
) -> dict[str, Any]:
    screen = screen_config_by_slug(config, slug_key)
    if not screen:
        raise HTTPException(status_code=404, detail="Экран не найден.")
    mw = find_monitor_widget(screen, monitor_widget_id)
    if not mw:
        raise HTTPException(status_code=404, detail="Виджет сводки не найден.")
    places = sanitize_places_list((mw.get("settings") or {}).get("places"))
    period_n = checkin_period_normalize(period)
    event_slug = checkin_events_screen_slug_for_monitor(config, mw, slug_key)
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
