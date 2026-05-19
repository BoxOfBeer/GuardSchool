"""Extract routes_auth, routes_public, gs_app_config from app.py."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "guardschool" / "app.py"
lines = APP.read_text(encoding="utf-8").splitlines(keepends=True)


def sl(s: int, e: int) -> str:
    return "".join(lines[s - 1 : e])


def auth_public() -> None:
    auth = sl(2996, 3150).replace("@app.", "@router.")
    auth_hdr = '''"""Auth and bootstrap API (/api/setup, login, capabilities). Open-core."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Form, HTTPException, Query, Request, Response

router = APIRouter(tags=["auth"])


def register_auth_routes(app) -> None:
    app.include_router(router)


def _app():
    from guardschool import app as m
    return m


def __getattr__(name: str) -> Any:
    return getattr(_app(), name)


'''
    (ROOT / "guardschool" / "routes_auth.py").write_text(auth_hdr + auth, encoding="utf-8")

    pub = sl(2775, 2797) + sl(3175, 3232)
    pub = pub.replace("@app.", "@router.")
    pub_hdr = '''"""Public read-only API: version, school news."""
from __future__ import annotations

import html
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["public"])


def register_public_routes(app) -> None:
    app.include_router(router)


def _app():
    from guardschool import app as m
    return m


def __getattr__(name: str) -> Any:
    return getattr(_app(), name)


'''
    (ROOT / "guardschool" / "routes_public.py").write_text(pub_hdr + pub, encoding="utf-8")
    print("routes_auth, routes_public OK")


def gs_config() -> None:
    chunks = [
        (330, 578),
        (581, 791),
        (794, 904),
        (930, 955),
        (1095, 1106),
        (1175, 1203),
        (1206, 1468),
    ]
    body = ""
    for s, e in chunks:
        body += sl(s, e) + "\n"
    hdr = '''"""School config.json: load, sanitize, defaults, emergency templates."""
from __future__ import annotations

import copy
import ipaddress
import re
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from .gs_checkin import sanitize_checkin_block
from .gs_jsonio import read_json
from .gs_paths import CONFIG_PATH
from .gs_rss_news import sanitize_rss_refresh_minutes, sanitize_rss_sources
from .gs_uploads_bg import safe_rel_uploads_subdir
from .widget_registry import (
    ADMIN_PALETTE_WIDGET_TYPES,
    GRID_COLS,
    GRID_ROWS,
    SINGLETON_WIDGET_IDS,
    WidgetLoadStatus,
    dedupe_widgets,
    loaded_widget_types,
    normalize_widget,
    widget_status,
)

DEFAULT_BELL_TRIGGER_SEC_WINDOW = 25

'''
    (ROOT / "guardschool" / "gs_app_config.py").write_text(hdr + body, encoding="utf-8")
    print("gs_app_config OK", (hdr + body).count("\\n"))


if __name__ == "__main__":
    auth_public()
    gs_config()
