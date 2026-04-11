"""Состояние автоимпорта Excel из data/import/ (сигнатуры файлов)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from gs_jsonio import read_json, write_json
from gs_paths import IMPORT_STATE_PATH


def load_import_state() -> dict[str, Any]:
    return read_json(IMPORT_STATE_PATH, {})


def save_import_state(state: dict[str, Any]) -> None:
    write_json(IMPORT_STATE_PATH, state)


def import_signature(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    stat = path.stat()
    return {"mtime_ns": stat.st_mtime_ns, "size": stat.st_size}
