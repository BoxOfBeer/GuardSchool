"""Лимиты загрузок в режиме GUARDSCHOOL_SAAS_MODE."""
from __future__ import annotations

import json
import os
from typing import Any


def saas_mode() -> bool:
    return os.environ.get("GUARDSCHOOL_SAAS_MODE", "").strip().lower() in ("1", "true", "yes")


def max_schedule_xlsx_bytes() -> int:
    raw = (os.environ.get("GUARDSCHOOL_SAAS_MAX_SCHEDULE_XLSX_BYTES") or "").strip()
    if raw:
        try:
            return max(4096, int(raw))
        except ValueError:
            pass
    return 15 * 1024 * 1024


def max_schedule_json_bytes() -> int:
    raw = (os.environ.get("GUARDSCHOOL_SAAS_MAX_SCHEDULE_JSON_BYTES") or "").strip()
    if raw:
        try:
            return max(256, int(raw))
        except ValueError:
            pass
    return 1024 * 1024


def max_weekly_zip_bytes() -> int:
    raw = (os.environ.get("GUARDSCHOOL_SAAS_MAX_WEEKLY_ZIP_BYTES") or "").strip()
    if raw:
        try:
            return max(4096, int(raw))
        except ValueError:
            pass
    return 15 * 1024 * 1024


def max_user_data_bytes() -> int:
    """Мягкая квота «пользовательские данные» (json расписаний и т.д.) — суммарно."""
    raw = (os.environ.get("GUARDSCHOOL_SAAS_MAX_USER_DATA_BYTES") or "").strip()
    if raw:
        try:
            return max(1024, int(raw))
        except ValueError:
            pass
    return 15 * 1024 * 1024


def json_utf8_size(payload: Any) -> int:
    try:
        return len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError):
        return 0
