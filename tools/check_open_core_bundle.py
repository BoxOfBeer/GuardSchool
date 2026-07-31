#!/usr/bin/env python3
"""Проверка: в open-core сборке не должно быть закрытых модулей из manifest (CI/release)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = Path(__file__).resolve().parent / "private_modules_manifest.json"


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    paths: list[str] = []
    for section in ("saas", "commercial"):
        block = data.get(section) or {}
        paths.extend(block.get("python_modules") or [])
    present = [p for p in paths if (ROOT / p).is_file()]
    if not present:
        print("open-core bundle OK: private modules not in tree")
        return 0
    print("open-core bundle check FAILED — remove or exclude:", file=sys.stderr)
    for p in present:
        print(f"  {p}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
