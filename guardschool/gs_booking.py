"""Tenant-local generic appointment storage and slot calculation."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .gs_app_config import load_config
from .gs_paths import DATA_DIR
from .tenant_ctx import map_data_path

ACTIVE_STATUSES = ("confirmed", "cancel_requested")


def default_booking_config() -> dict[str, Any]:
    return {
        "labels": {
            "title": "Запись",
            "resource": "Специалист",
            "place": "Место",
            "service": "Услуга",
            "person": "Посетитель",
            "family_name": "Фамилия",
            "given_name": "Имя",
            "phone": "Телефон",
        },
        "step_min": 30,
        "max_per_week": 5,
        "paused": False,
        "pause_message": "Новые записи временно приостановлены.",
        "services": [{"id": "basic", "title": "Основная услуга", "duration_min": 30, "active": True}],
        "weekly_windows": {str(i): ([["09:00", "18:00"]] if i < 5 else []) for i in range(7)},
        "exceptions": {},
        "booking_horizon_weeks": 12,
        "reminder_minutes": 120,
        "morning_time": "08:00",
    }


def _db_path() -> Path:
    return map_data_path(DATA_DIR) / "booking.sqlite3"


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS booking_modules (
          module_id TEXT PRIMARY KEY, config_json TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bookings (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          module_id TEXT NOT NULL,
          screen_slug TEXT NOT NULL DEFAULT '',
          device_hash TEXT NOT NULL DEFAULT '',
          source TEXT NOT NULL DEFAULT 'public',
          family_name TEXT NOT NULL, given_name TEXT NOT NULL, phone TEXT NOT NULL,
          service_id TEXT NOT NULL, service_title TEXT NOT NULL,
          duration_min INTEGER NOT NULL,
          start_at TEXT NOT NULL, end_at TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'confirmed',
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          cancel_requested_at TEXT NOT NULL DEFAULT '', reminder_sent_at TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS booking_module_start ON bookings(module_id,start_at);
        CREATE INDEX IF NOT EXISTS booking_device_start ON bookings(module_id,device_hash,start_at);
        CREATE TABLE IF NOT EXISTS booking_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT, booking_id INTEGER NOT NULL,
          module_id TEXT NOT NULL, event_type TEXT NOT NULL, actor TEXT NOT NULL,
          details_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL,
          FOREIGN KEY(booking_id) REFERENCES bookings(id)
        );
        CREATE TABLE IF NOT EXISTS booking_notification_marks (
          module_id TEXT NOT NULL, mark_key TEXT NOT NULL, created_at TEXT NOT NULL,
          PRIMARY KEY(module_id, mark_key)
        );
        """
    )
    columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(bookings)").fetchall()}
    if "screen_slug" not in columns:
        conn.execute("ALTER TABLE bookings ADD COLUMN screen_slug TEXT NOT NULL DEFAULT ''")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _tz() -> ZoneInfo:
    name = str(load_config().get("timezone") or "Europe/Moscow")
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("Europe/Moscow")


def _timezone_name() -> str:
    tz = _tz()
    return str(getattr(tz, "key", "") or tz)


def device_hash(raw: str) -> str:
    value = str(raw or "").strip()
    if len(value) < 12 or len(value) > 256:
        raise ValueError("Не удалось определить устройство.")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _clean_module_id(raw: str) -> str:
    value = "".join(ch for ch in str(raw or "").strip().lower() if ch.isalnum() or ch in "-_")[:80]
    if not value:
        raise ValueError("Не указан модуль записи.")
    return value


