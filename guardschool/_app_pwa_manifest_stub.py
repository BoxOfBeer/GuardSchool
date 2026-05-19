"""Community stub: PWA manifest для local /pwa/screen; SaaS tv-pair — недоступен."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .gs_deploy import deployment_mode
from .gs_paths import APP_VERSION
from .gs_tv_screen_api import normalize_screen_slug_for_api as _normalize_screen_slug_for_api

router = APIRouter(tags=["pwa-manifest"])


def register_routes(app: FastAPI) -> None:
    app.include_router(router)


def _pwa_screen_html_manifest_link(request: Request, slug_for_manifest: str) -> str:
    slug_key = (slug_for_manifest or "").strip().lower()
    if not slug_key or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", slug_key):
        return ""
    if deployment_mode() == "saas":
        return ""
    q = f"?v={quote(APP_VERSION, safe='')}"
    return f'<link rel="manifest" href="/pwa/screen/{quote(slug_key, safe="")}.webmanifest{q}" />\n'


def _pwa_tv_pair_html_manifest_link(request: Request, code_canon: str, slug_for_manifest: str) -> str:
    return ""


def _apply_saas_screen_tenant_from_request(request: Request, slug: str) -> None:
    return None


def _tv_access_lookup_row(cur: Any, *, code_canon: str) -> tuple[Any, Any, Any, Any] | None:
    return None


@router.get("/pwa/screen/{screen_slug}.webmanifest", response_class=JSONResponse)
def pwa_manifest_for_screen_standalone(request: Request, screen_slug: str) -> JSONResponse:
    if deployment_mode() == "saas":
        raise HTTPException(status_code=404, detail="Not found.")
    slug_n = _normalize_screen_slug_for_api(str(screen_slug or ""))
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", slug_n):
        raise HTTPException(status_code=404, detail="Not found.")
    manifest = {
        "name": "GuardSchool",
        "short_name": "GuardSchool",
        "id": f"/pwa/screen/local/{slug_n}",
        "start_url": f"/screen/{quote(slug_n, safe='')}?pwa=1",
        "scope": "/",
        "display": "standalone",
        "background_color": "#0f172a",
        "theme_color": "#0f172a",
        "icons": [{"src": "/static/pwa/icon_default.png", "sizes": "512x512", "type": "image/png"}],
        "gs_pwa_manifest_version": APP_VERSION,
    }
    return JSONResponse(
        content=manifest,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache"},
    )


screen_html_manifest_link = _pwa_screen_html_manifest_link
tv_pair_html_manifest_link = _pwa_tv_pair_html_manifest_link
apply_saas_screen_tenant_from_request = _apply_saas_screen_tenant_from_request
tv_access_lookup_row = _tv_access_lookup_row
