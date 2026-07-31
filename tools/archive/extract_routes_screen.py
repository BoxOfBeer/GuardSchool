"""Extract screen API routes into routes_screen.py; fix routes_admin checkin split."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
app_path = ROOT / "guardschool" / "app.py"
admin_path = ROOT / "guardschool" / "routes_admin.py"
lines = app_path.read_text(encoding="utf-8").splitlines(keepends=True)
admin_lines = admin_path.read_text(encoding="utf-8").splitlines(keepends=True)


def slice_lines(src: list[str], start: int, end: int) -> str:
    return "".join(src[start - 1 : end])


def build_screen() -> None:
    body = slice_lines(lines, 3235, 3458)
    body = body.replace("@app.get(", "@router.get(")
    body = body.replace("@app.post(", "@router.post(")
    # Screen checkin confirm block from routes_admin (lines 833-953 approx)
    chk = slice_lines(admin_lines, 833, 953)
    header = '''"""Screen/TV JSON API and check-in routes. Open-core."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

_log = logging.getLogger(__name__)
router = APIRouter(tags=["screen"])


def register_screen_routes(app) -> None:
    app.include_router(router)


def _app():
    from guardschool import app as app_module

    return app_module


def __getattr__(name: str) -> Any:
    return getattr(_app(), name)


'''
    out = ROOT / "guardschool" / "routes_screen.py"
    out.write_text(header + body + chk, encoding="utf-8")
    print("Wrote", out)


def fix_admin() -> None:
    text = admin_path.read_text(encoding="utf-8")
    # Remove screen checkin block (from _checkin_tenant through events-status handler end)
    start = text.find("def _checkin_tenant_from_request")
    end = text.find("@router.post(\"/api/admin/checkin/confirm\")")
    if start == -1 or end == -1:
        raise SystemExit("admin split markers not found")
    text = text[:start] + text[end:]
    # Fix broken admin events-status decorator
    orphan_body = slice_lines(lines, 3461, 3496)
    orphan_body = orphan_body.replace("def api_admin_checkin_events_status", "@router.get(\"/api/admin/checkin/events-status\")\ndef api_admin_checkin_events_status")
    broken = '@router.get("/api/admin/checkin/events-status")\n\n@router.get("/api/admin/screen-watch")'
    text = text.replace(broken, orphan_body + "\n\n@router.get(\"/api/admin/screen-watch\")")
    admin_path.write_text(text, encoding="utf-8")
    print("Fixed routes_admin.py")


if __name__ == "__main__":
    build_screen()
    fix_admin()
