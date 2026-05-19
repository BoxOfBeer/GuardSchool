"""PWA webmanifest routes and helpers (SaaS tv-pair + local /pwa/screen)."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .gs_admin_http import session_cookie_secure
from .gs_deploy import deployment_mode
from .gs_paths import APP_VERSION, SAAS_TENANT_COOKIE, UPLOADS_DIR, WIDGET_IMAGES_SUBDIR
from .gs_tv_screen_api import (
    canonical_tv_school_code as _canonical_tv_school_code,
    encode_saas_tenant_cookie_value as _encode_saas_tenant_cookie_value,
    normalize_screen_slug_for_api as _normalize_screen_slug_for_api,
    normalize_tv_pair_text as _normalize_tv_pair_text,
    screen_api_tenant_slug as _screen_api_tenant_slug,
    tv_path_code_segment as _tv_path_code_segment,
    tv_school_code_compact as _tv_school_code_compact,
)
from .gs_tv_pair import tv_code_plaintext_for_tenant, tv_token_active_tenant
from .saas_db import connect_public, saas_db_enabled, tv_code_hash, tv_device_token_hash, utcnow
from .tenant_ctx import set_tenant_slug

_log = logging.getLogger(__name__)
router = APIRouter(tags=["pwa-manifest"])


def register_routes(app: FastAPI) -> None:
    app.include_router(router)


def load_config() -> dict[str, Any]:
    from .gs_app_config import load_config as _load_config

    return _load_config()


def _pwa_manifest_resolve_tenant_slug(request: Request, screen_slug_norm: str) -> str | None:
    """Тенант для PWA-manifest: контекст/cookie, иначе ?gs_tv_token= + slug (SaaS). Non-SaaS — не None."""
    if deployment_mode() != "saas":
        return _screen_api_tenant_slug(request) or "local"
    resolved = _screen_api_tenant_slug(request)
    if resolved and resolved != "local":
        return resolved
    tok = str(request.query_params.get("gs_tv_token") or "").strip()
    if not tok or not saas_db_enabled():
        return None
    slug_key = (screen_slug_norm or "").strip().lower()
    if not slug_key:
        return None
    try:
        th = tv_device_token_hash(tok)
        now = utcnow()
        with connect_public() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tenant_slug, status, expires_at FROM tv_devices
                    WHERE token_hash=%s AND lower(trim(screen_slug))=%s
                    """,
                    (th, slug_key),
                )
                row = cur.fetchone()
        if not row:
            return None
        tenant_from_device, status, expires_at = row[0], row[1], row[2]
        if status != "active":
            return None
        if expires_at is not None and expires_at <= now:
            return None
        out = str(tenant_from_device or "").strip().lower()
        return out or None
    except Exception:
        return None


def _pwa_tv_pair_html_manifest_link(request: Request, code_canon: str, slug_for_manifest: str) -> str:
    slug_key = (slug_for_manifest or "").strip().lower()
    code_key = _canonical_tv_school_code(_normalize_tv_pair_text(str(code_canon or "")))
    if not slug_key or not code_key or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", slug_key):
        return ""
    tok_q = str(request.query_params.get("gs_tv_token") or "").strip()
    q_parts = [f"v={quote(APP_VERSION, safe='')}"]
    if tok_q:
        q_parts.insert(0, f"gs_tv_token={quote(tok_q, safe='')}")
    q = "?" + "&".join(q_parts)
    return (
        f'<link rel="manifest" href="/pwa/t/{quote(code_key, safe="")}/'
        f'{quote(slug_key, safe="")}.webmanifest{q}" />\n'
    )


def _pwa_screen_html_manifest_link(request: Request, slug_for_manifest: str) -> str:
    """
    <link rel=manifest> в screen.html до screen.js.
    В SaaS нельзя отдавать /pwa/screen/<slug> — 404; нужен /pwa/t/<код>/<slug>.
    """
    slug_key = (slug_for_manifest or "").strip().lower()
    if not slug_key or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", slug_key):
        return ""
    tok_q = str(request.query_params.get("gs_tv_token") or "").strip()
    q_parts = [f"v={quote(APP_VERSION, safe='')}"]
    if tok_q:
        q_parts.insert(0, f"gs_tv_token={quote(tok_q, safe='')}")
    q = "?" + "&".join(q_parts)
    if deployment_mode() == "saas" and saas_db_enabled():
        tenant = _pwa_manifest_resolve_tenant_slug(request, slug_key)
        if not tenant:
            return ""
        code = _canonical_tv_school_code(_normalize_tv_pair_text(tv_code_plaintext_for_tenant(tenant)))
        if not code:
            return ""
        return _pwa_tv_pair_html_manifest_link(request, code, slug_key)
    return (
        f'<link rel="manifest" href="/pwa/screen/{quote(slug_key, safe="")}.webmanifest{q}" />\n'
    )

