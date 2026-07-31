"""Community stub: публичный CMS JSON; страницы портала — 404 вне guarddoc.ru."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .app_host_routing import is_guarddoc_portal as _is_guarddoc_portal
from .gs_portal_cms import load_portal_cms_merged

router = APIRouter(tags=["portal-web"])


def register_routes(app: FastAPI) -> None:
    app.include_router(router)


@router.get("/api/portal/cms")
def api_portal_cms_public() -> dict[str, Any]:
    return load_portal_cms_merged()


def _portal_not_found(request: Request) -> None:
    if not _is_guarddoc_portal(request):
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/register")
def portal_register_unavailable(request: Request) -> None:
    _portal_not_found(request)
    raise HTTPException(status_code=503, detail="Registration is not available in this build.")


@router.get("/ADM")
def portal_adm_unavailable(request: Request) -> None:
    _portal_not_found(request)
    raise HTTPException(status_code=503, detail="Portal ADM is not available in this build.")
