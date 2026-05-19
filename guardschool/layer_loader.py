"""Загрузка опциональных закрытых слоёв (SaaS, Commercial) с диска."""
from __future__ import annotations

import importlib.util
import logging
import os
import sys
from pathlib import Path
from typing import Any

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
    register_capability_provider,
)

_LOG = logging.getLogger(__name__)

_layers_bootstrapped = False
_loaded_layer_names: list[str] = []
_saas_route_groups_mounted: set[str] = set()
_commercial_routes_mounted: bool = False


def is_saas_layer_loaded() -> bool:
    load_optional_layers()
    return "saas" in _loaded_layer_names


def saas_layer_mounted_groups() -> frozenset[str]:
    load_optional_layers()
    return frozenset(_saas_route_groups_mounted)


def mark_saas_routes_mounted(*groups: str) -> None:
    for g in groups:
        _saas_route_groups_mounted.add(g)


def is_commercial_layer_loaded() -> bool:
    load_optional_layers()
    return "commercial" in _loaded_layer_names


def commercial_routes_mounted_by_layer() -> bool:
    load_optional_layers()
    return _commercial_routes_mounted


def mark_commercial_routes_mounted() -> None:
    global _commercial_routes_mounted
    _commercial_routes_mounted = True


def layer_path() -> Path | None:
    raw = (os.environ.get("GUARDSCHOOL_LAYER_PATH") or "").strip()
    if not raw:
        return None
    p = Path(raw)
    return p if p.is_dir() else None


def _import_layer_module(layer_dir: Path, module_name: str) -> Any | None:
    init_py = layer_dir / "__init__.py"
    if not init_py.is_file():
        return None
    spec = importlib.util.spec_from_file_location(module_name, init_py)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _saas_layer_provider(registry: dict[str, CapabilityInfo]) -> None:
    """Помечает SaaS capabilities как available если слой загружен (детали — в слое)."""
    for cap_id in (
        CAP_MOBILE_EXTERNAL,
        CAP_PUSH_NOTIFICATIONS,
        CAP_CLOUD_SYNC,
        CAP_TENANT_FEEDBACK,
        CAP_REMOTE_TV_PAIRING,
        CAP_CLOUD_STATUS,
    ):
        if cap_id in registry and registry[cap_id].status == CapabilityStatus.missing:
            registry[cap_id] = CapabilityInfo(
                status=CapabilityStatus.available,
                message="Функция доступна (SaaS слой установлен).",
                module_hint="saas",
            )


def _commercial_layer_provider(registry: dict[str, CapabilityInfo]) -> None:
    for cap_id in (
        CAP_LICENSE_CHECK,
        CAP_REGISTRATION,
        CAP_PAYMENT,
        CAP_TENANT_PROVISIONING,
        CAP_TARIFF_LIMITS,
        CAP_PRODUCTION_PORTAL,
    ):
        if cap_id in registry and registry[cap_id].status == CapabilityStatus.missing:
            registry[cap_id] = CapabilityInfo(
                status=CapabilityStatus.available,
                message="Функция доступна (Commercial слой установлен).",
                module_hint="commercial",
            )


def load_optional_layers() -> list[str]:
    global _layers_bootstrapped, _loaded_layer_names
    if _layers_bootstrapped:
        return list(_loaded_layer_names)
    _layers_bootstrapped = True
    try:
        from .private_modules import ensure_private_pythonpath

        ensure_private_pythonpath()
    except Exception:
        pass
    base = layer_path()
    if base is None:
        return []

    for layer_name, provider in (
        ("saas", _saas_layer_provider),
        ("commercial", _commercial_layer_provider),
    ):
        layer_dir = base / "layers" / layer_name
        if not layer_dir.is_dir():
            layer_dir = base / layer_name
        if not layer_dir.is_dir():
            continue
        mod_name = f"guardschool_layer_{layer_name}"
        try:
            mod = _import_layer_module(layer_dir, mod_name)
            if mod is not None and hasattr(mod, "register_capabilities"):
                register_capability_provider(mod.register_capabilities)
            else:
                register_capability_provider(provider)
            if mod is not None and hasattr(mod, "register_routes"):
                _pending_route_registrars.append(mod.register_routes)
            _loaded_layer_names.append(layer_name)
            _LOG.info("Loaded GuardSchool layer: %s from %s", layer_name, layer_dir)
        except Exception as exc:
            _LOG.warning("Failed to load layer %s: %s", layer_name, exc)
            for cap_hint in (layer_name,):
                pass

    return list(_loaded_layer_names)


_pending_route_registrars: list[Any] = []


def apply_layer_routes(app: Any) -> None:
    """Вызвать после создания FastAPI app."""
    load_optional_layers()
    for registrar in _pending_route_registrars:
        try:
            registrar(app)
        except Exception as exc:
            _LOG.warning("Layer route registration failed: %s", exc)


def reset_layer_loader_for_tests() -> None:
    """Сброс кэша загрузки слоёв (unit tests)."""
    global _layers_bootstrapped, _loaded_layer_names, _pending_route_registrars
    global _saas_route_groups_mounted, _commercial_routes_mounted
    _layers_bootstrapped = False
    _loaded_layer_names = []
    _pending_route_registrars = []
    _saas_route_groups_mounted = set()
    _commercial_routes_mounted = False
