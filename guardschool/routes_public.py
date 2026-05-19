"""Public read-only API: version, school news."""
from __future__ import annotations

import html
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from .app_host_routing import (
    public_school_host_normalized as _public_school_host_normalized,
    request_host_for_routing as _request_host_for_routing,
)
from .gs_deploy import deployment_mode
from .gs_paths import APP_VERSION, AUTH_PATH, CONFIG_PATH, SAAS_TENANT_COOKIE, SESSION_COOKIE
from .gs_school_news import load_school_news
from .provider_auth import require_provider_admin as _require_provider_admin

router = APIRouter(tags=["public"])


def register_public_routes(app) -> None:
    app.include_router(router)


@router.get("/api/version")
def get_public_version() -> dict[str, str]:
    return {"product": "GuardSchool", "version": APP_VERSION}


@router.get("/api/_debug/tenant")
async def debug_tenant(request: Request) -> dict[str, Any]:
    """Диагностика SaaS tenant routing (только для провайдера)."""
    _require_provider_admin(request)
    from .tenant_ctx import tenant_slug as current_tenant
    from .tenant_ctx import map_data_path
    return {
        "host": _request_host_for_routing(request),
        "deployment_mode": deployment_mode(),
        "public_school_host": _public_school_host_normalized(),
        "tenant_slug": current_tenant(),
        "auth_path": str(map_data_path(AUTH_PATH)),
        "config_path": str(map_data_path(CONFIG_PATH)),
        "cookies": {
            "tenant": request.cookies.get(SAAS_TENANT_COOKIE),
            "session": request.cookies.get(SESSION_COOKIE),
        },
    }
@router.get("/api/school-news")
def get_public_school_news(limit: int = Query(default=3, ge=1, le=30)) -> dict[str, Any]:
    rows = [item for item in load_school_news() if item.get("is_active", True)]
    return {"items": rows[:limit]}


@router.get("/api/school-news/{news_id}")
def get_public_school_news_item(news_id: str) -> dict[str, Any]:
    nid = str(news_id or "").strip()
    row = next(
        (
            item
            for item in load_school_news()
            if str(item.get("id") or "") == nid and item.get("is_active", True)
        ),
        None,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Новость не найдена.")
    return {"item": row}


@router.get("/school-news/{news_id}", response_class=HTMLResponse)
def school_news_page(news_id: str) -> HTMLResponse:
    nid = str(news_id or "").strip()
    row = next((item for item in load_school_news() if str(item.get("id") or "") == nid and item.get("is_active", True)), None)
    if not row:
        return HTMLResponse("<h1>Новость не найдена</h1>", status_code=404)
    title = html.escape(str(row.get("title") or "Новость"))
    content = str(row.get("content") or "")
    # Делает ссылки кликабельными/безопаснее в выдаче страницы новости.
    # (TinyMCE сам генерит <a>, но target/rel полезны на телефонах.)
    try:
        content = re.sub(
            r'(?is)<a\s+(?![^>]*\btarget=)([^>]*href\s*=\s*["\'][^"\']+["\'][^>]*)>',
            r'<a target="_blank" rel="noopener" \1>',
            content,
        )
    except Exception:
        pass
    cover = str(row.get("cover_image") or "").strip()
    cover_html = f'<img src="{html.escape(cover)}" alt="" style="max-width:100%;border-radius:14px;margin:0 0 16px;">' if cover else ""
    gal_raw = row.get("gallery_images") or []
    gallery_urls = [str(u).strip() for u in gal_raw if isinstance(u, str) and str(u).strip()][:4]
    gallery_html = ""
    if gallery_urls:
        cells = "".join(
            f'<div style="flex:1 1 45%;min-width:140px"><img src="{html.escape(u)}" alt="" style="width:100%;border-radius:12px;object-fit:contain"></div>'
            for u in gallery_urls
        )
        gallery_html = f'<div class="news-gallery" style="display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px">{cells}</div>'
    dt = html.escape(str(row.get("created_at") or ""))
    body = (
        "<!doctype html><html lang=\"ru\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{title}</title><style>body{{margin:0;background:#0b1220;color:#e2e8f0;font:16px/1.5 Arial,sans-serif}}main{{max-width:900px;margin:0 auto;padding:20px}}h1{{margin:0 0 8px}}.meta{{opacity:.8;margin:0 0 12px}}a{{color:#38bdf8}}a:visited{{color:#60a5fa}}</style></head>"
        f"<body><main><h1>{title}</h1><p class=\"meta\">{dt}</p>{cover_html}{gallery_html}<article>{content}</article></main></body></html>"
    )
    return HTMLResponse(body)
