"""Extract TV routes + helpers from app.py into _routes_tv_pg.py and gs_tv_pair.py."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
app_path = ROOT / "guardschool" / "app.py"
lines = app_path.read_text(encoding="utf-8").splitlines(keepends=True)


def slice_lines(start: int, end: int) -> str:
    return "".join(lines[start - 1 : end])


def build_routes_tv_pg() -> None:
    route_body = slice_lines(4993, 5382)
    route_body = route_body.replace("@app.get(", "@router.get(")
    route_body = route_body.replace("@app.post(", "@router.post(")
    header = '''"""SaaS TV pairing: /t/{code}/{slug}, POST /api/tv/pair, admin tv-access."""
from __future__ import annotations

import html
import hmac
import json
import logging
import os
import re
import secrets
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from .app_screen_html import render_screen_html_page
from .app_pwa_manifest import tv_access_lookup_row
from .capabilities import CAP_REMOTE_TV_PAIRING
from .gs_admin_http import session_cookie_secure
from .gs_auth import require_auth
from .gs_capability_http import require_capability
from .gs_deploy import deployment_mode
from .gs_paths import CONFIG_PATH, SAAS_TENANT_COOKIE, STATIC_DIR
from .gs_jsonio import read_json, write_json
from .gs_tv_screen_api import (
    canonical_tv_school_code as _canonical_tv_school_code,
    encode_saas_tenant_cookie_value as _encode_saas_tenant_cookie_value,
    normalize_screen_slug_for_api as _normalize_screen_slug_for_api,
    normalize_tv_pair_text as _normalize_tv_pair_text,
    tv_path_code_segment as _tv_path_code_segment,
    tv_pwa_screen_url as _tv_pwa_screen_url,
)
from .gs_tv_pair import (
    generate_tv_code,
    normalize_tv_pair_pin,
    tv_pair_check_rate_limit,
    tv_pair_client_key,
    tv_pair_gate_notice_html,
    tv_pair_pin_bypass_effective,
    tv_pair_pin_bypass_env,
    tv_pair_pin_entry_file_response,
    tv_pair_record_failure,
    tv_pair_record_success,
    tv_token_active_tenant,
)
from .saas_db import connect_public, saas_db_enabled, tv_code_hash, tv_device_token_hash, tv_pin_hash

_log = logging.getLogger(__name__)
router = APIRouter(tags=["tv-pair"])


def register_routes(app) -> None:
    app.include_router(router)


def load_config() -> dict[str, Any]:
    return read_json(CONFIG_PATH, default={})


def _sanitize_config(config: dict[str, Any]) -> dict[str, Any]:
    from guardschool import app as app_mod

    return app_mod.sanitize_config(config)


def _maybe_push_screen_content_if_data_revision_changed(request: Request) -> None:
    from guardschool import app as app_mod

    app_mod._maybe_push_screen_content_if_data_revision_changed(request)


'''
    out = ROOT / "guardschool" / "_routes_tv_pg.py"
    out.write_text(header + route_body, encoding="utf-8")
    print("Wrote", out)


def build_gs_tv_pair() -> None:
    chunks = [
        (297, 330),  # constants + pin bypass (without TV_PAIR_ATTEMPT if we include 297-301)
        (1112, 1161),
        (4614, 4622),
        (4969, 4986),
    ]
    # Also need tv_token from pwa - read from pwa file lines 84-127 approx
    body = ""
    for s, e in chunks:
        body += slice_lines(s, e)
    # Rename functions to public names without leading underscore for exported API
    renames = [
        ("_tv_pair_pin_bypass_env", "tv_pair_pin_bypass_env"),
        ("_tv_pair_pin_bypass_from_tenant_config", "tv_pair_pin_bypass_from_tenant_config"),
        ("_tv_pair_pin_bypass_effective", "tv_pair_pin_bypass_effective"),
        ("_normalize_tv_pair_pin", "normalize_tv_pair_pin"),
        ("_tv_pair_client_key", "tv_pair_client_key"),
        ("_tv_pair_prune_attempts", "tv_pair_prune_attempts"),
        ("_tv_pair_check_rate_limit", "tv_pair_check_rate_limit"),
        ("_tv_pair_record_failure", "tv_pair_record_failure"),
        ("_tv_pair_record_success", "tv_pair_record_success"),
        ("_generate_tv_code", "generate_tv_code"),
        ("_tv_pair_pin_entry_file_response", "tv_pair_pin_entry_file_response"),
        ("_tv_pair_gate_notice_html", "tv_pair_gate_notice_html"),
    ]
    for old, new in renames:
        body = body.replace(old, new)

    pwa_tv = (ROOT / "guardschool" / "_app_pwa_manifest_pg.py").read_text(encoding="utf-8")
    # Extract _tv_code_plaintext and _tv_token_active_tenant from pwa file
    import re as re_mod

    m1 = re_mod.search(
        r"def _tv_code_plaintext_for_tenant.*?^def ",
        pwa_tv,
        re_mod.MULTILINE | re_mod.DOTALL,
    )
    m2 = re_mod.search(
        r"def _tv_token_active_tenant.*?^def ",
        pwa_tv,
        re_mod.MULTILINE | re_mod.DOTALL,
    )
    extra = ""
    if m1:
        extra += m1.group(0).rsplit("def ", 1)[0]
    if m2:
        extra += m2.group(0).rsplit("def ", 1)[0]
    extra = extra.replace("_tv_code_plaintext_for_tenant", "tv_code_plaintext_for_tenant")
    extra = extra.replace("_tv_token_active_tenant", "tv_token_active_tenant")

    header = '''"""TV pairing helpers (rate limit, PIN bypass, device tokens). Open-core."""
from __future__ import annotations

import html
import logging
import os
import secrets
import time
from typing import Any

from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse

from .gs_deploy import deployment_mode
from .gs_paths import STATIC_DIR
from .gs_tv_screen_api import normalize_tv_pair_text as _normalize_tv_pair_text
from .saas_db import connect_public, saas_db_enabled, tv_device_token_hash, utcnow

_log = logging.getLogger(__name__)

TV_PAIR_ATTEMPT_WINDOW_SEC = 5 * 60
TV_PAIR_ATTEMPT_LIMIT = 8
TV_PAIR_BLOCK_SEC = 10
_TV_PAIR_ATTEMPTS: dict[str, list[float]] = {}
_TV_PAIR_BLOCK_UNTIL: dict[str, float] = {}


def load_config() -> dict[str, Any]:
    from .gs_jsonio import read_json
    from .gs_paths import CONFIG_PATH

    return read_json(CONFIG_PATH, default={})


def _pin_digits_to_ascii(raw: str) -> str:
    out: list[str] = []
    for ch in str(raw or ""):
        try:
            d = ord(ch) - ord("0")
        except (TypeError, ValueError):
            continue
        if 0 <= d <= 9:
            out.append(str(int(d)))
    return "".join(out)


'''
    out = ROOT / "guardschool" / "gs_tv_pair.py"
    out.write_text(header + body + extra, encoding="utf-8")
    print("Wrote", out)


if __name__ == "__main__":
    build_gs_tv_pair()
    build_routes_tv_pg()
