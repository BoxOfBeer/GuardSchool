"""HTML pages: /, /screen, /uploads, sw.js."""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from .app_host_routing import (
    is_guarddoc_portal as _is_guarddoc_portal,
    is_public_school_host as _is_public_school_host,
    portal_request_host as _portal_request_host,
)
from .app_screen_html import render_screen_html_page
from .gs_auth import is_authenticated, load_auth
from .gs_deploy import deployment_mode
from .gs_paths import SAAS_TENANT_COOKIE, STATIC_DIR, UPLOADS_DIR, resolve_brand_logo_path
from .gs_tv_pair import tv_code_plaintext_for_tenant, tv_token_active_tenant
from .gs_tv_screen_api import (
    canonical_tv_school_code as _canonical_tv_school_code,
    decode_saas_tenant_cookie_value as _decode_saas_tenant_cookie_value,
    normalize_screen_slug_for_api as _normalize_screen_slug_for_api,
    normalize_tv_pair_text as _normalize_tv_pair_text,
    tv_pwa_screen_url as _tv_pwa_screen_url,
)
from .saas_db import saas_db_enabled

router = APIRouter(tags=["pages"])


def register_page_routes(app) -> None:
    app.include_router(router)

def _tenant_upload_local_file(full_path_under_uploads_rel: Path) -> FileResponse | None:
    """Строим FileResponse для файла под UPLOADS тенанта; None если файла нет или путь небезопасен."""
    import mimetypes

    from .tenant_ctx import map_data_path

    base = map_data_path(UPLOADS_DIR).resolve()
    rel = Path(str(full_path_under_uploads_rel or "").lstrip("/").replace("\\", "/"))
    clean_parts = [p for p in rel.parts if p not in ("..", ".", "")]
    if not clean_parts:
        return None
    full = (base / Path(*clean_parts)).resolve()
    if base not in full.parents and full != base:
        return None
    if not full.is_file():
        return None
    mt, _ = mimetypes.guess_type(str(full))
    return FileResponse(full, media_type=mt or "application/octet-stream")


@router.get("/uploads/{path:path}")
def uploads_file(request: Request, path: str) -> Response:
    """
    В SaaS /uploads/ мапится на tenants/<slug>/data/uploads.
    Иконки из manifest подгружает Chromium отдельно: иногда контекст тенанта в middleware уже сброшен,
    но cookie gs_saas_tenant ещё есть — второй раз читаем cookie и подставляем slug.
    """
    from .tenant_ctx import set_tenant_slug, tenant_slug

    resp = _tenant_upload_local_file(Path(path))
    if resp:
        return resp

    prev = tenant_slug()
    if deployment_mode() == "saas":
        ck = _decode_saas_tenant_cookie_value(request.cookies.get(SAAS_TENANT_COOKIE) or "")
        if ck and ck.strip().lower():
            try:
                set_tenant_slug(ck.strip().lower())
                resp2 = _tenant_upload_local_file(Path(path))
                if resp2:
                    return resp2
            finally:
                try:
                    set_tenant_slug(prev)
                except Exception:
                    pass
    raise HTTPException(status_code=404, detail="Not found.")


@router.get("/sw.js")
def service_worker_js() -> Response:
    # Для PWA eligibility (manifest + SW). Не кешируем: экраны часто должны обновляться сразу.
    return FileResponse(
        STATIC_DIR / "sw.js",
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@router.get("/", response_class=HTMLResponse)
def root(request: Request) -> Response:
    # guarddoc.ru — портал экосистемы (лендинг/регистрация), не админка школы
    if _is_guarddoc_portal(request):
        return FileResponse(STATIC_DIR / "portal.html")
    if not load_auth():
        return RedirectResponse("/setup")
    if not is_authenticated(request):
        return RedirectResponse("/login")
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )




@router.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request) -> Response:
    # В SaaS на общем школьном хосте (school.*) первичная настройка не нужна:
    # админ = владелец лицензии, а auth.json создаётся регистрацией.
    host = _portal_request_host(request)
    if deployment_mode() == "saas" and saas_db_enabled() and _is_public_school_host(host):
        raise HTTPException(status_code=404, detail="Not found.")
    return FileResponse(STATIC_DIR / "setup.html")


@router.get("/login", response_class=HTMLResponse)
def login_page() -> Response:
    return FileResponse(STATIC_DIR / "login.html")


@router.get("/brand-logo")
def brand_logo() -> Response:
    logo_path = resolve_brand_logo_path()
    if not logo_path:
        raise HTTPException(status_code=404, detail="Логотип не найден (положите ico.png рядом с программой или в сборку).")
    return FileResponse(logo_path)


@router.get("/favicon.ico")
def favicon_ico() -> Response:
    """Убирает 404 в консоли; при наличии ico.png в корне — тот же файл, что /brand-logo."""
    logo_path = resolve_brand_logo_path()
    if logo_path:
        return FileResponse(logo_path, media_type="image/png")
    # Минимальный прозрачный PNG 1×1 — без добавления файла в репозиторий.
    return Response(
        content=base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/aurd9kAAAAASUVORK5CYII="
        ),
        media_type="image/png",
    )


@router.get("/screen/{slug}", response_class=HTMLResponse)
def screen_page(request: Request, slug: str) -> HTMLResponse:
    """
    HTML-страница ТВ. В SaaS обложки/загрузки живут в tenants/<slug>/data, а <img> не шлёт Bearer.
    Поэтому при заходе на экран с gs_tv_token из URL выставляем cookie тенанта, чтобы /uploads/* резолвился
    в правильный tenant data/ (иначе на ТВ «битые» картинки из-за 404 на /uploads/...).

    Для установки второго PWA (?pwa=1 / ?gs_pwa_install=1) редирект на /t/{код}/{slug} — иначе Chrome
    открывает уже установленный ярлык «Форпост» (scope /screen/ попадает в первое приложение).
    """
    slug_for_manifest = _normalize_screen_slug_for_api(slug) or str(slug or "").strip().lower()
    if deployment_mode() == "saas" and saas_db_enabled() and slug_for_manifest:
        q = request.query_params
        want_pwa = str(q.get("pwa") or "").strip().lower() in ("1", "true", "yes")
        want_inst = str(q.get("gs_pwa_install") or "").strip().lower() in ("1", "true", "yes")
        if want_pwa or want_inst:
            tok = str(q.get("gs_tv_token") or "").strip()
            if tok:
                tenant = tv_token_active_tenant(tok, slug_for_manifest)
                if tenant:
                    code = _canonical_tv_school_code(
                        _normalize_tv_pair_text(tv_code_plaintext_for_tenant(tenant))
                    )
                    if code:
                        return RedirectResponse(
                            _tv_pwa_screen_url(code, slug_for_manifest, tok, pwa=True),
                            status_code=302,
                        )
    return render_screen_html_page(request, slug)


@router.get("/screen/{slug}/menu")
def screen_menu(slug: str) -> Response:
    return RedirectResponse(f"/screen/{slug}?gs_menu=1")


@router.get("/screens", response_class=HTMLResponse)
def screens_index_page(request: Request) -> Response:
    """Страница выбора экрана. В SaaS с БД — только после входа (иначе утечка списка slug)."""
    if deployment_mode() == "saas" and saas_db_enabled() and not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=302)
    return FileResponse(
        STATIC_DIR / "screens.html",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )
