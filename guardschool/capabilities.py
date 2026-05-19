"""Единый реестр доступности функций (capabilities) для UI и API."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from .gs_deploy import deployment_mode

CapabilityProvider = Callable[[dict[str, "CapabilityInfo"]], None]


class CapabilityStatus(str, Enum):
    available = "available"
    missing = "missing"
    disabled = "disabled"
    locked = "locked"
    unavailable = "unavailable"
    error = "error"


# --- Capability ids ---
# SaaS / online
CAP_MOBILE_EXTERNAL = "mobile_external"
CAP_PUSH_NOTIFICATIONS = "push_notifications"
CAP_CLOUD_SYNC = "cloud_sync"
CAP_TENANT_FEEDBACK = "tenant_feedback"
CAP_REMOTE_TV_PAIRING = "remote_tv_pairing"
CAP_CLOUD_STATUS = "cloud_status"

# Commercial / platform
CAP_LICENSE_CHECK = "license_check"
CAP_REGISTRATION = "registration"
CAP_PAYMENT = "payment"
CAP_TENANT_PROVISIONING = "tenant_provisioning"
CAP_TARIFF_LIMITS = "tariff_limits"
CAP_PRODUCTION_PORTAL = "production_portal"

# Core / local
CAP_LOCAL_WIDGETS = "local_widgets"
CAP_CUSTOM_WIDGETS = "custom_widgets"

ALL_CAPABILITY_IDS: tuple[str, ...] = (
    CAP_MOBILE_EXTERNAL,
    CAP_PUSH_NOTIFICATIONS,
    CAP_CLOUD_SYNC,
    CAP_TENANT_FEEDBACK,
    CAP_REMOTE_TV_PAIRING,
    CAP_CLOUD_STATUS,
    CAP_LICENSE_CHECK,
    CAP_REGISTRATION,
    CAP_PAYMENT,
    CAP_TENANT_PROVISIONING,
    CAP_TARIFF_LIMITS,
    CAP_PRODUCTION_PORTAL,
    CAP_LOCAL_WIDGETS,
    CAP_CUSTOM_WIDGETS,
)

SAAS_CAPABILITY_IDS: frozenset[str] = frozenset(
    {
        CAP_MOBILE_EXTERNAL,
        CAP_PUSH_NOTIFICATIONS,
        CAP_CLOUD_SYNC,
        CAP_TENANT_FEEDBACK,
        CAP_REMOTE_TV_PAIRING,
        CAP_CLOUD_STATUS,
    }
)

COMMERCIAL_CAPABILITY_IDS: frozenset[str] = frozenset(
    {
        CAP_LICENSE_CHECK,
        CAP_REGISTRATION,
        CAP_PAYMENT,
        CAP_TENANT_PROVISIONING,
        CAP_TARIFF_LIMITS,
        CAP_PRODUCTION_PORTAL,
    }
)

CORE_CAPABILITY_IDS: frozenset[str] = frozenset({CAP_LOCAL_WIDGETS, CAP_CUSTOM_WIDGETS})


@dataclass
class CapabilityInfo:
    status: CapabilityStatus
    message: str = ""
    module_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "message": self.message,
            "module_hint": self.module_hint,
        }


_registry: dict[str, CapabilityInfo] = {}
_providers: list[CapabilityProvider] = []
_layers_loaded: bool = False


def _default_core_capabilities() -> dict[str, CapabilityInfo]:
    out: dict[str, CapabilityInfo] = {}
    for cap_id in SAAS_CAPABILITY_IDS:
        out[cap_id] = CapabilityInfo(
            status=CapabilityStatus.missing,
            message=_explain_status(CapabilityStatus.missing, cap_id),
            module_hint="saas",
        )
    for cap_id in COMMERCIAL_CAPABILITY_IDS:
        out[cap_id] = CapabilityInfo(
            status=CapabilityStatus.missing,
            message=_explain_status(CapabilityStatus.missing, cap_id),
            module_hint="commercial",
        )
    mode = deployment_mode()
    out[CAP_LOCAL_WIDGETS] = CapabilityInfo(
        status=CapabilityStatus.available,
        message=_explain_status(CapabilityStatus.available, CAP_LOCAL_WIDGETS),
    )
    if mode == "local":
        out[CAP_CUSTOM_WIDGETS] = CapabilityInfo(
            status=CapabilityStatus.available,
            message=_explain_status(CapabilityStatus.available, CAP_CUSTOM_WIDGETS),
        )
    else:
        out[CAP_CUSTOM_WIDGETS] = CapabilityInfo(
            status=CapabilityStatus.unavailable,
            message="Сторонние виджеты доступны только в локальной (self-hosted) установке.",
            module_hint="local",
        )
    return out


def _explain_status(status: CapabilityStatus, cap_id: str) -> str:
    if status == CapabilityStatus.available:
        return "Функция доступна."
    if status == CapabilityStatus.missing:
        if cap_id in SAAS_CAPABILITY_IDS:
            return (
                "Функция недоступна в текущей сборке. Для работы требуется SaaS/Online слой, "
                "так как модуль использует удалённый доступ, синхронизацию или уведомления вне локальной сети."
            )
        if cap_id in COMMERCIAL_CAPABILITY_IDS:
            return "Модуль лицензирования и коммерческих функций отсутствует в текущей сборке."
        return "Модуль отсутствует в текущей сборке."
    if status == CapabilityStatus.disabled:
        return "Функция отключена настройкой."
    if status == CapabilityStatus.locked:
        return "Модуль установлен, но недоступен в текущей редакции."
    if status == CapabilityStatus.unavailable:
        if cap_id in SAAS_CAPABILITY_IDS:
            return (
                "Функция недоступна в текущей сборке. Для работы требуется SaaS/Online слой, "
                "так как модуль использует удалённый доступ, синхронизацию или уведомления вне локальной сети."
            )
        return "Функция недоступна в текущих условиях (нет подключения или конфигурации)."
    if status == CapabilityStatus.error:
        return "Модуль найден, но не удалось загрузить."
    return ""


def explain_capability_status(name: str) -> str:
    info = get_capabilities().get(name)
    if info is None:
        return "Неизвестная функция."
    if info.message:
        return info.message
    return _explain_status(info.status, name)


def register_capability_provider(provider: CapabilityProvider) -> None:
    _providers.append(provider)


def set_capability(cap_id: str, status: CapabilityStatus, *, message: str = "", module_hint: str = "") -> None:
    if cap_id not in ALL_CAPABILITY_IDS:
        return
    msg = message or _explain_status(status, cap_id)
    _registry[cap_id] = CapabilityInfo(status=status, message=msg, module_hint=module_hint)


def _apply_config_provider(registry: dict[str, CapabilityInfo]) -> None:
    disabled_raw = (os.environ.get("GUARDSCHOOL_DISABLED_CAPABILITIES") or "").strip()
    if not disabled_raw:
        return
    for part in disabled_raw.split(","):
        cap_id = part.strip()
        if cap_id in registry:
            registry[cap_id] = CapabilityInfo(
                status=CapabilityStatus.disabled,
                message=_explain_status(CapabilityStatus.disabled, cap_id),
            )


def _ensure_builtin_providers() -> None:
    if getattr(_ensure_builtin_providers, "_done", False):
        return
    from .capability_bootstrap import register_embedded_capabilities
    from .license_capability_provider import register_license_capabilities

    register_capability_provider(register_embedded_capabilities)
    register_capability_provider(register_license_capabilities)
    _ensure_builtin_providers._done = True  # type: ignore[attr-defined]


def _rebuild_registry() -> None:
    global _registry, _layers_loaded
    _ensure_builtin_providers()
    _registry = _default_core_capabilities()
    _apply_config_provider(_registry)
    for provider in _providers:
        try:
            provider(_registry)
        except Exception:
            pass
    _layers_loaded = True


def ensure_capabilities_initialized() -> None:
    if not _layers_loaded:
        from .layer_loader import load_optional_layers

        load_optional_layers()
        _rebuild_registry()


def get_capabilities() -> dict[str, CapabilityInfo]:
    ensure_capabilities_initialized()
    out = dict(_registry)
    try:
        from .license_capability_provider import apply_plan_for_request_context

        apply_plan_for_request_context(out)
    except Exception:
        pass
    return out


def get_capabilities_public() -> dict[str, dict[str, Any]]:
    return {k: v.to_dict() for k, v in get_capabilities().items()}


def has_capability(name: str) -> bool:
    info = get_capabilities().get(name)
    return info is not None and info.status == CapabilityStatus.available


def reset_capabilities_for_tests() -> None:
    """Сброс состояния (только для тестов)."""
    global _registry, _layers_loaded, _providers
    _registry = {}
    _providers = []
    _layers_loaded = False
    if hasattr(_ensure_builtin_providers, "_done"):
        _ensure_builtin_providers._done = False  # type: ignore[attr-defined]
