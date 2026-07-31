"""SaaS: контекст текущей школы (тенанта) и маппинг путей data/ на tenant-data."""
from __future__ import annotations

import os
from contextvars import ContextVar
from pathlib import Path

from .gs_deploy import deployment_mode

_TENANT_SLUG: ContextVar[str | None] = ContextVar("guardschool_tenant_slug", default=None)


def set_tenant_slug(slug: str | None) -> None:
    _TENANT_SLUG.set((slug or "").strip().lower() or None)


def tenant_slug() -> str | None:
    return _TENANT_SLUG.get()


def _app_dir() -> Path:
    # guardschool/ -> repo root
    return Path(__file__).resolve().parent.parent


def default_data_dir() -> Path:
    raw = (os.environ.get("GUARDSCHOOL_DATA_DIR") or "").strip()
    if raw:
        return Path(raw).resolve()
    return (_app_dir() / "data").resolve()


def tenant_data_root() -> Path:
    raw = (os.environ.get("GUARDSCHOOL_SAAS_DATA_ROOT") or "").strip()
    if raw:
        return Path(raw).resolve()
    return (_app_dir() / "tenants").resolve()


def tenant_data_dir(slug: str) -> Path:
    return tenant_data_root() / slug / "data"


def map_data_path(path: Path) -> Path:
    """
    Если deployment_mode=saas и задан tenant_slug, то все пути внутри default data/
    перенаправляются в tenants/<slug>/data/.
    """
    if deployment_mode() != "saas":
        return path
    slug = tenant_slug()
    if not slug:
        return path
    try:
        base = default_data_dir()
        p = path.resolve()
        if p == base or base in p.parents:
            rel = p.relative_to(base)
            return (tenant_data_dir(slug) / rel).resolve()
    except Exception:
        return path
    return path

