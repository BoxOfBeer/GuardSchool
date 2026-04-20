"""Аутентификация администратора и сессия по cookie."""
from __future__ import annotations

import hashlib
import hmac
import os
import time
import base64
from typing import Any

from fastapi import HTTPException, Request
from starlette.responses import Response

from .gs_admin_http import admin_msg, admin_ui_lang
from .gs_jsonio import read_json
from .gs_paths import AUTH_PATH, SAAS_TENANT_COOKIE, SESSION_COOKIE


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
        response.delete_cookie(SAAS_TENANT_COOKIE, path="/", secure=sec, httponly=True, samesite="lax")
        response.set_cookie(
            SAAS_TENANT_COOKIE,
            "",
            max_age=0,
            path="/",
            secure=sec,
            httponly=True,
            samesite="lax",
        )


def create_session_token(username: str, auth: dict[str, Any]) -> str:
    """
    Сессионная cookie должна быть ASCII (заголовок Set-Cookie кодируется latin-1).
    Поэтому username упаковываем в base64url (utf-8) без паддинга.
    """
    user_raw = (username or "").strip()
    user_b64 = base64.urlsafe_b64encode(user_raw.encode("utf-8")).decode("ascii").rstrip("=")
    signature = hmac.new(
        auth["password_hash"].encode("utf-8"),
        user_raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{user_b64}:{signature}"


def _demo_session_secret_bytes() -> bytes:
    raw = (
        (os.environ.get("GUARDSCHOOL_DEMO_SESSION_SECRET") or "").strip()
        or (os.environ.get("GUARDSCHOOL_LICENSE_PEPPER") or "").strip()
        or "guardschool-demo-session"
    )
    return hashlib.sha256(raw.encode("utf-8")).digest()


def create_demo_session_token(
    exp_epoch: int,
    template_slug: str | None = None,
    isolated_slug: str | None = None,
) -> str:
    """
    Временная сессия после /demo/{token}; не использует password_hash владельца.
    Если заданы template_slug и isolated_slug (копия данных), выпускается v3-токен,
    привязанный к поддомену/тенанту-шаблону — без этого нельзя подставить чужой isolated_slug.
    """
    exp = int(exp_epoch)
    tpl = (template_slug or "").strip().lower()
    iso = (isolated_slug or "").strip().lower()
    if tpl and iso and iso != tpl:
        msg = f"__gsdemo_v3__:{exp}:{tpl}:{iso}".encode("utf-8")
        sig = hmac.new(_demo_session_secret_bytes(), msg, hashlib.sha256).hexdigest()
        return f"__gsdemo_v3__:{exp}:{tpl}:{iso}:{sig}"
    msg = f"__gsdemo__:{exp}".encode("utf-8")
    sig = hmac.new(_demo_session_secret_bytes(), msg, hashlib.sha256).hexdigest()
    return f"__gsdemo__:{exp}:{sig}"


def verify_demo_session_token(token: str | None) -> bool:
    if not token:
        return False
    s = str(token)
    if s.startswith("__gsdemo_v3__:"):
        parts = s.split(":")
        if len(parts) != 5:
            return False
        try:
            exp = int(parts[1])
        except ValueError:
            return False
        if int(time.time()) > exp:
            return False
        tpl, iso, sig = parts[2], parts[3], parts[4]
        msg = f"__gsdemo_v3__:{exp}:{tpl}:{iso}".encode("utf-8")
        expected = hmac.new(_demo_session_secret_bytes(), msg, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig)
    if not s.startswith("__gsdemo__:"):
        return False
    parts = s.split(":")
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


def demo_v3_binding_from_token(token: str | None) -> tuple[str, str] | None:
    """Для v3-демо: (template_slug, isolated_slug) или None."""
    if not token or not str(token).startswith("__gsdemo_v3__:"):
        return None
    parts = str(token).split(":")
    if len(parts) != 5:
        return None
    if not verify_demo_session_token(token):
        return None
    return parts[2].strip().lower(), parts[3].strip().lower()


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
    user_b64, signature = token.split(":", 1)
    try:
        # добавить padding до кратности 4
        padded = user_b64 + "=" * ((4 - (len(user_b64) % 4)) % 4)
        username = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except Exception:
        return False
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
