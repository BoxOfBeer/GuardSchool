"""Демо-сессии провайдера (изолированные копии тенантов)."""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import shutil
from datetime import timedelta
from typing import Any

from .gs_deploy import deployment_mode
from .saas_db import ensure_tenant_schema, schema_name_for_slug, utcnow


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
    if deployment_mode() != "saas":
        return
    try:
        from .tenant_ctx import tenant_data_dir

        root = tenant_data_dir((slug or "").strip().lower())
        if root.is_dir():
            shutil.rmtree(root, ignore_errors=True)
        try:
            tenant_root = root.parent
            if tenant_root.is_dir() and not any(tenant_root.iterdir()):
                tenant_root.rmdir()
        except Exception:
            pass
    except Exception:
        pass


def purge_isolated_demo_copy(iso_slug: str) -> None:
    s = (iso_slug or "").strip().lower()
    if not is_demo_isolated_slug(s):
        return
    try:
        from .saas_db import drop_tenant_schema_if_exists

        drop_tenant_schema_if_exists(s)
    except Exception:
        pass
    rmtree_tenant_data_disk(s)


def provision_demo_isolated_snapshot(template_slug: str, isolated_slug: str) -> None:
    from .tenant_ctx import tenant_data_dir

    tpl = (template_slug or "").strip().lower()
    iso = (isolated_slug or "").strip().lower()
    if not tpl or not iso or not is_demo_isolated_slug(iso):
        raise ValueError("Invalid demo snapshot slugs")
    src = tenant_data_dir(tpl)
    dst = tenant_data_dir(iso)
    if not src.is_dir():
        raise FileNotFoundError(f"Missing tenant data for template {tpl!r}")
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    skip_uploads = (os.environ.get("GUARDSCHOOL_DEMO_SNAPSHOT_SKIP_UPLOADS") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    kw: dict[str, Any] = {"symlinks": False}
    if skip_uploads:
        kw["ignore"] = lambda _src, names: [n for n in names if n == "uploads"]
    shutil.copytree(src, dst, **kw)
    ensure_tenant_schema(schema_name_for_slug(iso))


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
