"""Стартовая запись в журнале версий при первом запуске."""
from __future__ import annotations

import json
from datetime import datetime

from gs_jsonio import write_json
from gs_paths import APP_VERSION, CHANGE_LOG_PATH


def ensure_default_change_log() -> None:
    """Одна стартовая запись для новой установки (если файла нет или он пустой)."""
    if CHANGE_LOG_PATH.exists():
        try:
            raw = json.loads(CHANGE_LOG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = []
        if isinstance(raw, list) and len(raw) > 0:
            return
    write_json(
        CHANGE_LOG_PATH,
        [
            {
                "version": APP_VERSION,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "message": (
                    "Первая установка: журнал выпусков в data/change_log.json. При каждом релизе поднимайте APP_VERSION "
                    "и добавляйте сюда краткое описание изменений."
                ),
            },
        ],
    )
