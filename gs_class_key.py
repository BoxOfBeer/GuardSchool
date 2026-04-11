"""Нормализация ключа класса для сравнения и импорта Excel."""
from __future__ import annotations


def normalize_class(value: str) -> str:
    return str(value).strip().lower()
