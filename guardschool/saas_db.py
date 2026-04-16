"""SaaS: PostgreSQL (public + schema-per-tenant) и простые миграции."""
from __future__ import annotations

import os
import secrets
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Any, Iterable


def saas_database_url() -> str:
    # отдельная переменная, чтобы не конфликтовать с cloud_store (school_snapshot)
    return (os.environ.get("GUARDSCHOOL_SAAS_DATABASE_URL") or os.environ.get("GUARDSCHOOL_DATABASE_URL") or "").strip()


def saas_db_enabled() -> bool:
    return bool(saas_database_url())


def _connect():
    import psycopg2

    return psycopg2.connect(saas_database_url())


@contextmanager
def connect_public():
    """Подключение к БД для операций в public."""
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


def _exec_many(cur, statements: Iterable[str]) -> None:
    for s in statements:
        cur.execute(s)


def ensure_public_schema() -> None:
    """Создать базовые таблицы SaaS (public)."""
    if not saas_db_enabled():
        return
    with connect_public() as conn:
        with conn.cursor() as cur:
            _exec_many(
                cur,
                [
                    """
                    CREATE TABLE IF NOT EXISTS plans (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        level TEXT NOT NULL, -- free|paid|saas_only
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    );
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS licenses (
                        key_hash TEXT PRIMARY KEY,
                        plan_id TEXT NOT NULL REFERENCES plans(id),
                        status TEXT NOT NULL DEFAULT 'active', -- active|disabled|revoked
                        issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        expires_at TIMESTAMPTZ NULL,
                        notes TEXT NOT NULL DEFAULT ''
                    );
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        license_key_hash TEXT NOT NULL REFERENCES licenses(key_hash),
                        password_salt TEXT NOT NULL,
                        password_hash TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        last_login_at TIMESTAMPTZ NULL
                    );
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS sessions (
                        token_hash TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL REFERENCES users(id),
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        expires_at TIMESTAMPTZ NOT NULL
                    );
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS tenants (
                        id TEXT PRIMARY KEY,
                        slug TEXT NOT NULL UNIQUE,
                        schema_name TEXT NOT NULL UNIQUE,
                        status TEXT NOT NULL DEFAULT 'active', -- active|disabled
                        plan_id TEXT NOT NULL REFERENCES plans(id),
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        expires_at TIMESTAMPTZ NULL,
                        owner_user_id TEXT NOT NULL REFERENCES users(id)
                    );
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS demo_sessions (
                        token_hash TEXT PRIMARY KEY,
                        tenant_slug TEXT NOT NULL DEFAULT '',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        expires_at TIMESTAMPTZ NOT NULL
                    );
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS tv_access (
                        tenant_slug TEXT PRIMARY KEY,
                        code_plaintext TEXT NOT NULL DEFAULT '',
                        code_hash TEXT NOT NULL UNIQUE,
                        pin_salt TEXT NOT NULL,
                        pin_hash TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    );
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS tv_devices (
                        token_hash TEXT PRIMARY KEY,
                        tenant_slug TEXT NOT NULL,
                        screen_slug TEXT NOT NULL,
                        label TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL DEFAULT 'active', -- active|revoked
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        last_seen_at TIMESTAMPTZ NULL,
                        expires_at TIMESTAMPTZ NULL
                    );
                    """,
                    "CREATE INDEX IF NOT EXISTS tv_devices_tenant_idx ON tv_devices(tenant_slug);",
                    "CREATE INDEX IF NOT EXISTS tv_devices_screen_idx ON tv_devices(tenant_slug, screen_slug);",
                ],
            )
            # Backward-compatible: add tenant_slug if table existed before.
            try:
                cur.execute("ALTER TABLE demo_sessions ADD COLUMN IF NOT EXISTS tenant_slug TEXT NOT NULL DEFAULT ''")
            except Exception:
                pass
            try:
                cur.execute("ALTER TABLE tv_access ADD COLUMN IF NOT EXISTS code_plaintext TEXT NOT NULL DEFAULT ''")
            except Exception:
                pass

            # Минимальные планы (идемпотентно).
            cur.execute("SELECT id FROM plans WHERE id IN ('free','paid','saas_only')")
            existing = {r[0] for r in (cur.fetchall() or [])}
            seeds = [
                ("free", "Free", "free"),
                ("paid", "Paid", "paid"),
                ("saas_only", "SaaS only", "saas_only"),
            ]
            for pid, title, level in seeds:
                if pid in existing:
                    continue
                cur.execute("INSERT INTO plans (id, title, level) VALUES (%s,%s,%s)", (pid, title, level))
        conn.commit()


def ensure_tenant_schema(schema_name: str) -> None:
    """Создать схему школы + таблицу снапшота (как в cloud_store), но внутри tenant-схемы."""
    if not saas_db_enabled():
        return
    schema = schema_name.strip()
    if not schema or not schema.replace("_", "").isalnum():
        raise ValueError("Invalid schema_name")
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS "{schema}".school_snapshot (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    revision BIGINT NOT NULL DEFAULT 1,
                    snapshot JSONB NOT NULL DEFAULT '{{}}'::jsonb
                );
                """
            )
        conn.commit()


def schema_name_for_slug(slug: str) -> str:
    s = (slug or "").strip().lower()
    s = "".join(ch for ch in s if ch.isalnum() or ch == "_")
    if not s:
        raise ValueError("Invalid tenant slug")
    if s[0].isdigit():
        s = f"t{s}"
    return f"t_{s}"[:48]


def set_search_path(conn, schema_name: str) -> None:
    with conn.cursor() as cur:
        cur.execute('SET search_path TO "%s", public' % schema_name.replace('"', ""))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def random_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(10)}"


def license_key_hash(key: str) -> str:
    pepper = (os.environ.get("GUARDSCHOOL_LICENSE_PEPPER") or "").encode("utf-8")
    raw = (key or "").strip().encode("utf-8")
    return hashlib.sha256(pepper + b"\n" + raw).hexdigest()


def tv_pepper_bytes() -> bytes:
    """
    Отдельный pepper для ТВ-кодов/PIN. По умолчанию берём GUARDSCHOOL_LICENSE_PEPPER,
    чтобы не требовать новую переменную в окружении.
    """
    raw = (os.environ.get("GUARDSCHOOL_TV_PEPPER") or os.environ.get("GUARDSCHOOL_LICENSE_PEPPER") or "").encode("utf-8")
    return raw


def tv_code_hash(code: str) -> str:
    pep = tv_pepper_bytes()
    raw = (code or "").strip().lower().encode("utf-8")
    return hashlib.sha256(pep + b"\ncode\n" + raw).hexdigest()


def tv_pin_hash(pin: str, salt: str) -> str:
    pep = tv_pepper_bytes()
    p = (pin or "").strip().encode("utf-8")
    s = (salt or "").strip().encode("utf-8")
    return hashlib.sha256(pep + b"\npin\n" + s + b"\n" + p).hexdigest()


def tv_device_token_hash(token: str) -> str:
    pep = tv_pepper_bytes()
    raw = (token or "").strip().encode("utf-8")
    return hashlib.sha256(pep + b"\ndevice\n" + raw).hexdigest()


def cleanup_expired_demo_sessions() -> int:
    """Удаляет просроченные строки demo_sessions (токен уже недействителен)."""
    if not saas_db_enabled():
        return 0
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM demo_sessions WHERE expires_at < now()")
            n = int(cur.rowcount or 0)
        conn.commit()
    return n

