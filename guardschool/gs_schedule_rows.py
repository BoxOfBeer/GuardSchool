"""Обогащённые строки расписания для ТВ (dated + weekly + sample + overrides)."""
from __future__ import annotations

import time
from datetime import date
from typing import Any

from .gs_bell_schedules_io import _norm_hex_color, schedule_date_iso
from .gs_class_key import normalize_class
from .gs_data_loaders import load_full_schedule, load_overrides, load_schedule, load_schedule_sample
from .gs_bell_entries import as_lesson_number
from .gs_schedule_class import (
    _TEMP_DISABLE_SCREEN_CLASS_FILTER,
    class_in_selected,
    class_sort_key,
)

_ML_INDEX_CACHE: dict[tuple[Any, str], tuple[int | None, float]] = {}
_ML_INDEX_TTL_SEC = 12.0

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
