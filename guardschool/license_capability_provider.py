"""Маппинг plan_id → capabilities (тариф SaaS / лицензия)."""
from __future__ import annotations

import os

from .capabilities import (
    CAP_CLOUD_STATUS,
    CAP_CLOUD_SYNC,
    CAP_MOBILE_EXTERNAL,
    CAP_PAYMENT,
    CAP_PRODUCTION_PORTAL,
    CAP_PUSH_NOTIFICATIONS,
    CAP_REMOTE_TV_PAIRING,
    CAP_REGISTRATION,
    CAP_TARIFF_LIMITS,
    CAP_TENANT_PROVISIONING,
    CAP_LICENSE_CHECK,
    CapabilityInfo,
    CapabilityStatus,
)

# Полный SaaS-набор для школы (без платформенных registration / tenant_provisioning).
_FULL_SCHOOL_PLAN_CAPS = frozenset(
    {
        CAP_CLOUD_SYNC,
        CAP_CLOUD_STATUS,
        CAP_PUSH_NOTIFICATIONS,
        CAP_MOBILE_EXTERNAL,
        CAP_REMOTE_TV_PAIRING,
        CAP_PAYMENT,
        CAP_PRODUCTION_PORTAL,
        CAP_TARIFF_LIMITS,
    }
)

# plan_id → capabilities, которые остаются available (остальные SaaS/commercial → locked)
# public.plans: free | paid (локаль + SaaS) | saas_only (только облачная школа)
_PLAN_ALLOWED: dict[str, frozenset[str]] = {
    "free": frozenset(),
    "paid": _FULL_SCHOOL_PLAN_CAPS,
    "saas_only": _FULL_SCHOOL_PLAN_CAPS,
    "pro": frozenset(
        {
            CAP_CLOUD_SYNC,
            CAP_PUSH_NOTIFICATIONS,
            CAP_MOBILE_EXTERNAL,
            CAP_REMOTE_TV_PAIRING,
        }
    ),
    "enterprise": _FULL_SCHOOL_PLAN_CAPS,
}

_PLAN_ALIASES: dict[str, str] = {
    "full": "paid",
    "starter": "free",
}

_COMMERCIAL_GATED = frozenset(
    {
        CAP_CLOUD_SYNC,
        CAP_PUSH_NOTIFICATIONS,
        CAP_MOBILE_EXTERNAL,
        CAP_REMOTE_TV_PAIRING,
        CAP_CLOUD_STATUS,
        CAP_TENANT_PROVISIONING,
        CAP_PAYMENT,
        CAP_PRODUCTION_PORTAL,
        CAP_TARIFF_LIMITS,
        CAP_REGISTRATION,
    }
)

def _plan_lock_message(plan_norm: str) -> str:
    return f"Модуль установлен, но недоступен в тарифе «{plan_norm}» (полный школьный — paid)."


def normalize_plan_id(plan: str | None) -> str | None:
    if not plan:
        return None
    p = str(plan).strip().lower()
    if not p:
        return None
    return _PLAN_ALIASES.get(p, p)


def _plan_from_env() -> str | None:
    raw = (os.environ.get("GUARDSCHOOL_TENANT_PLAN_ID") or os.environ.get("GUARDSCHOOL_LICENSE_PLAN") or "").strip()
    return normalize_plan_id(raw) if raw else None


def _plan_from_tenant_db() -> str | None:
    try:
        from .tenant_ctx import tenant_slug

        slug = tenant_slug()
        if not slug:
            return None
        from .saas_db import lookup_tenant_plan_id, saas_db_enabled

        if not saas_db_enabled():
            return None
        return normalize_plan_id(lookup_tenant_plan_id(slug))
    except Exception:
        return None


def resolve_effective_plan_id() -> str | None:
    """Приоритет: plan_id тенанта из БД → env GUARDSCHOOL_TENANT_PLAN_ID."""
    return _plan_from_tenant_db() or _plan_from_env()


def apply_plan_capability_limits(registry: dict[str, CapabilityInfo], plan: str | None) -> None:
    """Пометить SaaS/commercial caps как locked, если их нет в тарифе plan_id."""
    plan_norm = normalize_plan_id(plan)
    if not plan_norm:
        return
    allowed = _PLAN_ALLOWED.get(plan_norm)
    if allowed is None:
        return
    for cap_id in _COMMERCIAL_GATED:
        info = registry.get(cap_id)
        if info is None or info.status != CapabilityStatus.available:
            continue
        if cap_id not in allowed:
            registry[cap_id] = CapabilityInfo(
                status=CapabilityStatus.locked,
                message=_plan_lock_message(plan_norm),
                module_hint=f"plan:{plan_norm}",
            )


def apply_plan_for_request_context(registry: dict[str, CapabilityInfo]) -> None:
    lic = registry.get(CAP_LICENSE_CHECK)
    if lic is None or lic.status != CapabilityStatus.available:
        return
    plan = resolve_effective_plan_id()
    if plan:
        apply_plan_capability_limits(registry, plan)


def register_license_capabilities(_registry: dict[str, CapabilityInfo]) -> None:
    """Provider hook (зарезервирован). Лимиты по plan_id — только в get_capabilities()."""
