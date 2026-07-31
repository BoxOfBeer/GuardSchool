"""Demo-данные community/local при первой настройке (без SaaS)."""
from __future__ import annotations

import os
from typing import Any

from .gs_app_config import default_config, sanitize_config
from .gs_deploy import deployment_mode
from .gs_ensure_dirs import ensure_dirs
from .gs_jsonio import write_json
from .gs_paths import (
    ANNOUNCEMENTS_PATH,
    BELL_SCHEDULES_PATH,
    CONFIG_PATH,
    FULL_SCHEDULE_PATH,
)
from .gs_schedule_bells import default_bell_schedules
from .tenant_ctx import map_data_path


def _demo_full_schedule_rows() -> list[dict[str, Any]]:
    """Недельная сетка для группы «5» — достаточно для превью и ТВ."""
    plan: list[tuple[int, list[str]]] = [
        (0, ["Математика", "Русский язык", "Литература", "Окружающий мир"]),
        (1, ["История", "Английский язык", "Физическая культура", ""]),
        (2, ["Математика", "Русский язык", "Технология", "Музыка"]),
        (3, ["Биология", "География", "Информатика", ""]),
        (4, ["Математика", "Русский язык", "ИЗО", ""]),
    ]
    rows: list[dict[str, Any]] = []
    for weekday, subjects in plan:
        rows.append(
            {
                "weekday": weekday,
                "class_name": "5",
                "class_key": "5",
                "lessons": [{"index": i + 1, "subject": sub} for i, sub in enumerate(subjects)],
            }
        )
    return rows


def _demo_announcements() -> list[dict[str, Any]]:
    return [
        {
            "text": (
                "Добро пожаловать в GuardSchool.\n"
                "Откройте экран /screen/tv-1 и настройте расписание и сигналы в админке."
            )
        }
    ]


def seed_community_demo_data_if_empty() -> bool:
    """
    Записать config + расписание + сигналы, если config.json ещё нет.
    Не трогает существующие данные. SaaS и GUARDSCHOOL_SKIP_DEMO_SEED=1 — пропуск.
    """
    if (os.environ.get("GUARDSCHOOL_SKIP_DEMO_SEED") or "").strip() == "1":
        return False
    if deployment_mode() == "saas":
        return False
    cfg_path = map_data_path(CONFIG_PATH)
    if cfg_path.is_file():
        return False
    ensure_dirs()
    write_json(cfg_path, sanitize_config(default_config()))
    write_json(map_data_path(BELL_SCHEDULES_PATH), default_bell_schedules())
    write_json(map_data_path(FULL_SCHEDULE_PATH), _demo_full_schedule_rows())
    write_json(map_data_path(ANNOUNCEMENTS_PATH), _demo_announcements())
    return True
