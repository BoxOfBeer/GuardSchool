"""Загрузка backend для open-core: private → `_name_pg` → `_name_stub`."""
from __future__ import annotations

import importlib
import sys
from typing import Any


def backend_cache_key(name: str) -> str:
    return f"guardschool._{name}_backend"


def load_private_backend(name: str) -> Any:
    key = backend_cache_key(name)
    cached = sys.modules.get(key)
    if cached is not None:
        return cached
    mod: Any | None = None
    from .private_modules import ensure_private_pythonpath, private_pythonpath

    if private_pythonpath() is not None:
        ensure_private_pythonpath()
        try:
            mod = importlib.import_module(f"guardschool_private.{name}")
        except ImportError:
            mod = None
    if mod is None:
        try:
            mod = importlib.import_module(f"guardschool._{name}_pg")
        except ImportError:
            mod = importlib.import_module(f"guardschool._{name}_stub")
    sys.modules[key] = mod
    return mod


def facade_getattr(name: str, attr: str) -> Any:
    return getattr(load_private_backend(name), attr)


def facade_dir(name: str) -> list[str]:
    return sorted(dir(load_private_backend(name)))
