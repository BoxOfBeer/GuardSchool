"""Публичный контент портала GuardDoc: data/portal_cms.json (глобально, без тенанта)."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .gs_paths import PORTAL_CMS_PATH

_MAX_STR = 12000
_MAX_URL = 2048
_MAX_APPS = 16
_MAX_BULLETS = 24
_MAX_ACTIONS = 8
_MAX_SHELL_NAV = 24
_MAX_SHOWCASE_SHOTS = 18
_MAX_PANEL_PARAS = 10
_MAX_BLOCKS = 80
_MAX_UL_ITEMS = 40
_MAX_BODY_HTML = 100_000

_SCHOOL_HOST_ROOT_RE = re.compile(r"^https?://school\.guarddoc\.ru/?$", re.I)

PAGE_SLUG_GUARDSCHOOL = "guardschool"
PAGE_SLUG_GUARDSCHOOL_DEMO = "guardschool-demo"


def _clip(s: str, n: int = _MAX_STR) -> str:
    t = str(s or "").strip()
    return t if len(t) <= n else t[:n]


def normalize_guardschool_entry_url(url: str | None) -> str:
    u = str(url or "").strip()
    if _SCHOOL_HOST_ROOT_RE.match(u):
        return "https://school.guarddoc.ru/login"
    return u


def _safe_image_url(raw: str | None) -> str:
    u = str(raw or "").strip()
    if not u:
        return ""
    if u.startswith("/") and not u.startswith("//"):
        if re.match(r"^/(static|uploads)/", u):
            return u[:_MAX_URL]
    if re.match(r"^https?://", u, re.I):
        return u[:_MAX_URL]
    return ""


def _safe_href(raw: str | None) -> str:
    u = str(raw or "").strip()
    if not u:
        return ""
    if u.startswith("/") and not u.startswith("//"):
        return u[:_MAX_URL]
    if re.match(r"^https?://", u, re.I):
        return u[:_MAX_URL]
    if u.lower().startswith("mailto:") and "@" in u:
        return u[:_MAX_URL]
    return ""


def _default_page_guardschool() -> dict[str, Any]:
    return {
        "title": "О GuardSchool",
        "meta_description": (
            "GuardSchool: информационные экраны для школы, админка, расписание и виджеты в браузере."
        ),
        "version_badge": {"text": "Версия актуальна", "variant": "success"},
        "blocks": [
            {"type": "p", "text": _clip(_default_about_guardschool_intro())},
            {"type": "h2", "text": "Что это"},
            {
                "type": "p",
                "text": (
                    "GuardSchool — веб-приложение для информационных экранов: кабинет администратора и публичные "
                    "страницы для телевизоров в коридоре, столовой, на входе. Работает в браузере, без отдельного "
                    "приложения на каждый экран — достаточно открыть ссылку."
                ),
            },
            {
                "type": "p",
                "text": (
                    "В админке собирается сетка виджетов: расписание (день, неделя, полное), объявления, бегущая строка, "
                    "часы, фоновое изображение или видео, звонки, медиа. Разные экраны для корпусов, «аварийные» шаблоны "
                    "для важных сообщений. Данные можно импортировать из Excel или вести вручную."
                ),
            },
            {"type": "h2", "text": "Скриншоты"},
            {
                "type": "p",
                "text": (
                    "Добавьте свои картинки ниже (блоки «Изображение») — например ссылки на файлы в облаке или "
                    "пути вида /static/… после загрузки в репозиторий."
                ),
            },
        ],
    }


def _default_about_guardschool_intro() -> str:
    return (
        "Редактируйте текст страницы одним полем (как новости в GuardSchool): HTML с абзацами, списками и "
        "картинками; метку версии — отдельно выше. Старый формат «блоков» при открытии подставится сюда до первого сохранения."
    )


def _default_page_guardschool_demo() -> dict[str, Any]:
    return {
        "title": "Демо GuardSchool",
        "meta_description": "Как устроена пробная песочница GuardSchool: срок, одноразовый вход, изоляция данных.",
        "version_badge": None,
        "blocks": [
            {"type": "h2", "text": "Временный доступ"},
            {
                "type": "p",
                "text": (
                    "Демо — отдельная «песочница» с примером данных GuardSchool. Вы получаете одноразовую ссылку; "
                    "вход по лицензии не нужен. Данные не смешиваются с реальными школами."
                ),
            },
            {
                "type": "badge",
                "text": "Сессия обычно до 1 часа — точное время задаёт провайдер на сервере",
                "variant": "warning",
            },
            {"type": "h2", "text": "Что учитывать"},
            {
                "type": "ul",
                "items": [
                    "Один переход по токену может быть одноразовым — при необходимости запросите новое демо с главной.",
                    "После теста зарегистрируйте школу по ключу и входите через страницу /login школьного хоста.",
                    "Корень школьного сайта без учётной записи может перенаправлять на настройку — используйте вход.",
                ],
            },
            {
                "type": "p",
                "text": (
                    "Запустить песочницу можно с главной портала кнопкой «Демо-песочница» или по прямой ссылке "
                    "сервиса try-demo после настройки провайдера."
                ),
            },
        ],
    }


def _default_footer_legal() -> dict[str, Any]:
    return {
        "copyright": "© GuardDoc. Все права на материалы сайта защищены.",
        "privacy_text": (
            "Мы обрабатываем персональные данные в объёме, необходимом для работы сервисов экосистемы GuardDoc "
            "(регистрация, вход, лицензирование). Подробности обработки уточняйте у оператора вашей организации "
            "или по контактам ниже."
        ),
        "cookies_text": (
            "Сайт может использовать cookie и локальное хранилище браузера для сессии входа, языка интерфейса "
            "и устойчивости настроек. Отключение cookie может ограничить работу личного кабинета."
        ),
        "contacts_text": (
            "По вопросам лицензий и доступа используйте контакты, указанные вашей организацией или провайдером GuardDoc."
        ),
        "extra_links": [],
    }


def default_portal_cms() -> dict[str, Any]:
    return {
        "version": 2,
        "meta": {
            "page_title": "GuardDoc — экосистема приложений для школ",
            "description": (
                "GuardDoc объединяет сервисы для школ: GuardSchool для экранов и расписания, GuardNotes и другие "
                "приложения на общей платформе."
            ),
            "portal_public_url": "https://guarddoc.ru",
        },
        "shell": {
            "nav_title": "GuardDoc",
            "nav_subtitle": "Экосистема для школ",
            "nav": [
                {"label": "Главная", "href": "/"},
                {"label": "О GuardSchool", "href": "/about/guardschool"},
                {"label": "Демо GuardSchool", "href": "/about/guardschool-demo"},
                {"label": "Регистрация", "href": "/register"},
                {"label": "Вход в GuardSchool", "href": "https://school.guarddoc.ru/login", "external": True},
            ],
            "about_program": {"title": "", "paragraphs": []},
            "demo_notice": {"title": "", "paragraphs": []},
        },
        "hero": {
            "brand": "GuardDoc",
            "title": "Платформа для школ: несколько приложений — один портал",
            "lead": (
                "GuardDoc объединяет сервисы вроде GuardSchool (экраны и расписание) и будущие продукты вроде "
                "GuardNotes. Здесь — общая точка входа: зачем экосистема, как попробовать демо и как подключить школу. "
                "Подробности о продукте и о демо — на отдельных страницах в разделе /about/."
            ),
            "primary_action": {
                "label": "Войти в GuardSchool",
                "href": "https://school.guarddoc.ru/login",
                "external": True,
            },
            "secondary_actions": [
                {"label": "Демо-песочница", "href": "/try-demo", "role": "demo"},
                {"label": "Регистрация школы", "href": "/register", "role": "register"},
            ],
        },
        "ecosystem": {
            "heading": "Зачем этот сайт",
            "paragraphs": [
                (
                    "Экосистема GuardDoc даёт школе специализированные приложения на общей инфраструктуре: лицензии, "
                    "регистрация, единый стиль портала. Вы подключаете то, что нужно: чаще всего начинают с GuardSchool."
                ),
                (
                    "Технические и юридические детали продуктов — на страницах раздела «О продукте» (/about/…); "
                    "главная остаётся коротким обзором."
                ),
            ],
        },
        "applications": [
            {
                "id": "guardschool",
                "name": "GuardSchool",
                "tag": "Доступно",
                "tag_style": "live",
                "summary": "Экраны, расписание, звонки, объявления и медиа в браузере.",
                "detail": (
                    "Полноценное описание, скриншоты и актуальные пометки — на странице «О GuardSchool» (редактируется в CMS)."
                ),
                "url": "https://school.guarddoc.ru/login",
                "url_label": "Войти",
            },
            {
                "id": "guardnotes",
                "name": "GuardNotes",
                "tag": "В разработке",
                "tag_style": "soon",
                "summary": "Заметки и документы для персонала школы.",
                "detail": "Планируется как отдельный модуль экосистемы.",
                "url": "",
                "url_label": "",
            },
            {
                "id": "guarddoc_core",
                "name": "GuardDoc (ядро)",
                "tag": "Платформа",
                "tag_style": "platform",
                "summary": "Лицензии, регистрация школ, общий портал.",
                "detail": "Инфраструктура для всех приложений GuardDoc.",
                "url": "",
                "url_label": "",
            },
        ],
        "demo": {
            "heading": "Попробовать",
            "intro": "Кратко: изолированная песочница с примером данных. Подробности — на странице «Демо GuardSchool».",
            "bullets": [
                "Запуск демо — с главной кнопкой «Демо-песочница».",
                "Срок и правила — в разделе /about/guardschool-demo.",
            ],
            "action": {"label": "Открыть песочницу", "href": "/try-demo"},
        },
        "links_column": {"heading": "", "items": []},
        "footer": {
            "note": (
                "Краткий обзор экосистемы. Юридическая информация и контакты — в подвале страницы (редактируются в CMS)."
            ),
        },
        "footer_legal": _default_footer_legal(),
        "pages": {
            PAGE_SLUG_GUARDSCHOOL: _default_page_guardschool(),
            PAGE_SLUG_GUARDSCHOOL_DEMO: _default_page_guardschool_demo(),
        },
        "showcase": {"guardschool": {}},
    }


def _merge_defaults(stored: dict[str, Any]) -> dict[str, Any]:
    base = deepcopy(default_portal_cms())
    if not isinstance(stored, dict):
        return base

    def deep_merge(dst: dict[str, Any], src: dict[str, Any]) -> None:
        for k, v in src.items():
            if k in dst and isinstance(dst[k], dict) and isinstance(v, dict):
                deep_merge(dst[k], v)
            else:
                dst[k] = v

    deep_merge(base, stored)
    return base


def _normalize_merged_cms_urls(d: dict[str, Any]) -> None:
    hero = d.get("hero")
    if isinstance(hero, dict):
        pa = hero.get("primary_action")
        if isinstance(pa, dict):
            h = pa.get("href")
            if isinstance(h, str) and h.strip():
                pa["href"] = normalize_guardschool_entry_url(h)
    for app in d.get("applications") or []:
        if not isinstance(app, dict):
            continue
        if str(app.get("id", "")).strip().lower() != "guardschool":
            continue
        u = app.get("url")
        if isinstance(u, str) and u.strip():
            app["url"] = normalize_guardschool_entry_url(u)


def _migrate_legacy_to_pages(d: dict[str, Any]) -> None:
    """Перенос старых showcase / сайдбара в pages, если страницы ещё пустые."""
    pages = d.setdefault("pages", {})
    shell = d.setdefault("shell", {})

    gs = pages.get(PAGE_SLUG_GUARDSCHOOL)
    if not isinstance(gs, dict):
        gs = {}
        pages[PAGE_SLUG_GUARDSCHOOL] = gs
    migrated_gs = False
    if not gs.get("blocks"):
        blocks: list[dict[str, Any]] = []
        ap = shell.get("about_program") or {}
        for para in ap.get("paragraphs") or []:
            t = _clip(para)
            if t:
                blocks.append({"type": "p", "text": t})
        sh = (d.get("showcase") or {}).get("guardschool") or {}
        if sh.get("intro"):
            blocks.append({"type": "p", "text": _clip(sh["intro"])})
        for para in sh.get("paragraphs") or []:
            t = _clip(para)
            if t:
                blocks.append({"type": "p", "text": t})
        for shot in sh.get("screenshots") or []:
            if not isinstance(shot, dict):
                continue
            src = _safe_image_url(str(shot.get("src") or ""))
            if not src:
                continue
            blocks.append(
                {
                    "type": "figure",
                    "src": src,
                    "title": _clip(shot.get("title"), 200),
                    "caption": _clip(shot.get("caption")),
                    "alt": _clip(shot.get("title"), 300),
                }
            )
        if not gs.get("title") and sh.get("page_title"):
            gs["title"] = _clip(sh.get("page_title"), 200)
        if blocks:
            gs["blocks"] = blocks[:_MAX_BLOCKS]
            migrated_gs = True
        if not gs.get("title"):
            gs["title"] = "О GuardSchool"
        if not gs.get("meta_description") and sh.get("meta_description"):
            gs["meta_description"] = _clip(sh.get("meta_description"))

    demo_p = pages.get(PAGE_SLUG_GUARDSCHOOL_DEMO)
    if not isinstance(demo_p, dict):
        demo_p = {}
        pages[PAGE_SLUG_GUARDSCHOOL_DEMO] = demo_p
    migrated_demo = False
    if not demo_p.get("blocks"):
        blocks2: list[dict[str, Any]] = []
        dn = shell.get("demo_notice") or {}
        for para in dn.get("paragraphs") or []:
            t = _clip(para)
            if t:
                blocks2.append({"type": "p", "text": t})
        demo_sec = d.get("demo") or {}
        if demo_sec.get("intro"):
            blocks2.insert(0, {"type": "p", "text": _clip(demo_sec["intro"])})
        items_demo: list[str] = []
        for b in demo_sec.get("bullets") or []:
            t = _clip(b)
            if t:
                items_demo.append(t)
        if items_demo:
            blocks2.append({"type": "ul", "items": items_demo})
        if blocks2:
            demo_p["blocks"] = blocks2[:_MAX_BLOCKS]
            migrated_demo = True
        if not demo_p.get("title"):
            demo_p["title"] = "Демо GuardSchool"

    d.setdefault("footer_legal", _default_footer_legal())

    if migrated_gs:
        shell["about_program"] = {"title": "", "paragraphs": []}
    if migrated_demo:
        shell["demo_notice"] = {"title": "", "paragraphs": []}


def _normalize_portal_pages_body_priority(d: dict[str, Any]) -> None:
    """Одна форма контента: либо body_html, либо blocks (легаси), не оба сразу после merge."""
    pages = d.get("pages")
    if not isinstance(pages, dict):
        return
    for pg in pages.values():
        if not isinstance(pg, dict):
            continue
        bh = str(pg.get("body_html") or "").strip()
        blocks = pg.get("blocks")
        has_b = isinstance(blocks, list) and len(blocks) > 0
        if bh and has_b:
            pg["blocks"] = []
        elif has_b and not bh:
            pg.pop("body_html", None)


def _sanitize_portal_page_body_html(raw: Any) -> str:
    """Как контент школьных новостей: без script и inline on*."""
    s = str(raw or "").strip()
    if len(s) > _MAX_BODY_HTML:
        s = s[:_MAX_BODY_HTML]
    s = re.sub(r"(?is)<script[^>]*>.*?</script>", "", s)
    s = re.sub(r"(?is)</?script[^>]*>", "", s)
    s = re.sub(r'(?is)on[a-z]+\s*=\s*"[^"]*"', "", s)
    s = re.sub(r"(?is)on[a-z]+\s*=\s*'[^']*'", "", s)
    return s.strip()


def load_portal_cms_merged() -> dict[str, Any]:
    path: Path = PORTAL_CMS_PATH
    if not path.is_file():
        out = deepcopy(default_portal_cms())
        _normalize_merged_cms_urls(out)
        return out
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        out = deepcopy(default_portal_cms())
        _normalize_merged_cms_urls(out)
        return out
    merged = _merge_defaults(raw if isinstance(raw, dict) else {})
    try:
        _migrate_legacy_to_pages(merged)
    except Exception:
        pass
    try:
        _normalize_portal_pages_body_priority(merged)
    except Exception:
        pass
    _normalize_merged_cms_urls(merged)
    return merged


def get_portal_page(slug: str) -> dict[str, Any] | None:
    """Одна страница /about/{slug} из merged CMS."""
    cms = load_portal_cms_merged()
    pages = cms.get("pages")
    if not isinstance(pages, dict):
        return None
    p = pages.get(slug.strip().lower())
    return deepcopy(p) if isinstance(p, dict) else None


def _sanitize_action(item: Any) -> dict[str, str | bool] | None:
    if not isinstance(item, dict):
        return None
    label = _clip(item.get("label"), 200)
    href = _safe_href(str(item.get("href") or ""))
    if not label or not href:
        return None
    ext = bool(item.get("external"))
    out: dict[str, str | bool] = {"label": label, "href": href}
    if ext:
        out["external"] = True
    role = str(item.get("role") or "").strip().lower()
    if role in ("demo", "register"):
        out["role"] = role
    return out


def _sanitize_block(b: Any) -> dict[str, Any] | None:
    if not isinstance(b, dict):
        return None
    t = str(b.get("type") or "").strip().lower()
    if t == "h2":
        tx = _clip(b.get("text"), 500)
        return {"type": "h2", "text": tx} if tx else None
    if t == "p":
        tx = _clip(b.get("text"))
        return {"type": "p", "text": tx} if tx else None
    if t == "badge":
        v = str(b.get("variant") or "neutral").lower()
        if v not in ("success", "neutral", "warning"):
            v = "neutral"
        tx = _clip(b.get("text"), 400)
        return {"type": "badge", "text": tx, "variant": v} if tx else None
    if t == "figure":
        src = _safe_image_url(str(b.get("src") or ""))
        if not src:
            return None
        return {
            "type": "figure",
            "src": src,
            "title": _clip(b.get("title"), 200),
            "caption": _clip(b.get("caption")),
            "alt": _clip(b.get("alt"), 400),
        }
    if t == "ul":
        raw_items = b.get("items")
        items: list[str] = []
        if isinstance(raw_items, list):
            for x in raw_items[:_MAX_UL_ITEMS]:
                s = _clip(str(x))
                if s:
                    items.append(s)
        return {"type": "ul", "items": items} if items else None
    return None


def _sanitize_page(page: Any) -> dict[str, Any] | None:
    if not isinstance(page, dict):
        return None
    title = _clip(page.get("title"), 200)
    if not title:
        return None
    out: dict[str, Any] = {
        "title": title,
        "meta_description": _clip(page.get("meta_description")),
    }
    vb = page.get("version_badge")
    if isinstance(vb, dict) and _clip(vb.get("text")):
        v = str(vb.get("variant") or "neutral").lower()
        if v not in ("success", "neutral", "warning"):
            v = "neutral"
        out["version_badge"] = {"text": _clip(vb.get("text"), 200), "variant": v}
    else:
        out["version_badge"] = None
    body = _sanitize_portal_page_body_html(page.get("body_html"))
    if body:
        out["body_html"] = body
        out["blocks"] = []
        return out
    blocks_in = page.get("blocks")
    blocks: list[dict[str, Any]] = []
    if isinstance(blocks_in, list):
        for b in blocks_in[:_MAX_BLOCKS]:
            sb = _sanitize_block(b)
            if sb:
                blocks.append(sb)
    out["blocks"] = blocks
    return out


def _sanitize_app(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    tag_style = str(item.get("tag_style") or "soon").strip().lower()
    if tag_style not in ("live", "soon", "planned", "platform"):
        tag_style = "soon"
    url = _safe_href(str(item.get("url") or ""))
    name = _clip(item.get("name"), 120)
    if not name:
        return None
    return {
        "id": _clip(item.get("id"), 64) or re.sub(r"[^a-z0-9_-]+", "-", name.lower())[:48],
        "name": name,
        "tag": _clip(item.get("tag"), 80),
        "tag_style": tag_style,
        "summary": _clip(item.get("summary")),
        "detail": _clip(item.get("detail")),
        "url": url,
        "url_label": _clip(item.get("url_label"), 80),
    }


def _sanitize_showcase_guardschool(gs: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "page_title": "",
        "meta_description": "",
        "intro": "",
        "paragraphs": [],
        "screenshots": [],
    }
    if not isinstance(gs, dict):
        return out
    out["page_title"] = _clip(gs.get("page_title"), 200)
    out["meta_description"] = _clip(gs.get("meta_description"))
    out["intro"] = _clip(gs.get("intro"))
    ps = gs.get("paragraphs")
    if isinstance(ps, list):
        out["paragraphs"] = [_clip(p) for p in ps[:12] if _clip(p)]
    shots = gs.get("screenshots")
    if isinstance(shots, list):
        clean_sh: list[dict[str, Any]] = []
        for shot in shots[:_MAX_SHOWCASE_SHOTS]:
            if not isinstance(shot, dict):
                continue
            src = _safe_image_url(str(shot.get("src") or ""))
            tit = _clip(shot.get("title"), 200)
            cap = _clip(shot.get("caption"))
            if not src and not tit and not cap:
                continue
            clean_sh.append({"title": tit, "caption": cap, "src": src})
        out["screenshots"] = clean_sh
    return out


def _sanitize_showcase_root(raw: Any) -> dict[str, Any]:
    base = deepcopy(default_portal_cms()["showcase"])
    if not isinstance(raw, dict):
        return base
    gs = raw.get("guardschool")
    base["guardschool"] = _sanitize_showcase_guardschool(gs)
    return base


def _sanitize_footer_legal(raw: Any) -> dict[str, Any]:
    base = _default_footer_legal()
    if not isinstance(raw, dict):
        return base
    base["copyright"] = _clip(raw.get("copyright"), 500)
    base["privacy_text"] = _clip(raw.get("privacy_text"))
    base["cookies_text"] = _clip(raw.get("cookies_text"))
    base["contacts_text"] = _clip(raw.get("contacts_text"))
    links: list[dict[str, str]] = []
    for it in (raw.get("extra_links") or [])[:12]:
        if not isinstance(it, dict):
            continue
        lab = _clip(it.get("label"), 200)
        hf = _safe_href(str(it.get("href") or ""))
        if lab and hf:
            links.append({"label": lab, "href": hf})
    base["extra_links"] = links
    return base


def sanitize_portal_cms_payload(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return deepcopy(default_portal_cms())
    out = deepcopy(default_portal_cms())

    meta = raw.get("meta")
    if isinstance(meta, dict):
        out["meta"]["page_title"] = _clip(meta.get("page_title"), 200)
        out["meta"]["description"] = _clip(meta.get("description"))
        ppu = _safe_href(str(meta.get("portal_public_url") or ""))
        if ppu:
            out["meta"]["portal_public_url"] = ppu

    hero = raw.get("hero")
    if isinstance(hero, dict):
        out["hero"]["brand"] = _clip(hero.get("brand"), 120)
        out["hero"]["title"] = _clip(hero.get("title"), 300)
        out["hero"]["lead"] = _clip(hero.get("lead"))
        pa = hero.get("primary_action")
        if isinstance(pa, dict):
            lab = _clip(pa.get("label"), 120)
            href = _safe_href(str(pa.get("href") or ""))
            if lab and href:
                out["hero"]["primary_action"] = {
                    "label": lab,
                    "href": href,
                    "external": bool(pa.get("external")),
                }
        secs = hero.get("secondary_actions")
        if isinstance(secs, list):
            actions: list[dict[str, Any]] = []
            for it in secs[:_MAX_ACTIONS]:
                a = _sanitize_action(it)
                if a:
                    actions.append(a)
            out["hero"]["secondary_actions"] = actions

    eco = raw.get("ecosystem")
    if isinstance(eco, dict):
        out["ecosystem"]["heading"] = _clip(eco.get("heading"), 300)
        paras = eco.get("paragraphs")
        if isinstance(paras, list):
            clean = [_clip(p) for p in paras[:12] if _clip(p)]
            if clean:
                out["ecosystem"]["paragraphs"] = clean

    apps = raw.get("applications")
    if isinstance(apps, list):
        clean_a: list[dict[str, Any]] = []
        for it in apps[:_MAX_APPS]:
            ap = _sanitize_app(it)
            if ap:
                clean_a.append(ap)
        if clean_a:
            out["applications"] = clean_a

    demo = raw.get("demo")
    if isinstance(demo, dict):
        out["demo"]["heading"] = _clip(demo.get("heading"), 200)
        out["demo"]["intro"] = _clip(demo.get("intro"))
        bl = demo.get("bullets")
        if isinstance(bl, list):
            out["demo"]["bullets"] = [_clip(x) for x in bl[:_MAX_BULLETS] if _clip(x)]
        act = demo.get("action")
        if isinstance(act, dict):
            lb = _clip(act.get("label"), 120)
            hf = _safe_href(str(act.get("href") or ""))
            if lb and hf:
                out["demo"]["action"] = {"label": lb, "href": hf}

    lc = raw.get("links_column")
    if isinstance(lc, dict):
        out["links_column"]["heading"] = _clip(lc.get("heading"), 200)
        items = lc.get("items")
        if isinstance(items, list):
            li: list[dict[str, str]] = []
            for it in items[:_MAX_ACTIONS]:
                if not isinstance(it, dict):
                    continue
                lab = _clip(it.get("label"), 200)
                hf = _safe_href(str(it.get("href") or ""))
                if lab and hf:
                    li.append({"label": lab, "href": hf})
            out["links_column"]["items"] = li

    foot = raw.get("footer")
    if isinstance(foot, dict):
        out["footer"]["note"] = _clip(foot.get("note"))

    out["footer_legal"] = _sanitize_footer_legal(raw.get("footer_legal"))

    shell = raw.get("shell")
    if isinstance(shell, dict):
        out["shell"]["nav_title"] = _clip(shell.get("nav_title"), 120)
        out["shell"]["nav_subtitle"] = _clip(shell.get("nav_subtitle"), 200)
        nav = shell.get("nav")
        if isinstance(nav, list):
            nv: list[dict[str, Any]] = []
            for it in nav[:_MAX_SHELL_NAV]:
                a = _sanitize_action(it)
                if a:
                    nv.append(a)
            if nv:
                out["shell"]["nav"] = nv
        ap = shell.get("about_program")
        if isinstance(ap, dict):
            out["shell"]["about_program"]["title"] = _clip(ap.get("title"), 200)
            ps = ap.get("paragraphs")
            if isinstance(ps, list):
                clean_p = [_clip(p) for p in ps[:_MAX_PANEL_PARAS] if _clip(p)]
                if clean_p:
                    out["shell"]["about_program"]["paragraphs"] = clean_p
        dn = shell.get("demo_notice")
        if isinstance(dn, dict):
            out["shell"]["demo_notice"]["title"] = _clip(dn.get("title"), 200)
            ps2 = dn.get("paragraphs")
            if isinstance(ps2, list):
                clean_d = [_clip(p) for p in ps2[:_MAX_PANEL_PARAS] if _clip(p)]
                if clean_d:
                    out["shell"]["demo_notice"]["paragraphs"] = clean_d

    pages_raw = raw.get("pages")
    if isinstance(pages_raw, dict):
        new_pages: dict[str, Any] = {}
        for slug, pg in pages_raw.items():
            sk = str(slug or "").strip().lower()
            if not sk or not re.match(r"^[a-z0-9][a-z0-9-]*$", sk):
                continue
            sp = _sanitize_page(pg)
            if sp:
                new_pages[sk] = sp
        if new_pages:
            out["pages"] = new_pages

    out["showcase"] = _sanitize_showcase_root(raw.get("showcase"))

    out["version"] = 2
    _normalize_merged_cms_urls(out)
    return out


def write_portal_cms(payload: dict[str, Any]) -> None:
    path = PORTAL_CMS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        from .cloud_store import notify_data_file_written

        notify_data_file_written(path)
    except Exception:
        pass
