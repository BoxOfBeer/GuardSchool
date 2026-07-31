"""Schedule rows, bell status/audio, build_schedule_payload for TV API."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from .gs_app_config import DEFAULT_BELL_TRIGGER_SEC_WINDOW, load_config
from .gs_class_key import normalize_class
from .gs_data_loaders import (
    load_full_schedule,
    load_overrides,
    load_schedule,
    load_schedule_sample,
)
from .gs_ensure_dirs import ensure_dirs
from .gs_paths import BELL_SOUNDS_DIR

# --- submodules (re-export for backward-compatible imports) ---
from .gs_bell_entries import (  # noqa: F401
    BREAK_ORCH_FADE_SEC,
    BREAK_ORCH_HEAD_SEC,
    BREAK_ORCH_SILENCE_SEC,
    BREAK_ORCH_START_BELL_SEC,
    MORNING_PRE_FIRST_LESSON_MIN,
    PRE_BELL_AFADE_IN_SEC,
    PRE_BELL_FIRE_SEC_WINDOW,
    PRE_BELL_LEAD_MINUTES,
    PRE_BELL_MAX_DURATION_SEC,
    as_lesson_number,
    bell_audio_url_to_path,
    entry_academic_num,
    get_screen_bell_entries_and_bells,
    last_lesson_cap,
    time_to_minutes,
)
from .gs_bell_schedules_io import (  # noqa: F401
    _norm_hex_color,
    default_bell_schedules,
    load_bell_schedules,
    migrate_bell_schedules,
    schedule_date_iso,
)
from .gs_bell_status import build_bell_status, tomorrow_schedule_visible
from .gs_schedule_bells_time import (  # noqa: F401
    calendar_today_for_config,
    display_settings_dict,
    wall_clock_minutes_for_config,
)
from .gs_schedule_class import (  # noqa: F401
    _TEMP_DISABLE_SCREEN_CLASS_FILTER,
    class_in_selected,
    class_matches_selector,
    class_sort_key,
    distinct_schedule_class_names_from_sources,
    pickable_classes_for_screen,
    pickable_classes_for_tv_device_panel,
)
from .gs_schedule_rows import (  # noqa: F401
    collect_enriched_schedule_rows,
    compute_max_lesson_index_for_screen_day,
    max_lesson_index_from_enriched_rows,
)
from .gs_bell_entries import pick_entry_sound, resolve_bell_sound_url


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
