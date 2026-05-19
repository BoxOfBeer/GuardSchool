"""Portal web pages: register, ADM, about, portal-adm API (guarddoc.ru)."""
from __future__ import annotations

import os
import re

from fastapi import APIRouter, FastAPI, HTTPException, Request
from typing import Any

from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response

from .app_host_routing import is_guarddoc_portal as _is_guarddoc_portal
from .gs_admin_http import session_cookie_secure
from .gs_paths import STATIC_DIR
from .gs_portal_cms import load_portal_cms_merged
from .provider_auth import (
    PORTAL_ADM_COOKIE_MAX_AGE_SEC,
    PORTAL_ADM_COOKIE_NAME,
    make_portal_adm_cookie_value as _make_portal_adm_cookie_value,
    portal_adm_credentials_configured as _portal_adm_credentials_configured,
    verify_portal_adm_cookie as _verify_portal_adm_cookie,
)

router = APIRouter(tags=["portal-web"])


def register_routes(app: FastAPI) -> None:
    app.include_router(router)


@router.get("/api/portal/cms")
def api_portal_cms_public() -> dict[str, Any]:
    """Публичный контент главной страницы портала экосистемы (без авторизации)."""
    return load_portal_cms_merged()

@router.get("/register", response_class=HTMLResponse)
def portal_register_page(request: Request) -> Response:
    """Публичная страница регистрации SaaS (только для guarddoc.ru)."""
    if not _is_guarddoc_portal(request):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(STATIC_DIR / "portal_register.html")


@router.get("/guardschool")
def portal_guardschool_legacy_redirect(request: Request) -> Response:
    """Старая ссылка: контент перенесён в CMS → страница /about/guardschool."""
    if not _is_guarddoc_portal(request):
        raise HTTPException(status_code=404, detail="Not found")
    return RedirectResponse("/about/guardschool", status_code=302)


@router.get("/about/{slug}", response_class=HTMLResponse)
def portal_about_cms_page(request: Request, slug: str) -> Response:
    """Публичные страницы раздела «О продукте»: контент в portal_cms.json → pages.{slug}."""
    if not _is_guarddoc_portal(request):
        raise HTTPException(status_code=404, detail="Not found")
    sk = str(slug or "").strip().lower()
    if not sk or not re.match(r"^[a-z0-9][a-z0-9-]*$", sk):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(STATIC_DIR / "about_page.html")


@router.get("/provider")
def portal_provider_redirect(request: Request) -> Response:
    """Старая ссылка: провайдерский UI перенесён на /ADM."""
    if not _is_guarddoc_portal(request):
        raise HTTPException(status_code=404, detail="Not found")
    return RedirectResponse("/ADM", status_code=302)


@router.get("/adm")
def portal_adm_redirect_lowercase() -> Response:
    """Редирект /adm → /ADM (без проверки Host: иначе за кривым прокси был бы 404 вместо редиректа)."""
    return RedirectResponse("/ADM", status_code=302)


@router.post("/api/portal-adm/login")
async def portal_adm_login(request: Request) -> Response:
    if not _is_guarddoc_portal(request):
        raise HTTPException(status_code=404, detail="Not found")
    if not _portal_adm_credentials_configured():
        raise HTTPException(status_code=501, detail="Portal ADM login is not configured.")
    body = await request.json()
    u = str(body.get("username") or "").strip()
    p = str(body.get("password") or "").strip()
    eu = (os.environ.get("GUARDSCHOOL_PORTAL_ADM_USERNAME") or "").strip()
    ep = (os.environ.get("GUARDSCHOOL_PORTAL_ADM_PASSWORD") or "").strip()
    if u != eu or p != ep:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    out = JSONResponse({"status": "ok"})
    sec = session_cookie_secure(request)
    out.set_cookie(
        PORTAL_ADM_COOKIE_NAME,
        _make_portal_adm_cookie_value(),
        max_age=PORTAL_ADM_COOKIE_MAX_AGE_SEC,
        httponly=True,
        samesite="lax",
        secure=sec,
        path="/",
    )
    return out


@router.post("/api/portal-adm/logout")
def portal_adm_logout(request: Request) -> Response:
    if not _is_guarddoc_portal(request):
        raise HTTPException(status_code=404, detail="Not found")
    out = JSONResponse({"status": "ok"})
    sec = session_cookie_secure(request)
    out.delete_cookie(PORTAL_ADM_COOKIE_NAME, path="/", secure=sec, httponly=True, samesite="lax")
    return out


@router.get("/ADM", response_class=HTMLResponse)
def portal_adm_page(request: Request) -> Response:
    """Служебная страница лицензий: логин/пароль из env или fallback на Bearer-страницу."""
    if not _is_guarddoc_portal(request):
        raise HTTPException(status_code=404, detail="Not found")
    if _portal_adm_credentials_configured():
        if _verify_portal_adm_cookie(request):
            return FileResponse(STATIC_DIR / "portal_adm.html")
        return FileResponse(STATIC_DIR / "portal_adm_login.html")
    if (os.environ.get("GUARDSCHOOL_PROVIDER_ADMIN_TOKEN") or "").strip():
        return FileResponse(STATIC_DIR / "portal_provider.html")
    return HTMLResponse(
        content=(
            "<!doctype html><html lang='ru'><head><meta charset='utf-8' /><title>ADM</title></head>"
            "<body style='font-family:system-ui;padding:24px;max-width:720px;line-height:1.5'>"
            "<h1 style='font-size:1.1rem'>ADM: лицензии не настроены</h1>"
            "<p>На сервере GuardSchool (процесс uvicorn) задайте <strong>один</strong> из вариантов:</p>"
            "<ul>"
            "<li><strong>Вход по логину/паролю</strong> в веб-форме: переменные "
            "<code>GUARDSCHOOL_PORTAL_ADM_USERNAME</code> и <code>GUARDSCHOOL_PORTAL_ADM_PASSWORD</code> "
            "(пароль ≥8 символов, буквы и цифры), затем перезапуск сервиса. Откройте "
            "<a href='/ADM'>/ADM</a> (именно заглавные ADM).</li>"
            "<li><strong>Провайдер по токену</strong> (страница с Bearer): "
            "<code>GUARDSCHOOL_PROVIDER_ADMIN_TOKEN</code> — тот же секрет вставляется в браузере на /ADM.</li>"
            "</ul>"
            "<p>Доступ к ADM включается <strong>только</strong> этими переменными в окружении процесса на сервере. "
            "Логин и пароль администратора школы (например, на поддомене <code>school.*</code>) — отдельная сущность и к выдаче лицензий не относится.</p>"
            "</body></html>"
        ),
        status_code=503,
    )


@router.get("/demo-setup", response_class=HTMLResponse)
def portal_demo_setup_page(request: Request) -> Response:
    """Страница выдачи временного демо-доступа (только guarddoc.ru)."""
    if not _is_guarddoc_portal(request):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(STATIC_DIR / "portal_demo_setup.html")

