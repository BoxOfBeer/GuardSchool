"""PWA webmanifest: фасад register_routes и HTML-хелперы для screen.html."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request

from ._private_facade import load_private_backend

_PUBLIC = frozenset(
    {
        "screen_html_manifest_link",
        "tv_pair_html_manifest_link",
        "apply_saas_screen_tenant_from_request",
        "tv_access_lookup_row",
    }
)


def register_pwa_manifest_routes(app: FastAPI) -> None:
    load_private_backend("app_pwa_manifest").register_routes(app)


def screen_html_manifest_link(request: Request, slug_for_manifest: str) -> str:
    return load_private_backend("app_pwa_manifest").screen_html_manifest_link(request, slug_for_manifest)


def tv_pair_html_manifest_link(request: Request, code_canon: str, slug_for_manifest: str) -> str:
    return load_private_backend("app_pwa_manifest").tv_pair_html_manifest_link(
        request, code_canon, slug_for_manifest
    )


def apply_saas_screen_tenant_from_request(request: Request, slug: str) -> None:
    load_private_backend("app_pwa_manifest").apply_saas_screen_tenant_from_request(request, slug)


def tv_access_lookup_row(cur: Any, *, code_canon: str) -> tuple[Any, Any, Any, Any] | None:
    return load_private_backend("app_pwa_manifest").tv_access_lookup_row(cur, code_canon=code_canon)


def __getattr__(name: str) -> Any:
    if name in _PUBLIC:
        return getattr(load_private_backend("app_pwa_manifest"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | _PUBLIC | {"register_pwa_manifest_routes"})
