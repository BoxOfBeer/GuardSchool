"""Лицензии провайдера: helpers и purge."""
from __future__ import annotations

import calendar
import os
import secrets
import shutil
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException

from .gs_deploy import deployment_mode
from .saas_db import connect_public, license_key_hash, utcnow

LICENSE_LIST_SQL = """
SELECT l.key_hash, l.license_no, l.key_plaintext, l.plan_id, l.status, l.issued_at, l.expires_at, l.notes,
       t.slug, u.id
FROM licenses l
LEFT JOIN users u ON u.license_key_hash = l.key_hash
LEFT JOIN tenants t ON t.owner_user_id = u.id
ORDER BY l.issued_at DESC
LIMIT 500
"""


def license_ts_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def add_calendar_years(dt: datetime, years: int) -> datetime:
    if years <= 0:
        return license_ts_utc(dt)
    d = license_ts_utc(dt)
    y = d.year + years
    mo, da = d.month, d.day
    if mo == 2 and da == 29:
        da = min(da, calendar.monthrange(y, mo)[1])
    try:
        return d.replace(year=y, month=mo, day=da)
    except ValueError:
        return d.replace(year=y, month=2, day=28)


def license_row_public(
    key_hash: str,
    license_no: Any,
    plan_id: str,
    status: str,
    issued_at: Any,
    expires_at: Any,
    notes: str,
    tenant_slug: str | None,
    owner_user_id: str | None,
    key_plaintext: Any = None,
) -> dict[str, Any]:
    iy: int | None = None
    ey: int | None = None
    try:
        if isinstance(issued_at, datetime):
            iy = license_ts_utc(issued_at).year
    except Exception:
        pass
    try:
        if isinstance(expires_at, datetime):
            ey = license_ts_utc(expires_at).year
    except Exception:
        pass
    return {
        "key_hash": key_hash,
        "license_no": int(license_no) if license_no is not None else None,
        "license_key": (str(key_plaintext) if isinstance(key_plaintext, str) and key_plaintext else None),
        "plan_id": plan_id,
        "status": status,
        "issued_at": issued_at.isoformat() if issued_at else None,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "issued_year": iy,
        "expires_year": ey,
        "notes": notes or "",
        "tenant_slug": tenant_slug or None,
        "owner_user_id": owner_user_id or None,
        "registered": bool(owner_user_id),
    }


def generate_license_key() -> str:
    raw = secrets.token_hex(12).upper()
    return f"GS-{raw[:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:24]}"


