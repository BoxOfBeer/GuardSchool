"""Встроенные возможности при hybrid/saas (до выноса в закрытый слой)."""
from __future__ import annotations

from .capabilities import (
    CAP_CLOUD_STATUS,
    CAP_CLOUD_SYNC,
    CAP_LICENSE_CHECK,
    CAP_MOBILE_EXTERNAL,
    CAP_PAYMENT,
    CAP_PRODUCTION_PORTAL,
    CAP_PUSH_NOTIFICATIONS,
    CAP_REGISTRATION,
    CAP_REMOTE_TV_PAIRING,
    CAP_TARIFF_LIMITS,
    CAP_TENANT_FEEDBACK,
    CAP_TENANT_PROVISIONING,
    CapabilityInfo,
    CapabilityStatus,
    make_capability_info,
)
from .gs_deploy import deployment_mode


def _pkg_has(module_suffix: str) -> bool:
    from .private_modules import module_present

    return module_present(module_suffix)


def register_embedded_capabilities(registry: dict[str, CapabilityInfo]) -> None:
    """
    Пока SaaS/Commercial код в community tree: в hybrid/saas помечаем функции available,
    если соответствующий модуль на месте. В local без слоя — остаётся missing из core.
    """
    mode = deployment_mode()
    if mode == "local":
        return

    def _set_available(cap_id: str) -> None:
        registry[cap_id] = make_capability_info(
            cap_id,
            CapabilityStatus.available,
            message="Функция доступна (встроенный модуль).",
            module_hint="embedded",
        )

    if _pkg_has("gs_push"):
        for cap in (CAP_PUSH_NOTIFICATIONS, CAP_MOBILE_EXTERNAL):
            _set_available(cap)
    if _pkg_has("gs_cloud_sync"):
        for cap in (CAP_CLOUD_SYNC, CAP_CLOUD_STATUS):
            _set_available(cap)
    if _pkg_has("gs_feedback"):
        _set_available(CAP_TENANT_FEEDBACK)
    if _pkg_has("saas_db"):
        for cap in (
            CAP_LICENSE_CHECK,
            CAP_REGISTRATION,
            CAP_TENANT_PROVISIONING,
            CAP_TARIFF_LIMITS,
            CAP_PRODUCTION_PORTAL,
        ):
            _set_available(cap)
    if mode == "saas":
        _set_available(CAP_REMOTE_TV_PAIRING)
        _set_available(CAP_PAYMENT)
