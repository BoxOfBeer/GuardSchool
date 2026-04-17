"""Аутентификация администратора и сессия по cookie."""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Any

from fastapi import HTTPException, Request
from starlette.responses import Response

from .gs_admin_http import admin_msg, admin_ui_lang
from .gs_jsonio import read_json
from .gs_paths import AUTH_PATH, SESSION_COOKIE


def load_auth() -> dict[str, Any]:
    return read_json(AUTH_PATH, {})


def hash_password(password: str, salt: str) -> str:
    raw = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 150000)
    return raw.hex()


def password_is_valid(password: str) -> bool:
    return len(password) >= 8 and any(ch.isalpha() for ch in password) and any(ch.isdigit() for ch in password)


def obliterate_session_cookies(response: Response) -> None:
    """
    Снять session-cookie в вариантах Secure=True и Secure=False.
    Иначе после входа по HTTP (cookie без Secure) и работы по HTTPS (delete только с Secure)
    в браузере остаётся старая демо-cookie — плашка «Демо» не исчезает после обычного логина.
    """
    for sec in (True, False):
        response.delete_cookie(SESSION_COOKIE, path="/", secure=sec, httponly=True, samesite="lax")
        response.set_cookie(
            SESSION_COOKIE,
            "",
            max_age=0,
            path="/",
            secure=sec,
            httponly=True,
            samesite="lax",
        )


def create_session_token(username: str, auth: dict[str, Any]) -> str:
    signature = hmac.new(
        auth["password_hash"].encode("utf-8"),
        username.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{username}:{signature}"


def _demo_session_secret_bytes() -> bytes:
    raw = (
        (os.environ.get("GUARDSCHOOL_DEMO_SESSION_SECRET") or "").strip()
        or (os.environ.get("GUARDSCHOOL_LICENSE_PEPPER") or "").strip()
        or "guardschool-demo-session"
    )
    return hashlib.sha256(raw.encode("utf-8")).digest()


def create_demo_session_token(exp_epoch: int) -> str:
    """Временная сессия после /demo/{token}; не использует password_hash владельца."""
    exp = int(exp_epoch)
    msg = f"__gsdemo__:{exp}".encode("utf-8")
    sig = hmac.new(_demo_session_secret_bytes(), msg, hashlib.sha256).hexdigest()
    return f"__gsdemo__:{exp}:{sig}"


def verify_demo_session_token(token: str | None) -> bool:
    if not token or not str(token).startswith("__gsdemo__:"):
        return False
    parts = str(token).split(":")
    if len(parts) != 3:
        return False
    try:
        exp = int(parts[1])
    except ValueError:
        return False
    if int(time.time()) > exp:
        return False
    msg = f"__gsdemo__:{exp}".encode("utf-8")
    expected = hmac.new(_demo_session_secret_bytes(), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, parts[2])


def is_demo_session_for_admin_ui(request: Request) -> bool:
    """
    Плашка «Демо» только при действительной демо-сессии.
    Если cookie — обычный вход школы (даже при сбоях с дублями Secure), не показывать демо.
    """
    token = request.cookies.get(SESSION_COOKIE)
    auth = load_auth()
    if auth and token and verify_session_token(token, auth):
        return False
    return verify_demo_session_token(token)


def verify_session_token(token: str | None, auth: dict[str, Any]) -> bool:
    if not token or ":" not in token or not auth:
        return False
    username, signature = token.split(":", 1)
    if username != auth.get("username"):
        return False
    expected = create_session_token(username, auth).split(":", 1)[1]
    return hmac.compare_digest(signature, expected)


def is_authenticated(request: Request) -> bool:
    token = request.cookies.get(SESSION_COOKIE)
    if verify_demo_session_token(token):
        return True
    auth = load_auth()
    if not auth:
        return False
    return verify_session_token(token, auth)


def require_auth(request: Request) -> None:
    loc = admin_ui_lang(request)
    token = request.cookies.get(SESSION_COOKIE)
    if verify_demo_session_token(token):
        return
    if not load_auth():
        raise HTTPException(
            status_code=428,
            detail=admin_msg(
                loc,
                "Требуется первичная настройка администратора.",
                "Complete initial administrator setup first.",
            ),
        )
    if not verify_session_token(token, load_auth()):
        raise HTTPException(
            status_code=401,
            detail=admin_msg(loc, "Требуется вход.", "Sign in required."),
        )
