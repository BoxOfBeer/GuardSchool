"""TV/screen API: slug, доступ Bearer/device-token, tenant context, PWA URLs."""
from __future__ import annotations

import base64
import hmac
import os
import re
import unicodedata
from typing import Any
from urllib.parse import quote

from fastapi import HTTPException, Request

from .gs_deploy import deployment_mode
from .gs_paths import SAAS_TENANT_COOKIE
from .saas_db import connect_public, ensure_tenant_schema, saas_db_enabled, schema_name_for_slug, tv_device_token_hash, utcnow

_TV_PAIR_ZW_RE = re.compile(r"[\u200b-\u200d\ufeff]")
_TV_SCHOOL_CODE_TRIPLET = re.compile(r"^[a-z2-9]{4}-[a-z2-9]{4}-[a-z2-9]{4}$")
_TV_SCHOOL_CODE_TRIPLET_LOOSE = re.compile(r"^[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}$")


def normalize_tv_pair_text(s: str) -> str:
    """NFKC + убрать ZWSP/BOM: на ТВ часто приходят полноширинные цифры и невидимые символы."""
    t = unicodedata.normalize("NFKC", str(s or ""))
    t = _TV_PAIR_ZW_RE.sub("", t).strip()
    for bad, good in (
        ("\u2010", "-"),
        ("\u2011", "-"),
        ("\u2012", "-"),
        ("\u2013", "-"),
        ("\u2014", "-"),
        ("\u2015", "-"),
        ("\u2212", "-"),
        ("\uff0d", "-"),
    ):
        t = t.replace(bad, good)
    return t


def tv_school_code_compact(s: str) -> str:
    t = normalize_tv_pair_text(str(s or "")).lower()
    return re.sub(r"[^a-z0-9]", "", t)


def tv_path_code_segment(raw: str) -> str:
    return str(raw or "").strip().strip("/.").strip()


def normalize_screen_slug_for_api(slug: str) -> str:
    return normalize_tv_pair_text(str(slug or "")).strip().lower()


def canonical_tv_school_code(normalized_lower: str) -> str | None:
    s = (normalized_lower or "").strip()
    if _TV_SCHOOL_CODE_TRIPLET.fullmatch(s):
        return s
    letters = tv_school_code_compact(s)
    if len(letters) != 12:
        return None
    cand = f"{letters[:4]}-{letters[4:8]}-{letters[8:12]}"
    if _TV_SCHOOL_CODE_TRIPLET.fullmatch(cand):
        return cand
    if _TV_SCHOOL_CODE_TRIPLET_LOOSE.fullmatch(cand):
        return cand
    return None


def encode_saas_tenant_cookie_value(slug: str) -> str:
    raw = (slug or "").strip().lower()
    b64 = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")
    return f"b64.{b64}"


def decode_saas_tenant_cookie_value(value: str) -> str | None:
    v = (value or "").strip()
    if not v:
        return None
    vv = v.strip()
    if vv.lower().startswith("b64."):
        vv = vv[4:]
        try:
            padded = vv + "=" * ((4 - (len(vv) % 4)) % 4)
            decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8").strip().lower()
            return decoded or None
        except Exception:
            return None
    vv_low = vv.lower()
    if all(ch.isalnum() or ch == "-" for ch in vv_low):
        return vv_low
    return None


def screen_api_tenant_slug(request: Request) -> str:
    try:
        from .tenant_ctx import tenant_slug as _tg

        ctx = str(_tg() or "").strip()
        if ctx:
            return ctx
    except Exception:
        pass
    ck = decode_saas_tenant_cookie_value(request.cookies.get(SAAS_TENANT_COOKIE) or "")
    if ck:
        return ck
    return "local"


def require_tv_access_for_screen(request: Request, screen_slug: str) -> None:
    auth = (request.headers.get("authorization") or "").strip()
    got = auth[7:].strip() if auth.startswith("Bearer ") else ""
    expected = (os.environ.get("GUARDSCHOOL_TV_BEARER_TOKEN") or "").strip()

    if expected:
        if not got:
            raise HTTPException(status_code=401, detail="Требуется токен ТВ (Bearer).")
        if hmac.compare_digest(got, expected):
            return

    if deployment_mode() == "saas" and saas_db_enabled() and got:
        from .tenant_ctx import set_tenant_slug

        th = tv_device_token_hash(got)
        now = utcnow()
        with connect_public() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tenant_slug, status, expires_at FROM tv_devices
                    WHERE token_hash=%s AND lower(trim(screen_slug)) = %s
                    """,
                    (th, screen_slug),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=403, detail="Неверный токен ТВ.")
                tenant_from_device, status, expires_at = row[0], row[1], row[2]
                if status != "active":
                    raise HTTPException(status_code=403, detail="Токен ТВ отключён.")
                if expires_at is not None and expires_at <= now:
                    raise HTTPException(status_code=403, detail="Токен ТВ истёк.")
                cur.execute(
                    "UPDATE tv_devices SET last_seen_at=now() WHERE token_hash=%s AND lower(trim(screen_slug)) = %s",
                    (th, screen_slug),
                )
            conn.commit()
        slug = str(tenant_from_device or "").strip()
        if not slug:
            raise HTTPException(status_code=403, detail="Неверный токен ТВ.")
        set_tenant_slug(slug)
        try:
            ensure_tenant_schema(schema_name_for_slug(slug))
        except Exception:
            pass
        return

    if expected:
        raise HTTPException(status_code=401, detail="Требуется токен ТВ (Bearer).")


def tv_pwa_screen_url(code_canon: str, screen_slug: str, token: str = "", *, pwa: bool = False) -> str:
    code_q = quote(str(code_canon or "").strip(), safe="")
    slug_q = quote(str(screen_slug or "").strip().lower(), safe="")
    q_parts: list[str] = []
    tok_s = str(token or "").strip()
    if tok_s:
        q_parts.append(f"gs_tv_token={quote(tok_s, safe='')}")
    if pwa:
        q_parts.append("pwa=1")
    q = ("?" + "&".join(q_parts)) if q_parts else ""
    return f"/t/{code_q}/{slug_q}{q}"


def require_optional_tv_bearer(request: Request) -> None:
    """Если задан GUARDSCHOOL_TV_BEARER_TOKEN — /api/screen требует Authorization: Bearer …"""
    tok = (os.environ.get("GUARDSCHOOL_TV_BEARER_TOKEN") or "").strip()
    if not tok:
        return
    auth = request.headers.get("authorization") or ""
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Требуется токен ТВ (Bearer).")
    got = auth[7:].strip()
    if not hmac.compare_digest(got, tok):
        raise HTTPException(status_code=403, detail="Неверный токен ТВ.")


def find_active_screen(slug: str) -> dict[str, Any] | None:
    """Активный экран из config по slug (ленивый load_config — без цикла при импорте app)."""
    slug_key = normalize_screen_slug_for_api(slug)
    if not slug_key:
        return None
    from .gs_app_config import load_config

    config = load_config()
    return next(
        (
            item
            for item in (config.get("screens") or [])
            if normalize_screen_slug_for_api(str(item.get("slug") or "")) == slug_key
            and item.get("is_active", True)
        ),
        None,
    )
