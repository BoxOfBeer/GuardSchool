"""Сканирование data/uploads для фона ТВ и безопасные относительные пути подпапок."""
from __future__ import annotations

from typing import Any

from .gs_ensure_dirs import ensure_dirs
from .gs_paths import (
    BACKGROUND_UPLOAD_IMAGE_SUFFIXES,
    UPLOADS_DIR,
    WIDGET_IMAGES_SUBDIR,
)
from .tenant_ctx import map_data_path


def safe_rel_uploads_subdir(raw: Any) -> str:
    s = str(raw or "").strip().replace("\\", "/").strip("/")
    if not s or s in (".",):
        return ""
    parts = [p for p in s.split("/") if p and p not in (".", "..")]
    if not parts:
        return ""
    return "/".join(parts)[:120]


def list_background_images_from_uploads(subdir: str = "") -> list[str]:
    """Публичные URL изображений в data/uploads/<subdir> (bells не используем)."""
    ensure_dirs()
    rel = safe_rel_uploads_subdir(subdir)
    uploads = map_data_path(UPLOADS_DIR)
    base = uploads / rel if rel else uploads
    if not base.is_dir():
        return []
    names: list[str] = []
    for p in base.iterdir():
        if not p.is_file():
            continue
        if p.name.startswith("."):
            continue
        if p.suffix.lower() not in BACKGROUND_UPLOAD_IMAGE_SUFFIXES:
            continue
        names.append(p.name)
    names.sort(key=str.lower)
    prefix = f"/uploads/{rel}/" if rel else "/uploads/"
    return [f"{prefix}{n}" for n in names]


def list_background_subdirs_from_uploads() -> list[str]:
    """Список подпапок в uploads, где есть хотя бы 1 картинка. Корень обозначается пустой строкой."""
    ensure_dirs()
    out: set[str] = set()
    if any(list_background_images_from_uploads("")):
        out.add("")
    uploads = map_data_path(UPLOADS_DIR)
    if not uploads.is_dir():
        return [""]
    for p in uploads.iterdir():
        if not p.is_dir():
            continue
        if p.name.startswith(".") or p.name.lower() == "bells" or p.name.lower() == WIDGET_IMAGES_SUBDIR:
            continue
        rel = p.name
        if list_background_images_from_uploads(rel):
            out.add(rel)
    rest = sorted([x for x in out if x], key=str.lower)
    return ["", *rest]