def parse_license_expires_at_raw(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            iso = s.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid expires_at (use ISO-8601).") from None
    raise HTTPException(status_code=400, detail="Invalid expires_at type.")


def provider_tenant_slug_param_safe(slug: str) -> str:
    s = (slug or "").strip()
    if not s or len(s) > 64 or "/" in s or "\\" in s or ".." in s:
        raise HTTPException(status_code=400, detail="Invalid tenant slug.")
    return s


def provider_purge_license_db_and_disk(key_hash: str) -> dict[str, Any]:
    from .provider_demo import purge_isolated_demo_copy
    import psycopg2.sql as sql

    slugs: list[str] = []
    schemas: list[str] = []
    user_ids: list[str] = []
    demo_iso_slugs: list[str] = []
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM licenses WHERE key_hash=%s LIMIT 1", (key_hash,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Not found")
            cur.execute(
                "SELECT u.id, t.slug, t.schema_name FROM users u "
                "LEFT JOIN tenants t ON t.owner_user_id = u.id "
                "WHERE u.license_key_hash=%s",
                (key_hash,),
            )
            for row in cur.fetchall() or []:
                uid, slug, schema = row[0], row[1], row[2]
                if uid and str(uid) not in user_ids:
                    user_ids.append(str(uid))
                if slug:
                    s = str(slug).strip()
                    if s and s not in slugs:
                        slugs.append(s)
                if schema and str(schema) not in schemas:
                    schemas.append(str(schema))
            for sch in schemas:
                cur.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(sch)))
            if slugs:
                cur.execute(
                    "SELECT DISTINCT isolated_slug FROM demo_sessions WHERE tenant_slug = ANY(%s) AND COALESCE(isolated_slug,'')<>''",
                    (slugs,),
                )
                demo_iso_slugs = [str(r[0]).strip().lower() for r in (cur.fetchall() or []) if r and r[0]]
                cur.execute("DELETE FROM tv_devices WHERE tenant_slug = ANY(%s)", (slugs,))
                cur.execute("DELETE FROM tv_access WHERE tenant_slug = ANY(%s)", (slugs,))
                cur.execute("DELETE FROM demo_sessions WHERE tenant_slug = ANY(%s)", (slugs,))
            if user_ids:
                cur.execute("DELETE FROM sessions WHERE user_id = ANY(%s)", (user_ids,))
                cur.execute("DELETE FROM tenants WHERE owner_user_id = ANY(%s)", (user_ids,))
                cur.execute("DELETE FROM users WHERE license_key_hash=%s", (key_hash,))
            cur.execute("DELETE FROM licenses WHERE key_hash=%s", (key_hash,))
            if cur.rowcount <= 0:
                raise HTTPException(status_code=404, detail="Not found")
        conn.commit()
    if deployment_mode() == "saas":
        try:
            from .tenant_ctx import tenant_data_dir

            for iso in demo_iso_slugs:
                purge_isolated_demo_copy(iso)
            for slug in slugs:
                root = tenant_data_dir(slug)
                if root.is_dir():
                    shutil.rmtree(root, ignore_errors=True)
        except Exception:
            pass
    return {"status": "ok", "purged": True, "tenant_slugs": slugs, "schemas_dropped": schemas}


def provider_purge_tenant_by_slug(slug: str) -> dict[str, Any]:
    from .provider_demo import purge_isolated_demo_copy
    import psycopg2.sql as sql

    slug_n = provider_tenant_slug_param_safe(slug)
    schema_dropped: str | None = None
    demo_iso: list[str] = []
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT t.schema_name, t.owner_user_id, u.license_key_hash FROM tenants t "
                "INNER JOIN users u ON u.id = t.owner_user_id WHERE t.slug = %s",
                (slug_n,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Tenant not found.")
            schema_name, owner_id, lic_hash = str(row[0]), str(row[1]), str(row[2])
            schema_dropped = schema_name
            cur.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema_name)))
            cur.execute("DELETE FROM tv_devices WHERE tenant_slug=%s", (slug_n,))
            cur.execute("DELETE FROM tv_access WHERE tenant_slug=%s", (slug_n,))
            cur.execute(
                "SELECT DISTINCT isolated_slug FROM demo_sessions WHERE tenant_slug=%s AND COALESCE(isolated_slug,'')<>''",
                (slug_n,),
            )
            demo_iso = [str(r[0]).strip().lower() for r in (cur.fetchall() or []) if r and r[0]]
            cur.execute("DELETE FROM demo_sessions WHERE tenant_slug=%s", (slug_n,))
            cur.execute("DELETE FROM sessions WHERE user_id=%s", (owner_id,))
            cur.execute("DELETE FROM tenants WHERE slug=%s", (slug_n,))
            cur.execute("DELETE FROM users WHERE id=%s", (owner_id,))
            cur.execute("DELETE FROM licenses WHERE key_hash=%s", (lic_hash,))
        conn.commit()
    if deployment_mode() == "saas":
        for iso in demo_iso:
            purge_isolated_demo_copy(iso)
        try:
            from .tenant_ctx import tenant_data_dir

            root = tenant_data_dir(slug_n)
            if root.is_dir():
                shutil.rmtree(root, ignore_errors=True)
        except Exception:
            pass
    return {"status": "ok", "purged": True, "slug": slug_n, "schema_dropped": schema_dropped}

