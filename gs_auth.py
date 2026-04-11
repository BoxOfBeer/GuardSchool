"""Аутентификация администратора и сессия по cookie."""
from __future__ import annotations

import hashlib
import hmac
from typing import Any

from fastapi import HTTPException, Request

from gs_admin_http import admin_msg, admin_ui_lang
from gs_jsonio import read_json
from gs_paths import AUTH_PATH, SESSION_COOKIE


def load_auth() -> dict[str, Any]:
    return read_json(AUTH_PATH, {})


def hash_password(password: str, salt: str) -> str:
    raw = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 150000)
    return raw.hex()


def password_is_valid(password: str) -> bool:
    return len(password) >= 8 and any(ch.isalpha() for ch in password) and any(ch.isdigit() for ch in password)


def create_session_token(username: str, auth: dict[str, Any]) -> str:
    signature = hmac.new(
        auth["password_hash"].encode("utf-8"),
        username.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{username}:{signature}"


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
    return verify_session_token(token, load_auth())


def require_auth(request: Request) -> None:
    loc = admin_ui_lang(request)
    if not load_auth():
        raise HTTPException(
            status_code=428,
            detail=admin_msg(
                loc,
                "Требуется первичная настройка администратора.",
                "Complete initial administrator setup first.",
            ),
        )
    if not is_authenticated(request):
        raise HTTPException(
            status_code=401,
            detail=admin_msg(loc, "Требуется вход.", "Sign in required."),
        )
