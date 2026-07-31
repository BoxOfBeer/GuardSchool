"""Extract /api/admin/* handlers from app.py into routes_admin.py."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
app_path = ROOT / "guardschool" / "app.py"
lines = app_path.read_text(encoding="utf-8").splitlines(keepends=True)


def slice_lines(start: int, end: int) -> str:
    return "".join(lines[start - 1 : end])


def build() -> None:
    chunks = [
        (3149, 3705),
        (3788, 3969),
        (4198, 4455),
        (4842, 4852),
    ]
    body = ""
    for s, e in chunks:
        body += slice_lines(s, e) + "\n"
    body = body.replace("@app.get(", "@router.get(")
    body = body.replace("@app.post(", "@router.post(")
    body = body.replace("@app.delete(", "@router.delete(")

    header = '''"""Admin HTTP API (/api/admin/*). Open-core, монтируется из app.py."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import (
    APIRouter,
    Body,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse

_log = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])


def register_admin_routes(app) -> None:
    app.include_router(router)


def _app():
    """Lazy access to app module (handlers/config helpers live there until further split)."""
    from guardschool import app as app_module

    return app_module


def __getattr__(name: str) -> Any:
    """Delegate missing names to guardschool.app (load_config, build_schedule_payload, …)."""
    return getattr(_app(), name)


'''
    out = ROOT / "guardschool" / "routes_admin.py"
    out.write_text(header + body, encoding="utf-8")
    print("Wrote", out, "lines", (header + body).count("\\n"))


if __name__ == "__main__":
    build()
