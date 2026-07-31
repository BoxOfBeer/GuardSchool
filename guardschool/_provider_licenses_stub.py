"""Community stub: лицензии провайдера недоступны."""
from __future__ import annotations

import calendar
import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

LICENSE_LIST_SQL = """
SELECT l.key_hash FROM licenses l LIMIT 0
"""


def license_ts_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def add_calendar_years(dt: datetime, years: int) -> datetime:
    if years <= 0:
        return license_ts_utc(dt)
    d = license_ts_utc(dt)
    y = d.year + years
    mo, da = d.month, d.day
    if mo == 2 and da == 29:
        da = min(da, calendar.monthrange(y, mo)[1])
    try:
        return d.replace(year=y, month=mo, day=da)
    except ValueError:
        return d.replace(year=y, month=2, day=28)


def generate_license_key() -> str:
    return secrets.token_urlsafe(24)[:32]


def license_row_public(
    key_hash: str,
    license_no: Any,
    plan_id: str,
    status: str,
    issued_at: Any,
    expires_at: Any,
    notes: str,
    tenant_slug: str | None,
    owner_user_id: str | None,
    key_plaintext: Any = None,
) -> dict[str, Any]:
    return {
        "key_hash": key_hash,
        "license_no": license_no,
        "plan_id": plan_id,
        "status": status,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "notes": notes,
        "tenant_slug": tenant_slug,
        "owner_user_id": owner_user_id,
        "registered": bool(owner_user_id),
    }


def parse_license_expires_at_raw(raw: Any) -> datetime | None:
    return None


def provider_tenant_slug_param_safe(slug: str) -> str:
    s = (slug or "").strip().lower()
    if not s or not s.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid tenant slug")
    return s[:64]


def provider_purge_license_db_and_disk(key_hash: str) -> dict[str, Any]:
    raise HTTPException(status_code=503, detail="Commercial module not available")


def provider_purge_tenant_by_slug(slug: str) -> dict[str, Any]:
    raise HTTPException(status_code=503, detail="Commercial module not available")
