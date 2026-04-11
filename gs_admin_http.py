"""Локаль админки и флаги cookie (FastAPI Request)."""
from __future__ import annotations

from fastapi import Request


def admin_ui_lang(request: Request) -> str:
    return "en" if request.headers.get("X-UI-Locale", "").strip().lower() == "en" else "ru"


def admin_msg(lang: str, ru: str, en: str) -> str:
    return en if lang == "en" else ru


def session_cookie_secure(request: Request) -> bool:
    xfp = str(request.headers.get("x-forwarded-proto", "")).strip().lower()
    if xfp.startswith("https"):
        return True
    try:
        return request.url.scheme == "https"
    except Exception:
        return False
