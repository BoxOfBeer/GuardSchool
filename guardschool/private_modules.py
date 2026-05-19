"""Поиск опциональных модулей: в `guardschool/` (embedded) или пакете `guardschool_private` на PYTHONPATH."""
from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

PRIVATE_PACKAGE = "guardschool_private"


def private_pythonpath() -> Path | None:
    raw = (os.environ.get("GUARDSCHOOL_PRIVATE_PYTHONPATH") or "").strip()
    if not raw:
        return None
    p = Path(raw).resolve()
    return p if p.is_dir() else None


def ensure_private_pythonpath() -> None:
    p = private_pythonpath()
    if p is None:
        return
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)


def module_present(module_basename: str) -> bool:
    """Есть ли полная реализация модуля (`_*_pg`, private), не только фасад."""
    root = Path(__file__).resolve().parent
    if (root / f"_{module_basename}_pg.py").is_file():
        return True
    ensure_private_pythonpath()
    try:
        spec = importlib.util.find_spec(f"{PRIVATE_PACKAGE}.{module_basename}")
        return spec is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def import_optional_module(module_basename: str) -> Any:
    """Импорт через фасад guardschool.<name> или guardschool_private.<name>."""
    root = Path(__file__).resolve().parent
    facade = root / f"{module_basename}.py"
    if facade.is_file():
        return importlib.import_module(f".{module_basename}", package="guardschool")
    ensure_private_pythonpath()
    return importlib.import_module(f"{PRIVATE_PACKAGE}.{module_basename}")
