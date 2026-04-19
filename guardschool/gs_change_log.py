"""Журнал выпусков: data/change_log.json (только записи с полем version)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .gs_jsonio import read_json, write_json
from .gs_paths import APP_VERSION, CHANGE_LOG_PATH

_MAX_ENTRIES = 200
# Файл в корне репозитория (рядом с каталогом пакета guardschool/), см. README / ru.json про журнал.
_SEED_PATH = Path(__file__).resolve().parent.parent / "change_log_seed.json"


def _load_seed_entries() -> list[dict[str, Any]]:
    if _SEED_PATH.is_file():
        try:
            raw = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            raw = []
        if isinstance(raw, list):
            out: list[dict[str, Any]] = []
            for item in raw:
                if not isinstance(item, dict):
                    continue
                ver = str(item.get("version") or "").strip()
                msg = item.get("message")
                if not ver or msg is None:
                    continue
                ts = str(item.get("timestamp") or datetime.now().isoformat(timespec="seconds"))
                out.append({"version": ver, "timestamp": ts, "message": str(msg).strip()})
            if out:
                return out[:_MAX_ENTRIES]
    return [
        {
            "version": APP_VERSION,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "message": (
                "Обновите файл change_log_seed.json в корне репозитория — сюда подставится полноценный журнал выпусков."
            ),
        }
    ]


def _version_sort_key(ver: str) -> tuple[Any, ...]:
    key: list[Any] = []
    for seg in str(ver or "").strip().split("."):
        seg = seg.strip()
        if not seg:
            continue
        try:
            key.append(int(seg))
        except ValueError:
            key.append(seg)
    return tuple(key)


def load_change_log() -> list[dict[str, Any]]:
    """Записи с непустым version: объединение журнала школы (файл) и сида репозитория; при одной version — приоритет у файла школы."""
    raw = read_json(CHANGE_LOG_PATH, [])
    tenant: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            msg = item.get("message")
            if msg is None:
                continue
            ver_s = str(item.get("version") or "").strip()
            if not ver_s:
                continue
            ts = item.get("timestamp")
            if not ts:
                ts = datetime.now().isoformat(timespec="seconds")
            tenant.append({"timestamp": str(ts), "message": str(msg), "version": ver_s})
    by_ver: dict[str, dict[str, Any]] = {}
    for item in _load_seed_entries():
        v = str(item.get("version") or "").strip()
        if v:
            by_ver[v] = {"timestamp": str(item.get("timestamp") or ""), "message": str(item.get("message") or ""), "version": v}
    for item in tenant:
        v = str(item.get("version") or "").strip()
        if v:
            by_ver[v] = item
    merged = list(by_ver.values())
    merged.sort(key=lambda x: _version_sort_key(str(x.get("version") or "")), reverse=True)
    return merged[:_MAX_ENTRIES]


def append_release_note(message: str, *, version: str | None = None) -> None:
    """Добавить запись о выпуске (поднять APP_VERSION и вызвать из кода или править JSON вручную)."""
    v = (version or APP_VERSION).strip()
    raw = read_json(CHANGE_LOG_PATH, [])
    entries: list[dict[str, Any]] = raw if isinstance(raw, list) else []
    entries.insert(0, {"version": v, "timestamp": datetime.now().isoformat(timespec="seconds"), "message": message.strip()})
    write_json(CHANGE_LOG_PATH, entries[:_MAX_ENTRIES])


def _is_only_bootstrap_stub(versioned: list[dict[str, Any]]) -> bool:
    if len(versioned) != 1:
        return False
    m = str(versioned[0].get("message") or "")
    if "Первая установка" in m:
        return True
    if "On first run" in m or "first run" in m.lower():
        return True
    if "change_log.json" in m and ("релиз" in m.lower() or "release" in m.lower()):
        return True
    return False


def ensure_change_log_file() -> None:
    """Если файла нет или список пуст — записать сид из change_log_seed.json."""
    need_write = True
    if CHANGE_LOG_PATH.exists():
        try:
            raw = json.loads(CHANGE_LOG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            raw = []
        if isinstance(raw, list) and len(raw) > 0:
            need_write = False
    if need_write:
        write_json(CHANGE_LOG_PATH, _load_seed_entries())


def repair_change_log_strip_audit() -> None:
    """Удалить из файла записи без version; если не осталось ни одной — сид. Заменить однострочный bootstrap на сид."""
    ensure_change_log_file()
    raw = read_json(CHANGE_LOG_PATH, [])
    if not isinstance(raw, list):
        return
    cleaned: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        msg = item.get("message")
        if msg is None:
            continue
        ver_s = str(item.get("version") or "").strip()
        if not ver_s:
            continue
        ts = item.get("timestamp") or datetime.now().isoformat(timespec="seconds")
        cleaned.append({"timestamp": str(ts), "message": str(msg), "version": ver_s})
    if len(cleaned) != len(raw):
        write_json(CHANGE_LOG_PATH, (cleaned if cleaned else _load_seed_entries())[:_MAX_ENTRIES])
        return
    if _is_only_bootstrap_stub(cleaned):
        write_json(CHANGE_LOG_PATH, _load_seed_entries())

