"""Нормализация ключа класса для сравнения и импорта Excel."""
from __future__ import annotations

from typing import Any


def class_name_from_excel(value: Any) -> str:
    """Строка названия класса из значения ячейки Excel (сохраняет *, не режет символы)."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.replace("\u00a0", " ").strip()
    if isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)
    return str(value).replace("\u00a0", " ").strip()


def normalize_class(value: str) -> str:
    return str(value).strip().lower()
