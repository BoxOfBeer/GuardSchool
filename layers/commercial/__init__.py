"""
Commercial layer (reference skeleton in community repo).

    export GUARDSCHOOL_LAYER_PATH=/path/to/GuardSchool
    # → layers/commercial/__init__.py
"""
from __future__ import annotations

from typing import Any

from guardschool.capabilities import (
    CAP_LICENSE_CHECK,
    CAP_PAYMENT,
    CAP_PRODUCTION_PORTAL,
    CAP_REGISTRATION,
    CAP_TARIFF_LIMITS,
    CAP_TENANT_PROVISIONING,
    CapabilityInfo,
    CapabilityStatus,
    make_capability_info,
)
from guardschool.commercial_routes import mount_commercial_routes
from guardschool.layer_loader import mark_commercial_routes_mounted

_COMMERCIAL_CAPS = (
    CAP_LICENSE_CHECK,
    CAP_REGISTRATION,
    CAP_PAYMENT,
    CAP_TENANT_PROVISIONING,
    CAP_TARIFF_LIMITS,
    CAP_PRODUCTION_PORTAL,
)


def register_capabilities(registry: dict[str, CapabilityInfo]) -> None:
    for cap_id in _COMMERCIAL_CAPS:
        registry[cap_id] = make_capability_info(
            cap_id,
            CapabilityStatus.available,
            message="Функция доступна (Commercial слой).",
            module_hint="commercial",
        )


def register_routes(app: Any) -> None:
    mount_commercial_routes(app)
    mark_commercial_routes_mounted()
