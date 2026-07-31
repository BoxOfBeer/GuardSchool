"""SaaS upload limits and quota checks for admin imports."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile, Request

from .gs_admin_http import admin_msg, admin_ui_lang
from .gs_paths import BELL_SCHEDULES_PATH, FULL_SCHEDULE_PATH, OVERRIDES_PATH, SCHEDULE_PATH, SCHEDULE_SAMPLE_PATH
from .gs_saas_limits import json_utf8_size, max_schedule_json_bytes, max_user_data_bytes, saas_mode

def reject_if_saas_upload(request: Request) -> None:
    """Тяжёлые/несущественные для SaaS загрузки (фоны, звуки, полный ZIP импорт)."""
    if not saas_mode():
        return
    loc = admin_ui_lang(request)
    raise HTTPException(
        status_code=403,
        detail=admin_msg(
            loc,
            "В режиме SaaS эта загрузка отключена (используйте расписание и правки в формах).",
            "This upload is disabled in SaaS mode (use schedule uploads and form edits).",
        ),
    )


async def read_upload_capped(request: Request, file: UploadFile, max_bytes: int) -> bytes:
    raw = await file.read()
    if len(raw) > max_bytes:
        loc = admin_ui_lang(request)
        raise HTTPException(
            status_code=413,
            detail=admin_msg(
                loc,
                f"Файл слишком большой: {len(raw)} байт, максимум {max_bytes}.",
                f"File too large: {len(raw)} bytes, max {max_bytes}.",
            ),
        )
    return raw


def saas_check_json_payload_size(request: Request, payload: Any, label: str) -> None:
    if not saas_mode():
        return
    n = json_utf8_size(payload)
    lim = max_schedule_json_bytes()
    if n > lim:
        loc = admin_ui_lang(request)
        raise HTTPException(
            status_code=413,
            detail=admin_msg(
                loc,
                f"{label}: после импорта JSON ≈ {n} байт (лимит {lim}). Упростите расписание.",
                f"{label}: JSON size ~{n} bytes (limit {lim}).",
            ),
        )


def saas_check_quota_for_path(request: Request, path: Path, new_payload: Any) -> None:
    """Проверка суммарной квоты до записи JSON (замена одного файла)."""
    if not saas_mode():
        return
    new_bytes = len(json.dumps(new_payload, ensure_ascii=False, indent=2).encode("utf-8"))
    total = new_bytes
    for p in (SCHEDULE_PATH, FULL_SCHEDULE_PATH, SCHEDULE_SAMPLE_PATH, OVERRIDES_PATH, BELL_SCHEDULES_PATH):
        if p == path:
            continue
        if p.exists():
            total += p.stat().st_size
    lim = max_user_data_bytes()
    if total > lim:
        loc = admin_ui_lang(request)
        raise HTTPException(
            status_code=413,
            detail=admin_msg(
                loc,
                f"Превышена квота пользовательских данных: ~{total} байт (лимит {lim}). Упростите расписание или обратитесь к поддержке.",
                f"User data quota exceeded: ~{total} bytes (limit {lim}).",
            ),
        )


def saas_enforce_user_data_quota_after_multi_write(request: Request) -> None:
    """После импорта ZIP или сложной записи — проверка фактического размера на диске."""
    if not saas_mode():
        return
    total = 0
    for p in (SCHEDULE_PATH, FULL_SCHEDULE_PATH, SCHEDULE_SAMPLE_PATH, OVERRIDES_PATH, BELL_SCHEDULES_PATH):
        if p.exists():
            total += p.stat().st_size
    lim = max_user_data_bytes()
    if total > lim:
        loc = admin_ui_lang(request)
        raise HTTPException(
            status_code=413,
            detail=admin_msg(
                loc,
                f"Превышена квота данных: {total} байт (лимит {lim}). Импорт отменить нельзя автоматически — удалите лишние данные вручную.",
                f"Data quota exceeded: {total} bytes (limit {lim}).",
            ),
        )
