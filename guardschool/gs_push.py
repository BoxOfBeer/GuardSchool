"""Web Push subscriptions + rate limit (SQLite), tenant-scoped via tenant_ctx."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .gs_paths import DATA_DIR


def _data_dir() -> Path:
    try:
        from .tenant_ctx import map_data_path

        return map_data_path(DATA_DIR)
    except Exception:
        return Path(DATA_DIR)


PUSH_DB_PATH = lambda: _data_dir() / "push.sqlite3"


def _connect() -> sqlite3.Connection:
    _data_dir().mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(PUSH_DB_PATH()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def ensure_push_tables() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                screen_slug TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                topics_json TEXT NOT NULL DEFAULT '{}',
                min_interval_sec INTEGER NOT NULL DEFAULT 300,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1
            );
            CREATE UNIQUE INDEX IF NOT EXISTS push_subscriptions_uniq
                ON push_subscriptions(tenant_id, screen_slug, endpoint);

            CREATE TABLE IF NOT EXISTS push_rate_limits (
                key TEXT PRIMARY KEY,
                last_sent_at INTEGER NOT NULL DEFAULT 0,
                pending_count INTEGER NOT NULL DEFAULT 0
            );
            """
        )


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sanitize_topics(raw: Any) -> dict[str, bool]:
    out: dict[str, bool] = {}
    if not isinstance(raw, dict):
        return out
    for k, v in raw.items():
        key = str(k or "").strip().lower()
        if not key or len(key) > 64:
            continue
        out[key] = bool(v)
    return out


def upsert_subscription(
    *,
    tenant_id: str,
    screen_slug: str,
    endpoint: str,
    p256dh: str,
    auth: str,
    topics: dict[str, bool],
    min_interval_sec: int,
    enabled: bool = True,
) -> None:
    ensure_push_tables()
    tid = (tenant_id or "local").strip() or "local"
    slug = (screen_slug or "").strip().lower()
    ep = (endpoint or "").strip()
    if not slug or not ep:
        return
    mi = int(min_interval_sec or 300)
    mi = max(30, min(24 * 60 * 60, mi))
    topics_s = json.dumps(sanitize_topics(topics), ensure_ascii=False, separators=(",", ":"))
    ts = utc_iso_now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO push_subscriptions (
                tenant_id, screen_slug, endpoint, p256dh, auth,
                topics_json, min_interval_sec,
                created_at, last_seen_at, enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tenant_id, screen_slug, endpoint) DO UPDATE SET
                p256dh=excluded.p256dh,
                auth=excluded.auth,
                topics_json=excluded.topics_json,
                min_interval_sec=excluded.min_interval_sec,
                last_seen_at=excluded.last_seen_at,
                enabled=excluded.enabled
            """,
            (
                tid,
                slug[:64],
                ep[:1000],
                str(p256dh or "")[:256],
                str(auth or "")[:256],
                topics_s,
                mi,
                ts,
                ts,
                1 if enabled else 0,
            ),
        )


def delete_subscription(*, tenant_id: str, screen_slug: str, endpoint: str) -> int:
    ensure_push_tables()
    tid = (tenant_id or "local").strip() or "local"
    slug = (screen_slug or "").strip().lower()
    ep = (endpoint or "").strip()
    if not slug or not ep:
        return 0
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM push_subscriptions WHERE tenant_id=? AND screen_slug=? AND endpoint=?",
            (tid, slug[:64], ep[:1000]),
        )
        return int(cur.rowcount or 0)


def list_subscriptions(*, tenant_id: str, screen_slug: str, topic: str | None = None) -> list[dict[str, Any]]:
    ensure_push_tables()
    tid = (tenant_id or "local").strip() or "local"
    slug = (screen_slug or "").strip().lower()
    tp = (topic or "").strip().lower()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT endpoint, p256dh, auth, topics_json, min_interval_sec
            FROM push_subscriptions
            WHERE tenant_id=? AND screen_slug=? AND enabled=1
            ORDER BY id DESC
            """,
            (tid, slug[:64]),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        try:
            topics = json.loads(str(r["topics_json"] or "{}"))
        except Exception:
            topics = {}
        if tp:
            if not isinstance(topics, dict) or topics.get(tp) is not True:
                continue
        out.append(
            {
                "endpoint": str(r["endpoint"] or ""),
                "keys": {"p256dh": str(r["p256dh"] or ""), "auth": str(r["auth"] or "")},
                "min_interval_sec": int(r["min_interval_sec"] or 300),
            }
        )
    return out


@dataclass
class RateLimitDecision:
    should_send: bool
    pending_count: int


def rate_limit_decide(*, tenant_id: str, screen_slug: str, topic: str, min_interval_sec: int) -> RateLimitDecision:
    """
    Возвращает should_send и pending_count (сколько накопилось, включая текущий инкремент, если не отправляем).
    Ключ на уровне (tenant, screen, topic).
    """
    ensure_push_tables()
    tid = (tenant_id or "local").strip() or "local"
    slug = (screen_slug or "").strip().lower()[:64]
    tp = (topic or "").strip().lower()[:64]
    mi = int(min_interval_sec or 300)
    mi = max(30, min(24 * 60 * 60, mi))
    key = f"{tid}|{slug}|{tp}"
    now = int(time.time())
    with _connect() as conn:
        row = conn.execute("SELECT last_sent_at, pending_count FROM push_rate_limits WHERE key=?", (key,)).fetchone()
        last = int(row["last_sent_at"] or 0) if row else 0
        pending = int(row["pending_count"] or 0) if row else 0
        if last and (now - last) < mi:
            pending += 1
            conn.execute(
                "INSERT INTO push_rate_limits(key,last_sent_at,pending_count) VALUES(?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET pending_count=excluded.pending_count",
                (key, last, pending),
            )
            return RateLimitDecision(False, pending)
        # allow send
        conn.execute(
            "INSERT INTO push_rate_limits(key,last_sent_at,pending_count) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET last_sent_at=excluded.last_sent_at, pending_count=0",
            (key, now, 0),
        )
        return RateLimitDecision(True, 0)


def _vapid_pem_from_env_or_file(*, env_var: str, file_var: str) -> str:
    """
    PEM из переменной или из файла (удобно для systemd EnvironmentFile,
    где многострочные значения задать нельзя).
    """
    fp = (os.environ.get(file_var) or "").strip()
    if fp:
        try:
            p = Path(fp)
            if p.is_file():
                return p.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return (os.environ.get(env_var) or "").strip()


def vapid_public_key() -> str:
    return _vapid_pem_from_env_or_file(
        env_var="GUARDSCHOOL_VAPID_PUBLIC_KEY",
        file_var="GUARDSCHOOL_VAPID_PUBLIC_KEY_FILE",
    )


def vapid_private_key() -> str:
    return _vapid_pem_from_env_or_file(
        env_var="GUARDSCHOOL_VAPID_PRIVATE_KEY",
        file_var="GUARDSCHOOL_VAPID_PRIVATE_KEY_FILE",
    )


def vapid_subject() -> str:
    return (os.environ.get("GUARDSCHOOL_VAPID_SUBJECT") or "mailto:adm@guarddoc.ru").strip()

