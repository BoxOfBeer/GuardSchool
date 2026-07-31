"""Иконки local/community PWA manifest без ложных значений sizes."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote, unquote

from .gs_paths import STATIC_DIR, UPLOADS_DIR

_DEFAULT_ICON_512 = "/static/pwa/icon_default.png"
_DEFAULT_ICON_192 = "/static/pwa/icon_default_192.png"


def _path_inside(base: Path, candidate: Path) -> bool:
    try:
        base_r = base.resolve()
        candidate_r = candidate.resolve()
        return candidate_r == base_r or base_r in candidate_r.parents
    except Exception:
        return False


def _clean_public_icon_url(icon_url: str) -> str:
    raw = str(icon_url or "").strip().split("?", 1)[0].split("#", 1)[0]
    if raw and not raw.startswith("/") and raw.lower().startswith(("static/", "uploads/")):
        raw = "/" + raw
    return raw


def _resolve_public_icon(icon_url: str) -> tuple[Path | None, bool]:
    """Возвращает локальный файл и признак writable uploads."""
    clean = _clean_public_icon_url(icon_url)
    base: Path
    rel: str
    writable = False
    if clean.startswith("/static/"):
        base = STATIC_DIR.resolve()
        rel = clean[len("/static/") :]
    elif clean.startswith("/uploads/"):
        try:
            from .tenant_ctx import map_data_path

            base = map_data_path(UPLOADS_DIR).resolve()
        except Exception:
            base = UPLOADS_DIR.resolve()
        rel = clean[len("/uploads/") :]
        writable = True
    else:
        return None, False
    parts = [unquote(p) for p in rel.split("/") if p and p not in (".", "..")]
    if not parts or len(parts) != len([p for p in rel.split("/") if p]):
        return None, False
    candidate = base.joinpath(*parts).resolve()
    if not _path_inside(base, candidate) or not candidate.is_file():
        return None, writable
    return candidate, writable


def _raster_mime(icon_url: str) -> str:
    low = _clean_public_icon_url(icon_url).lower()
    if low.endswith(".webp"):
        return "image/webp"
    if low.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    return "image/png"


def _image_size(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image

        with Image.open(path) as image:
            width, height = image.size
        if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
            return width, height
    except Exception:
        pass
    return None


def _variant_url(icon_url: str, filename: str) -> str:
    clean = _clean_public_icon_url(icon_url)
    parent = clean.rsplit("/", 1)[0]
    return f"{parent}/{quote(filename)}"


def _ensure_square_png_variant(source: Path, size: int) -> Path | None:
    """Создаёт рядом безопасную квадратную PNG-копию с прозрачными полями."""
    destination = source.with_name(f"{source.stem}_gs_pwa{size}.png")
    if not _path_inside(source.parent, destination):
        return None
    try:
        fresh = destination.is_file() and destination.stat().st_mtime >= source.stat().st_mtime
    except OSError:
        fresh = False
    if fresh and _image_size(destination) == (size, size):
        return destination
    temporary = destination.with_name(destination.name + ".tmp")
    try:
        from PIL import Image

        with Image.open(source) as image:
            converted = image.convert("RGBA")
            converted.thumbnail((size, size), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            left = (size - converted.width) // 2
            top = (size - converted.height) // 2
            canvas.alpha_composite(converted, (left, top))
            canvas.save(temporary, format="PNG", optimize=True)
        temporary.replace(destination)
        return destination if _image_size(destination) == (size, size) else None
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def local_manifest_icon_entries(icon_url: str) -> list[dict[str, str]]:
    """Формирует icons[] для local manifest и никогда не выдумывает размер растра."""
    clean = _clean_public_icon_url(icon_url) or _DEFAULT_ICON_512
    low = clean.lower()
    if low.endswith((".svg", ".svgz")):
        return [{"src": clean, "sizes": "any", "type": "image/svg+xml", "purpose": "any"}]
    if low.endswith(".ico"):
        return [{"src": clean, "sizes": "any", "type": "image/x-icon", "purpose": "any"}]
    if low == _DEFAULT_ICON_512:
        return [
            {"src": _DEFAULT_ICON_192, "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": _DEFAULT_ICON_512, "sizes": "512x512", "type": "image/png", "purpose": "any"},
        ]

    mime = _raster_mime(clean)
    source, writable = _resolve_public_icon(clean)
    if source is None:
        return [{"src": clean, "sizes": "any", "type": mime, "purpose": "any"}]

    if writable:
        variants: list[dict[str, str]] = []
        for size in (192, 512):
            variant = _ensure_square_png_variant(source, size)
            if variant is not None:
                variants.append(
                    {
                        "src": _variant_url(clean, variant.name),
                        "sizes": f"{size}x{size}",
                        "type": "image/png",
                        "purpose": "any",
                    }
                )
        if len(variants) == 2:
            return variants
    else:
        variants = []

    actual = _image_size(source)
    original = {
        "src": clean,
        "sizes": f"{actual[0]}x{actual[1]}" if actual else "any",
        "type": mime,
        "purpose": "any",
    }
    return variants + [original]
