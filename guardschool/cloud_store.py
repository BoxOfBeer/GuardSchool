"""Опциональная выгрузка состояния в PostgreSQL (облако guarddoc.ru).

При GUARDSCHOOL_DATABASE_URL данные дублируются в таблицу school_snapshot после записи JSON.
При старте приложения — гидратация с диска из БД, если таблица не пуста.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from .gs_jsonio import read_json
from .gs_paths import (
    ANNOUNCEMENTS_PATH,
    AUTH_PATH,
    BELL_SCHEDULES_PATH,
    CHANGE_LOG_PATH,
    CONFIG_PATH,
    FULL_SCHEDULE_PATH,
    HOLIDAYS_PATH,
    MARQUEE_PATH,
    OVERRIDES_PATH,
    SCHEDULE_PATH,
    SCHEDULE_SAMPLE_PATH,
    DATA_DIR,
)
from .tenant_ctx import map_data_path

_LOG = logging.getLogger(__name__)

_SNAPSHOT_KEYS: tuple[tuple[str, Path], ...] = (
    ("config.json", CONFIG_PATH),
    ("auth.json", AUTH_PATH),
    ("schedule.json", SCHEDULE_PATH),
    ("full_schedule.json", FULL_SCHEDULE_PATH),
    ("schedule_sample.json", SCHEDULE_SAMPLE_PATH),
    ("holidays.json", HOLIDAYS_PATH),
    ("announcements.json", ANNOUNCEMENTS_PATH),
    ("marquee.json", MARQUEE_PATH),
    ("overrides.json", OVERRIDES_PATH),
    ("bell_schedules.json", BELL_SCHEDULES_PATH),
    ("change_log.json", CHANGE_LOG_PATH),
)


def database_url() -> str:
    return (os.environ.get("GUARDSCHOOL_DATABASE_URL") or "").strip()


def is_cloud_database_enabled() -> bool:
    return bool(database_url())


def _connect():
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(database_url())
    # SaaS: если есть tenant в контексте — используем отдельную схему для school_snapshot.
    try:
        from .gs_deploy import deployment_mode
        from .tenant_ctx import tenant_slug
        from .saas_db import schema_name_for_slug, set_search_path

        if deployment_mode() == "saas":
            slug = tenant_slug()
            if slug:
                schema = schema_name_for_slug(slug)
                set_search_path(conn, schema)
                conn.commit()
    except Exception:
        pass
    return conn


def _ensure_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS school_snapshot (
                id INTEGER PRIMARY KEY DEFAULT 1,
                revision BIGINT NOT NULL DEFAULT 1,
                snapshot JSONB NOT NULL DEFAULT '{}'::jsonb
            );
            """
        )
    conn.commit()


def _build_snapshot_dict() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, path in _SNAPSHOT_KEYS:
        if not map_data_path(path).exists():
            continue
        try:
            out[name] = read_json(path, None)
        except (OSError, TypeError, ValueError):
            continue
    return out


def persist_snapshot_to_database() -> int | None:
    """Сохранить текущие JSON-файлы в БД; вернуть новую revision или None."""
    if not is_cloud_database_enabled():
        return None
    snap = _build_snapshot_dict()
    try:
        import psycopg2.extras

        conn = _connect()
        try:
            _ensure_table(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT revision, snapshot FROM school_snapshot WHERE id = 1")
                row = cur.fetchone()
                snap_json = psycopg2.extras.Json(snap)
                if row:
                    old_rev, old_snap = row[0], row[1]
                    old_d = dict(old_snap) if old_snap is not None else {}
                    if json.dumps(old_d, sort_keys=True) == json.dumps(snap, sort_keys=True):
                        return int(old_rev)
                    cur.execute(
                        "UPDATE school_snapshot SET revision = revision + 1, snapshot = %s WHERE id = 1 RETURNING revision",
                        (snap_json,),
                    )
                else:
                    cur.execute(
                        "INSERT INTO school_snapshot (id, revision, snapshot) VALUES (1, 1, %s) RETURNING revision",
                        (snap_json,),
                    )
                rev_row = cur.fetchone()
                conn.commit()
                return int(rev_row[0]) if rev_row else None
        finally:
            conn.close()
    except Exception as e:
        _LOG.warning("cloud_store persist failed: %s", e)
        return None


def hydrate_data_dir_from_database() -> bool:
    """Записать JSON из БД в GUARDSCHOOL_DATA_DIR. Возвращает True, если были данные."""
    if not is_cloud_database_enabled():
        return False
    try:
        conn = _connect()
        try:
            _ensure_table(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT snapshot FROM school_snapshot WHERE id = 1")
                row = cur.fetchone()
                if not row or not row[0]:
                    return False
                snap = dict(row[0])
        finally:
            conn.close()
    except Exception as e:
        _LOG.warning("cloud_store hydrate failed: %s", e)
        return False

    map_data_path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    for name, path in _SNAPSHOT_KEYS:
        if name not in snap:
            continue
        try:
            mapped = map_data_path(path)
            mapped.parent.mkdir(parents=True, exist_ok=True)
            mapped.write_text(
                json.dumps(snap[name], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except (OSError, TypeError) as e:
            _LOG.warning("cloud_store hydrate write %s: %s", name, e)
    return True


def read_revision_from_database() -> int | None:
    if not is_cloud_database_enabled():
        return None
    try:
        conn = _connect()
        try:
            _ensure_table(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT revision FROM school_snapshot WHERE id = 1")
                row = cur.fetchone()
                return int(row[0]) if row else None
        finally:
            conn.close()
    except Exception:
        return None


def notify_data_file_written(_path: Path) -> None:
    """Вызывается из write_json после записи."""
    persist_snapshot_to_database()
