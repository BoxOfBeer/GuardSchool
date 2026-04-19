"""Нормализация ключа класса для сравнения и импорта Excel."""
from __future__ import annotations

import re
from typing import Any

# Звёздочка в «7*», «7 *», полноширинная ＊ и т.п. — один ключ после normalize_class.
_STAR_CLASS_RE = re.compile(r"^(\d+)\s*([*＊∗⁎])?\s*$")


def class_name_from_excel(value: Any) -> str:
    """Строка названия класса из значения ячейки Excel (сохраняет * в подписи; ключ — через normalize_class)."""
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
    t = str(value).replace("\u00a0", " ").strip().lower()
    m = _STAR_CLASS_RE.fullmatch(t)
    if m:
        return f"{m.group(1)}*" if m.group(2) else m.group(1)
    # «7a» с латинской «a» (конфиг/URL) → «7а» как в Excel с кириллической «а».
    if re.fullmatch(r"\d+a", t):
        return t[:-1] + "а"
    return t
