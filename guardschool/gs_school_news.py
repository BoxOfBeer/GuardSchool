"""School news: load/sanitize, image uploads under /uploads/school_news/."""
from __future__ import annotations

import re
import secrets
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .gs_ensure_dirs import ensure_dirs
from .gs_jsonio import read_json
from .gs_paths import SCHOOL_NEWS_PATH, UPLOADS_DIR
from .gs_saas_limits import max_school_news_image_bytes
from .gs_schedule_bells import schedule_date_iso

SCHOOL_NEWS_GALLERY_MAX = 4


def _school_news_image_width_percent(raw: Any) -> int:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = 32
    return max(15, min(55, n))


def _school_news_image_max_height_px(raw: Any) -> int:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = 200
    return max(80, min(400, n))


def sanitize_school_news_display_html(raw: str) -> str:
    """HTML для показа на ТВ/в превью: без script/on*, опасных вставок и гигантских полезных нагрузок."""
    s = str(raw or "").strip()
    if len(s) > 120_000:
        s = s[:120_000]
    s = re.sub(r"(?is)<script[^>]*>.*?</script>", "", s)
    s = re.sub(r"(?is)</?script[^>]*>", "", s)
    s = re.sub(r"(?is)<\s*iframe[^>]*>.*?</iframe>", "", s)
    s = re.sub(r"(?is)<\s*(?:object|embed)[^>]*>.*?</(?:object|embed)>", "", s)
    s = re.sub(r'(?is)on[a-z]+\s*=\s*"[^"]*"', "", s)
    s = re.sub(r"(?is)on[a-z]+\s*=\s*'[^']*'", "", s)
    s = re.sub(r'(?is)\sstyle\s*=\s*"[^"]*"', "", s)
    s = re.sub(r"(?is)\sstyle\s*=\s*'[^']*'", "", s)
    s = re.sub(r'(?is)href\s*=\s*"javascript:[^"]*"', 'href="#"', s)
    s = re.sub(r"(?is)href\s*=\s*'javascript:[^']*'", "href='#'", s)
    return s.strip()


