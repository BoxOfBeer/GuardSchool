"""Schedule rows, bell status/audio, build_schedule_payload for TV API."""
from __future__ import annotations

import copy
import logging
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from . import gs_bell_strings as _bell_i18n
from .gs_app_config import DEFAULT_BELL_TRIGGER_SEC_WINDOW, load_config
from .gs_class_key import normalize_class
from .gs_data_loaders import (
    load_announcements,
    load_full_schedule,
    load_holidays,
    load_overrides,
    load_schedule,
    load_schedule_sample,
)
from .gs_ensure_dirs import ensure_dirs
from .gs_paths import BELL_SCHEDULES_PATH, BELL_SOUNDS_DIR
from .gs_jsonio import read_json

_log = logging.getLogger(__name__)
_TEMP_DISABLE_SCREEN_CLASS_FILTER = False

PRE_BELL_LEAD_MINUTES = 1
PRE_BELL_FIRE_SEC_WINDOW = 12
PRE_BELL_MAX_DURATION_SEC = 52
PRE_BELL_AFADE_IN_SEC = 3.0
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
_ML_INDEX_CACHE: dict[tuple[Any, str], tuple[int | None, float]] = {}
_ML_INDEX_TTL_SEC = 12.0

def _tzinfo_from_config_timezone(tzname: str):
    key = (tzname or "").strip() or "Europe/Moscow"
    for cand in (key, "Europe/Moscow"):
        try:
            return ZoneInfo(cand)
        except Exception:
            continue
    lt = datetime.now().astimezone().tzinfo
    return lt if lt is not None else timezone.utc


def display_settings_dict(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "timezone": str((config or {}).get("timezone") or "Europe/Moscow"),
        "clock_offset_minutes": int((config or {}).get("clock_offset_minutes") or 0),
        "ui_locale": str((config or {}).get("ui_locale") or "ru"),
    }


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


def minutes_phrase(n: int, locale: str = "ru") -> str:
    """Склонение для фразы «N минут» в статусе сигналов (ru/en)."""
    return _bell_i18n.minutes_phrase(n, locale)


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


def entry_slot_title(entry: dict[str, Any], locale: str = "ru") -> str:
    """Краткое имя интервала для строк состояния (им. падеж после «Идёт» / «Закончился»)."""
    return _bell_i18n.entry_slot_title(entry, locale, academic_num=entry_academic_num(entry))


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


def display_name_for_academic_lesson_number(
    entries: list[dict[str, Any]], lesson_num: int | None, locale: str = "ru"
) -> str:
    return _bell_i18n.display_name_for_academic_lesson_number(entries, lesson_num, locale)


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
    loc = _bell_i18n.ui_locale_from_config(cfg)
    now_minutes = wall_clock_minutes_for_config(cfg)
    status = {
        "template_name": source_name,
        "entries": entries,
        "current_lesson": None,
        "next_lesson": None,
        "state": "done",
        **_bell_i18n.bell_status_idle_defaults(loc),
    }

    if not entries:
        # Не "done": иначе виджет расписания на ТВ скрывает таблицу на сегодня (как после последнего сигнала).
        status["state"] = "no_bells"
        status.update(_bell_i18n.bell_status_no_entries(loc))
        return status

    first_start = time_to_minutes(entries[0]["start"])
    if now_minutes < first_start:
        diff = first_start - now_minutes
        status["state"] = "before"
        first = entries[0]
        cap = entry_slot_title(first, loc)
        status["next_lesson"] = entry_academic_num(first)
        mp = minutes_phrase(diff, loc)
        status.update(_bell_i18n.bell_status_before(cap, mp, loc))
        return status

    for index, entry in enumerate(entries):
        start = time_to_minutes(entry["start"])
        end = time_to_minutes(entry["end"])
        if start <= now_minutes <= end:
            diff = end - now_minutes
            if not entry_is_academic(entry):
                last_ac = last_academic_lesson_ended_before(entries, now_minutes)
                next_ac = next_academic_lesson_after_index(entries, index)
                label = entry_slot_title(entry, loc)
                mp = minutes_phrase(diff, loc)
                status["state"] = "activity"
                status["current_lesson"] = last_ac
                status["next_lesson"] = next_ac
                status.update(_bell_i18n.bell_status_activity(label, mp, loc))
                return status
            ln = entry_academic_num(entry)
            if ln is None:
                ln = 0
            shown = entry_slot_title(entry, loc)
            mp = minutes_phrase(diff, loc)
            status["state"] = "lesson"
            status["current_lesson"] = ln
            status.update(_bell_i18n.bell_status_lesson(shown, mp, loc))
            return status
        next_start = time_to_minutes(entries[index + 1]["start"]) if index + 1 < len(entries) else None
        if end < now_minutes and next_start is not None and now_minutes < next_start:
            diff = next_start - now_minutes
            last_ac = last_academic_lesson_ended_before(entries, now_minutes)
            next_ac = next_academic_lesson_after_index(entries, index)
            ended_entry = entries[index]
            ended_label = entry_slot_title(ended_entry, loc)
            mp = minutes_phrase(diff, loc)
            status["state"] = "break"
            status["current_lesson"] = last_ac
            status["next_lesson"] = next_ac
            status.update(_bell_i18n.bell_status_break(ended_label, mp, loc))
            return status

    status.update(_bell_i18n.bell_status_day_done(loc))
    return status


def tomorrow_schedule_visible(bell_status: dict[str, Any]) -> bool:
    """Блок «следующий рабочий день» на ТВ — только после окончания последнего интервала дня (сигналы завершены)."""
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
