"""Admin API: школьные новости (CRUD, обложка, галерея)."""
from __future__ import annotations

import re
import secrets
from typing import Any
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, Body, File, Form, HTTPException, Request, UploadFile

from .gs_auth import require_auth
from .gs_jsonio import write_json
from .gs_paths import SCHOOL_NEWS_PATH
from .gs_saas_limits import max_school_news_image_bytes
from .gs_school_news import (
    extract_school_news_local_upload_urls as _extract_school_news_local_upload_urls,
    load_school_news,
    safe_unlink_school_news_upload_url as _safe_unlink_upload_url,
    sanitize_school_news_item,
    save_school_news_image_bytes as _save_school_news_image_bytes,
)

router = APIRouter(tags=["admin"])


@router.get("/api/admin/school-news")
def get_admin_school_news(request: Request) -> dict[str, Any]:
    require_auth(request)
    return {"items": load_school_news()}


@router.post("/api/admin/school-news")
async def save_admin_school_news(request: Request, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    require_auth(request)
    rows = load_school_news()
    nid = str(payload.get("id") or "").strip()
    item = sanitize_school_news_item(payload, fallback_id=nid or secrets.token_hex(6))
    replaced = False
    if nid:
        for i, row in enumerate(rows):
            if str(row.get("id") or "") == nid:
                rows[i] = item
                replaced = True
                break
    if not replaced:
        rows.append(item)
    rows.sort(key=lambda x: (str(x.get("created_at") or ""), str(x.get("id") or "")), reverse=True)
    write_json(SCHOOL_NEWS_PATH, rows)
    return {"status": "ok", "item": item, "items": rows}


@router.delete("/api/admin/school-news/{news_id}")
def delete_admin_school_news(request: Request, news_id: str) -> dict[str, Any]:
    require_auth(request)
    nid = str(news_id or "").strip()
    if not nid:
        raise HTTPException(status_code=400, detail="Не указан id новости.")
    existing = load_school_news()
    deleted = next((x for x in existing if str(x.get("id") or "") == nid), None)
    rows = [item for item in existing if str(item.get("id") or "") != nid]
    write_json(SCHOOL_NEWS_PATH, rows)
    try:
        if deleted:
            _safe_unlink_upload_url(str(deleted.get("cover_image") or ""))
            for u in deleted.get("gallery_images") or []:
                _safe_unlink_upload_url(str(u))
            for u in _extract_school_news_local_upload_urls(str(deleted.get("content") or "")):
                _safe_unlink_upload_url(u)
    except Exception:
        pass
    return {"status": "ok", "items": rows}


@router.post("/api/admin/school-news/cover-upload")
async def admin_school_news_cover_upload(
    request: Request,
    file: UploadFile = File(...),
    news_id: str = Form(default=""),
) -> dict[str, Any]:
    require_auth(request)
    nid = str(news_id or "").strip()[:64] or secrets.token_hex(6)
    raw = await file.read()
    url = _save_school_news_image_bytes(
        nid,
        raw,
        content_type=file.content_type,
        source_name=file.filename or "",
    )
    return {"status": "ok", "news_id": nid, "url": url}


@router.post("/api/admin/school-news/cover-fetch")
async def admin_school_news_cover_fetch(
    request: Request,
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    require_auth(request)
    url_raw = str(payload.get("url") or "").strip()
    if not re.fullmatch(r"(?i)https?://.{6,500}", url_raw):
        raise HTTPException(status_code=400, detail="Неверный URL (нужен http/https).")
    nid = str(payload.get("news_id") or "").strip()[:64] or secrets.token_hex(6)
    try:
        req = UrlRequest(url_raw, headers={"User-Agent": "GuardSchool/1.0"})
        with urlopen(req, timeout=8) as resp:
            ct = str(resp.headers.get("Content-Type") or "").strip()
            data = resp.read(max_school_news_image_bytes() + 1)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Не удалось загрузить картинку: {e}")
    url = _save_school_news_image_bytes(nid, data, content_type=ct, source_name=url_raw)
    return {"status": "ok", "news_id": nid, "url": url}


@router.post("/api/admin/school-news/gallery-upload")
async def admin_school_news_gallery_upload(
    request: Request,
    file: UploadFile = File(...),
    news_id: str = Form(default=""),
) -> dict[str, Any]:
    """То же хранение, что обложка; URL подставляется в нужный слот галереи на клиенте."""
    require_auth(request)
    nid = str(news_id or "").strip()[:64] or secrets.token_hex(6)
    raw = await file.read()
    url = _save_school_news_image_bytes(
        nid,
        raw,
        content_type=file.content_type,
        source_name=file.filename or "",
    )
    return {"status": "ok", "news_id": nid, "url": url}


@router.post("/api/admin/school-news/gallery-fetch")
async def admin_school_news_gallery_fetch(
    request: Request,
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    require_auth(request)
    url_raw = str(payload.get("url") or "").strip()
    if not re.fullmatch(r"(?i)https?://.{6,500}", url_raw):
        raise HTTPException(status_code=400, detail="Неверный URL (нужен http/https).")
    nid = str(payload.get("news_id") or "").strip()[:64] or secrets.token_hex(6)
    try:
        req = UrlRequest(url_raw, headers={"User-Agent": "GuardSchool/1.0"})
        with urlopen(req, timeout=8) as resp:
            ct = str(resp.headers.get("Content-Type") or "").strip()
            data = resp.read(max_school_news_image_bytes() + 1)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Не удалось загрузить картинку: {e}")
    url = _save_school_news_image_bytes(nid, data, content_type=ct, source_name=url_raw)
    return {"status": "ok", "news_id": nid, "url": url}
