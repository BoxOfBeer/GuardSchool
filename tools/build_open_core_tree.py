#!/usr/bin/env python3
"""
Собрать open-core копию репозитория без закрытых *_pg.py и routes из manifest.

Пример:
  python tools/build_open_core_tree.py --out ../GuardSchool-open-core
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = Path(__file__).resolve().parent / "private_modules_manifest.json"

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    "tenants",
    "data",
    "dist",
}


def _collect_exclude_paths(data: dict) -> set[Path]:
    out: set[Path] = set()
    for section in ("saas", "commercial"):
        block = data.get(section) or {}
        for rel in block.get("python_modules") or []:
            out.add(ROOT / rel.replace("/", "\\") if "\\" in str(ROOT) else ROOT / rel)
    # normalize
    return {p.resolve() for p in out}


def _should_skip_dir(name: str) -> bool:
    return name in SKIP_DIR_NAMES or name.endswith(".egg-info")


def copy_tree(src: Path, dst: Path, exclude_files: set[Path]) -> list[str]:
    """Копия без обхода .git и прочих SKIP_DIR_NAMES (os.walk с pruning)."""
    removed: list[str] = []
    for dirpath, dirnames, filenames in os.walk(src, topdown=True):
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
        for fn in filenames:
            path = Path(dirpath) / fn
            rel = path.relative_to(src)
            if path.resolve() in exclude_files:
                removed.append(str(rel).replace("\\", "/"))
                continue
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    return removed


def main() -> int:
    ap = argparse.ArgumentParser(description="Build open-core tree without private modules")
    ap.add_argument("--out", required=True, help="Output directory (will be created)")
    ap.add_argument("--force", action="store_true", help="Remove output dir if exists")
    args = ap.parse_args()
    out = Path(args.out).resolve()
    if out.exists():
        if not args.force:
            print(f"Output exists: {out} (use --force)", flush=True)
            return 1
        shutil.rmtree(out)
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    exclude = _collect_exclude_paths(data)
    out.mkdir(parents=True, exist_ok=True)
    removed = copy_tree(ROOT, out, exclude)
    print(f"Open-core tree: {out}")
    print(f"Excluded {len(removed)} private files")
    for line in sorted(removed)[:20]:
        print(f"  - {line}")
    if len(removed) > 20:
        print(f"  ... and {len(removed) - 20} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
