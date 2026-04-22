"""Учёт последних опросов ТВ (GET /api/screen/{slug}) для админки «Статистика».

Данные в памяти процесса — при перезапуске сервера сбрасываются (прототип).
"""
from __future__ import annotations

import hashlib
import re
import threading
import time
from typing import Any

from .gs_jsonio import read_json, write_json
from .gs_paths import SCREEN_WATCH_STATS_PATH

_LOCK = threading.Lock()
# (slug, client_id) -> ts, session_start (начало «сессии» после простоя), …
_CLIENT_ROWS: dict[tuple[str, str], dict[str, Any]] = {}

_CLIENT_ID_RE = re.compile(r"^[a-zA-Z0-9._-]{4,80}$")
_PRUNE_SEC = 60.0

# Персистентная статистика посещений (в data/): уникальные за день/месяц + счётчик подключений.
_STATS_LOCK = threading.Lock()
_STATS_CACHE: dict[str, Any] | None = None
_STATS_DIRTY = False
_STATS_LAST_FLUSH = 0.0


def _device_kind(device: str) -> str:
    s = (device or "").lower()
    if "android" in s:
        return "android"
    if "iphone" in s or "ipad" in s or "ios" in s:
        return "ios"
    if "windows" in s:
        return "windows"
    if "mac os" in s or "macos" in s:
        return "mac"
    if "linux" in s:
        return "linux"
    return "unknown"


def _hash_client_id(cid: str) -> str:
    # Не храним сырой client_id в статистике, только короткий хэш.
    return hashlib.sha256(cid.encode("utf-8", errors="ignore")).hexdigest()[:24]


def _today_iso(now: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(now))


def _month_iso(now: float) -> str:
    return time.strftime("%Y-%m", time.localtime(now))


def _load_stats_locked() -> dict[str, Any]:
    global _STATS_CACHE
    if _STATS_CACHE is not None:
        return _STATS_CACHE
    raw = read_json(SCREEN_WATCH_STATS_PATH, {})
    if not isinstance(raw, dict):
        raw = {}
    raw.setdefault("total_connections", 0)
    raw.setdefault("month", "")
    raw.setdefault("month_unique", {})
    raw.setdefault("today", "")
    raw.setdefault("today_unique", {})
    _STATS_CACHE = raw
    return raw


def _flush_stats_locked(force: bool = False) -> None:
    global _STATS_DIRTY, _STATS_LAST_FLUSH
    if not _STATS_DIRTY:
        return
    now = time.time()
    if not force and now - _STATS_LAST_FLUSH < 2.0:
        return
    if _STATS_CACHE is None:
        return
    write_json(SCREEN_WATCH_STATS_PATH, _STATS_CACHE)
    _STATS_DIRTY = False
    _STATS_LAST_FLUSH = now


def _stats_record_visit(now: float, client_id: str, device: str, is_new_connection: bool) -> None:
    """
    Уникальные считаем по client_id (через хэш) и по текущим (today/month).
    total_connections: считаем "подключение" как появление нового клиента в active-таблице после простоя.
    """
    global _STATS_DIRTY
    cid = _safe_client_id(client_id)
    if cid == "unknown":
        return
    kid = _hash_client_id(cid)
    dk = _device_kind(device)
    day = _today_iso(now)
    month = _month_iso(now)
    with _STATS_LOCK:
        st = _load_stats_locked()
        if is_new_connection:
            try:
                st["total_connections"] = int(st.get("total_connections") or 0) + 1
            except (TypeError, ValueError):
                st["total_connections"] = 1
        # rollover day
        if st.get("today") != day:
            st["today"] = day
            st["today_unique"] = {}
        # rollover month
        if st.get("month") != month:
            st["month"] = month
            st["month_unique"] = {}
        # today unique by device
        tu = st.get("today_unique")
        if not isinstance(tu, dict):
            tu = {}
            st["today_unique"] = tu
        arr = tu.get(dk)
        if not isinstance(arr, list):
            arr = []
            tu[dk] = arr
        if kid not in arr:
            arr.append(kid)
        # month unique overall + by device (for future)
        mu = st.get("month_unique")
        if not isinstance(mu, dict):
            mu = {}
            st["month_unique"] = mu
        marr = mu.get(dk)
        if not isinstance(marr, list):
            marr = []
            mu[dk] = marr
        if kid not in marr:
            marr.append(kid)
        _STATS_DIRTY = True
        _flush_stats_locked(force=False)


def stats_snapshot() -> dict[str, Any]:
    """Сводка: сегодня по типам + уникальные за месяц + счётчик подключений."""
    with _STATS_LOCK:
        st = _load_stats_locked()
        today_unique = st.get("today_unique") if isinstance(st.get("today_unique"), dict) else {}
        today_by = {k: len(v) for k, v in today_unique.items() if isinstance(v, list)}
        month_unique = st.get("month_unique") if isinstance(st.get("month_unique"), dict) else {}
        # уникальные за месяц считаем как объединение списков по типам
        uniq: set[str] = set()
        for v in month_unique.values():
            if isinstance(v, list):
                uniq.update([str(x) for x in v])
        return {
            "today": str(st.get("today") or ""),
            "month": str(st.get("month") or ""),
            "today_unique_by_device": today_by,
            "month_unique_users": len(uniq),
            "total_connections": int(st.get("total_connections") or 0),
        }


def reset_stats_counters() -> dict[str, Any]:
    """Очищаем счётчики посещений (по требованию администратора)."""
    global _STATS_DIRTY
    with _STATS_LOCK:
        st = _load_stats_locked()
        st["total_connections"] = 0
        st["today_unique"] = {}
        st["month_unique"] = {}
        _STATS_DIRTY = True
        _flush_stats_locked(force=True)
    return stats_snapshot()


