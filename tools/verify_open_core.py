#!/usr/bin/env python3
"""CI: собрать open-core tree, проверить импорт app и unit-тесты community mode."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    out = Path(tempfile.mkdtemp(prefix="gs-open-core-verify-"))
    print(f"Building open-core tree in {out}")
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build_open_core_tree.py"), "--out", str(out), "--force"],
        cwd=ROOT,
    )
    if r.returncode != 0:
        return r.returncode
    r2 = subprocess.run([sys.executable, str(out / "tools" / "check_open_core_bundle.py")], cwd=out)
    if r2.returncode != 0:
        return r2.returncode
    env = os.environ.copy()
    env["GUARDSCHOOL_DEPLOYMENT_MODE"] = "local"
    env.pop("GUARDSCHOOL_LAYER_PATH", None)
    env.pop("GUARDSCHOOL_SAAS_DATABASE_URL", None)
    env["PYTHONPATH"] = str(out)
    r3 = subprocess.run(
        [
            sys.executable,
            "-c",
            "from guardschool.app import app; assert app.title == 'GuardSchool'",
        ],
        cwd=out,
        env=env,
    )
    if r3.returncode != 0:
        return r3.returncode
    r4 = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_community_local_mode",
            "tests.test_community_commercial",
            "tests.test_routes_separation",
            "-q",
        ],
        cwd=out,
        env=env,
    )
    print("verify_open_core: OK" if r4.returncode == 0 else "verify_open_core: tests failed")
    return r4.returncode


if __name__ == "__main__":
    raise SystemExit(main())