def _apply_saas_screen_tenant_from_request(request: Request, slug: str) -> None:
    """Выставить tenant_ctx по gs_tenant / gs_tv_token (картинки /uploads на ТВ)."""
    if deployment_mode() != "saas":
        return
    try:
        explicit_tenant = str(request.query_params.get("gs_tenant") or "").strip().lower()
        if explicit_tenant and 1 <= len(explicit_tenant) <= 64 and explicit_tenant not in ("www", "admin"):
            from .tenant_ctx import set_tenant_slug

            set_tenant_slug(explicit_tenant)
        if not saas_db_enabled():
            return
        tok = str(request.query_params.get("gs_tv_token") or "").strip()
        scr = _normalize_screen_slug_for_api(slug) or str(slug or "").strip().lower()
        if not tok or not scr:
            return
        ts = tv_token_active_tenant(tok, scr)
        if ts:
            from .tenant_ctx import set_tenant_slug

            set_tenant_slug(ts)
    except Exception:
        pass

_TV_ACCESS_BY_CODE_SQL = (
    "SELECT tenant_slug, pin_salt, pin_hash, COALESCE(pin_bypass, false) FROM tv_access "
    "WHERE code_hash=%s "
    "OR lower(trim(coalesce(code_plaintext, '')))=%s "
    "OR regexp_replace(lower(trim(coalesce(code_plaintext, ''))), '[^a-z0-9]', '', 'g')=%s "
    "LIMIT 1"
)


def _normalize_pwa_upload_icon_path(raw: object) -> str | None:
    """
    Поле pwa_icon_url в виджете: нужен путь вида /uploads/..., либо полный URL с таким же путём
    (копируют из браузера). Иначе иконку в manifest не ставим — Chromium не любит произвольные URL.
    """
    cand = str(raw or "").strip()
    if not cand:
        return None
    low = cand.lower()
    if low.startswith("uploads/"):
        cand = "/" + cand
    if cand.startswith("/uploads/"):
        return cand.split("?", 1)[0][:512]
    if low.startswith(("http://", "https://")):
        try:
            path = urlparse(cand).path or ""
            path = path.split("?", 1)[0]
            if path.startswith("/uploads/"):
                return path[:512]
        except Exception:
            return None
    return None


def _pwa_manifest_icon_src_public(request: Request, rel_path: str) -> str:
    """Абсолютный URL иконки: часть клиентов криво резолвит относительные пути к /pwa/*.webmanifest."""
    rp = str(rel_path or "").strip()
    if not rp.startswith("/"):
        return rp
    try:
        return str(request.base_url).rstrip("/") + rp
    except Exception:
        return rp


_PWA_DEFAULT_ICON_REL_512 = "/static/pwa/icon_default.png"
_PWA_DEFAULT_ICON_REL_192 = "/static/pwa/icon_default_192.png"
_WIDGET_PWA_ICON_FILENAME_RE = re.compile(r"^[a-zA-Z0-9._-]{1,220}$")
_PWA_DERIVED_192_MARKER = "_gs_pwa192"
# Если нигде не задан «Название ярлыка (PWA)», всё равно нужен непустой name в manifest (Chrome).
_PWA_MANIFEST_DEFAULT_TITLE = "Приложение"


def _pwa_manifest_json_with_version(manifest: dict[str, Any]) -> dict[str, Any]:
    """Копия тела webmanifest + gs_pwa_manifest_version (=APP_VERSION).

    Меняется при каждом релизе вместе с `?v=` на href манифеста в HTML — браузер чаще подтягивает
    свежий JSON; часть движков учитывает изменения полей манифеста при обновлении установленного PWA.
    Поле не из спецификации W3C — префикс gs_, на клиентов без поддержки не влияет.
    """
    out = dict(manifest)
    out["gs_pwa_manifest_version"] = APP_VERSION
    return out


