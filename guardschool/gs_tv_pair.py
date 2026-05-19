"""TV pairing helpers: rate limit, PIN bypass, device-token lookup. Open-core."""
from __future__ import annotations

import html
import logging
import os
import secrets
import time
import unicodedata
from typing import Any

from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse

from .gs_deploy import deployment_mode
from .gs_paths import STATIC_DIR
from .gs_tv_screen_api import normalize_tv_pair_text
from .saas_db import connect_public, saas_db_enabled, tv_device_token_hash, utcnow

_log = logging.getLogger(__name__)

TV_PAIR_ATTEMPT_WINDOW_SEC = 5 * 60
TV_PAIR_ATTEMPT_LIMIT = 8
TV_PAIR_BLOCK_SEC = 10
_TV_PAIR_ATTEMPTS: dict[str, list[float]] = {}
_TV_PAIR_BLOCK_UNTIL: dict[str, float] = {}


def load_config() -> dict[str, Any]:
    from .gs_app_config import load_config as _load_config

    return _load_config()


def tv_pair_pin_bypass_env() -> bool:
    """Опционально в env: GUARDSCHOOL_TV_PAIR_BYPASS_PIN=1|true|yes|on."""
    v = (os.environ.get("GUARDSCHOOL_TV_PAIR_BYPASS_PIN") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def tv_pair_pin_bypass_from_tenant_config(tenant_slug: str) -> bool:
    ts = (tenant_slug or "").strip()
    if not ts:
        return False
    from .tenant_ctx import set_tenant_slug

    set_tenant_slug(ts)
    try:
        return bool(load_config().get("tv_pair_pin_bypass"))
    finally:
        set_tenant_slug(None)


def tv_pair_pin_bypass_effective(tenant_slug: str, pin_bypass_db: bool = False) -> bool:
    if tv_pair_pin_bypass_env():
        return True
    if pin_bypass_db:
        return True
    return tv_pair_pin_bypass_from_tenant_config(tenant_slug)


def pin_digits_to_ascii(s: str) -> str:
    out: list[str] = []
    for ch in s:
        if "0" <= ch <= "9":
            out.append(ch)
            continue
        if ch.isspace():
            continue
        try:
            d = unicodedata.decimal(ch)
        except (TypeError, ValueError):
            continue
        if 0 <= d <= 9:
            out.append(str(int(d)))
    return "".join(out)


def normalize_tv_pair_pin(raw: str) -> str:
    return pin_digits_to_ascii(normalize_tv_pair_text(str(raw or "")))


def tv_pair_client_key(request: Request, code: str) -> str:
    xff = str(request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    ip = xff or (request.client.host if request.client else "") or "unknown"
    return f"{ip}|{code}"


def _tv_pair_prune_attempts(key: str, now_ts: float) -> list[float]:
    arr = [ts for ts in _TV_PAIR_ATTEMPTS.get(key, []) if now_ts - ts <= TV_PAIR_ATTEMPT_WINDOW_SEC]
    if arr:
        _TV_PAIR_ATTEMPTS[key] = arr
    else:
        _TV_PAIR_ATTEMPTS.pop(key, None)
    return arr


def tv_pair_check_rate_limit(key: str, now_ts: float) -> int:
    blocked_until = _TV_PAIR_BLOCK_UNTIL.get(key, 0.0)
    if blocked_until > now_ts:
        return max(1, int(blocked_until - now_ts))
    _TV_PAIR_BLOCK_UNTIL.pop(key, None)
    attempts = _tv_pair_prune_attempts(key, now_ts)
    if len(attempts) >= TV_PAIR_ATTEMPT_LIMIT:
        _TV_PAIR_BLOCK_UNTIL[key] = now_ts + TV_PAIR_BLOCK_SEC
        return TV_PAIR_BLOCK_SEC
    return 0


def tv_pair_record_failure(key: str, now_ts: float) -> None:
    attempts = _tv_pair_prune_attempts(key, now_ts)
    attempts.append(now_ts)
    _TV_PAIR_ATTEMPTS[key] = attempts
    if len(attempts) >= TV_PAIR_ATTEMPT_LIMIT:
        _TV_PAIR_BLOCK_UNTIL[key] = now_ts + TV_PAIR_BLOCK_SEC


def tv_pair_record_success(key: str) -> None:
    _TV_PAIR_ATTEMPTS.pop(key, None)
    _TV_PAIR_BLOCK_UNTIL.pop(key, None)


def generate_tv_code() -> str:
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    raw = "".join(alphabet[secrets.randbelow(len(alphabet))] for _ in range(12))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:12]}"


def tv_pair_pin_entry_file_response() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "tv_pair.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


def tv_pair_gate_notice_html(*, title: str, message: str, status: int = 404) -> HTMLResponse:
    t = html.escape(title)
    m = html.escape(message, quote=False)
    doc = (
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'/>"
        "<meta http-equiv='Cache-Control' content='no-store'/>"
        f"<title>{t}</title></head>"
        "<body style='margin:0;font-family:system-ui;background:#0f172a;color:#e2e8f0;padding:28px;max-width:560px'>"
        f"<h1 style='font-size:20px;margin:0 0 12px'>{t}</h1>"
        f"<p style='margin:0;line-height:1.5;font-size:16px;color:#cbd5e1'>{m}</p>"
        "</body></html>"
    )
    return HTMLResponse(
        content=doc,
        status_code=status,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache"},
    )


def tv_code_plaintext_for_tenant(tenant_slug: str) -> str:
    if deployment_mode() != "saas" or not saas_db_enabled():
        return ""
    ts = (tenant_slug or "").strip()
    if not ts:
        return ""
    try:
        with connect_public() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT code_plaintext FROM tv_access WHERE tenant_slug=%s", (ts,))
                row = cur.fetchone()
        return str(row[0] or "").strip() if row else ""
    except Exception:
        return ""


def tv_token_active_tenant(tok: str, screen_slug_norm: str) -> str | None:
    if deployment_mode() != "saas" or not saas_db_enabled():
        return None
    tok_s = str(tok or "").strip()
    slug_key = (screen_slug_norm or "").strip().lower()
    if not tok_s or not slug_key:
        return None
    try:
        th = tv_device_token_hash(tok_s)
        now = utcnow()
        with connect_public() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tenant_slug, status, expires_at FROM tv_devices
                    WHERE token_hash=%s AND lower(trim(screen_slug))=%s
                    """,
                    (th, slug_key),
                )
                row = cur.fetchone()
        if not row:
            return None
        tenant_from_device, status, expires_at = row[0], row[1], row[2]
        if status != "active":
            return None
        if expires_at is not None and expires_at <= now:
            return None
        out = str(tenant_from_device or "").strip().lower()
        return out or None
    except Exception:
        return None
