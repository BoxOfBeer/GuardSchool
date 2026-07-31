"""Единый реестр доступности функций (capabilities) для UI и API."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

from .gs_deploy import deployment_mode

if TYPE_CHECKING:
    from fastapi import Request

CapabilityProvider = Callable[[dict[str, "CapabilityInfo"]], None]


class CapabilityStatus(str, Enum):
    available = "available"
    missing = "missing"
    disabled = "disabled"
    locked = "locked"
    unavailable = "unavailable"
    error = "error"


class CapabilityVisibility(str, Enum):
    """Кому показывать capability в UI (не влияет на has_capability / API gates)."""

    school = "school"
    licensor = "licensor"
    internal = "internal"


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

# school: функции, о которых школа должна знать состояние
# licensor: платформа / портал провайдера
DEFAULT_CAPABILITY_VISIBILITY: dict[str, CapabilityVisibility] = {
    CAP_MOBILE_EXTERNAL: CapabilityVisibility.school,
    CAP_PUSH_NOTIFICATIONS: CapabilityVisibility.school,
    CAP_CLOUD_SYNC: CapabilityVisibility.school,
    CAP_TENANT_FEEDBACK: CapabilityVisibility.school,
    CAP_REMOTE_TV_PAIRING: CapabilityVisibility.school,
    CAP_CLOUD_STATUS: CapabilityVisibility.school,
    CAP_LOCAL_WIDGETS: CapabilityVisibility.school,
    CAP_CUSTOM_WIDGETS: CapabilityVisibility.school,
    CAP_LICENSE_CHECK: CapabilityVisibility.licensor,
    CAP_REGISTRATION: CapabilityVisibility.licensor,
    CAP_PAYMENT: CapabilityVisibility.licensor,
    CAP_TENANT_PROVISIONING: CapabilityVisibility.licensor,
    CAP_TARIFF_LIMITS: CapabilityVisibility.licensor,
    CAP_PRODUCTION_PORTAL: CapabilityVisibility.licensor,
}

_AUDIENCE_ALLOWED_VISIBILITY: dict[str, frozenset[CapabilityVisibility]] = {
    "school": frozenset({CapabilityVisibility.school}),
    "licensor": frozenset({CapabilityVisibility.school, CapabilityVisibility.licensor}),
    "internal": frozenset(
        {CapabilityVisibility.school, CapabilityVisibility.licensor, CapabilityVisibility.internal}
    ),
}


def default_capability_visibility(cap_id: str) -> CapabilityVisibility:
    return DEFAULT_CAPABILITY_VISIBILITY.get(cap_id, CapabilityVisibility.internal)


def make_capability_info(
    cap_id: str,
    status: CapabilityStatus,
    *,
    message: str = "",
    module_hint: str = "",
    visibility: CapabilityVisibility | None = None,
) -> CapabilityInfo:
    msg = message or _explain_status(status, cap_id)
    vis = visibility if visibility is not None else default_capability_visibility(cap_id)
    return CapabilityInfo(status=status, message=msg, module_hint=module_hint, visibility=vis)


@dataclass
class CapabilityInfo:
    status: CapabilityStatus
    message: str = ""
    module_hint: str = ""
    visibility: CapabilityVisibility = field(default=CapabilityVisibility.internal)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "message": self.message,
            "module_hint": self.module_hint,
            "visibility": self.visibility.value,
        }


_registry: dict[str, CapabilityInfo] = {}
_providers: list[CapabilityProvider] = []
_layers_loaded: bool = False


def _default_core_capabilities() -> dict[str, CapabilityInfo]:
    out: dict[str, CapabilityInfo] = {}
    for cap_id in SAAS_CAPABILITY_IDS:
        out[cap_id] = make_capability_info(
            cap_id,
            CapabilityStatus.missing,
            message=_explain_status(CapabilityStatus.missing, cap_id),
            module_hint="saas",
        )
    for cap_id in COMMERCIAL_CAPABILITY_IDS:
        out[cap_id] = make_capability_info(
            cap_id,
            CapabilityStatus.missing,
            message=_explain_status(CapabilityStatus.missing, cap_id),
            module_hint="commercial",
        )
    mode = deployment_mode()
    out[CAP_LOCAL_WIDGETS] = make_capability_info(
        CAP_LOCAL_WIDGETS,
        CapabilityStatus.available,
        message=_explain_status(CapabilityStatus.available, CAP_LOCAL_WIDGETS),
    )
    if mode == "local":
        out[CAP_CUSTOM_WIDGETS] = make_capability_info(
            CAP_CUSTOM_WIDGETS,
            CapabilityStatus.available,
            message=_explain_status(CapabilityStatus.available, CAP_CUSTOM_WIDGETS),
        )
    else:
        out[CAP_CUSTOM_WIDGETS] = make_capability_info(
            CAP_CUSTOM_WIDGETS,
            CapabilityStatus.unavailable,
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
    prev_vis = _registry.get(cap_id).visibility if cap_id in _registry else None
    _registry[cap_id] = make_capability_info(
        cap_id,
        status,
        message=message,
        module_hint=module_hint,
        visibility=prev_vis,
    )


def _apply_config_provider(registry: dict[str, CapabilityInfo]) -> None:
    disabled_raw = (os.environ.get("GUARDSCHOOL_DISABLED_CAPABILITIES") or "").strip()
    if not disabled_raw:
        return
    for part in disabled_raw.split(","):
        cap_id = part.strip()
        if cap_id in registry:
            prev = registry[cap_id]
            registry[cap_id] = make_capability_info(
                cap_id,
                CapabilityStatus.disabled,
                message=_explain_status(CapabilityStatus.disabled, cap_id),
                visibility=prev.visibility,
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


def normalize_capabilities_audience(audience: str | None) -> str:
    a = (audience or "school").strip().lower()
    if a not in _AUDIENCE_ALLOWED_VISIBILITY:
        return "school"
    return a


def filter_capabilities_for_audience(
    caps: dict[str, CapabilityInfo],
    audience: str,
) -> dict[str, CapabilityInfo]:
    aud = normalize_capabilities_audience(audience)
    allowed = _AUDIENCE_ALLOWED_VISIBILITY[aud]
    return {k: v for k, v in caps.items() if v.visibility in allowed}


def resolve_capabilities_audience(request: "Request | None" = None) -> str:
    """
    school — админка школы (school.*);
    licensor — портал guarddoc.ru;
    internal — localhost / GUARDSCHOOL_DEV_CAPABILITIES / env override.
    """
    forced = (os.environ.get("GUARDSCHOOL_CAPABILITIES_AUDIENCE") or "").strip().lower()
    if forced in _AUDIENCE_ALLOWED_VISIBILITY:
        return forced
    if request is not None:
        from .app_host_routing import (
            is_guarddoc_portal,
            is_public_school_host,
            portal_request_host,
        )

        if is_guarddoc_portal(request):
            return "licensor"
        host = portal_request_host(request)
        if is_public_school_host(host):
            return "school"
        h = host.split(":")[0].strip().lower()
        if h in ("127.0.0.1", "localhost", "[::1]") or h.startswith("127."):
            return "internal"
    dev = (os.environ.get("GUARDSCHOOL_DEV_CAPABILITIES") or "").strip().lower()
    if dev in ("1", "true", "yes", "on"):
        return "internal"
    return "school"


def get_capabilities_public(
    *,
    audience: str | None = None,
    request: "Request | None" = None,
) -> dict[str, dict[str, Any]]:
    aud = normalize_capabilities_audience(audience or resolve_capabilities_audience(request))
    filtered = filter_capabilities_for_audience(get_capabilities(), aud)
    return {k: v.to_dict() for k, v in filtered.items()}


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
