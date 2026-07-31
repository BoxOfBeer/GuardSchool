"""Проверки для GET /api/health (без FastAPI)."""
from __future__ import annotations

import secrets
from pathlib import Path

from .gs_deploy import deployment_mode
from .gs_paths import APP_VERSION, DATA_DIR
from .tenant_ctx import map_data_path


def probe_data_dir_writable() -> bool:
    data_dir = map_data_path(DATA_DIR)
    probe = data_dir / f".health_probe_{secrets.token_hex(8)}"
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        try:
            if probe.is_file():
                probe.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def health_payload() -> dict[str, str | bool]:
    writable = probe_data_dir_writable()
    return {
        "status": "ok" if writable else "degraded",
        "product": "GuardSchool",
        "version": APP_VERSION,
        "deployment_mode": deployment_mode(),
        "data_dir_writable": writable,
    }
