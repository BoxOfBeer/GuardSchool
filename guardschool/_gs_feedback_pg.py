"""Хранилище и операции обратной связи с экрана (SQLite)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .gs_paths import DATA_DIR

FEEDBACK_DB_PATH = DATA_DIR / "feedback.sqlite3"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(FEEDBACK_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def ensure_feedback_tables() -> None:
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS feedback_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL DEFAULT 'local',
                device_hash TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_hidden INTEGER NOT NULL DEFAULT 0,
                is_read INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS feedback_messages_created_idx
                ON feedback_messages(created_at DESC);
            CREATE INDEX IF NOT EXISTS feedback_messages_device_idx
                ON feedback_messages(device_hash, created_at DESC);
            CREATE TABLE IF NOT EXISTS feedback_blocked_hashes (
                device_hash TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            );
            """
        )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_feedback_blocked(device_hash: str) -> bool:
    h = (device_hash or "").strip()
    if not h:
        return True
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM feedback_blocked_hashes WHERE device_hash=? LIMIT 1",
            (h,),
        ).fetchone()
    return bool(row)


def can_send_feedback(device_hash: str, cooldown_minutes: int = 5) -> bool:
    h = (device_hash or "").strip()
    if not h:
        return False
    if is_feedback_blocked(h):
        return False
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)).isoformat()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id FROM feedback_messages
            WHERE device_hash=? AND created_at>=?
            ORDER BY id DESC LIMIT 1
            """,
            (h, cutoff),
        ).fetchone()
    return row is None


def create_feedback_message(tenant_id: str, device_hash: str, message: str) -> dict[str, Any]:
    ts = _utc_now_iso()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO feedback_messages (tenant_id, device_hash, message, created_at, is_hidden, is_read)
            VALUES (?, ?, ?, ?, 0, 0)
            """,
            ((tenant_id or "local").strip() or "local", (device_hash or "").strip(), (message or "").strip(), ts),
        )
        new_id = int(cur.lastrowid or 0)
    return {"id": new_id, "created_at": ts}


def list_feedback_messages(limit: int = 300, include_hidden: bool = False) -> list[dict[str, Any]]:
    lim = max(1, min(1000, int(limit or 300)))
    query = """
        SELECT id, tenant_id, device_hash, message, created_at, is_hidden, is_read
        FROM feedback_messages
    """
    params: list[Any] = []
    if not include_hidden:
        query += " WHERE is_hidden=0"
    query += " ORDER BY id DESC LIMIT ?"
    params.append(lim)
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [
        {
            "id": int(r["id"]),
            "tenant_id": str(r["tenant_id"] or ""),
            "device_hash": str(r["device_hash"] or ""),
            "message": str(r["message"] or ""),
            "created_at": str(r["created_at"] or ""),
            "is_hidden": bool(r["is_hidden"]),
            "is_read": bool(r["is_read"]),
        }
        for r in rows
    ]


def count_unread_feedback_messages() -> int:
    ensure_feedback_tables()
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM feedback_messages WHERE is_read=0 AND is_hidden=0",
        ).fetchone()
    return int(row["n"] if row else 0)


def mark_feedback_read(message_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE feedback_messages SET is_read=1 WHERE id=?", (int(message_id),))


def hide_feedback(message_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE feedback_messages SET is_hidden=1 WHERE id=?", (int(message_id),))


def block_feedback_hash(device_hash: str) -> None:
    h = (device_hash or "").strip()
    if not h:
        return
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO feedback_blocked_hashes(device_hash, created_at) VALUES(?, ?)",
            (h, _utc_now_iso()),
        )
