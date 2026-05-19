"""Community stub: изолированные демо-тенанты недоступны."""
from __future__ import annotations

import hashlib
import os
import re
import secrets


def demo_token_hash(token: str) -> str:
    pepper = (os.environ.get("GUARDSCHOOL_DEMO_PEPPER") or os.environ.get("GUARDSCHOOL_LICENSE_PEPPER") or "").encode(
        "utf-8"
    )
    raw = (token or "").strip().encode("utf-8")
    return hashlib.sha256(pepper + b"\n" + raw).hexdigest()


def new_demo_isolated_slug() -> str:
    return "d" + secrets.token_hex(12)


def is_demo_isolated_slug(s: str) -> bool:
    return bool(re.fullmatch(r"d[0-9a-f]{24}", (s or "").strip().lower()))


def rmtree_tenant_data_disk(slug: str) -> None:
    return


def purge_isolated_demo_copy(iso_slug: str) -> None:
    return


def provision_demo_isolated_snapshot(template_slug: str, isolated_slug: str) -> None:
    raise RuntimeError("Demo provisioning is not available (community edition)")


def tenant_ui_host_for_demo(tenant_slug: str) -> str:
    fixed = (os.environ.get("GUARDSCHOOL_PUBLIC_SCHOOL_HOST") or "").strip().lower()
    if fixed:
        return fixed
    return f"{tenant_slug}.guarddoc.ru"


def saas_tenant_slug_cookie_ok(slug: str) -> bool:
    s = (slug or "").strip().lower()
    if not s or len(s) > 48:
        return False
    if s in ("www", "admin"):
        return False
    return all(ch.isalnum() or ch == "-" for ch in s)


def school_entry_url() -> str:
    scheme = (os.environ.get("GUARDSCHOOL_PUBLIC_SCHOOL_SCHEME") or "https").strip().lower().rstrip("/") or "https"
    host = (os.environ.get("GUARDSCHOOL_PUBLIC_SCHOOL_HOST") or "").strip().lower().split(":")[0] or "school.guarddoc.ru"
    return f"{scheme}://{host}/"
