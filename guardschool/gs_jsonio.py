"""Чтение/запись JSON в data/."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        from .cloud_store import notify_data_file_written

        notify_data_file_written(path)
    except Exception:
        pass
