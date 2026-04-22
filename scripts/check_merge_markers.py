#!/usr/bin/env python3
"""Проверка репозитория на маркеры merge-конфликтов (<<<<<<<, =======, >>>>>>>)."""
from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {'.git', '.venv', '__pycache__', 'node_modules'}
MARKER_RE = re.compile(r'^(<{7}|={7}|>{7})(?:\s|$)', re.MULTILINE)


def main() -> int:
    bad: list[str] = []
    for p in ROOT.rglob('*'):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.pdf', '.xlsx', '.xlsm', '.zip'}:
            continue
        try:
            text = p.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        if MARKER_RE.search(text):
            bad.append(str(p.relative_to(ROOT)))
    if bad:
        print('Найдены маркеры конфликтов:')
        for item in bad:
            print(f'- {item}')
        return 1
    print('OK: маркеры конфликтов не найдены.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
