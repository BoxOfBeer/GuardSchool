"""Community open-core: заглушки SaaS PostgreSQL (без psycopg2 и public schema)."""
from __future__ import annotations

import hashlib
import os
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator


def saas_database_url() -> str:
    return ""


def saas_db_enabled() -> bool:
    return False


@contextmanager
def connect_public() -> Iterator[Any]:
    raise RuntimeError("SaaS database is not available (community / local edition).")


def ensure_public_schema() -> None:
    return


def ensure_tenant_schema(schema_name: str) -> None:
    return


def schema_name_for_slug(slug: str) -> str:
    s = (slug or "").strip().lower()
    s = "".join(ch for ch in s if ch.isalnum() or ch == "_")
    if not s:
        raise ValueError("Invalid tenant slug")
    if s[0].isdigit():
        s = f"t{s}"
    return f"t_{s}"[:48]


def lookup_tenant_plan_id(slug: str) -> str | None:
    return None


def set_search_path(conn: Any, schema_name: str) -> None:
    return


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def random_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(10)}"


def license_key_hash(key: str) -> str:
    pepper = (os.environ.get("GUARDSCHOOL_LICENSE_PEPPER") or "").encode("utf-8")
    raw = (key or "").strip().encode("utf-8")
    return hashlib.sha256(pepper + b"\n" + raw).hexdigest()


def tv_pepper_bytes() -> bytes:
    raw = (os.environ.get("GUARDSCHOOL_TV_PEPPER") or os.environ.get("GUARDSCHOOL_LICENSE_PEPPER") or "").encode(
        "utf-8"
    )
    return raw


def tv_code_hash(code: str) -> str:
    pep = tv_pepper_bytes()
    raw = (code or "").strip().lower().encode("utf-8")
    return hashlib.sha256(pep + b"\ncode\n" + raw).hexdigest()


def tv_pin_hash(pin: str, salt: str) -> str:
    pep = tv_pepper_bytes()
    p = (pin or "").strip().encode("utf-8")
    s = (salt or "").strip().encode("utf-8")
    return hashlib.sha256(pep + b"\npin\n" + s + b"\n" + p).hexdigest()


def tv_device_token_hash(token: str) -> str:
    pep = tv_pepper_bytes()
    raw = (token or "").strip().encode("utf-8")
    return hashlib.sha256(pep + b"\ndevice\n" + raw).hexdigest()


def drop_tenant_schema_if_exists(tenant_slug: str) -> None:
    return


def cleanup_expired_demo_sessions() -> int:
    return 0
