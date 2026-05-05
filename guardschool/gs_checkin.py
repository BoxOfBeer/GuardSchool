"""Оперативные отметки состояния мест: только таблица событий в SQLite."""
from __future__ import annotations

import csv
import io
import re
import sqlite3
from datetime import date, datetime, time as time_cls, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from .gs_paths import DATA_DIR

CHECKIN_DB_PATH = DATA_DIR / "checkin.sqlite3"

_PLACE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(CHECKIN_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def _migrate_checkin_columns(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(checkin_events)").fetchall()
    cols = {str(r[1]) for r in rows}
    if "screen_slug" not in cols:
        conn.execute("ALTER TABLE checkin_events ADD COLUMN screen_slug TEXT NOT NULL DEFAULT ''")
    if "submit_widget_id" not in cols:
        conn.execute("ALTER TABLE checkin_events ADD COLUMN submit_widget_id TEXT NOT NULL DEFAULT ''")
    if "confirmed_at" not in cols:
        conn.execute("ALTER TABLE checkin_events ADD COLUMN confirmed_at TEXT")


def ensure_checkin_tables() -> None:
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS checkin_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL DEFAULT 'local',
                device_hash TEXT NOT NULL,
                device_name TEXT NOT NULL DEFAULT '',
                place_id TEXT NOT NULL,
                level TEXT NOT NULL,
                comment TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS checkin_events_tenant_created_idx
                ON checkin_events(tenant_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS checkin_events_tenant_place_created_idx
                ON checkin_events(tenant_id, place_id, created_at DESC);
            """
        )
        _migrate_checkin_columns(conn)


def _tz_for_school(tzname: str):
    key = (tzname or "").strip() or "Europe/Moscow"
    for cand in (key, "Europe/Moscow"):
        try:
            return ZoneInfo(cand)
        except Exception:
            continue
    lt = datetime.now().astimezone().tzinfo
    return lt if lt is not None else timezone.utc


def school_calendar_date(config: dict[str, Any]) -> date:
    """Календарная дата «сегодня» для школы: timezone + clock_offset_minutes."""
    tzname = str((config or {}).get("timezone") or "Europe/Moscow").strip()
    z = _tz_for_school(tzname)
    try:
        off = int((config or {}).get("clock_offset_minutes") or 0)
    except (TypeError, ValueError):
        off = 0
    off = max(-720, min(720, off))
    now_adj = datetime.now(z) + timedelta(minutes=off)
    return now_adj.date()


def school_day_bounds_utc(config: dict[str, Any]) -> tuple[datetime, datetime]:
    """Начало и конец текущего календарного дня школы в UTC (полуинтервал [start, end))."""
    tzname = str((config or {}).get("timezone") or "Europe/Moscow").strip()
    z = _tz_for_school(tzname)
    try:
        off = int((config or {}).get("clock_offset_minutes") or 0)
    except (TypeError, ValueError):
        off = 0
    off = max(-720, min(720, off))
    now_adj = datetime.now(z) + timedelta(minutes=off)
    d = now_adj.date()
    start_local = datetime.combine(d, time_cls.min, tzinfo=z) - timedelta(minutes=off)
    end_local = start_local + timedelta(days=1)
    su = start_local.astimezone(timezone.utc)
    eu = end_local.astimezone(timezone.utc)
    return su, eu


def range_bounds_utc(config: dict[str, Any], range_key: str) -> tuple[datetime, datetime, str]:
    """Границы периода в UTC и метка. day | week | month — в календаре школы (timezone + offset)."""
    rk = (range_key or "day").strip().lower()
    if rk not in ("day", "week", "month"):
        rk = "day"
    tzname = str((config or {}).get("timezone") or "Europe/Moscow").strip()
    z = _tz_for_school(tzname)
    try:
        off = int((config or {}).get("clock_offset_minutes") or 0)
    except (TypeError, ValueError):
        off = 0
    off = max(-720, min(720, off))
    now_adj = datetime.now(z) + timedelta(minutes=off)
    today = now_adj.date()

    if rk == "day":
        su, eu = school_day_bounds_utc(config)
        label = today.isoformat()
        return su, eu, label

    if rk == "week":
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        start_local = datetime.combine(monday, time_cls.min, tzinfo=z) - timedelta(minutes=off)
        end_local = datetime.combine(sunday, time_cls.min, tzinfo=z) - timedelta(minutes=off) + timedelta(days=1)
        su = start_local.astimezone(timezone.utc)
        eu = end_local.astimezone(timezone.utc)
        label = f"{monday.isoformat()}–{sunday.isoformat()}"
        return su, eu, label

    # month
    first = today.replace(day=1)
    if first.month == 12:
        next_first = date(first.year + 1, 1, 1)
    else:
        next_first = date(first.year, first.month + 1, 1)
    last = next_first - timedelta(days=1)
    start_local = datetime.combine(first, time_cls.min, tzinfo=z) - timedelta(minutes=off)
    end_local = datetime.combine(last, time_cls.min, tzinfo=z) - timedelta(minutes=off) + timedelta(days=1)
    su = start_local.astimezone(timezone.utc)
    eu = end_local.astimezone(timezone.utc)
    label = f"{first.year}-{first.month:02d}"
    return su, eu, label


def _utc_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _parse_iso_utc(s: str) -> datetime | None:
    raw = (s or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def school_wall_datetime(config: dict[str, Any], dt_utc: datetime) -> datetime:
    """Мгновенное UTC-время, показанное «как на сервере»: timezone + clock_offset_minutes."""
    tzname = str((config or {}).get("timezone") or "Europe/Moscow").strip()
    z = _tz_for_school(tzname)
    try:
        off = int((config or {}).get("clock_offset_minutes") or 0)
    except (TypeError, ValueError):
        off = 0
    off = max(-720, min(720, off))
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    local = dt_utc.astimezone(z) + timedelta(minutes=off)
    return local


def format_created_local_parts(config: dict[str, Any], created_at_iso: str) -> tuple[str, str]:
    """ДД.ММ.ГГГГ и ЧЧ:ММ в логике «время школы» (как в остальном сервере)."""
    dtu = _parse_iso_utc(created_at_iso)
    if not dtu:
        return "", ""
    local = school_wall_datetime(config, dtu)
    d_str = f"{local.day:02d}.{local.month:02d}.{local.year:04d}"
    t_str = f"{local.hour:02d}:{local.minute:02d}"
    return d_str, t_str


def enrich_checkin_event_for_client(config: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    d, t = format_created_local_parts(config, out.get("created_at") or "")
    out["created_date"] = d
    out["created_time"] = t
    conf = (out.get("confirmed_at") or "").strip()
    if conf:
        cd, ct = format_created_local_parts(config, conf)
        out["confirmed_date"] = cd
        out["confirmed_time"] = ct
    else:
        out["confirmed_date"] = ""
        out["confirmed_time"] = ""
    return out


def list_journal_filtered(
    tenant_id: str,
    start_utc: datetime,
    end_utc: datetime,
    place_ids: set[str] | None,
    screen_slug_filter: str | None,
) -> list[dict[str, Any]]:
    """События за интервал [start, end) UTC; опционально по местам и экрану."""
    start_s = _utc_iso(start_utc)
    end_s = _utc_iso(end_utc)
    tid = (tenant_id or "local").strip() or "local"
    clauses = ["tenant_id = ?", "created_at >= ?", "created_at < ?"]
    params: list[Any] = [tid, start_s, end_s]
    if place_ids:
        ph = ",".join("?" * len(place_ids))
        clauses.append(f"place_id IN ({ph})")
        params.extend(sorted(place_ids))
    if screen_slug_filter:
        ss = screen_slug_filter.strip().lower()
        clauses.append("lower(trim(screen_slug)) = ?")
        params.append(ss)
    where_sql = " AND ".join(clauses)
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, tenant_id, device_hash, device_name, place_id, level, comment, created_at,
                   screen_slug, submit_widget_id, confirmed_at
            FROM checkin_events
            WHERE {where_sql}
            ORDER BY created_at DESC, id DESC
            """,
            params,
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def list_journal_for_school_day(tenant_id: str, config: dict[str, Any]) -> list[dict[str, Any]]:
    """Все события за календарный день школы (совместимость)."""
    start_utc, end_utc, _lbl = range_bounds_utc(config, "day")
    return list_journal_filtered(tenant_id, start_utc, end_utc, None, None)


def _row_to_dict(r: sqlite3.Row) -> dict[str, Any]:
    def col(name: str, default: str = "") -> str:
        try:
            v = r[name]
        except (KeyError, IndexError):
            return default
        return str(v) if v is not None else default

    return {
        "id": int(r["id"]),
        "tenant_id": col("tenant_id"),
        "device_hash": col("device_hash"),
        "device_name": col("device_name"),
        "place_id": col("place_id"),
        "level": col("level"),
        "comment": col("comment"),
        "created_at": col("created_at"),
        "screen_slug": col("screen_slug"),
        "submit_widget_id": col("submit_widget_id"),
        "confirmed_at": col("confirmed_at"),
    }


def sanitize_places_list(raw: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return out
    seen: set[str] = set()
    for p in raw:
        if not isinstance(p, dict):
            continue
        pid = str(p.get("id") or "").strip()[:64]
        title = str(p.get("title") or "").strip()[:200]
        if not pid or not _PLACE_ID_RE.match(pid):
            continue
        if pid in seen:
            continue
        seen.add(pid)
        out.append({"id": pid, "title": title or pid})
        if len(out) >= 500:
            break
    return out


def build_summary_for_places(
    tenant_id: str,
    config: dict[str, Any],
    places: list[dict[str, str]],
    range_key: str,
    screen_slug: str | None,
) -> tuple[str, list[dict[str, Any]]]:
    """Сводка по списку мест за период; последнее событие на место внутри периода или none."""
    start_utc, end_utc, label = range_bounds_utc(config, range_key)
    pids = {p["id"] for p in places}
    journal = list_journal_filtered(
        tenant_id,
        start_utc,
        end_utc,
        pids if pids else None,
        screen_slug,
    )
    last_by_place: dict[str, dict[str, Any]] = {}
    for ev in journal:
        pid = ev.get("place_id") or ""
        if pid not in last_by_place:
            last_by_place[pid] = ev
    items: list[dict[str, Any]] = []
    for pl in places:
        pid = pl["id"]
        last = last_by_place.get(pid)
        if last is None:
            items.append(
                {
                    "place_id": pid,
                    "place_title": pl["title"],
                    "status": "none",
                    "last_event": None,
                }
            )
        else:
            items.append(
                {
                    "place_id": pid,
                    "place_title": pl["title"],
                    "status": str(last.get("level") or ""),
                    "last_event": last,
                }
            )
    return label, items


def build_summary_for_school_day(tenant_id: str, config: dict[str, Any]) -> tuple[date, list[dict[str, Any]]]:
    """Совместимость: места из устаревшего config['checkin'].places, только день."""
    ch = (config or {}).get("checkin") if isinstance(config, dict) else {}
    places = sanitize_places_list(ch.get("places") if isinstance(ch, dict) else None)
    day = school_calendar_date(config)
    _lbl, items = build_summary_for_places(tenant_id, config, places, "day", None)
    return day, items


DEFAULT_CHECKIN_LABELS: dict[str, str] = {
    "module_title": "Оперативные отметки",
    "actor": "Имя",
    "place": "Место",
    "ok": "Всё в порядке",
    "warn": "Нужно внимание",
    "alert": "Проблема",
    "none": "Нет отметки",
    "comment": "Комментарий",
    "device_name": "Имя",
    "submit": "Отправить отметку",
    "save": "Сохранить",
    "summary_title": "Сводка по местам",
    "journal_title": "Журнал отметок",
    "export_csv": "Скачать CSV за сегодня",
    "state": "Состояние",
    "place_id": "Код места",
    "time_utc": "Время (UTC, ISO)",
    "open_page": "Страница отметки",
}

def sanitize_checkin_block(raw: Any) -> dict[str, Any]:
    """Нормализация секции config['checkin'] для сохранения и load_config."""
    out: dict[str, Any] = {
        "enabled": False,
        "places": [],
        "labels": dict(DEFAULT_CHECKIN_LABELS),
    }
    if not isinstance(raw, dict):
        return out
    out["enabled"] = bool(raw.get("enabled"))
    places_out: list[dict[str, str]] = []
    pl = raw.get("places")
    if isinstance(pl, list):
        seen: set[str] = set()
        for p in pl:
            if not isinstance(p, dict):
                continue
            pid = str(p.get("id") or "").strip()[:64]
            title = str(p.get("title") or "").strip()[:200]
            if not pid or not _PLACE_ID_RE.match(pid):
                continue
            if pid in seen:
                continue
            seen.add(pid)
            places_out.append({"id": pid, "title": title or pid})
            if len(places_out) >= 500:
                break
    out["places"] = places_out
    labels_in = raw.get("labels")
    if isinstance(labels_in, dict):
        merged = dict(DEFAULT_CHECKIN_LABELS)
        for k, v in labels_in.items():
            key = str(k).strip()[:80]
            if not key:
                continue
            merged[key] = str(v).strip()[:500]
        out["labels"] = merged
    return out


def validate_comment_for_level(level: str, comment: str) -> tuple[bool, str]:
    lv = (level or "").strip().lower()
    c = (comment or "").strip()
    if lv == "alert" and len(c) < 1:
        return False, "Для уровня «проблема» нужен комментарий."
    return True, ""


def insert_event(
    tenant_id: str,
    device_hash: str,
    device_name: str,
    place_id: str,
    level: str,
    comment: str,
    *,
    screen_slug: str = "",
    submit_widget_id: str = "",
) -> dict[str, Any]:
    ok, err = validate_comment_for_level(level, comment)
    if not ok:
        raise ValueError(err)
    lv = (level or "").strip().lower()
    if lv not in ("ok", "warn", "alert"):
        raise ValueError("Недопустимый уровень отметки.")
    h = (device_hash or "").strip()
    if not h:
        raise ValueError("Не передан идентификатор устройства.")
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    tid = (tenant_id or "local").strip() or "local"
    dn = (device_name or "").strip()[:200]
    pid = (place_id or "").strip()
    if not _PLACE_ID_RE.match(pid):
        raise ValueError("Недопустимое место.")
    com = (comment or "").strip()[:4000]
    ss = str(screen_slug or "").strip().lower()[:128]
    sw = str(submit_widget_id or "").strip()[:80]

    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO checkin_events (
                tenant_id, device_hash, device_name, place_id, level, comment, created_at,
                screen_slug, submit_widget_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (tid, h[:128], dn, pid, lv, com, ts, ss, sw),
        )
        new_id = int(cur.lastrowid or 0)
    return {"id": new_id, "created_at": ts}


def journal_rows_to_csv_bytes(rows: list[dict[str, Any]], place_titles: dict[str, str]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "created_at_utc",
            "screen_slug",
            "submit_widget_id",
            "place_id",
            "place_title",
            "level",
            "device_name",
            "device_hash",
            "comment",
        ]
    )
    for r in rows:
        pid = str(r.get("place_id") or "")
        writer.writerow(
            [
                r.get("id"),
                r.get("created_at"),
                r.get("screen_slug"),
                r.get("submit_widget_id"),
                pid,
                place_titles.get(pid, ""),
                r.get("level"),
                r.get("device_name"),
                r.get("device_hash"),
                r.get("comment"),
            ]
        )
    return buf.getvalue().encode("utf-8-sig")


def journal_to_csv_bytes_filtered(
    tenant_id: str,
    config: dict[str, Any],
    range_key: str,
    place_ids: set[str] | None,
    screen_slug: str | None,
    place_titles: dict[str, str],
) -> bytes:
    start_utc, end_utc, _lbl = range_bounds_utc(config, range_key)
    rows = list_journal_filtered(tenant_id, start_utc, end_utc, place_ids, screen_slug)
    return journal_rows_to_csv_bytes(rows, place_titles)


def journal_to_csv_bytes(config: dict[str, Any], tenant_id: str) -> bytes:
    """Совместимость: выгрузка за день без фильтра экрана."""
    place_titles: dict[str, str] = {}
    ch = (config or {}).get("checkin") if isinstance(config, dict) else {}
    raw_places = ch.get("places") if isinstance(ch, dict) else None
    if isinstance(raw_places, list):
        for p in raw_places:
            if isinstance(p, dict):
                pid = str(p.get("id") or "").strip()
                if pid:
                    place_titles[pid] = str(p.get("title") or "").strip()[:200]
    return journal_to_csv_bytes_filtered(tenant_id, config, "day", None, None, place_titles)


def set_checkin_event_confirmed(
    tenant_id: str,
    event_id: int,
    *,
    screen_slug: str,
    allowed_place_ids: set[str],
) -> str | None:
    """Проставить подтверждение; возвращает confirmed_at (уже был или новый) либо None."""
    tid = (tenant_id or "local").strip() or "local"
    ss = (screen_slug or "").strip().lower()
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, tenant_id, place_id, screen_slug, confirmed_at FROM checkin_events WHERE id = ?",
            (int(event_id),),
        ).fetchone()
        if not row:
            return None
        if str(row["tenant_id"] or "") != tid:
            return None
        if str(row["screen_slug"] or "").strip().lower() != ss:
            return None
        pid = str(row["place_id"] or "")
        if allowed_place_ids and pid not in allowed_place_ids:
            return None
        prev = (row["confirmed_at"] or "").strip() if row["confirmed_at"] is not None else ""
        if prev:
            return prev
        conn.execute("UPDATE checkin_events SET confirmed_at = ? WHERE id = ?", (ts, int(event_id)))
    return ts


def confirm_all_unconfirmed_in_range(
    tenant_id: str,
    config: dict[str, Any],
    screen_slug: str,
    place_ids: set[str],
    range_key: str,
) -> int:
    """Подтвердить все ещё неподтверждённые события журнала за период на экране (по списку мест)."""
    start_utc, end_utc, _ = range_bounds_utc(config, range_key)
    ss = (screen_slug or "").strip().lower()
    rows = list_journal_filtered(
        tenant_id, start_utc, end_utc, place_ids if place_ids else None, ss
    )
    tid = (tenant_id or "local").strip() or "local"
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    n = 0
    with _connect() as conn:
        for r in rows:
            if (r.get("confirmed_at") or "").strip():
                continue
            eid = int(r["id"])
            cur = conn.execute(
                """
                UPDATE checkin_events SET confirmed_at = ?
                WHERE id = ? AND tenant_id = ?
                  AND (confirmed_at IS NULL OR trim(confirmed_at) = '')
                """,
                (ts, eid, tid),
            )
            if cur.rowcount:
                n += 1
    return n


def get_checkin_events_status_for_device(
    tenant_id: str,
    screen_slug: str,
    submit_widget_id: str,
    device_hash: str,
    event_ids: list[int],
) -> list[dict[str, Any]]:
    tid = (tenant_id or "local").strip() or "local"
    ss = (screen_slug or "").strip().lower()
    sw = str(submit_widget_id or "").strip()[:80]
    h = str(device_hash or "").strip()[:128]
    ids: list[int] = []
    for x in event_ids:
        try:
            ids.append(int(x))
        except (TypeError, ValueError):
            continue
    ids = ids[:24]
    if not ids:
        return []
    ph = ",".join("?" * len(ids))
    params: list[Any] = [tid, ss, sw, h, *ids]
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, confirmed_at FROM checkin_events
            WHERE tenant_id = ? AND lower(trim(screen_slug)) = ? AND submit_widget_id = ?
              AND device_hash = ? AND id IN ({ph})
            """,
            params,
        ).fetchall()
    return [{"id": int(r["id"]), "confirmed_at": str(r["confirmed_at"] or "").strip()} for r in rows]
