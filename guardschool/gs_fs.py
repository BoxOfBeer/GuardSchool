"""Операции с каталогами на диске."""
from __future__ import annotations

from pathlib import Path


def clear_directory(path: Path) -> None:
    if not path.exists():
        return
    for item in path.iterdir():
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            clear_directory(item)
            item.rmdir()
