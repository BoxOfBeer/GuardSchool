"""Commercial / provider API (лицензии, тенанты, демо, portal CMS, регистрация SaaS)."""
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request

from .capabilities import (
    CAP_LICENSE_CHECK,
    CAP_PRODUCTION_PORTAL,
    CAP_REGISTRATION,
    CAP_TENANT_PROVISIONING,
)
from .gs_auth import hash_password, password_is_valid
from .gs_capability_http import require_capability
from .gs_deploy import deployment_mode
from .gs_ensure_dirs import ensure_dirs
from .gs_jsonio import write_json
from .gs_paths import AUTH_PATH
from .gs_portal_cms import load_portal_cms_merged, sanitize_portal_cms_payload, write_portal_cms
from .provider_auth import require_provider_admin
from .provider_demo import (
    demo_token_hash,
    new_demo_isolated_slug,
    provision_demo_isolated_snapshot,
    purge_isolated_demo_copy,
    saas_tenant_slug_cookie_ok,
    school_entry_url,
    tenant_ui_host_for_demo,
)
from .provider_licenses import (
    LICENSE_LIST_SQL,
    add_calendar_years,
    generate_license_key,
    license_row_public,
    parse_license_expires_at_raw,
    provider_purge_license_db_and_disk,
    provider_purge_tenant_by_slug,
)
from .saas_db import (
    cleanup_expired_demo_sessions,
    connect_public,
    ensure_tenant_schema,
    license_key_hash,
    random_id,
    saas_db_enabled,
    schema_name_for_slug,
    utcnow,
)

router = APIRouter(tags=["commercial"])


@router.get("/api/provider/licenses")
def provider_list_licenses(request: Request) -> dict[str, Any]:
    require_capability(CAP_LICENSE_CHECK)
    require_provider_admin(request)
    if not saas_db_enabled():
        return {"licenses": []}
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute(LICENSE_LIST_SQL)
            rows = cur.fetchall() or []
    return {
        "licenses": [
            license_row_public(r[0], r[1], r[3], r[4], r[5], r[6], r[7] or "", r[8], r[9], r[2])
            for r in rows
        ]
    }


