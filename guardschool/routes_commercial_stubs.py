"""Заглушки commercial API — 503 без commercial layer (community local)."""
from __future__ import annotations

from fastapi import APIRouter, Request

from .capabilities import (
    CAP_LICENSE_CHECK,
    CAP_PRODUCTION_PORTAL,
    CAP_REGISTRATION,
    CAP_TENANT_PROVISIONING,
)
from .gs_capability_http import require_capability

router = APIRouter(tags=["commercial-stubs"])


@router.get("/api/provider/licenses")
def stub_provider_list_licenses(request: Request) -> None:
    require_capability(CAP_LICENSE_CHECK)


@router.get("/api/provider/licenses/{key_hash}")
def stub_provider_get_license(key_hash: str, request: Request) -> None:
    require_capability(CAP_LICENSE_CHECK)


@router.post("/api/provider/licenses")
def stub_provider_create_license(request: Request) -> None:
    require_capability(CAP_LICENSE_CHECK)


@router.post("/api/provider/licenses/{key_hash}/status")
def stub_provider_license_status(key_hash: str, request: Request) -> None:
    require_capability(CAP_LICENSE_CHECK)


@router.patch("/api/provider/licenses/{key_hash}")
def stub_provider_patch_license(key_hash: str, request: Request) -> None:
    require_capability(CAP_LICENSE_CHECK)


@router.delete("/api/provider/licenses/{key_hash}")
def stub_provider_delete_license(key_hash: str, request: Request) -> None:
    require_capability(CAP_LICENSE_CHECK)


@router.delete("/api/provider/tenants/{slug}")
def stub_provider_delete_tenant(slug: str, request: Request) -> None:
    require_capability(CAP_TENANT_PROVISIONING)


@router.post("/api/provider/demo")
def stub_provider_demo(request: Request) -> None:
    require_capability(CAP_LICENSE_CHECK)


@router.get("/api/provider/portal-cms")
def stub_provider_portal_cms_get(request: Request) -> None:
    require_capability(CAP_PRODUCTION_PORTAL)


@router.put("/api/provider/portal-cms")
def stub_provider_portal_cms_put(request: Request) -> None:
    require_capability(CAP_PRODUCTION_PORTAL)


@router.post("/api/saas/register")
def stub_saas_register(request: Request) -> None:
    require_capability(CAP_REGISTRATION)