def sanitize_config(raw: dict[str, Any]) -> dict[str, Any]:
    base = default_booking_config()
    src = raw if isinstance(raw, dict) else {}
    labels = dict(base["labels"])
    if isinstance(src.get("labels"), dict):
        for key in labels:
            text = str(src["labels"].get(key) or "").strip()[:80]
            if text:
                labels[key] = text
    try:
        step = int(src.get("step_min", base["step_min"]))
    except (TypeError, ValueError):
        step = 30
    step = step if step in (15, 30, 60) else 30
    services = []
    for idx, item in enumerate(src.get("services") or []):
        if not isinstance(item, dict):
            continue
        sid = "".join(ch for ch in str(item.get("id") or f"service-{idx+1}").lower() if ch.isalnum() or ch in "-_")[:50]
        title = str(item.get("title") or "").strip()[:120]
        try:
            duration = int(item.get("duration_min") or step)
        except (TypeError, ValueError):
            duration = step
        duration = max(step, min(12 * 60, duration))
        duration = ((duration + step - 1) // step) * step
        if sid and title:
            services.append({"id": sid, "title": title, "duration_min": duration, "active": item.get("active") is not False})
    if not services:
        services = base["services"]
    windows: dict[str, list[list[str]]] = {}
    source_windows = src.get("weekly_windows") if isinstance(src.get("weekly_windows"), dict) else base["weekly_windows"]
    for day in range(7):
        rows = []
        for pair in source_windows.get(str(day), []) if isinstance(source_windows.get(str(day), []), list) else []:
            if isinstance(pair, list) and len(pair) == 2 and _parse_hhmm(pair[0]) and _parse_hhmm(pair[1]):
                rows.append([str(pair[0]), str(pair[1])])
        windows[str(day)] = rows[:6]
    exceptions: dict[str, Any] = {}
    if isinstance(src.get("exceptions"), dict):
        for key, value in list(src["exceptions"].items())[:180]:
            try:
                date.fromisoformat(str(key))
            except ValueError:
                continue
            if value is None or value == []:
                exceptions[str(key)] = []
            elif isinstance(value, list):
                rows = [p for p in value if isinstance(p, list) and len(p) == 2 and _parse_hhmm(p[0]) and _parse_hhmm(p[1])]
                exceptions[str(key)] = rows[:6]
    return {
        "labels": labels,
        "step_min": step,
        "max_per_week": 5,
        "paused": bool(src.get("paused", False)),
        "pause_message": str(src.get("pause_message") or base["pause_message"]).strip()[:300],
        "services": services,
        "weekly_windows": windows,
        "exceptions": exceptions,
        "booking_horizon_weeks": max(1, min(52, int(src.get("booking_horizon_weeks") or 12))),
        "reminder_minutes": max(15, min(1440, int(src.get("reminder_minutes") or 120))),
        "morning_time": str(src.get("morning_time") or "08:00") if _parse_hhmm(src.get("morning_time") or "08:00") else "08:00",
    }


def get_config(module_id: str) -> dict[str, Any]:
    mid = _clean_module_id(module_id)
    with _connect() as conn:
        row = conn.execute("SELECT config_json FROM booking_modules WHERE module_id=?", (mid,)).fetchone()
    return sanitize_config(json.loads(row[0])) if row else default_booking_config()


def save_config(module_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    mid, cfg = _clean_module_id(module_id), sanitize_config(raw)
    now = _iso(_now())
    with _connect() as conn:
        conn.execute(
            "INSERT INTO booking_modules(module_id,config_json,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(module_id) DO UPDATE SET config_json=excluded.config_json,updated_at=excluded.updated_at",
            (mid, json.dumps(cfg, ensure_ascii=False), now),
        )
    return cfg


def _parse_hhmm(raw: Any) -> time | None:
    try:
        return time.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None


def _service(cfg: dict[str, Any], service_id: str) -> dict[str, Any]:
    for item in cfg["services"]:
        if item["id"] == service_id and item.get("active", True):
            return item
    raise ValueError("Указанная услуга недоступна.")


def _week_start(raw: str | None) -> date:
    today = datetime.now(_tz()).date()
    try:
        chosen = date.fromisoformat(str(raw)) if raw else today
    except ValueError:
        chosen = today
    return chosen - timedelta(days=chosen.weekday())


def _window_datetimes(day: date, cfg: dict[str, Any]) -> list[tuple[datetime, datetime]]:
    tz = _tz()
    rows = cfg["exceptions"].get(day.isoformat(), cfg["weekly_windows"].get(str(day.weekday()), []))
    result = []
    for start_s, end_s in rows:
        st, en = _parse_hhmm(start_s), _parse_hhmm(end_s)
        if not st or not en:
            continue
        start = datetime.combine(day, st, tzinfo=tz)
        end = datetime.combine(day, en, tzinfo=tz)
        if end <= start:
            end += timedelta(days=1)
        result.append((start, end))
    return result


def _row_public(row: sqlite3.Row, *, own: bool = False) -> dict[str, Any]:
    out = {"id": row["id"], "service_title": row["service_title"], "start_at": row["start_at"], "end_at": row["end_at"], "status": row["status"]}
    if own:
        out["can_request_cancel"] = row["status"] == "confirmed"
    return out


def availability(module_id: str, week: str | None, service_id: str, raw_device: str = "") -> dict[str, Any]:
    mid, cfg = _clean_module_id(module_id), get_config(module_id)
    try:
        service = _service(cfg, service_id)
    except ValueError:
        service = next((item for item in cfg["services"] if item.get("active", True)), None)
        if service is None:
            raise
    monday = _week_start(week)
    today = datetime.now(_tz())
    max_day = today + timedelta(weeks=cfg["booking_horizon_weeks"])
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM bookings WHERE module_id=? AND status IN (?,?) AND start_at<? AND end_at>?",
            (mid, *ACTIVE_STATUSES, _iso(datetime.combine(monday + timedelta(days=8), time.min, tzinfo=_tz())), _iso(datetime.combine(monday, time.min, tzinfo=_tz()))),
        ).fetchall()
        mine = []
        if raw_device:
            dh = device_hash(raw_device)
            mine = conn.execute("SELECT * FROM bookings WHERE module_id=? AND device_hash=? AND start_at>=? ORDER BY start_at", (mid, dh, _iso(datetime.combine(monday, time.min, tzinfo=_tz())))).fetchall()
    busy = [
        (datetime.fromisoformat(r["start_at"]), datetime.fromisoformat(r["end_at"]), str(r["status"]))
        for r in rows
    ]
    days = []
    step = timedelta(minutes=cfg["step_min"])
    duration = timedelta(minutes=service["duration_min"])
    for offset in range(7):
        day = monday + timedelta(days=offset)
        slots = []
        for wstart, wend in _window_datetimes(day, cfg):
            cursor = wstart
            while cursor + duration <= wend:
                end = cursor + duration
                if cursor > today and cursor <= max_day:
                    overlaps = [status for b_start, b_end, status in busy if cursor < b_end and end > b_start]
                    slot_status = (
                        "cancel_requested"
                        if "cancel_requested" in overlaps
                        else "booked"
                        if overlaps
                        else "free"
                    )
                    slots.append(
                        {
                            "start_at": _iso(cursor),
                            "label": cursor.strftime("%H:%M"),
                            "status": slot_status,
                            "available": slot_status == "free",
                        }
                    )
                cursor += step
        days.append({"date": day.isoformat(), "slots": slots})
    return {
        "module_id": mid,
        "config": cfg,
        "service_id": service["id"],
        "timezone": _timezone_name(),
        "today": today.date().isoformat(),
        "week_start": monday.isoformat(),
        "days": days,
        "mine": [_row_public(r, own=True) for r in mine],
    }


def _overlaps(conn: sqlite3.Connection, mid: str, start: datetime, end: datetime, exclude_id: int = 0) -> bool:
    row = conn.execute(
        "SELECT 1 FROM bookings WHERE module_id=? AND status IN (?,?) AND id<>? AND start_at<? AND end_at>? LIMIT 1",
        (mid, *ACTIVE_STATUSES, exclude_id, _iso(end), _iso(start)),
    ).fetchone()
    return bool(row)


def _valid_slot(start: datetime, duration_min: int, cfg: dict[str, Any]) -> bool:
    local = start.astimezone(_tz())
    end = local + timedelta(minutes=duration_min)
    step = int(cfg["step_min"])
    if local.second or local.microsecond or local.minute % step:
        return False
    candidate_windows = _window_datetimes(local.date() - timedelta(days=1), cfg) + _window_datetimes(local.date(), cfg)
    return any(local >= wstart and end <= wend for wstart, wend in candidate_windows)


def create_booking(module_id: str, raw: dict[str, Any], *, actor: str = "public") -> dict[str, Any]:
    mid, cfg = _clean_module_id(module_id), get_config(module_id)
    if actor == "public" and cfg["paused"]:
        raise ValueError(cfg["pause_message"])
    service = _service(cfg, str(raw.get("service_id") or ""))
    try:
        start = datetime.fromisoformat(str(raw.get("start_at") or ""))
    except ValueError:
        raise ValueError("Некорректное время записи.") from None
    if start.tzinfo is None:
        raise ValueError("Время должно содержать часовой пояс.")
    start = start.astimezone(timezone.utc).replace(second=0, microsecond=0)
    end = start + timedelta(minutes=service["duration_min"])
    if actor == "public":
        local_now = datetime.now(_tz())
        local_start = start.astimezone(_tz())
        if local_start <= local_now or local_start > local_now + timedelta(weeks=cfg["booking_horizon_weeks"]):
            raise ValueError("Это время недоступно для записи.")
        if not _valid_slot(start, service["duration_min"], cfg):
            raise ValueError("Это время не входит в доступный интервал.")
    family = str(raw.get("family_name") or "").strip()[:100]
    given = str(raw.get("given_name") or "").strip()[:100]
    phone = str(raw.get("phone") or "").strip()[:60]
    if not family or not given or not phone:
        raise ValueError("Заполните имя, фамилию и телефон.")
    dh = device_hash(str(raw.get("device_id") or "")) if actor == "public" else ""
    now = _iso(_now())
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if _overlaps(conn, mid, start, end):
            raise ValueError("Это время уже занято.")
        if actor == "public":
            local = start.astimezone(_tz())
            monday = local.date() - timedelta(days=local.weekday())
            week_end = monday + timedelta(days=7)
            count = conn.execute("SELECT COUNT(*) FROM bookings WHERE module_id=? AND device_hash=? AND source='public' AND start_at>=? AND start_at<?", (mid, dh, _iso(datetime.combine(monday, time.min, tzinfo=_tz())), _iso(datetime.combine(week_end, time.min, tzinfo=_tz())))).fetchone()[0]
            if count >= cfg["max_per_week"]:
                raise ValueError("На этом устройстве уже создано максимальное число записей на неделю.")
        cur = conn.execute(
            "INSERT INTO bookings(module_id,screen_slug,device_hash,source,family_name,given_name,phone,service_id,service_title,duration_min,start_at,end_at,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (mid, str(raw.get("screen_slug") or "")[:80], dh, actor, family, given, phone, service["id"], service["title"], service["duration_min"], _iso(start), _iso(end), "confirmed", now, now),
        )
        bid = int(cur.lastrowid)
        conn.execute("INSERT INTO booking_events(booking_id,module_id,event_type,actor,details_json,created_at) VALUES(?,?,?,?,?,?)", (bid, mid, "created", actor, "{}", now))
        row = conn.execute("SELECT * FROM bookings WHERE id=?", (bid,)).fetchone()
    return dict(row)


def request_cancel(module_id: str, booking_id: int, raw_device: str) -> dict[str, Any]:
    mid, dh, now = _clean_module_id(module_id), device_hash(raw_device), _iso(_now())
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM bookings WHERE id=? AND module_id=? AND device_hash=?", (booking_id, mid, dh)).fetchone()
        if not row:
            raise ValueError("Запись не найдена на этом устройстве.")
        if row["status"] != "confirmed":
            raise ValueError("Запрос уже обработан или отправлен.")
        conn.execute("UPDATE bookings SET status='cancel_requested',cancel_requested_at=?,updated_at=? WHERE id=?", (now, now, booking_id))
        conn.execute("INSERT INTO booking_events(booking_id,module_id,event_type,actor,details_json,created_at) VALUES(?,?,?,?,?,?)", (booking_id, mid, "cancel_requested", "public", "{}", now))
        updated = conn.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()
    return dict(updated)


def admin_state(module_id: str, week: str | None = None) -> dict[str, Any]:
    mid, cfg = _clean_module_id(module_id), get_config(module_id)
    monday = _week_start(week) if week else None
    now = _now()
    with _connect() as conn:
        if monday is None:
            rows = conn.execute("SELECT * FROM bookings WHERE module_id=? ORDER BY start_at, id", (mid,)).fetchall()
        else:
            end = monday + timedelta(days=8)
            rows = conn.execute("SELECT * FROM bookings WHERE module_id=? AND start_at>=? AND start_at<? ORDER BY start_at, id", (mid, _iso(datetime.combine(monday, time.min, tzinfo=_tz())), _iso(datetime.combine(end, time.min, tzinfo=_tz())))).fetchall()
    rows = sorted(
        rows,
        key=lambda row: (
            0
            if row["status"] in {"confirmed", "cancel_requested"} and datetime.fromisoformat(row["end_at"]) > now
            else 1,
            -datetime.fromisoformat(row["start_at"]).timestamp()
            if row["status"] not in {"confirmed", "cancel_requested"} or datetime.fromisoformat(row["end_at"]) <= now
            else datetime.fromisoformat(row["start_at"]).timestamp(),
            int(row["id"]),
        ),
    )
    return {
        "module_id": mid,
        "config": cfg,
        "timezone": _timezone_name(),
        "now": _iso(now),
        "week_start": monday.isoformat() if monday else "",
        "scope": "week" if monday else "all",
        "bookings": [dict(r) for r in rows],
    }


def admin_action(module_id: str, booking_id: int, action: str, raw: dict[str, Any]) -> dict[str, Any]:
    mid, now = _clean_module_id(module_id), _iso(_now())
    allowed = {"confirm_cancel", "reject_cancel", "cancel", "move"}
    if action not in allowed:
        raise ValueError("Неизвестное действие.")
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM bookings WHERE id=? AND module_id=?", (booking_id, mid)).fetchone()
        if not row:
            raise ValueError("Запись не найдена.")
        if action == "confirm_cancel":
            if row["status"] != "cancel_requested": raise ValueError("Нет ожидающего запроса на отмену.")
            conn.execute("UPDATE bookings SET status='cancelled',updated_at=? WHERE id=?", (now, booking_id))
        elif action == "reject_cancel":
            if row["status"] != "cancel_requested": raise ValueError("Нет ожидающего запроса на отмену.")
            conn.execute("UPDATE bookings SET status='confirmed',cancel_requested_at='',updated_at=? WHERE id=?", (now, booking_id))
        elif action == "cancel":
            conn.execute("UPDATE bookings SET status='cancelled',updated_at=? WHERE id=?", (now, booking_id))
        else:
            try: start = datetime.fromisoformat(str(raw.get("start_at") or ""))
            except ValueError: raise ValueError("Некорректное новое время.") from None
            if start.tzinfo is None: raise ValueError("Время должно содержать часовой пояс.")
            start = start.astimezone(timezone.utc).replace(second=0, microsecond=0)
            end = start + timedelta(minutes=int(row["duration_min"]))
            if _overlaps(conn, mid, start, end, booking_id): raise ValueError("Новое время уже занято.")
            conn.execute("UPDATE bookings SET start_at=?,end_at=?,updated_at=? WHERE id=?", (_iso(start), _iso(end), now, booking_id))
        conn.execute("INSERT INTO booking_events(booking_id,module_id,event_type,actor,details_json,created_at) VALUES(?,?,?,?,?,?)", (booking_id, mid, action, "admin", json.dumps(raw, ensure_ascii=False), now))
        updated = conn.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()
    return dict(updated)


def claim_scheduled_notifications() -> dict[str, list[dict[str, Any]]]:
    """Atomically claim due reminders and daily summaries for the current tenant DB."""
    now_utc, tz = _now(), _tz()
    reminders: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        modules = [str(r[0]) for r in conn.execute("SELECT DISTINCT module_id FROM bookings").fetchall()]
        for mid in modules:
            row_cfg = conn.execute("SELECT config_json FROM booking_modules WHERE module_id=?", (mid,)).fetchone()
            cfg = sanitize_config(json.loads(row_cfg[0])) if row_cfg else default_booking_config()
            due_end = now_utc + timedelta(minutes=int(cfg["reminder_minutes"]))
            rows = conn.execute("SELECT * FROM bookings WHERE module_id=? AND status='confirmed' AND reminder_sent_at='' AND start_at>? AND start_at<=?", (mid, _iso(now_utc), _iso(due_end))).fetchall()
            for row in rows:
                conn.execute("UPDATE bookings SET reminder_sent_at=? WHERE id=? AND reminder_sent_at=''", (_iso(now_utc), row["id"]))
                reminders.append(dict(row))
            local_now = now_utc.astimezone(tz)
            morning = _parse_hhmm(cfg["morning_time"])
            if morning and local_now.time() >= morning:
                mark = f"morning:{local_now.date().isoformat()}"
                exists = conn.execute("SELECT 1 FROM booking_notification_marks WHERE module_id=? AND mark_key=?", (mid, mark)).fetchone()
                if not exists:
                    day_start = datetime.combine(local_now.date(), time.min, tzinfo=tz)
                    day_end = day_start + timedelta(days=1)
                    day_rows = conn.execute("SELECT * FROM bookings WHERE module_id=? AND status IN (?,?) AND start_at>=? AND start_at<? ORDER BY start_at", (mid, *ACTIVE_STATUSES, _iso(day_start), _iso(day_end))).fetchall()
                    conn.execute("INSERT INTO booking_notification_marks(module_id,mark_key,created_at) VALUES(?,?,?)", (mid, mark, _iso(now_utc)))
                    if day_rows:
                        summaries.append({"module_id": mid, "count": len(day_rows), "first_at": day_rows[0]["start_at"], "screen_slug": day_rows[0]["screen_slug"]})
    return {"reminders": reminders, "summaries": summaries}
