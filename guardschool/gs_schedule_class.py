"""Классы расписания: селекторы, сортировка, pickable для экрана/ТВ."""
from __future__ import annotations

import re
from typing import Any

from .gs_class_key import normalize_class
from .gs_data_loaders import load_full_schedule, load_schedule, load_schedule_sample

_TEMP_DISABLE_SCREEN_CLASS_FILTER = False

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
