"""Создание каталогов data/ и сопутствующие одноразовые файлы по умолчанию."""
from __future__ import annotations

from gs_change_log_bootstrap import ensure_default_change_log
from gs_paths import (
    BELL_SOUNDS_DIR,
    BREAK_MUSIC_DIR,
    DATA_DIR,
    IMPORT_DIR,
    UPLOADS_DIR,
    WIDGET_IMAGES_SUBDIR,
)
from gs_weekly_template import ensure_weekly_schedule_template_file


def ensure_dirs() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    UPLOADS_DIR.mkdir(exist_ok=True)
    (UPLOADS_DIR / WIDGET_IMAGES_SUBDIR).mkdir(parents=True, exist_ok=True)
    BELL_SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
    BREAK_MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    IMPORT_DIR.mkdir(exist_ok=True)
    ensure_weekly_schedule_template_file()
    ensure_default_change_log()
