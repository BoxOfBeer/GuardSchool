"""Создание каталогов data/ и сопутствующие одноразовые файлы по умолчанию."""
from __future__ import annotations

from .gs_change_log import ensure_change_log_file, repair_change_log_strip_audit
from .gs_paths import (
    BELL_SOUNDS_DIR,
    BREAK_MUSIC_DIR,
    DATA_DIR,
    IMPORT_DIR,
    UPLOADS_DIR,
    WIDGET_IMAGES_SUBDIR,
)
from .gs_weekly_template import ensure_weekly_schedule_template_file
from .tenant_ctx import map_data_path


def ensure_dirs() -> None:
    map_data_path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    map_data_path(UPLOADS_DIR).mkdir(parents=True, exist_ok=True)
    map_data_path(UPLOADS_DIR / WIDGET_IMAGES_SUBDIR).mkdir(parents=True, exist_ok=True)
    map_data_path(BELL_SOUNDS_DIR).mkdir(parents=True, exist_ok=True)
    map_data_path(BREAK_MUSIC_DIR).mkdir(parents=True, exist_ok=True)
    map_data_path(IMPORT_DIR).mkdir(parents=True, exist_ok=True)
    ensure_weekly_schedule_template_file()
    ensure_change_log_file()
    repair_change_log_strip_audit()
