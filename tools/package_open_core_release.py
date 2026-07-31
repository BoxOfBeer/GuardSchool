#!/usr/bin/env python3
"""
Собрать open-core дерево и упаковать в .tar.gz (и .zip на Windows).

Пример:
  python tools/package_open_core_release.py --out dist
  python tools/package_open_core_release.py --tree-only /tmp/gs-oc
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "tools" / "build_open_core_tree.py"
MANIFEST = ROOT / "tools" / "private_modules_manifest.json"


def _read_app_version(tree: Path) -> str:
    text = (tree / "guardschool" / "gs_paths.py").read_text(encoding="utf-8")
    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', text)
    return m.group(1) if m else "0.0.0"


def _write_release_notes(tree: Path, version: str, excluded: list[str]) -> None:
    lines = [
        f"GuardSchool open-core {version}",
        "",
        "Сборка без закрытых *_pg.py (см. tools/private_modules_manifest.json).",
        f"Исключено файлов: {len(excluded)}",
        "",
    ]
    for p in sorted(excluded):
        lines.append(f"  - {p}")
    (tree / "OPEN_CORE_BUILD.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_tree(out: Path, *, force: bool) -> list[str]:
    if out.exists():
        if not force:
            raise SystemExit(f"Output exists: {out} (use --force)")
        shutil.rmtree(out)
    r = subprocess.run(
        [sys.executable, str(BUILD), "--out", str(out), "--force"],
        cwd=ROOT,
    )
    if r.returncode != 0:
        raise SystemExit(r.returncode)
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    excluded: list[str] = []
    for section in ("saas", "commercial"):
        excluded.extend((data.get(section) or {}).get("python_modules") or [])
    _write_release_notes(out, _read_app_version(out), excluded)
    r2 = subprocess.run([sys.executable, str(out / "tools" / "check_open_core_bundle.py")], cwd=out)
    if r2.returncode != 0:
        raise SystemExit("check_open_core_bundle failed on built tree")
    return excluded


def package_archives(tree: Path, dist: Path, version: str) -> list[Path]:
    dist.mkdir(parents=True, exist_ok=True)
    base = f"guardschool-open-core-{version}"
    archives: list[Path] = []

    tar_path = dist / f"{base}.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(tree, arcname=base)
    archives.append(tar_path)

    zip_path = dist / f"{base}.zip"
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", root_dir=tree.parent, base_dir=tree.name)
    archives.append(zip_path)
    return archives


def main() -> int:
    ap = argparse.ArgumentParser(description="Build and package open-core release")
    ap.add_argument("--out", default="dist", help="Directory for .tar.gz / .zip (default: dist)")
    ap.add_argument(
        "--tree-only",
        metavar="DIR",
        help="Only build open-core tree into DIR (no archives)",
    )
    ap.add_argument("--force", action="store_true", help="Overwrite output")
    args = ap.parse_args()

    if args.tree_only:
        tree = Path(args.tree_only).resolve()
        build_tree(tree, force=args.force)
        print(f"Open-core tree: {tree}")
        return 0

    dist = Path(args.out).resolve()
    dist.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="gs-oc-staging-"))
    try:
        build_tree(staging, force=True)
        version = _read_app_version(staging)
        named = dist / f"guardschool-open-core-{version}"
        if named.exists():
            shutil.rmtree(named)
        shutil.move(str(staging), str(named))
        archives = package_archives(named, dist, version)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise
    for p in archives:
        print(f"Created: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
