"""
SaaS layer (reference skeleton in community repo).

На сервере: скопируйте каталог в GUARDSCHOOL_LAYER_PATH/layers/saas/
или укажите GUARDSCHOOL_LAYER_PATH на корень репозитория GuardSchool.

    export GUARDSCHOOL_LAYER_PATH=/opt/guardschool
    # → /opt/guardschool/layers/saas/__init__.py
"""
from __future__ import annotations

from typing import Any

from guardschool.capabilities import (
    CAP_CLOUD_STATUS,
    CAP_CLOUD_SYNC,
    CAP_MOBILE_EXTERNAL,
    CAP_PUSH_NOTIFICATIONS,
    CAP_REMOTE_TV_PAIRING,
    CAP_TENANT_FEEDBACK,
    CapabilityInfo,
    CapabilityStatus,
)
from guardschool.layer_loader import mark_saas_routes_mounted
from guardschool.saas_routes import ALL_SAAS_ROUTE_GROUPS, mount_all_saas_routes

_SAAS_CAPS = (
    CAP_MOBILE_EXTERNAL,
    CAP_PUSH_NOTIFICATIONS,
    CAP_CLOUD_SYNC,
    CAP_TENANT_FEEDBACK,
    CAP_REMOTE_TV_PAIRING,
    CAP_CLOUD_STATUS,
)


def register_capabilities(registry: dict[str, CapabilityInfo]) -> None:
    for cap_id in _SAAS_CAPS:
        registry[cap_id] = CapabilityInfo(
            status=CapabilityStatus.available,
            message="Функция доступна (SaaS слой).",
            module_hint="saas",
        )


def register_routes(app: Any) -> None:
    mount_all_saas_routes(app)
    mark_saas_routes_mounted(*ALL_SAAS_ROUTE_GROUPS)