def school_news_text_preview(raw_html: str) -> str:
    """Текст для виджета школьных новостей: без ограничения длины."""
    s = str(raw_html or "")
    # Сохраняем структуру: блоки/переносы превращаем в \n, потом чистим теги.
    s = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", s)
    s = re.sub(r"(?i)</\s*p\s*>", "\n\n", s)
    s = re.sub(r"(?i)</\s*div\s*>", "\n\n", s)
    s = re.sub(r"(?i)</\s*li\s*>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    # Нормализация: пробелы схлопываем, но переносы сохраняем.
    s = re.sub(r"[ \t\f\v]+", " ", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r" +\n", "\n", s)
    return s.strip()


def sanitize_school_news_item(item: dict[str, Any], fallback_id: str = "") -> dict[str, Any]:
    nid = str(item.get("id") or fallback_id or secrets.token_hex(6)).strip()[:64]
    tenant = ""
    try:
        from .tenant_ctx import tenant_slug as _tenant_slug

        tenant = str(_tenant_slug() or "").strip()[:64]
    except Exception:
        tenant = ""
    title = str(item.get("title") or "").strip()[:200]
    content = str(item.get("content") or "").strip()[:50000]
    # Защита от опасного встроенного JS в HTML-контенте новости.
    content = re.sub(r"(?is)<script[^>]*>.*?</script>", "", content)
    content = re.sub(r"(?is)on[a-z]+\s*=\s*\"[^\"]*\"", "", content)
    content = re.sub(r"(?is)on[a-z]+\s*=\s*'[^']*'", "", content)
    cover = sanitize_one_news_image_url(item.get("cover_image"))
    gallery_images = sanitize_gallery_images(item.get("gallery_images"))
    created = schedule_date_iso(item.get("created_at")) or date.today().isoformat()
    active = bool(item.get("is_active", True))
    wrap_raw = item.get("single_image_text_wrap")
    if wrap_raw is None:
        wrap_raw = item.get("singleImageTextWrap")
    single_image_text_wrap = True if wrap_raw is None else bool(wrap_raw)
    width_raw = item.get("image_width_percent")
    if width_raw is None:
        width_raw = item.get("imageWidthPercent")
    height_raw = item.get("image_max_height_px")
    if height_raw is None:
        height_raw = item.get("imageMaxHeightPx")
    out = {
        "id": nid,
        "tenant_id": tenant or str(item.get("tenant_id") or "").strip()[:64],
        "title": title,
        "content": content,
        "cover_image": cover,
        "gallery_images": gallery_images,
        "created_at": created,
        "is_active": active,
        "image_width_percent": _school_news_image_width_percent(width_raw),
        "image_max_height_px": _school_news_image_max_height_px(height_raw),
        "single_image_text_wrap": single_image_text_wrap,
    }
    out["summary"] = school_news_text_preview(content)
    out["display_html"] = sanitize_school_news_display_html(content)
    return out


def load_school_news() -> list[dict[str, Any]]:
    raw = read_json(SCHOOL_NEWS_PATH, [])
    out: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for idx, item in enumerate(raw):
            if isinstance(item, dict):
                out.append(sanitize_school_news_item(item, fallback_id=f"news_{idx + 1}"))
    out.sort(key=lambda x: (str(x.get("created_at") or ""), str(x.get("id") or "")), reverse=True)
    return out


def school_news_uploads_dir() -> Path:
    from .tenant_ctx import map_data_path

    return map_data_path(UPLOADS_DIR / "school_news")


def safe_unlink_school_news_upload_url(url: str) -> None:
    """
    Удаляем только локальные файлы в data/uploads/school_news/*.
    URL должен быть вида /uploads/school_news/<name>.
    """
    u = str(url or "").strip()
    if not u.startswith("/uploads/school_news/"):
        return
    name = u.split("/uploads/school_news/", 1)[1].strip().lstrip("/").split("?", 1)[0]
    if not name or "/" in name or "\\" in name:
        return
    base = school_news_uploads_dir()
    try:
        p = (base / name).resolve()
        if base.resolve() in p.parents and p.is_file():
            p.unlink(missing_ok=True)
    except Exception:
        return


SCHOOL_NEWS_GALLERY_MAX = 4


def sanitize_one_news_image_url(url: str) -> str:
    u = str(url or "").strip()[:500]
    if not u:
        return ""
    if u.startswith("/uploads/"):
        return u
    if re.fullmatch(r"(?i)https?://.{6,500}", u):
        return u
    return ""


def sanitize_gallery_images(raw: Any) -> list[str]:
    out: list[str] = []
    if isinstance(raw, list):
        for x in raw:
            if len(out) >= SCHOOL_NEWS_GALLERY_MAX:
                break
            s = sanitize_one_news_image_url(x)
            if s:
                out.append(s)
    return out


def extract_school_news_local_upload_urls(content_html: str) -> set[str]:
    s = str(content_html or "")
    out: set[str] = set()
    for m in re.finditer(r"(/uploads/school_news/[A-Za-z0-9._-]{1,180})", s):
        out.add(m.group(1))
    return out


def save_school_news_image_bytes(news_id: str, data: bytes, content_type: str | None = None, source_name: str = "") -> str:
    if not data:
        raise HTTPException(status_code=400, detail="Пустой файл.")
    lim = max_school_news_image_bytes()
    if len(data) > lim:
        mb = round(lim / (1024 * 1024), 1)
        raise HTTPException(
            status_code=413,
            detail=(
                f"Файл слишком большой ({len(data)} байт), максимум {lim} (~{mb} МиБ). "
                "Уменьшите изображение, задайте GUARDSCHOOL_SCHOOL_NEWS_IMAGE_MAX_BYTES или увеличьте client_max_body_size на nginx."
            ),
        )
    ensure_dirs()
    base = school_news_uploads_dir()
    base.mkdir(parents=True, exist_ok=True)
    nid = re.sub(r"[^A-Za-z0-9_-]+", "_", str(news_id or "").strip())[:64] or secrets.token_hex(6)
    ext = ""
    ct = (content_type or "").lower().strip()
    if "png" in ct:
        ext = ".png"
    elif "jpeg" in ct or "jpg" in ct:
        ext = ".jpg"
    elif "webp" in ct:
        ext = ".webp"
    elif "gif" in ct:
        ext = ".gif"
    if not ext:
        sn = str(source_name or "").lower()
        m = re.search(r"\.(png|jpg|jpeg|webp|gif)(?:\?|$)", sn)
        if m:
            ext = ".jpg" if m.group(1) in ("jpg", "jpeg") else f".{m.group(1)}"
    if not ext:
        ext = ".jpg"
    # Максимальная совместимость с ТВ: стараемся перекодировать в baseline JPEG (без прогрессива/CMYK).
    try:
        import io

        from PIL import Image  # type: ignore

        try:
            img = Image.open(io.BytesIO(data))
            img.load()
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            elif img.mode == "L":
                img = img.convert("RGB")
            out = io.BytesIO()
            quality = 85
            best = None
            while quality >= 50:
                out.seek(0)
                out.truncate(0)
                img.save(out, format="JPEG", quality=quality, optimize=True, progressive=False)
                b = out.getvalue()
                best = b
                if len(b) <= lim:
                    break
                quality -= 10
            if best:
                data = best
                ext = ".jpg"
        except Exception:
            pass
    except Exception:
        pass

    if len(data) > lim:
        mb = round(lim / (1024 * 1024), 1)
        raise HTTPException(
            status_code=413,
            detail=(
                f"После обработки изображение всё ещё больше лимита {lim} байт (~{mb} МиБ). "
                "Загрузите файл меньшего разрешения или увеличьте GUARDSCHOOL_SCHOOL_NEWS_IMAGE_MAX_BYTES."
            ),
        )

    fn = f"{nid}_{secrets.token_hex(4)}{ext}"
    (base / fn).write_bytes(data)
    return f"/uploads/school_news/{fn}"