@router.get("/api/provider/licenses/{key_hash}")
def provider_get_license(key_hash: str, request: Request) -> dict[str, Any]:
    require_capability(CAP_LICENSE_CHECK)
    require_provider_admin(request)
    if not saas_db_enabled():
        raise HTTPException(status_code=500, detail="SaaS database is not configured.")
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT l.key_hash, l.license_no, l.key_plaintext, l.plan_id, l.status, l.issued_at, l.expires_at, l.notes,
                       t.slug, u.id
                FROM licenses l
                LEFT JOIN users u ON u.license_key_hash = l.key_hash
                LEFT JOIN tenants t ON t.owner_user_id = u.id
                WHERE l.key_hash = %s
                """,
                (key_hash,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "license": license_row_public(row[0], row[1], row[3], row[4], row[5], row[6], row[7] or "", row[8], row[9], row[2])
    }


@router.post("/api/provider/licenses")
async def provider_create_license(request: Request) -> dict[str, Any]:
    require_capability(CAP_LICENSE_CHECK)
    require_provider_admin(request)
    if not saas_db_enabled():
        raise HTTPException(status_code=500, detail="SaaS database is not configured.")
    body = await request.json()
    plan_id = str(body.get("plan_id") or "").strip() or "free"
    notes = str(body.get("notes") or "").strip()
    default_years: int | None = None
    raw_def = (os.environ.get("GUARDSCHOOL_LICENSE_DEFAULT_TERM_YEARS") or "").strip()
    if raw_def:
        try:
            dy = int(raw_def)
            if dy > 0:
                default_years = dy
        except ValueError:
            pass
    expires_at: datetime | None = None
    if body.get("expires_years") is not None:
        try:
            y = int(body.get("expires_years"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="expires_years must be integer.") from None
        expires_at = None if y <= 0 else add_calendar_years(utcnow(), y)
    elif body.get("expires_days") is not None:
        try:
            d = int(body.get("expires_days"))
            if d > 0:
                expires_at = utcnow() + timedelta(days=d)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="expires_days must be integer.") from None
    elif default_years is not None:
        expires_at = add_calendar_years(utcnow(), default_years)
    key = generate_license_key()
    key_h = license_key_hash(key)
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM plans WHERE id=%s", (plan_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=400, detail="Unknown plan_id")
            cur.execute(
                "INSERT INTO licenses (key_hash, key_plaintext, plan_id, status, expires_at, notes) VALUES (%s,%s,%s,'active',%s,%s)",
                (key_h, key, plan_id, expires_at, notes),
            )
        conn.commit()
    lic_no = None
    try:
        with connect_public() as conn2:
            with conn2.cursor() as cur2:
                cur2.execute("SELECT license_no FROM licenses WHERE key_hash=%s", (key_h,))
                r = cur2.fetchone()
                lic_no = r[0] if r else None
    except Exception:
        pass
    return {
        "status": "ok",
        "license_no": int(lic_no) if lic_no is not None else None,
        "license_key": key,
        "key_hash": key_h,
        "plan_id": plan_id,
        "expires_at": expires_at.isoformat() if expires_at else None,
    }


@router.post("/api/provider/licenses/{key_hash}/status")
async def provider_set_license_status(key_hash: str, request: Request) -> dict[str, str]:
    require_capability(CAP_LICENSE_CHECK)
    require_provider_admin(request)
    if not saas_db_enabled():
        raise HTTPException(status_code=500, detail="SaaS database is not configured.")
    body = await request.json()
    status = str(body.get("status") or "").strip() or "active"
    if status not in ("active", "disabled", "revoked"):
        raise HTTPException(status_code=400, detail="Invalid status")
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE licenses SET status=%s WHERE key_hash=%s", (status, key_hash))
            if cur.rowcount <= 0:
                raise HTTPException(status_code=404, detail="Not found")
        conn.commit()
    return {"status": "ok"}


@router.patch("/api/provider/licenses/{key_hash}")
async def provider_patch_license(key_hash: str, request: Request) -> dict[str, str]:
    require_capability(CAP_LICENSE_CHECK)
    require_provider_admin(request)
    if not saas_db_enabled():
        raise HTTPException(status_code=500, detail="SaaS database is not configured.")
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object required.")
    sets: list[str] = []
    params: list[Any] = []
    if "status" in body:
        st = str(body.get("status") or "").strip() or "active"
        if st not in ("active", "disabled", "revoked"):
            raise HTTPException(status_code=400, detail="Invalid status")
        sets.append("status=%s")
        params.append(st)
    if "notes" in body:
        sets.append("notes=%s")
        params.append(str(body.get("notes") or ""))
    if "plan_id" in body:
        pid = str(body.get("plan_id") or "").strip() or "free"
        sets.append("plan_id=%s")
        params.append(pid)
    exp_dt: datetime | None | str = "omit"
    years_from_issue: int | None = None
    if "expires_at" in body:
        exp_dt = parse_license_expires_at_raw(body.get("expires_at"))
    elif "expires_years_from_issue" in body and body.get("expires_years_from_issue") is not None:
        try:
            ny = int(body.get("expires_years_from_issue"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="expires_years_from_issue must be integer.") from None
        if ny <= 0:
            exp_dt = None
        else:
            exp_dt = "fetch_issue"
            years_from_issue = ny
    elif "expires_years_from_now" in body and body.get("expires_years_from_now") is not None:
        try:
            ny = int(body.get("expires_years_from_now"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="expires_years_from_now must be integer.") from None
        exp_dt = None if ny <= 0 else add_calendar_years(utcnow(), ny)
    elif "expires_days" in body and body.get("expires_days") is not None:
        try:
            d = int(body.get("expires_days"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="expires_days must be integer.")
        if d <= 0:
            exp_dt = None
        else:
            exp_dt = utcnow() + timedelta(days=d)
    if not sets and exp_dt == "omit":
        raise HTTPException(
            status_code=400,
            detail=(
                "No fields to update (status, notes, plan_id, expires_at, expires_days, "
                "expires_years_from_issue, expires_years_from_now)."
            ),
        )
    with connect_public() as conn:
        with conn.cursor() as cur:
            if exp_dt == "fetch_issue":
                if years_from_issue is None:
                    raise HTTPException(status_code=500, detail="Internal expiry resolution error.")
                cur.execute("SELECT issued_at FROM licenses WHERE key_hash=%s", (key_hash,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Not found")
                issued = row[0]
                base = issued if isinstance(issued, datetime) else utcnow()
                exp_dt = add_calendar_years(base, years_from_issue)
            if "plan_id" in body:
                pid = str(body.get("plan_id") or "").strip() or "free"
                cur.execute("SELECT id FROM plans WHERE id=%s", (pid,))
                if not cur.fetchone():
                    raise HTTPException(status_code=400, detail="Unknown plan_id")
            if exp_dt != "omit":
                sets.append("expires_at=%s")
                params.append(exp_dt)
            if not sets:
                raise HTTPException(status_code=400, detail="No fields to update.")
            sql = f"UPDATE licenses SET {', '.join(sets)} WHERE key_hash=%s"
            params.append(key_hash)
            cur.execute(sql, tuple(params))
            if cur.rowcount <= 0:
                raise HTTPException(status_code=404, detail="Not found")
            if "plan_id" in body:
                pid_sync = str(body.get("plan_id") or "").strip() or "free"
                cur.execute(
                    "UPDATE tenants SET plan_id=%s WHERE owner_user_id IN "
                    "(SELECT id FROM users WHERE license_key_hash=%s)",
                    (pid_sync, key_hash),
                )
        conn.commit()
    return {"status": "ok"}


@router.delete("/api/provider/licenses/{key_hash}")
def provider_delete_license(
    key_hash: str,
    request: Request,
    purge: bool = Query(False, description="Полное удаление тенанта и данных."),
) -> dict[str, Any]:
    require_capability(CAP_LICENSE_CHECK)
    require_provider_admin(request)
    if not saas_db_enabled():
        raise HTTPException(status_code=500, detail="SaaS database is not configured.")
    if purge:
        return provider_purge_license_db_and_disk(key_hash)
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE license_key_hash=%s LIMIT 1", (key_hash,))
            if cur.fetchone():
                raise HTTPException(
                    status_code=409,
                    detail="License already used for registration; use DELETE with purge=1 to remove tenant and license, or revoke/disable.",
                )
            cur.execute("DELETE FROM licenses WHERE key_hash=%s", (key_hash,))
            if cur.rowcount <= 0:
                raise HTTPException(status_code=404, detail="Not found")
        conn.commit()
    return {"status": "ok"}


@router.delete("/api/provider/tenants/{slug}")
def provider_delete_tenant(
    slug: str,
    request: Request,
    confirm: bool = Query(False, description="Подтверждение: confirm=1"),
) -> dict[str, Any]:
    require_capability(CAP_TENANT_PROVISIONING)
    require_provider_admin(request)
    if not saas_db_enabled():
        raise HTTPException(status_code=500, detail="SaaS database is not configured.")
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Refusing to delete tenant without confirm=1 (deletes license, DB schema, and tenant data directory).",
        )
    return provider_purge_tenant_by_slug(slug)


@router.post("/api/provider/demo")
async def provider_create_demo(request: Request) -> dict[str, Any]:
    require_capability(CAP_TENANT_PROVISIONING)
    require_provider_admin(request)
    if deployment_mode() != "saas" or not saas_db_enabled():
        raise HTTPException(status_code=500, detail="SaaS is not configured.")
    try:
        cleanup_expired_demo_sessions()
    except Exception:
        pass
    body = await request.json()
    slug = str(body.get("tenant_slug") or "").strip().lower()
    try:
        ttl_min = int(body.get("expires_minutes") or 60)
    except Exception:
        ttl_min = 60
    ttl_min = max(5, min(180, ttl_min))
    if not slug:
        raise HTTPException(status_code=400, detail="tenant_slug required")
    from .tenant_ctx import tenant_data_dir

    if not tenant_data_dir(slug).is_dir():
        raise HTTPException(status_code=404, detail="Tenant data not found on server.")
    isolated = new_demo_isolated_slug()
    try:
        provision_demo_isolated_snapshot(slug, isolated)
    except Exception:
        purge_isolated_demo_copy(isolated)
        raise HTTPException(status_code=503, detail="Could not allocate an isolated demo copy (snapshot).") from None
    token = secrets.token_urlsafe(24)
    th = demo_token_hash(token)
    expires_at = utcnow() + timedelta(minutes=ttl_min)
    try:
        with connect_public() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO demo_sessions (token_hash, tenant_slug, isolated_slug, expires_at) VALUES (%s,%s,%s,%s)",
                    (th, slug, isolated, expires_at),
                )
            conn.commit()
    except Exception:
        purge_isolated_demo_copy(isolated)
        raise
    return {
        "status": "ok",
        "token": token,
        "url_path": f"/demo/{token}",
        "tenant_host": tenant_ui_host_for_demo(slug),
        "expires_at": expires_at.isoformat(),
    }


@router.get("/api/provider/portal-cms")
def api_provider_portal_cms_get(request: Request) -> dict[str, Any]:
    require_capability(CAP_PRODUCTION_PORTAL)
    require_provider_admin(request)
    return {"cms": load_portal_cms_merged()}


@router.put("/api/provider/portal-cms")
async def api_provider_portal_cms_put(request: Request) -> dict[str, Any]:
    require_capability(CAP_PRODUCTION_PORTAL)
    require_provider_admin(request)
    raw_body = await request.json()
    raw_cms = raw_body.get("cms") if isinstance(raw_body, dict) and "cms" in raw_body else raw_body
    if raw_cms is None:
        raise HTTPException(status_code=400, detail="Expected JSON body with a cms object.")
    try:
        dumped = json.dumps(raw_cms if isinstance(raw_cms, (dict, list)) else {}, ensure_ascii=False)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.") from None
    if len(dumped.encode("utf-8")) > 480_000:
        raise HTTPException(status_code=413, detail="CMS payload too large.")
    payload = sanitize_portal_cms_payload(raw_cms)
    write_portal_cms(payload)
    return {"status": "ok", "cms": payload}


@router.post("/api/saas/register")
async def saas_register(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    require_capability(CAP_REGISTRATION)
    if deployment_mode() != "saas":
        raise HTTPException(status_code=404, detail="Not found.")
    if not saas_db_enabled():
        raise HTTPException(status_code=500, detail="SaaS database is not configured.")
    lic_key = str(payload.get("license_key") or "").strip()
    password = str(payload.get("password") or "").strip()
    slug = str(payload.get("tenant_slug") or "").strip().lower()
    if not lic_key:
        raise HTTPException(status_code=400, detail="license_key is required.")
    if not password_is_valid(password):
        raise HTTPException(status_code=400, detail="Пароль: не менее 8 символов, нужны буквы и цифры.")
    if not slug:
        slug = f"s{secrets.token_hex(6)}"
    if not saas_tenant_slug_cookie_ok(slug):
        raise HTTPException(status_code=400, detail="tenant_slug: используйте латиницу/цифры/дефис (например, s1a2b3c4d5e6f).")
    key_h = license_key_hash(lic_key)
    now = utcnow()
    schema = schema_name_for_slug(slug)
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT plan_id, status, expires_at FROM licenses WHERE key_hash=%s", (key_h,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Лицензия не найдена.")
            plan_id, status, expires_at = row[0], row[1], row[2]
            if str(status) != "active":
                raise HTTPException(status_code=403, detail="Лицензия отключена.")
            if expires_at is not None and expires_at <= now:
                raise HTTPException(status_code=403, detail="Срок лицензии истёк.")
            cur.execute(
                "SELECT id, slug FROM tenants WHERE owner_user_id IN (SELECT id FROM users WHERE license_key_hash=%s)",
                (key_h,),
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Эта лицензия уже использована.")
            cur.execute("SELECT id FROM tenants WHERE slug=%s", (slug,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Поддомен уже занят.")
            user_id = random_id("u")
            salt = secrets.token_hex(16)
            pwd_hash = hash_password(password, salt)
            cur.execute(
                "INSERT INTO users (id, license_key_hash, password_salt, password_hash) VALUES (%s,%s,%s,%s)",
                (user_id, key_h, salt, pwd_hash),
            )
            tenant_id = random_id("t")
            cur.execute(
                "INSERT INTO tenants (id, slug, schema_name, plan_id, owner_user_id) VALUES (%s,%s,%s,%s,%s)",
                (tenant_id, slug, schema, plan_id, user_id),
            )
        conn.commit()
    ensure_tenant_schema(schema)
    from .tenant_ctx import set_tenant_slug

    set_tenant_slug(slug)
    try:
        ensure_dirs()
        write_json(AUTH_PATH, {"username": lic_key, "salt": salt, "password_hash": pwd_hash})
    finally:
        set_tenant_slug(None)
    return {
        "status": "ok",
        "tenant": {"slug": slug, "schema": schema},
        "school_entry_url": school_entry_url(),
    }
