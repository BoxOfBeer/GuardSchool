"""Extract HTML page routes from app.py to routes_pages.py."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "guardschool" / "app.py"
lines = APP.read_text(encoding="utf-8").splitlines(keepends=True)


def sl(s: int, e: int) -> str:
    return "".join(lines[s - 1 : e])


def main() -> None:
    # Find line numbers dynamically
    text = "".join(lines)
    chunks = []
    for start_marker, end_marker in [
        ('@app.get("/uploads/', '@app.get("/sw.js")'),
        ('@app.get("/sw.js")', '@app.get("/", response_class=HTMLResponse)'),
        ('@app.get("/", response_class=HTMLResponse)', '@app.get("/api/version")'),
    ]:
        i = text.find(start_marker)
        j = text.find(end_marker, i + 1)
        if i < 0 or j < 0:
            raise SystemExit(f"markers not found: {start_marker}")
        # line numbers
        before = text[:i]
        s = before.count("\n") + 1
        before_j = text[:j]
        e = before_j.count("\n")
        chunk = sl(s, e)
        chunks.append(chunk)

    # Also need _tenant_upload and _demo_middleware before uploads
    demo_start = text.find("def _demo_middleware_binding_slug")
    upload_start = text.find("def _tenant_upload_local_file")
    uploads_route = text.find('@app.get("/uploads/')
    if demo_start >= 0 and upload_start >= 0:
        s = text[:demo_start].count("\n") + 1
        e = text[:uploads_route].count("\n")
        helper = sl(s, e)
    else:
        helper = sl(
            text.find("def _tenant_upload_local_file") and 0 or 1,
            0,
        )

    # Simpler: use known line numbers from grep after patch
    helper = sl(
        next(i for i, L in enumerate(lines, 1) if "def _demo_middleware_binding_slug" in L),
        next(i for i, L in enumerate(lines, 1) if '@app.get("/uploads/' in L) - 1,
    )
    pages = ""
    for s, e in [
        (
            next(i for i, L in enumerate(lines, 1) if '@app.get("/uploads/' in L),
            next(i for i, L in enumerate(lines, 1) if '@app.get("/screens"' in L) + 8,
        ),
    ]:
        pages += sl(s, e)

    pages = pages.replace("@app.get(", "@router.get(")
    pages = pages.replace("@app.post(", "@router.post(")

    hdr = '''"""HTML pages and static-adjacent routes (/, /screen, /uploads, sw.js)."""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

router = APIRouter(tags=["pages"])


def register_page_routes(app) -> None:
    app.include_router(router)


def _app():
    from guardschool import app as m
    return m


def __getattr__(name: str) -> Any:
    return getattr(_app(), name)


'''
    body = helper + pages
    (ROOT / "guardschool" / "routes_pages.py").write_text(hdr + body, encoding="utf-8")
    print("routes_pages OK", body.count("\n"))


if __name__ == "__main__":
    main()
