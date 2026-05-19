"""Загрузка виджетов: builtin, official /widgets, custom_widgets (local)."""
from __future__ import annotations

import importlib.util
import logging
import os
import sys
from pathlib import Path

from .gs_deploy import deployment_mode
from .capabilities import has_capability
from .widgets_builtin import register_builtin_widgets

_LOG = logging.getLogger(__name__)

_loaded = False


def _repo_widgets_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "widgets"


def _custom_widgets_dir() -> Path | None:
    raw = (os.environ.get("GUARDSCHOOL_CUSTOM_WIDGETS_DIR") or "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_dir() else None
    data = (os.environ.get("GUARDSCHOOL_DATA_DIR") or "").strip()
    if data:
        p = Path(data).parent / "custom_widgets"
        if p.is_dir():
            return p
    p = Path(__file__).resolve().parent.parent / "custom_widgets"
    return p if p.is_dir() else None


def _load_py_modules_from_dir(directory: Path, *, official: bool) -> None:
    if not directory.is_dir():
        return
    for py_path in sorted(directory.glob("*.py")):
        if py_path.name.startswith("_"):
            continue
        mod_name = f"guardschool_widget_{'o' if official else 'c'}_{py_path.stem}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, py_path)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)
            _LOG.info("Loaded widget module %s from %s", py_path.name, py_path)
        except Exception as exc:
            wtype = py_path.stem
            from .widget_registry import _load_errors

            _load_errors[wtype] = str(exc)
            _LOG.exception("Failed to load widget %s: %s", py_path, exc)


def load_all_widgets() -> None:
    global _loaded
    if _loaded:
        return
    from .capabilities import ensure_capabilities_initialized

    ensure_capabilities_initialized()
    _loaded = True
    register_builtin_widgets()
    _load_py_modules_from_dir(_repo_widgets_dir(), official=True)
    if deployment_mode() == "local" and has_capability("custom_widgets"):
        custom = _custom_widgets_dir()
        if custom:
            _load_py_modules_from_dir(custom, official=False)


def reset_widget_loader_for_tests() -> None:
    """Сброс флага загрузки (только для unit-тестов)."""
    global _loaded
    _loaded = False
