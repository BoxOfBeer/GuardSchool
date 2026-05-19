"""Community stub: портал CMS — минимальные defaults, без полного редактора."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .gs_paths import PORTAL_CMS_PATH


def default_portal_cms() -> dict[str, Any]:
    return {
        "version": 2,
        "meta": {
            "page_title": "GuardDoc",
            "description": "",
            "portal_public_url": "https://guarddoc.ru",
        },
        "shell": {"nav_title": "GuardDoc", "nav_subtitle": "", "nav": [], "about_program": {"title": "", "paragraphs": []}},
        "hero": {"brand": "GuardDoc", "title": "", "lead": ""},
        "pages": {},
    }


def load_portal_cms_merged() -> dict[str, Any]:
    path: Path = PORTAL_CMS_PATH
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
        except Exception:
            pass
    return deepcopy(default_portal_cms())


def sanitize_portal_cms_payload(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return deepcopy(default_portal_cms())
    out = deepcopy(default_portal_cms())
    if isinstance(raw.get("meta"), dict):
        out["meta"] = {**out.get("meta", {}), **raw["meta"]}
    return out


def write_portal_cms(payload: dict[str, Any]) -> None:
    """Community: запись только если файл уже есть (локальная правка)."""
    path: Path = PORTAL_CMS_PATH
    if not path.parent.is_dir():
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        return
