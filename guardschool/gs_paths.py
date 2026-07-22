"""Пути данных, статики и версия продукта (общий слой без FastAPI)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
else:
    # Пакет лежит в guardschool/; data/ и static/ — в корне репозитория (родитель каталога пакета).
    _PKG_DIR = Path(__file__).resolve().parent
    APP_DIR = _PKG_DIR.parent
    RESOURCE_DIR = APP_DIR

# Облачный деплой: каталог данных вне репозитория (env задаётся до импорта приложения).
_env_data = (os.environ.get("GUARDSCHOOL_DATA_DIR") or "").strip()


def resolve_brand_logo_path() -> Path | None:
    for candidate in (APP_DIR / "ico.png", RESOURCE_DIR / "ico.png"):
        if candidate.is_file():
            return candidate
    return None


DATA_DIR = Path(_env_data).resolve() if _env_data else (APP_DIR / "data")
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
SCHOOL_NEWS_PATH = DATA_DIR / "school_news.json"
MARQUEE_PATH = DATA_DIR / "marquee.json"
RSS_NEWS_CACHE_PATH = DATA_DIR / "rss_news_cache.json"
SCREEN_WATCH_STATS_PATH = DATA_DIR / "screen_watch_stats.json"
OVERRIDES_PATH = DATA_DIR / "overrides.json"
BELL_SCHEDULES_PATH = DATA_DIR / "bell_schedules.json"
CHANGE_LOG_PATH = DATA_DIR / "change_log.json"
APP_VERSION = "1.02.046"
IMPORT_STATE_PATH = DATA_DIR / "import_state.json"
SYNC_STATE_PATH = DATA_DIR / "sync_state.json"
# Маркетинговый контент портала guarddoc.ru: всегда в корневом data/, не в tenants/<slug>/data.
PORTAL_CMS_PATH = DATA_DIR / "portal_cms.json"
AUTO_SCHEDULE_IMPORT_PATH = IMPORT_DIR / "schedule.xlsx"
AUTO_FULL_SCHEDULE_IMPORT_PATH = IMPORT_DIR / "full_schedule.xlsx"
AUTO_SCHEDULE_SAMPLE_IMPORT_PATH = IMPORT_DIR / "schedule_sample.xlsx"
FULL_SCHEDULE_SAMPLE_XLSX = IMPORT_DIR / "full_schedule_sample.xlsx"
AUTO_HOLIDAYS_IMPORT_PATH = IMPORT_DIR / "holidays.xlsx"
AUTO_ANNOUNCEMENTS_IMPORT_PATH = IMPORT_DIR / "announcements.xlsx"
AUTO_MARQUEE_IMPORT_PATH = IMPORT_DIR / "marquee.xlsx"
SESSION_COOKIE = "gornii_session"
# SaaS: при GUARDSCHOOL_PUBLIC_SCHOOL_HOST хранит slug школы для единого входа (например school.*).
SAAS_TENANT_COOKIE = "gs_saas_tenant"
WIDGET_IMAGES_SUBDIR = "widget_images"
