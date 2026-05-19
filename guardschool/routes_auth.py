"""Auth and bootstrap API (/api/setup, login, capabilities). Open-core."""
from __future__ import annotations

from typing import Any

import secrets

from fastapi import APIRouter, Form, HTTPException, Query, Request, Response

from .app_host_routing import (
    is_public_school_host as _is_public_school_host,
    portal_request_host as _portal_request_host,
)
from .capabilities import get_capabilities_public
from .gs_admin_http import admin_msg, admin_ui_lang, session_cookie_secure
from .gs_auth import (
    create_session_token,
    hash_password,
    load_auth,
    obliterate_session_cookies,
    password_is_valid,
    require_auth,
)
from .gs_deploy import deployment_mode
from .gs_jsonio import write_json
from .gs_paths import AUTH_PATH, SAAS_TENANT_COOKIE, SESSION_COOKIE
from .gs_saas_limits import saas_mode
from .gs_tv_screen_api import encode_saas_tenant_cookie_value as _encode_saas_tenant_cookie_value
from .saas_db import connect_public, license_key_hash, saas_db_enabled
from .widget_registry import widget_registry_public

router = APIRouter(tags=["auth"])


def register_auth_routes(app) -> None:
    app.include_router(router)


@router.get("/api/bootstrap")
def bootstrap_state() -> dict[str, Any]:
    return {
        "configured": bool(load_auth()),
        "saas_mode": saas_mode(),
        "deployment_mode": deployment_mode(),
        "capabilities": get_capabilities_public(),
    }


@router.get("/api/capabilities")
def api_capabilities() -> dict[str, Any]:
    return {"capabilities": get_capabilities_public()}


@router.get("/api/widgets/registry")
def api_widgets_registry(request: Request, official_only: bool = Query(False)) -> dict[str, Any]:
    require_auth(request)
    for_saas = saas_mode() or deployment_mode() == "saas"
    return widget_registry_public(official_only=official_only or for_saas, for_saas=for_saas)


@router.post("/api/setup")
async def setup_admin(request: Request, username: str = Form(...), password: str = Form(...)) -> dict[str, str]:
    host = _portal_request_host(request)
    if deployment_mode() == "saas" and saas_db_enabled() and _is_public_school_host(host):
        raise HTTPException(status_code=404, detail="Not found.")
    loc = admin_ui_lang(request)
    if load_auth():
        raise HTTPException(
            status_code=409,
            detail=admin_msg(loc, "Администратор уже создан.", "Administrator account already exists."),
        )
    if not password_is_valid(password):
        raise HTTPException(
            status_code=400,
            detail=admin_msg(
                loc,
                "Пароль: не менее 8 символов, нужны буквы и цифры.",
                "Password: at least 8 characters, with letters and digits.",
            ),
        )
    salt = secrets.token_hex(16)
    write_json(AUTH_PATH, {"username": username.strip(), "salt": salt, "password_hash": hash_password(password, salt)})
    return {"status": "ok"}


@router.post("/api/login")
async def login(request: Request, response: Response, username: str = Form(...), password: str = Form(...)) -> dict[str, str]:
    loc = admin_ui_lang(request)
    host = _portal_request_host(request)

    if deployment_mode() == "saas" and saas_db_enabled() and _is_public_school_host(host):
        u = username.strip()
        if not u:
            raise HTTPException(
                status_code=401,
                detail=admin_msg(loc, "Неверный логин или пароль.", "Invalid username or password."),
            )
        key_h = license_key_hash(u)
        with connect_public() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.password_salt, u.password_hash, t.slug
                    FROM users u
                    INNER JOIN tenants t ON t.owner_user_id = u.id
                    WHERE u.license_key_hash = %s
                    """,
                    (key_h,),
                )
                row = cur.fetchone()
        if not row or hash_password(password, row[0]) != row[1]:
            raise HTTPException(
                status_code=401,
                detail=admin_msg(loc, "Неверный логин или пароль.", "Invalid username or password."),
            )
        tenant_slug_val = str(row[2]).strip().lower()
        from .tenant_ctx import set_tenant_slug, tenant_slug as tenant_slug_get

        prev = tenant_slug_get()
        set_tenant_slug(tenant_slug_val)
        try:
            auth = load_auth()
            if not auth:
                raise HTTPException(
                    status_code=503,
                    detail=admin_msg(
                        loc,
                        "Данные организации не подготовлены. Обратитесь к поддержке.",
                        "School tenant data is not provisioned.",
                    ),
                )
            if str(auth.get("username") or "").strip() != u:
                raise HTTPException(
                    status_code=503,
                    detail=admin_msg(
                        loc,
                        "Несоответствие учётной записи и данных организации. Обратитесь к поддержке.",
                        "Auth data mismatch for this school.",
                    ),
                )
        finally:
            set_tenant_slug(prev)
        obliterate_session_cookies(response)
        token = create_session_token(u, auth)
        sec = session_cookie_secure(request)
        response.set_cookie(
            SESSION_COOKIE,
            token,
            httponly=True,
            samesite="lax",
            secure=sec,
            path="/",
        )
        response.set_cookie(
            SAAS_TENANT_COOKIE,
            _encode_saas_tenant_cookie_value(tenant_slug_val),
            httponly=True,
            samesite="lax",
            secure=sec,
            path="/",
        )
        return {"status": "ok"}

    auth = load_auth()
    if not auth:
        raise HTTPException(
            status_code=428,
            detail=admin_msg(loc, "Сначала создайте администратора.", "Create the administrator account first."),
        )
    if username.strip() != auth["username"] or hash_password(password, auth["salt"]) != auth["password_hash"]:
        raise HTTPException(
            status_code=401,
            detail=admin_msg(loc, "Неверный логин или пароль.", "Invalid username or password."),
        )
    sec = session_cookie_secure(request)
    obliterate_session_cookies(response)
    token = create_session_token(username.strip(), auth)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=sec,
        path="/",
    )
    return {"status": "ok"}


@router.post("/api/logout")
def logout(request: Request, response: Response) -> dict[str, str]:
    """Снимает обычную и демо-сессию (cookie `SESSION_COOKIE`, оба варианта Secure)."""
    obliterate_session_cookies(response)
    return {"status": "ok"}