def _safe_client_id(raw: str) -> str:
    s = (raw or "").strip()
    if _CLIENT_ID_RE.match(s):
        return s
    return "unknown"


def _safe_label(raw: str) -> str:
    return (raw or "").strip()[:120]


def _safe_device(raw: str) -> str:
    s = re.sub(r"[\x00-\x1f\x7f]", " ", (raw or "").strip())[:160]
    return s.strip() or ""


def _safe_screen_name(raw: str) -> str:
    return (raw or "").strip()[:120] or ""


def _client_ip(request: Any) -> str:
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        return xff.split(",")[0].strip()[:80]
    try:
        c = request.client
        if c and c.host:
            return str(c.host)[:80]
    except Exception:
        pass
    return ""


def record_screen_poll(
    request: Any,
    slug: str,
    client_id: str,
    label: str,
    device: str,
    screen_name: str = "",
) -> None:
    slug = (slug or "").strip()[:80]
    if not slug:
        return
    cid = _safe_client_id(client_id)
    now = time.time()
    ip = _client_ip(request)
    name = _safe_screen_name(screen_name) or slug
    key = (slug, cid)
    with _LOCK:
        prev = _CLIENT_ROWS.get(key)
        if prev:
            session_start = float(prev.get("session_start") or prev.get("ts") or now)
        else:
            session_start = now
        # Новое подключение: клиент появился впервые или был "забыт" после prune (простой > _PRUNE_SEC).
        is_new_conn = prev is None
        _CLIENT_ROWS[key] = {
            "ts": now,
            "session_start": session_start,
            "ip": ip,
            "label": _safe_label(label),
            "device": _safe_device(device),
            "screen_name": name,
        }
    try:
        _stats_record_visit(now, cid, device, is_new_conn)
    except Exception:
        pass


def _prune_locked(now: float) -> None:
    cutoff = now - _PRUNE_SEC
    dead = [k for k, v in _CLIENT_ROWS.items() if float(v.get("ts") or 0) < cutoff]
    for k in dead:
        del _CLIENT_ROWS[k]


def _connected_sec(now: float, row: dict[str, Any]) -> float:
    ts = float(row.get("ts") or 0)
    if ts <= 0:
        return 0.0
    ss = float(row.get("session_start") or ts)
    return max(0.0, now - ss)


def _connection_log_rows(now: float) -> list[dict[str, Any]]:
    """Все недавние клиенты по всем экранам: сортировка по последнему опросу (ts убыв.)."""
    rows: list[dict[str, Any]] = []
    for (slug, cid), r in _CLIENT_ROWS.items():
        ts = float(r.get("ts") or 0)
        if ts <= 0:
            continue
        cid_short = f"{cid[:10]}…" if len(cid) > 12 else cid
        csec = round(_connected_sec(now, r), 2)
        rows.append(
            {
                "ts": ts,
                "slug": slug,
                "screen_name": r.get("screen_name") or slug,
                "client_id": cid,
                "client_id_short": cid_short,
                "ip": r.get("ip") or "",
                "device": r.get("device") or "",
                "label": r.get("label") or "",
                "connected_sec": csec,
            }
        )
    rows.sort(key=lambda x: float(x.get("ts") or 0), reverse=True)
    for row in rows:
        row.pop("ts", None)
    return rows


def screen_watch_snapshot(screens: list[dict[str, Any]]) -> dict[str, Any]:
    """Собрать статусы для конфигурации экранов (poll_interval_sec из каждого)."""
    now = time.time()
    with _LOCK:
        _prune_locked(now)
        by_slug: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for (slug, cid), row in _CLIENT_ROWS.items():
            by_slug.setdefault(slug, []).append((cid, dict(row)))

    out_screens: list[dict[str, Any]] = []
    for sc in screens:
        if sc.get("is_active") is False:
            continue
        slug = str(sc.get("slug") or "").strip()
        if not slug:
            continue
        try:
            poll = int(sc.get("poll_interval_sec") or 10)
        except (TypeError, ValueError):
            poll = 10
        poll = max(5, min(120, poll))
        threshold = 3 * poll

        rows = by_slug.get(slug, [])
        last_any: float | None = None
        for _cid, r in rows:
            ts = float(r.get("ts") or 0)
            if ts > 0 and (last_any is None or ts > last_any):
                last_any = ts

        if last_any is None:
            status = "never"
            sec_ago = None
        else:
            sec_ago = max(0.0, now - last_any)
            status = "ok" if sec_ago < threshold else "stale"

        clients_out: list[dict[str, Any]] = []
        for cid, r in sorted(rows, key=lambda x: float(x[1].get("ts") or 0), reverse=True):
            ts = float(r.get("ts") or 0)
            cid_short = f"{cid[:10]}…" if len(cid) > 12 else cid
            clients_out.append(
                {
                    "client_id": cid,
                    "client_id_short": cid_short,
                    "label": r.get("label") or "",
                    "ip": r.get("ip") or "",
                    "device": r.get("device") or "",
                    "connected_sec": round(_connected_sec(now, r), 2),
                }
            )

        out_screens.append(
            {
                "id": sc.get("id"),
                "name": sc.get("name") or slug,
                "slug": slug,
                "ip_note": sc.get("ip_note") or "",
                "poll_interval_sec": poll,
                "stale_after_sec": threshold,
                "status": status,
                "last_seen_sec_ago": None if sec_ago is None else round(sec_ago, 1),
                "clients": clients_out,
            }
        )

    return {
        "server_time": time.time(),
        "screens": out_screens,
        # Историю "все кто был" больше не отдаём подробно — вместо этого отдаём агрегаты.
        "visits": stats_snapshot(),
    }
