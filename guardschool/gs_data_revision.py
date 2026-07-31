"""Ревизия данных для ТВ и синхронизации (хеш содержимого ключевых файлов)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .gs_jsonio import read_json
from .gs_paths import (
    ANNOUNCEMENTS_PATH,
    BELL_SCHEDULES_PATH,
    CHANGE_LOG_PATH,
    CONFIG_PATH,
    FULL_SCHEDULE_PATH,
    HOLIDAYS_PATH,
    MARQUEE_PATH,
    OVERRIDES_PATH,
    SCHEDULE_PATH,
    SCHEDULE_SAMPLE_PATH,
)

# Файлы, участвующие в ревизии (без uploads и auth — auth меняется редко; при необходимости добавить).
_REVISION_PATHS: tuple[Path, ...] = (
    CONFIG_PATH,
    SCHEDULE_PATH,
    FULL_SCHEDULE_PATH,
    SCHEDULE_SAMPLE_PATH,
    HOLIDAYS_PATH,
    ANNOUNCEMENTS_PATH,
    MARQUEE_PATH,
    OVERRIDES_PATH,
    BELL_SCHEDULES_PATH,
    CHANGE_LOG_PATH,
)


def compute_data_revision() -> str:
    """Стабильная hex-строка: SHA256 от канонического JSON каждого файла."""
    h = hashlib.sha256()
    for path in _REVISION_PATHS:
        h.update(path.name.encode("utf-8"))
        if path.exists():
            try:
                raw = path.read_bytes()
                data = json.loads(raw.decode("utf-8"))
                canonical = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
                h.update(canonical)
            except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
                h.update(b"__err__")
        else:
            h.update(b"__missing__")
    return h.hexdigest()[:32]
