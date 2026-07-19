"""Экспорт/импорт ZIP полной конфигурации и недельного расписания."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from fastapi import HTTPException

from .gs_admin_http import admin_msg
from .gs_ensure_dirs import ensure_dirs
from .gs_fs import clear_directory
from .gs_jsonio import read_json, write_json
from .gs_paths import (
    AUTH_PATH,
    BELL_SCHEDULES_PATH,
    CHANGE_LOG_PATH,
    CONFIG_PATH,
    DATA_DIR,
    FULL_SCHEDULE_PATH,
    FULL_SCHEDULE_SAMPLE_XLSX,
    OVERRIDES_PATH,
    SCHEDULE_PATH,
    SCHEDULE_SAMPLE_PATH,
    UPLOADS_DIR,
)
from .gs_weekly_template import ensure_weekly_schedule_template_file
from .tenant_ctx import map_data_path


def export_weekly_schedule_bundle_bytes() -> bytes:
    ensure_dirs()
    buffer = io.BytesIO()
    readme = (
        "Недельное расписание GuardSchool\n"
        "— full_schedule.json — полное по дням недели (как в админке после загрузки Excel).\n"
        "— schedule_sample.json — образец отличий от полного (подсветка на ТВ).\n"
        "— full_schedule_sample.xlsx — шаблон Excel: «День недели», «Класс»/«Группа», «Урок1»/«Слот1» …\n"
        "Импорт: ZIP с теми же именами файлов в разделе «Расписание».\n"
    )
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "full_schedule.json",
            json.dumps(read_json(FULL_SCHEDULE_PATH, []), ensure_ascii=False, indent=2).encode("utf-8"),
        )
        archive.writestr(
            "schedule_sample.json",
            json.dumps(read_json(SCHEDULE_SAMPLE_PATH, []), ensure_ascii=False, indent=2).encode("utf-8"),
        )
        ensure_weekly_schedule_template_file()
        if FULL_SCHEDULE_SAMPLE_XLSX.is_file():
            archive.writestr(FULL_SCHEDULE_SAMPLE_XLSX.name, FULL_SCHEDULE_SAMPLE_XLSX.read_bytes())
        archive.writestr("README.txt", readme.encode("utf-8"))
    return buffer.getvalue()


def import_weekly_schedule_bundle_bytes(raw_bytes: bytes, *, lang: str = "ru") -> None:
    with zipfile.ZipFile(io.BytesIO(raw_bytes), "r") as archive:
        names = archive.namelist()
        if not names:
            raise HTTPException(
                status_code=400,
                detail=admin_msg(lang, "Пустой ZIP-архив.", "Empty ZIP archive."),
            )
        found: set[str] = set()
        for name in names:
            if Path(name).is_absolute() or ".." in Path(name).parts:
                raise HTTPException(
                    status_code=400,
                    detail=admin_msg(lang, "Недопустимый путь в архиве.", "Invalid path in archive."),
                )
            base = Path(name).name
            if base not in ("full_schedule.json", "schedule_sample.json"):
                continue
            raw = archive.read(name)
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, list):
                raise HTTPException(
                    status_code=400,
                    detail=admin_msg(
                        lang,
                        f"{base}: ожидается JSON-массив.",
                        f"{base}: expected a JSON array.",
                    ),
                )
            if base == "full_schedule.json":
                write_json(FULL_SCHEDULE_PATH, data)
            else:
                write_json(SCHEDULE_SAMPLE_PATH, data)
            found.add(base)
        if not found:
            raise HTTPException(
                status_code=400,
                detail=admin_msg(
                    lang,
                    "В архиве нет full_schedule.json или schedule_sample.json.",
                    "The archive must contain full_schedule.json and/or schedule_sample.json.",
                ),
            )


def export_bundle_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in [
            CONFIG_PATH,
            AUTH_PATH,
            SCHEDULE_PATH,
            FULL_SCHEDULE_PATH,
            SCHEDULE_SAMPLE_PATH,
            OVERRIDES_PATH,
            BELL_SCHEDULES_PATH,
            CHANGE_LOG_PATH,
        ]:
            mapped = map_data_path(path)
            if mapped.exists():
                archive.writestr(path.name, mapped.read_bytes())
        uploads = map_data_path(UPLOADS_DIR)
        if uploads.exists():
            for file_path in uploads.rglob("*"):
                if file_path.is_file():
                    archive.writestr(str(Path("uploads") / file_path.relative_to(uploads)), file_path.read_bytes())
    return buffer.getvalue()


def import_bundle_bytes(raw_bytes: bytes, *, lang: str = "ru") -> None:
    with zipfile.ZipFile(io.BytesIO(raw_bytes), "r") as archive:
        names = archive.namelist()
        if not names:
            raise HTTPException(
                status_code=400,
                detail=admin_msg(lang, "Пустой ZIP-архив.", "Empty ZIP archive."),
            )
        allowed_files = {
            "config.json",
            "auth.json",
            "schedule.json",
            "full_schedule.json",
            "schedule_sample.json",
            "overrides.json",
            "bell_schedules.json",
            "change_log.json",
        }
        for name in names:
            path = Path(name)
            if path.is_absolute() or ".." in path.parts:
                raise HTTPException(
                    status_code=400,
                    detail=admin_msg(lang, "Архив содержит недопустимые пути.", "The archive contains invalid paths."),
                )
            if path.parts and path.parts[0] == "uploads":
                continue
            if path.name not in allowed_files or len(path.parts) != 1:
                raise HTTPException(
                    status_code=400,
                    detail=admin_msg(
                        lang,
                        f"Неизвестный файл в архиве: {name}",
                        f"Unknown file in archive: {name}",
                    ),
                )

        has_root_config = any(
            (not Path(n).is_absolute() and ".." not in Path(n).parts and len(Path(n).parts) == 1 and Path(n).name == "config.json")
            for n in names
        )
        if not has_root_config:
            raise HTTPException(
                status_code=400,
                detail=admin_msg(
                    lang,
                    "В корне ZIP должен быть config.json (экспорт GuardSchool). Импорт отменён, каталог uploads не очищался.",
                    "ZIP must contain config.json at archive root (GuardSchool export). Import aborted; uploads were not cleared.",
                ),
            )

        uploads = map_data_path(UPLOADS_DIR)
        data_dir = map_data_path(DATA_DIR)
        clear_directory(uploads)
        ensure_dirs()

        for name in names:
            path = Path(name)
            payload = archive.read(name)
            if path.parts and path.parts[0] == "uploads":
                target = uploads / Path(*path.parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
            else:
                (data_dir / path.name).write_bytes(payload)

    try:
        from .cloud_store import persist_snapshot_to_database

        persist_snapshot_to_database()
    except Exception:
        pass
