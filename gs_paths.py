"""Пути данных, статики и версия продукта (общий слой без FastAPI)."""
from __future__ import annotations

import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
else:
    APP_DIR = Path(__file__).resolve().parent
    RESOURCE_DIR = APP_DIR


def resolve_brand_logo_path() -> Path | None:
    for candidate in (APP_DIR / "ico.png", RESOURCE_DIR / "ico.png"):
        if candidate.is_file():
            return candidate
    return None


DATA_DIR = APP_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
BELL_SOUNDS_DIR = UPLOADS_DIR / "bells"
BACKGROUND_UPLOAD_IMAGE_SUFFIXES = frozenset(
    {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".avif"}
)
BREAK_MUSIC_DIR = DATA_DIR / "break_music"
IMPORT_DIR = DATA_DIR / "import"
STATIC_DIR = RESOURCE_DIR / "static"
CONFIG_PATH = DATA_DIR / "config.json"
AUTH_PATH = DATA_DIR / "auth.json"
SCHEDULE_PATH = DATA_DIR / "schedule.json"
FULL_SCHEDULE_PATH = DATA_DIR / "full_schedule.json"
SCHEDULE_SAMPLE_PATH = DATA_DIR / "schedule_sample.json"
HOLIDAYS_PATH = DATA_DIR / "holidays.json"
ANNOUNCEMENTS_PATH = DATA_DIR / "announcements.json"
MARQUEE_PATH = DATA_DIR / "marquee.json"
OVERRIDES_PATH = DATA_DIR / "overrides.json"
BELL_SCHEDULES_PATH = DATA_DIR / "bell_schedules.json"
CHANGE_LOG_PATH = DATA_DIR / "change_log.json"
APP_VERSION = "1.01.002"
IMPORT_STATE_PATH = DATA_DIR / "import_state.json"
AUTO_SCHEDULE_IMPORT_PATH = IMPORT_DIR / "schedule.xlsx"
AUTO_FULL_SCHEDULE_IMPORT_PATH = IMPORT_DIR / "full_schedule.xlsx"
AUTO_SCHEDULE_SAMPLE_IMPORT_PATH = IMPORT_DIR / "schedule_sample.xlsx"
FULL_SCHEDULE_SAMPLE_XLSX = IMPORT_DIR / "full_schedule_sample.xlsx"
AUTO_HOLIDAYS_IMPORT_PATH = IMPORT_DIR / "holidays.xlsx"
AUTO_ANNOUNCEMENTS_IMPORT_PATH = IMPORT_DIR / "announcements.xlsx"
AUTO_MARQUEE_IMPORT_PATH = IMPORT_DIR / "marquee.xlsx"
SESSION_COOKIE = "gornii_session"
WIDGET_IMAGES_SUBDIR = "widget_images"
