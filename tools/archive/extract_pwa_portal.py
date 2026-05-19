"""One-off: extract PWA + portal web blocks from app.py into _pg modules."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
app_path = ROOT / "guardschool" / "app.py"
lines = app_path.read_text(encoding="utf-8").splitlines(keepends=True)


def slice_lines(start: int, end: int) -> str:
    return "".join(lines[start - 1 : end])


def build_pwa_pg() -> None:
    pwa_chunks = [
        (2873, 3002),
        (3005, 3027),
        (5255, 6020),
        (6023, 6040),
    ]
    pwa_body = ""
    for s, e in pwa_chunks:
        pwa_body += slice_lines(s, e) + "\n"
    pwa_body = pwa_body.replace("@app.get(", "@router.get(")
    pwa_body = pwa_body.replace("@app.post(", "@router.post(")
    pwa_body += """
screen_html_manifest_link = _pwa_screen_html_manifest_link
tv_pair_html_manifest_link = _pwa_tv_pair_html_manifest_link
apply_saas_screen_tenant_from_request = _apply_saas_screen_tenant_from_request
tv_access_lookup_row = _tv_access_lookup_row
"""
    header = '''"""PWA webmanifest routes and helpers (SaaS tv-pair + local /pwa/screen)."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .gs_admin_http import session_cookie_secure
from .gs_deploy import deployment_mode
from .gs_paths import APP_VERSION, SAAS_TENANT_COOKIE, UPLOADS_DIR, WIDGET_IMAGES_SUBDIR
from .gs_tv_screen_api import (
    canonical_tv_school_code as _canonical_tv_school_code,
    encode_saas_tenant_cookie_value as _encode_saas_tenant_cookie_value,
    normalize_screen_slug_for_api as _normalize_screen_slug_for_api,
    normalize_tv_pair_text as _normalize_tv_pair_text,
    screen_api_tenant_slug as _screen_api_tenant_slug,
    tv_path_code_segment as _tv_path_code_segment,
    tv_school_code_compact as _tv_school_code_compact,
)
from .saas_db import connect_public, saas_db_enabled, tv_code_hash, tv_device_token_hash, utcnow
from .tenant_ctx import set_tenant_slug

_log = logging.getLogger(__name__)
router = APIRouter(tags=["pwa-manifest"])


def register_routes(app: FastAPI) -> None:
    app.include_router(router)


def load_config() -> dict[str, Any]:
    from .gs_jsonio import read_json
    from .gs_paths import CONFIG_PATH

    return read_json(CONFIG_PATH, default={})


'''
    out = ROOT / "guardschool" / "_app_pwa_manifest_pg.py"
    out.write_text(header + pwa_body, encoding="utf-8")
    print("Wrote", out, "lines", (header + pwa_body).count("\n"))


def build_portal_pg() -> None:
    portal_chunks = [(3090, 3093), (3174, 3290)]
    portal_body = ""
    for s, e in portal_chunks:
        portal_body += slice_lines(s, e) + "\n"
    portal_body = portal_body.replace("@app.get(", "@router.get(")
    portal_body = portal_body.replace("@app.post(", "@router.post(")
    header = '''"""Portal web pages: register, ADM, about, portal-adm API (guarddoc.ru)."""
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


'''
    out = ROOT / "guardschool" / "_app_portal_web_pg.py"
    out.write_text(header + portal_body, encoding="utf-8")
    print("Wrote", out, "lines", (header + portal_body).count("\n"))


if __name__ == "__main__":
    build_pwa_pg()
    build_portal_pg()
