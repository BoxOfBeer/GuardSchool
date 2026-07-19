"""SaaS portal routes: /demo/{token}, /try-demo."""
from __future__ import annotations

import os
import secrets
import time
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request, Response

from .app_host_routing import is_guarddoc_portal
from .app_try_demo import (
    demo_allow_any_tenant_token,
    try_demo_public_enabled,
    try_demo_redirect_host,
    try_demo_sandbox_slug,
    try_demo_ttl_minutes,
)
from .gs_admin_http import admin_msg, admin_ui_lang, session_cookie_secure
from .gs_auth import (
    create_demo_session_token,
    obliterate_session_cookies,
)
from .gs_deploy import deployment_mode
from .gs_paths import SAAS_TENANT_COOKIE, SESSION_COOKIE
from .gs_tv_screen_api import encode_saas_tenant_cookie_value
from .provider_demo import (
    demo_token_hash,
    is_demo_isolated_slug,
    new_demo_isolated_slug,
    provision_demo_isolated_snapshot,
    purge_isolated_demo_copy,
)
from .saas_db import cleanup_expired_demo_sessions, connect_public, saas_db_enabled, utcnow

router = APIRouter(tags=["saas-portal"])


@router.get("/demo/{token}")
def demo_login(token: str, request: Request, response: Response) -> Response:
    from fastapi.responses import RedirectResponse

    if deployment_mode() != "saas" or not saas_db_enabled():
        raise HTTPException(status_code=404, detail="Not found.")
    try:
        cleanup_expired_demo_sessions()
    except Exception:
        pass
    sandbox = try_demo_sandbox_slug()
    th = demo_token_hash(token)
    now = utcnow()
    slug = ""
    isolated_res = ""
    expires_at = None
    with connect_public() as conn:
        with conn.cursor() as cur:
            if demo_allow_any_tenant_token():
                cur.execute(
                    """
                    UPDATE demo_sessions
                    SET consumed_at = now()
                    WHERE token_hash=%s AND expires_at > %s AND consumed_at IS NULL
                    RETURNING tenant_slug, COALESCE(isolated_slug,''), expires_at
                    """,
                    (th, now),
                )
            else:
                cur.execute(
                    """
                    UPDATE demo_sessions
                    SET consumed_at = now()
                    WHERE token_hash=%s AND tenant_slug=%s AND expires_at > %s AND consumed_at IS NULL
                    RETURNING tenant_slug, COALESCE(isolated_slug,''), expires_at
                    """,
                    (th, sandbox, now),
                )
            row = cur.fetchone()
            if row:
                slug = str(row[0] or "").strip().lower()
                isolated_res = str(row[1] or "").strip().lower()
                expires_at = row[2]
            if not row:
                cur.execute(
                    "SELECT tenant_slug, expires_at, consumed_at FROM demo_sessions WHERE token_hash=%s",
                    (th,),
                )
                row2 = cur.fetchone()
                if not row2:
                    raise HTTPException(status_code=403, detail="Demo token invalid.")
                token_slug, exp2, cons2 = str(row2[0] or "").strip().lower(), row2[1], row2[2]
                if token_slug != sandbox and not demo_allow_any_tenant_token():
                    loc = admin_ui_lang(request)
                    raise HTTPException(
                        status_code=403,
                        detail=admin_msg(
                            loc,
                            "Гостевое демо доступно только в отдельной песочнице.",
                            "Guest demo is available only in the isolated sandbox.",
                        ),
                    )
                if not exp2 or exp2 <= now:
                    raise HTTPException(status_code=403, detail="Demo token expired.")
                if cons2:
                    raise HTTPException(status_code=403, detail="Demo token already used.")
                raise HTTPException(status_code=403, detail="Demo token invalid.")
        conn.commit()

    try:
        exp_epoch = int(expires_at.timestamp())  # type: ignore[union-attr]
    except Exception:
        exp_epoch = int(time.time()) + 3600
    if isolated_res and is_demo_isolated_slug(isolated_res):
        token2 = create_demo_session_token(exp_epoch, template_slug=slug, isolated_slug=isolated_res)
    else:
        token2 = create_demo_session_token(exp_epoch)
    sec = session_cookie_secure(request)
    max_age = max(60, exp_epoch - int(time.time()))
    response = RedirectResponse("/", status_code=302)
    obliterate_session_cookies(response)
    response.set_cookie(
        SESSION_COOKIE,
        token2,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=sec,
        path="/",
    )
    if isolated_res and is_demo_isolated_slug(isolated_res):
        response.set_cookie(
            SAAS_TENANT_COOKIE,
            encode_saas_tenant_cookie_value(isolated_res),
            max_age=max_age,
            httponly=True,
            samesite="lax",
            secure=sec,
            path="/",
        )
    return response


@router.get("/try-demo")
def portal_try_demo(request: Request) -> Response:
    from fastapi.responses import RedirectResponse

    if not is_guarddoc_portal(request):
        raise HTTPException(status_code=404, detail="Not found")
    if not try_demo_public_enabled():
        raise HTTPException(status_code=503, detail="Try-demo is disabled.")
    if deployment_mode() != "saas" or not saas_db_enabled():
        raise HTTPException(status_code=503, detail="SaaS is not configured.")
    try:
        cleanup_expired_demo_sessions()
    except Exception:
        pass
    slug = try_demo_sandbox_slug()
    isolated = new_demo_isolated_slug()
    try:
        provision_demo_isolated_snapshot(slug, isolated)
    except Exception:
        purge_isolated_demo_copy(isolated)
        raise HTTPException(
            status_code=503,
            detail="Could not allocate an isolated demo copy (snapshot).",
        ) from None
    token = secrets.token_urlsafe(24)
    th = demo_token_hash(token)
    ttl_min = try_demo_ttl_minutes()
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
    target_host = try_demo_redirect_host(slug)
    scheme = (os.environ.get("GUARDSCHOOL_PUBLIC_SCHOOL_SCHEME") or "https").strip().lower()
    if scheme not in ("http", "https"):
        scheme = "https"
    return RedirectResponse(f"{scheme}://{target_host}/demo/{token}", status_code=302)


def register_routes(app: FastAPI) -> None:
    app.include_router(router)
