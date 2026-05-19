"""HTML-страница экрана ТВ (/screen, /t/…): manifest link + cookie тенанта в SaaS."""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse

from .app_pwa_manifest import (
    apply_saas_screen_tenant_from_request,
    screen_html_manifest_link,
    tv_pair_html_manifest_link,
)
from .gs_deploy import deployment_mode
from .gs_paths import APP_VERSION, SAAS_TENANT_COOKIE, STATIC_DIR
from .gs_tv_screen_api import (
    encode_saas_tenant_cookie_value,
    normalize_screen_slug_for_api,
)


def render_screen_html_page(
    request: Request,
    slug: str,
    *,
    tv_code_for_manifest: str | None = None,
) -> HTMLResponse:
    apply_saas_screen_tenant_from_request(request, slug)
    raw = (STATIC_DIR / "screen.html").read_text(encoding="utf-8")
    slug_for_manifest = normalize_screen_slug_for_api(slug) or str(slug or "").strip().lower()
    if tv_code_for_manifest:
        manifest_line = tv_pair_html_manifest_link(request, tv_code_for_manifest, slug_for_manifest)
    else:
        manifest_line = screen_html_manifest_link(request, slug_for_manifest)
    html = raw.replace("__GS_ASSETS_VER__", APP_VERSION).replace("__GS_PWA_MANIFEST_LINK__", manifest_line)
    resp = HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )
    if deployment_mode() == "saas":
        try:
            from .tenant_ctx import tenant_slug as _tenant_slug

            ts2 = str(_tenant_slug() or "").strip()
            if ts2 and 1 <= len(ts2) <= 64 and ts2 not in ("www", "admin"):
                sec = getattr(request.url, "scheme", "") == "https"
                resp.set_cookie(
                    SAAS_TENANT_COOKIE,
                    encode_saas_tenant_cookie_value(ts2),
                    max_age=3600 * 24 * 30,
                    httponly=True,
                    samesite="lax",
                    secure=sec,
                    path="/",
                )
        except Exception:
            pass
    return resp
