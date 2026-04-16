"""Учёт последних опросов ТВ (GET /api/screen/{slug}) для админки «Статистика».

Данные в памяти процесса — при перезапуске сервера сбрасываются (прототип).
"""
from __future__ import annotations

import re
import threading
import time
from typing import Any

_LOCK = threading.Lock()
# (slug, client_id) -> ts, session_start (начало «сессии» после простоя), …
_CLIENT_ROWS: dict[tuple[str, str], dict[str, Any]] = {}

_CLIENT_ID_RE = re.compile(r"^[a-zA-Z0-9._-]{4,80}$")
_PRUNE_SEC = 60.0


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
        _CLIENT_ROWS[key] = {
            "ts": now,
            "session_start": session_start,
            "ip": ip,
            "label": _safe_label(label),
            "device": _safe_device(device),
            "screen_name": name,
        }


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
        log_rows = _connection_log_rows(now)

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
        "connection_log": log_rows,
    }
