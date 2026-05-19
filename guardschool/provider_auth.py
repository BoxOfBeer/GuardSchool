"""Авторизация провайдера (ADM / Bearer token)."""
from __future__ import annotations

import hashlib
import hmac
import os
import time

from fastapi import HTTPException, Request

PORTAL_ADM_COOKIE_NAME = "gs_portal_adm"
PORTAL_ADM_COOKIE_MAX_AGE_SEC = 12 * 3600


def _portal_adm_cookie_secret() -> bytes:
    raw = (
        (os.environ.get("GUARDSCHOOL_PORTAL_ADM_SECRET") or "").strip()
        or (os.environ.get("GUARDSCHOOL_PROVIDER_ADMIN_TOKEN") or "").strip()
        or (os.environ.get("GUARDSCHOOL_LICENSE_PEPPER") or "").strip()
        or "guardschool-portal-adm"
    )
    return hashlib.sha256(raw.encode("utf-8")).digest()


def make_portal_adm_cookie_value() -> str:
    exp = int(time.time()) + PORTAL_ADM_COOKIE_MAX_AGE_SEC
    msg = str(exp).encode("utf-8")
    sig = hmac.new(_portal_adm_cookie_secret(), msg, hashlib.sha256).hexdigest()
    return f"{exp}|{sig}"


def verify_portal_adm_cookie(request: Request) -> bool:
    raw = (request.cookies.get(PORTAL_ADM_COOKIE_NAME) or "").strip()
    if "|" not in raw:
        return False
    exp_s, sig = raw.split("|", 1)
    try:
        exp = int(exp_s)
    except ValueError:
        return False
    if exp < int(time.time()):
        return False
    msg = str(exp).encode("utf-8")
    expected = hmac.new(_portal_adm_cookie_secret(), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


def portal_adm_credentials_configured() -> bool:
    u = (os.environ.get("GUARDSCHOOL_PORTAL_ADM_USERNAME") or "").strip()
    p = (os.environ.get("GUARDSCHOOL_PORTAL_ADM_PASSWORD") or "").strip()
    return bool(u and p)


def provider_admin_configured() -> bool:
    if (os.environ.get("GUARDSCHOOL_PROVIDER_ADMIN_TOKEN") or "").strip():
        return True
    return portal_adm_credentials_configured()


def provider_admin_authorized(request: Request) -> bool:
    tok = (os.environ.get("GUARDSCHOOL_PROVIDER_ADMIN_TOKEN") or "").strip()
    auth = (request.headers.get("authorization") or "").strip()
    if tok and auth == f"Bearer {tok}":
        return True
    return verify_portal_adm_cookie(request)


def require_provider_admin(request: Request) -> None:
    if not provider_admin_configured():
        raise HTTPException(status_code=501, detail="Provider admin is not configured.")
    if not provider_admin_authorized(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