def _pwa_path_inside_dir_relaxed(base_dir: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(base_dir.resolve())
        return True
    except ValueError:
        return False


def _pwa_widget_uploads_icon_filename(icon_rel_no_query: str) -> str | None:
    """Имя файла в uploads/widget_images/… или None (path traversal отсекаем).

    Допускаем и автокопию «…_gs_pwa192.png» — её иногда подставляют вручную в pwa_icon_url.
    """
    cand = icon_rel_no_query.strip()
    if not cand.startswith("/"):
        if cand.lower().startswith("uploads/"):
            cand = "/" + cand
    prefix = f"/uploads/{WIDGET_IMAGES_SUBDIR}/"
    if cand[: len(prefix)].lower() != prefix.lower():
        return None
    name = cand[len(prefix) :].lstrip("/")
    if not name or "/" in name:
        return None
    if not _WIDGET_PWA_ICON_FILENAME_RE.fullmatch(name):
        return None
    return name


def _pwa_uploads_file_from_rel(icon_rel_no_query: str) -> Path | None:
    """Локальный файл по публичному URL /uploads/... внутри data/uploads (SaaS: map_data_path)."""
    cand = str(icon_rel_no_query or "").strip().split("?", 1)[0]
    if not cand.startswith("/"):
        if cand.lower().startswith("uploads/"):
            cand = "/" + cand
    if not cand.startswith("/uploads/"):
        return None
    rel = cand[len("/uploads/") :].lstrip("/")
    if not rel or ".." in rel.split("/"):
        return None
    parts = [p for p in rel.split("/") if p and p != "."]
    if not parts:
        return None
    try:
        from .tenant_ctx import map_data_path

        root = map_data_path(UPLOADS_DIR).resolve()
        target = root.joinpath(*parts).resolve()
        if not _pwa_path_inside_dir_relaxed(root, target):
            return None
        return target if target.is_file() else None
    except Exception:
        return None


def _pwa_web_path_under_uploads(disk: Path) -> str | None:
    try:
        from .tenant_ctx import map_data_path

        root = map_data_path(UPLOADS_DIR).resolve()
        rel = disk.resolve().relative_to(root).as_posix()
        return "/uploads/" + rel
    except Exception:
        return None


def _pwa_ensure_192_next_to_resolved_file(src: Path) -> str | None:
    """Рядом с любым растром в uploads создаёт/обновляет <stem>_gs_pwa192.png; возвращает публичный /uploads/..."""
    try:
        from .tenant_ctx import map_data_path

        root = map_data_path(UPLOADS_DIR).resolve()
        src_r = src.resolve()
        if not _pwa_path_inside_dir_relaxed(root, src_r) or not src_r.is_file():
            return None
        fs_dir = src_r.parent
        dst = (fs_dir / f"{src_r.stem}{_PWA_DERIVED_192_MARKER}.png").resolve()
        if not _pwa_path_inside_dir_relaxed(fs_dir, dst):
            return None
        need = True
        if dst.is_file():
            try:
                need = src_r.stat().st_mtime > dst.stat().st_mtime
            except OSError:
                need = True
        if need and not _pwa_write_png_192_from_raster(src_r, dst):
            return None
        return _pwa_web_path_under_uploads(dst)
    except Exception:
        return None


def _pwa_neighbor_original_upload_name(fs_dir: Path, derivative_nm: str) -> str | None:
    """Для имени вида foo_gs_pwa192.png находит файл оригинала foo.{png,jpg,...} рядом в каталоге."""
    p = Path(derivative_nm)
    sl = p.stem.lower()
    if not sl.endswith(_PWA_DERIVED_192_MARKER):
        return None
    base_stem = p.stem[: -len(_PWA_DERIVED_192_MARKER)]
    if not base_stem.strip():
        return None
    # Один активный файл с этим префиксом (.png предпочитаем — как после «Загрузить»).
    matches = [
        cand
        for cand in fs_dir.glob(f"{base_stem}.*")
        if cand.is_file() and not cand.stem.lower().endswith(_PWA_DERIVED_192_MARKER)
    ]
    matches.sort(key=lambda c: (c.suffix.lower() != ".png", c.name.lower()))
    return matches[0].name if matches else None


def _pwa_pil_image_size(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image

        with Image.open(path) as im:
            w, h = im.size
            if isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0:
                return (w, h)
    except Exception:
        pass
    return None


def _pwa_write_png_192_from_raster(src: Path, dst: Path) -> bool:
    """Ровно 192×192 PNG — под manifest sizes:«192x192» (intrinsic должны совпадать с объявлением)."""
    try:
        from PIL import Image

        with Image.open(src) as im:
            conv = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
            if conv.mode != "RGBA":
                conv = conv.convert("RGBA")
            sm = conv.resize((192, 192), Image.Resampling.LANCZOS)
        dst.parent.mkdir(parents=True, exist_ok=True)
        sm.save(dst, format="PNG", optimize=True)
        return True
    except Exception:
        try:
            if dst.exists():
                dst.unlink()
        except Exception:
            pass
        return False


def _pwa_ensure_manifest_192_upload_rel(request: Request, icon_rel_clean: str) -> str | None:
    """Копия 192×192 рядом с пользовательским файлом `<stem>_gs_pwa192.png` (обновление при более новой оригинале)."""
    nm = _pwa_widget_uploads_icon_filename(icon_rel_clean)
    if not nm:
        return None
    try:
        from .tenant_ctx import map_data_path

        fs_dir = map_data_path(UPLOADS_DIR / WIDGET_IMAGES_SUBDIR).resolve()
    except Exception:
        return None
    stem_low = Path(nm).stem.lower()
    if stem_low.endswith(_PWA_DERIVED_192_MARKER):
        dst = (fs_dir / nm).resolve()
        if _pwa_path_inside_dir_relaxed(fs_dir, dst) and dst.is_file():
            return f"/uploads/{WIDGET_IMAGES_SUBDIR}/{nm}"
        return None
    src = (fs_dir / nm).resolve()
    if not _pwa_path_inside_dir_relaxed(fs_dir, src) or not src.is_file():
        return None
    dst_nm = f"{src.stem}{_PWA_DERIVED_192_MARKER}.png"
    dst = (fs_dir / dst_nm).resolve()
    if not _pwa_path_inside_dir_relaxed(fs_dir, dst):
        return None
    need = True
    if dst.is_file():
        try:
            need = src.stat().st_mtime > dst.stat().st_mtime
        except OSError:
            need = True
    if need and not _pwa_write_png_192_from_raster(src, dst):
        return None
    return f"/uploads/{WIDGET_IMAGES_SUBDIR}/{dst_nm}"


def _pwa_manifest_mime_for_upload_suffix(filename: str) -> str:
    low = filename.lower()
    if low.endswith(".webp"):
        return "image/webp"
    if low.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    return "image/png"


def _pwa_manifest_raster_icons(
    request: Request | None,
    *,
    icon_rel_clean: str,
    mime: str,
) -> list[dict[str, str]]:
    """
    Chromium: каждая запись icons[] — заявленные пиксели должны совпадать с фактическим размером
    файла по src. Поэтому 192×192 — отдельный URL (копия), а не второй маркёр на файл 512×512.
    """
    if request is None:
        return [
            {"src": icon_rel_clean, "sizes": "any", "type": mime, "purpose": "any"},
        ]
    src_main_pub = _pwa_manifest_icon_src_public(request, icon_rel_clean)
    base_low = icon_rel_clean.lower()
    # Встроенный fallback без загрузки: два статических файла с разными intrinsic.
    if base_low.endswith(_PWA_DEFAULT_ICON_REL_512):
        pub192 = _pwa_manifest_icon_src_public(request, _PWA_DEFAULT_ICON_REL_192)
        pub512 = _pwa_manifest_icon_src_public(request, _PWA_DEFAULT_ICON_REL_512)
        return [
            {"src": pub192, "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": pub512, "sizes": "512x512", "type": "image/png", "purpose": "any"},
        ]

    icons: list[dict[str, str]] = []

    fs_dir: Path | None = None
    try:
        from .tenant_ctx import map_data_path

        fs_dir = map_data_path(UPLOADS_DIR / WIDGET_IMAGES_SUBDIR).resolve()
    except Exception:
        fs_dir = None

    nm = _pwa_widget_uploads_icon_filename(icon_rel_clean)
    path_512: Path | None = None
    path_192: Path | None = None
    path_user: Path | None = None
    fs_eff: Path | None = None
    nm_eff: str | None = None

    if fs_dir and nm:
        cand_u = (fs_dir / nm).resolve()
        if _pwa_path_inside_dir_relaxed(fs_dir, cand_u) and cand_u.is_file():
            path_user = cand_u
            fs_eff = fs_dir
            nm_eff = nm
    if path_user is None:
        cand2 = _pwa_uploads_file_from_rel(icon_rel_clean)
        if cand2 and cand2.is_file():
            path_user = cand2
            fs_eff = path_user.parent.resolve()
            nm_eff = path_user.name

    if path_user is not None and fs_eff is not None and nm_eff:
        stem_low = Path(nm_eff).stem.lower()
        if stem_low.endswith(_PWA_DERIVED_192_MARKER):
            path_192 = path_user
            nm512 = _pwa_neighbor_original_upload_name(fs_eff, nm_eff)
            if nm512:
                cand512 = (fs_eff / nm512).resolve()
                if _pwa_path_inside_dir_relaxed(fs_eff, cand512) and cand512.is_file():
                    path_512 = cand512
        else:
            path_512 = path_user
            rel_gen = _pwa_ensure_manifest_192_upload_rel(request, icon_rel_clean)
            if not rel_gen:
                rel_gen = _pwa_ensure_192_next_to_resolved_file(path_user)
            if rel_gen:
                nm192 = rel_gen.rstrip("/").rsplit("/", 1)[-1]
                cand192 = (fs_eff / nm192).resolve()
                if _pwa_path_inside_dir_relaxed(fs_eff, cand192) and cand192.is_file():
                    path_192 = cand192

    if path_192:
        rel_192 = _pwa_web_path_under_uploads(path_192)
        if rel_192:
            icons.append(
                {
                    "src": _pwa_manifest_icon_src_public(request, rel_192),
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any",
                }
            )

    if path_512:
        nm512_final = path_512.name
        sz = _pwa_pil_image_size(path_512)
        if sz:
            w, h = sz
            mime512 = _pwa_manifest_mime_for_upload_suffix(nm512_final)
            rel_512 = _pwa_web_path_under_uploads(path_512)
            if rel_512:
                icons.append(
                    {
                        "src": _pwa_manifest_icon_src_public(request, rel_512),
                        "sizes": f"{w}x{h}",
                        "type": mime512,
                        "purpose": "any",
                    }
                )

    if icons:
        return icons

    icons.append({"src": src_main_pub, "sizes": "any", "type": mime, "purpose": "any"})
    return icons


def _pwa_manifest_icon_specs(
    icon_rel: str,
    *,
    request: Request | None = None,
) -> tuple[list[dict[str, str]], str]:
    """
    Кортеж: список записей icons[] для manifest, MIME первой записи (для логики не обязательно).

    ICO/SVG — только sizes:any. Для PNG/WebP/JPEG см. _pwa_manifest_raster_icons (раздельный 192px URL).
    """
    icon_rel_clean = (icon_rel or "").split("?", 1)[0].strip()
    src = (
        _pwa_manifest_icon_src_public(request, icon_rel_clean)
        if request is not None
        else str(icon_rel_clean or "")
    )
    base_low = icon_rel_clean.lower()
    if base_low.endswith(".ico"):
        return (
            [{"src": src, "sizes": "any", "type": "image/x-icon", "purpose": "any"}],
            "image/x-icon",
        )
    if base_low.endswith(".svg") or base_low.endswith(".svgz"):
        return (
            [{"src": src, "sizes": "any", "type": "image/svg+xml", "purpose": "any"}],
            "image/svg+xml",
        )
    if base_low.endswith(".webp"):
        mime = "image/webp"
    elif base_low.endswith(".jpg") or base_low.endswith(".jpeg"):
        mime = "image/jpeg"
    else:
        mime = "image/png"
    icons_raster = _pwa_manifest_raster_icons(request, icon_rel_clean=icon_rel_clean, mime=mime)
    return (icons_raster, mime)


def _pwa_manifest_screenshots_entries(request: Request | None) -> list[dict[str, str]]:
    """Скрины для расширенного UI установки: wide (десктоп) и narrow (мобилки). Файлы в /static/pwa/."""
    if request is None:
        return []
    wide = _pwa_manifest_icon_src_public(request, "/static/pwa/screenshot_wide.png")
    narrow = _pwa_manifest_icon_src_public(request, "/static/pwa/screenshot_narrow.png")
    return [
        {
            "src": wide,
            "sizes": "1280x720",
            "type": "image/png",
            "form_factor": "wide",
            "label": "Экран",
        },
        {
            "src": narrow,
            "sizes": "540x720",
            "type": "image/png",
            "form_factor": "narrow",
            "label": "Экран",
        },
    ]


def _pwa_widget_enabled_for_manifest(w: dict[str, Any]) -> bool:
    return isinstance(w, dict) and w.get("enabled") is not False


def _pwa_fallback_pwa_fields_from_widgets(
    visit_all: list[dict[str, Any]],
    *,
    have_title: bool,
    have_icon: bool,
) -> tuple[str, str]:
    """Берём pwa_title / pwa_icon_url из включённых виджетов (админ мог заполнить не у checkin)."""
    if have_title and have_icon:
        return "", ""
    t_out = ""
    i_out = ""
    for w in visit_all:
        if not _pwa_widget_enabled_for_manifest(w):
            continue
        st = w.get("settings") if isinstance(w.get("settings"), dict) else {}
        if not have_title and not t_out:
            pt = str(st.get("pwa_title") or "").strip()[:64]
            if pt:
                t_out = pt
        if not have_icon and not i_out:
            ip = _normalize_pwa_upload_icon_path(st.get("pwa_icon_url"))
            if ip:
                i_out = ip
        if (have_title or t_out) and (have_icon or i_out):
            break
    return t_out, i_out


def _pwa_first_image_widget_icon_url(visit_enabled: list[dict[str, Any]]) -> str:
    """
    Иконка ярлыка из виджета «Изображение»: первая слот-картинка с URL под /uploads/...
    (как у pwa_icon_url — иначе Chromium может отвергнуть иконку).
    """
    for w in visit_enabled:
        if str(w.get("type") or "") != "image":
            continue
        st = w.get("settings") if isinstance(w.get("settings"), dict) else {}
        raw_images = st.get("images")
        if isinstance(raw_images, list):
            for item in raw_images:
                if not isinstance(item, dict):
                    continue
                u = str(item.get("url") or item.get("imageUrl") or "").strip()
                norm = _normalize_pwa_upload_icon_path(u)
                if norm:
                    return norm
        legacy = str(st.get("imageUrl") or "").strip()
        norm = _normalize_pwa_upload_icon_path(legacy)
        if norm:
            return norm
    return ""


def _pwa_widget_title_icon_for_slug(cfg: dict[str, Any], slug_n: str) -> tuple[str, str]:
    """Имя и иконка в webmanifest: checkin (сводка/оперативная) → pwa_* у любых виджетов → изображение (лого) → дефолт."""
    # Дефолт-иконка из статики (всегда 200), не из uploads/ тенанта — иначе 404 и пустой ярлык.
    icon_url = "/static/pwa/icon_default.png"
    slug_key = slug_n.strip().lower()
    tenant_for_log = ""
    try:
        from .tenant_ctx import tenant_slug as _tsl

        tenant_for_log = str(_tsl() or "").strip()
    except Exception:
        tenant_for_log = ""

    screens = cfg.get("screens") if isinstance(cfg, dict) else None
    if not isinstance(screens, list):
        _log.warning(
            "PWA manifest: у тенанта %r нет screens[] в конфиге (slug экрана %r) — name/icon по умолчанию",
            tenant_for_log or "?",
            slug_key,
        )
        return _PWA_MANIFEST_DEFAULT_TITLE[:64], icon_url
    sc = next(
        (
            s
            for s in screens
            if isinstance(s, dict) and str(s.get("slug") or "").strip().lower() == slug_key
        ),
        None,
    )
    if not isinstance(sc, dict):
        know = [
            str(s.get("slug") or "").strip()
            for s in screens
            if isinstance(s, dict) and str(s.get("slug") or "").strip()
        ][:48]
        _log.warning(
            "PWA manifest: экран slug=%r не найден для тенанта %r — name/icon по умолчанию; в конфиге slugs=%r",
            slug_key,
            tenant_for_log or "?",
            know,
        )
        return _PWA_MANIFEST_DEFAULT_TITLE[:64], icon_url
    visit_all = _screen_widgets_ordered_with_carousel_children(sc)
    visit_enabled = [w for w in visit_all if _pwa_widget_enabled_for_manifest(w)]
    checkin_ordered: list[dict[str, Any]] = []
    for w in visit_enabled:
        if str(w.get("type") or "") not in ("checkin_submit", "checkin_monitor"):
            continue
        checkin_ordered.append(w)
    submits = [w for w in checkin_ordered if str(w.get("type") or "") == "checkin_submit"]
    monitors = [w for w in checkin_ordered if str(w.get("type") or "") == "checkin_monitor"]
    visit = submits + monitors
    if not visit:
        fb_t, fb_i = _pwa_fallback_pwa_fields_from_widgets(visit_enabled, have_title=False, have_icon=False)
        chosen0 = (fb_t or _PWA_MANIFEST_DEFAULT_TITLE)[:64]
        icon0 = fb_i or _pwa_first_image_widget_icon_url(visit_enabled) or icon_url
        return chosen0, icon0
    pwa_title_submit = ""
    pwa_title_monitor = ""
    icon_submit = ""
    icon_monitor = ""
    for w in visit:
        st_w = w.get("settings") if isinstance(w.get("settings"), dict) else {}
        wt = str(w.get("type") or "")
        ip = _normalize_pwa_upload_icon_path(st_w.get("pwa_icon_url"))
        pt = str(st_w.get("pwa_title") or "").strip()[:64]
        if wt == "checkin_submit":
            if ip and not icon_submit:
                icon_submit = ip
            if pt and not pwa_title_submit:
                pwa_title_submit = pt
        elif wt == "checkin_monitor":
            if ip and not icon_monitor:
                icon_monitor = ip
            if pt and not pwa_title_monitor:
                pwa_title_monitor = pt
    if not pwa_title_monitor and monitors:
        for w in monitors:
            st_m = w.get("settings") if isinstance(w.get("settings"), dict) else {}
            panel_t = str(st_m.get("panel_title") or "").strip()[:64]
            if panel_t:
                pwa_title_monitor = panel_t
                break
    # Сводка важнее оперативной, если на экране оба включены; выключенные виджеты не учитываем.
    pwa_title_pick = pwa_title_monitor or pwa_title_submit
    icon_pick = icon_monitor or icon_submit
    fb_t, fb_i = _pwa_fallback_pwa_fields_from_widgets(
        visit_enabled,
        have_title=bool(pwa_title_pick),
        have_icon=bool(icon_pick),
    )
    if not pwa_title_pick and fb_t:
        pwa_title_pick = fb_t
    if not icon_pick and fb_i:
        icon_pick = fb_i
    if not icon_pick:
        img_icon = _pwa_first_image_widget_icon_url(visit_enabled)
        if img_icon:
            icon_pick = img_icon
    chosen = (pwa_title_pick or _PWA_MANIFEST_DEFAULT_TITLE)[:64]
    final_icon = icon_pick if icon_pick else icon_url
    return chosen, final_icon


def _pwa_manifest_for_tv_pair(
    *,
    request: Request,
    tenant_slug: str,
    code_canon: str,
    screen_slug: str,
    app_title: str,
    icon_url: str,
) -> JSONResponse:
    """
    SaaS: PWA manifest для ссылки /t/{code}/{screen_slug}.

    Ключевые требования:
    - start_url должен содержать code (чтобы “ярлык” вёл на брендированную ссылку);
    - icon должен быть tenant-scoped (через /uploads/*, который резолвится по cookie тенанта).
    """
    icon_entries, _mime = _pwa_manifest_icon_specs(icon_url, request=request)
    start_url = f"/t/{quote(code_canon, safe='')}/{quote(screen_slug, safe='')}?pwa=1"
    scope_path = f"/t/{quote(code_canon, safe='')}/{quote(screen_slug, safe='')}"
    manifest = {
        "name": app_title,
        "short_name": app_title[:24],
        "id": f"/pwa/t/{code_canon}/{screen_slug}",
        "start_url": start_url,
        "scope": scope_path,
        "display": "standalone",
        "background_color": "#0f172a",
        "theme_color": "#0f172a",
        "icons": icon_entries,
        "screenshots": _pwa_manifest_screenshots_entries(request),
    }
    resp = JSONResponse(
        content=_pwa_manifest_json_with_version(manifest),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )
    # Чтобы /uploads/* для icon_url отдался из data/ конкретного тенанта (map_data_path).
    sec = session_cookie_secure(request)
    resp.set_cookie(
        SAAS_TENANT_COOKIE,
        _encode_saas_tenant_cookie_value(tenant_slug),
        max_age=3600 * 24 * 365,
        httponly=True,
        samesite="lax",
        secure=sec,
        path="/",
    )
    return resp


@router.get("/pwa/t/{code}/{screen_slug}.webmanifest", response_class=JSONResponse)
def pwa_manifest_for_tv_pair(request: Request, code: str, screen_slug: str) -> JSONResponse:
    """
    SaaS: webmanifest для установки ярлыка с tenant-кодом и экраном (tv-1/tv-2).
    Иконка берётся из /uploads/..., т.е. из data/uploads конкретного тенанта.
    """
    if deployment_mode() != "saas" or not saas_db_enabled():
        raise HTTPException(status_code=404, detail="Not found.")
    code_raw = _normalize_tv_pair_text(_tv_path_code_segment(code)).lower()
    code_canon = _canonical_tv_school_code(code_raw)
    if not code_canon:
        raise HTTPException(status_code=404, detail="Not found.")
    slug_n = _normalize_screen_slug_for_api(str(screen_slug or ""))
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", slug_n):
        raise HTTPException(status_code=404, detail="Not found.")
    with connect_public() as conn:
        with conn.cursor() as cur:
            row = _tv_access_lookup_row(cur, code_canon=code_canon)
            if not row:
                raise HTTPException(status_code=404, detail="Not found.")
            tenant_slug = str(row[0] or "").strip()
    prev_tenant = None
    try:
        from .tenant_ctx import tenant_slug as _tenant_slug_get

        prev_tenant = _tenant_slug_get()
    except Exception:
        prev_tenant = None
    try:
        set_tenant_slug(tenant_slug)
        cfg = load_config()
        title, icon_url = _pwa_widget_title_icon_for_slug(cfg, slug_n)
    except Exception:
        _log.exception(
            "PWA /pwa/t manifest: ошибка load_config или разбора pwa_* slug=%r tenant=%r",
            slug_n,
            tenant_slug,
        )
        title, icon_url = _pwa_widget_title_icon_for_slug({}, slug_n)
    finally:
        try:
            set_tenant_slug(prev_tenant)
        except Exception:
            set_tenant_slug(None)
    return _pwa_manifest_for_tv_pair(
        request=request,
        tenant_slug=tenant_slug,
        code_canon=code_canon,
        screen_slug=slug_n,
        app_title=title,
        icon_url=icon_url,
    )


@router.get("/pwa/screen/{screen_slug}.webmanifest", response_class=JSONResponse)
def pwa_manifest_for_screen_standalone(request: Request, screen_slug: str) -> JSONResponse:
    """
    Manifest для /screen/<slug>: tenant из middleware (cookie), из декодированной cookie,
    либо из ?gs_tv_token= (совпадает со slug экрана) — когда cookie ещё не успела сохраниться.
    """
    slug_n = _normalize_screen_slug_for_api(str(screen_slug or ""))
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", slug_n):
        raise HTTPException(status_code=404, detail="Not found.")
    if deployment_mode() == "saas":
        tenant_slug = _pwa_manifest_resolve_tenant_slug(request, slug_n)
        if not tenant_slug:
            raise HTTPException(
                status_code=404,
                detail="Откройте экран с ?gs_tv_token=… или войдите в панель управления; обновите страницу (нужна привязка к организации).",
            )
    else:
        tenant_slug = _pwa_manifest_resolve_tenant_slug(request, slug_n) or "local"
    prev_tenant = None
    try:
        from .tenant_ctx import tenant_slug as _tenant_slug_get

        prev_tenant = _tenant_slug_get()
    except Exception:
        prev_tenant = None
    try:
        set_tenant_slug(tenant_slug)
        cfg = load_config()
        title, icon_url = _pwa_widget_title_icon_for_slug(cfg, slug_n)
    except Exception:
        _log.exception(
            "PWA /pwa/screen manifest: ошибка load_config или разбора pwa_* slug=%r tenant=%r",
            slug_n,
            tenant_slug,
        )
        title, icon_url = _pwa_widget_title_icon_for_slug({}, slug_n)
    finally:
        try:
            set_tenant_slug(prev_tenant)
        except Exception:
            set_tenant_slug(None)

    icon_entries_sc, _mime_sc = _pwa_manifest_icon_specs(icon_url, request=request)
    start_url = f"/screen/{quote(slug_n, safe='')}?pwa=1"
    manifest = {
        "name": title,
        "short_name": title[:24],
        "id": f"/pwa/screen/{tenant_slug}/{slug_n}",
        "start_url": start_url,
        "scope": "/",
        "display": "standalone",
        "background_color": "#0f172a",
        "theme_color": "#0f172a",
        "icons": icon_entries_sc,
        "screenshots": _pwa_manifest_screenshots_entries(request),
    }
    resp = JSONResponse(
        content=_pwa_manifest_json_with_version(manifest),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )
    sec = session_cookie_secure(request)
    resp.set_cookie(
        SAAS_TENANT_COOKIE,
        _encode_saas_tenant_cookie_value(tenant_slug),
        max_age=3600 * 24 * 365,
        httponly=True,
        samesite="lax",
        secure=sec,
        path="/",
    )
    return resp

def _tv_access_lookup_row(cur: Any, *, code_canon: str) -> tuple[Any, Any, Any, Any] | None:
    """Поиск tv_access по хешу/SQL и резервно по компактному коду (ZWSP/дефисы Unicode в БД или в URL ТВ)."""
    ch = tv_code_hash(code_canon)
    code_digits_only = re.sub(r"[^a-z0-9]", "", code_canon)
    cur.execute(_TV_ACCESS_BY_CODE_SQL, (ch, code_canon, code_digits_only))
    row = cur.fetchone()
    if row:
        return row
    want = _tv_school_code_compact(code_canon)
    if len(want) != 12:
        return None
    cur.execute(
        "SELECT tenant_slug, pin_salt, pin_hash, COALESCE(pin_bypass, false), coalesce(code_plaintext,'') FROM tv_access"
    )
    for r in cur.fetchall() or []:
        if _tv_school_code_compact(str(r[4] or "")) == want:
            return (r[0], r[1], r[2], r[3])
    return None


screen_html_manifest_link = _pwa_screen_html_manifest_link
tv_pair_html_manifest_link = _pwa_tv_pair_html_manifest_link
apply_saas_screen_tenant_from_request = _apply_saas_screen_tenant_from_request
tv_access_lookup_row = _tv_access_lookup_row
