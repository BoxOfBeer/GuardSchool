"""Публичный контент портала экосистемы GuardDoc (JSON в глобальном data/, без маппинга тенанта)."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .gs_paths import PORTAL_CMS_PATH

_MAX_STR = 6000
_MAX_URL = 2048
_MAX_APPS = 16
_MAX_BULLETS = 24
_MAX_ACTIONS = 8
_MAX_SHELL_NAV = 16

# Корень школьного хоста редиректит на /setup, если нет auth.json — в ссылках используем /login.
_SCHOOL_HOST_ROOT_RE = re.compile(r"^https?://school\.guarddoc\.ru/?$", re.I)


def _clip(s: str, n: int = _MAX_STR) -> str:
    t = str(s or "").strip()
    return t if len(t) <= n else t[:n]


def normalize_guardschool_entry_url(url: str | None) -> str:
    """school.guarddoc.ru/ → …/login (избегаем редиректа на /setup у анонимного корня)."""
    u = str(url or "").strip()
    if _SCHOOL_HOST_ROOT_RE.match(u):
        return "https://school.guarddoc.ru/login"
    return u


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


def default_portal_cms() -> dict[str, Any]:
    return {
        "version": 1,
        "meta": {
            "page_title": "GuardDoc — экосистема приложений для школ",
            "description": (
                "GuardDoc объединяет специализированные сервисы: электронные табло, расписание, "
                "коммуникации и рабочие инструменты. Один портал доступа, разные продукты."
            ),
            "portal_public_url": "https://guarddoc.ru",
        },
        "shell": {
            "nav_title": "GuardDoc",
            "nav_subtitle": "Экосистема для школ",
            "nav": [
                {"label": "Обзор", "href": "#portal-main-top"},
                {"label": "О платформе", "href": "#section-ecosystem"},
                {"label": "Приложения", "href": "#section-apps"},
                {"label": "Пробный доступ", "href": "#section-demo"},
                {"label": "Регистрация школы", "href": "/register"},
                {"label": "Вход в GuardSchool", "href": "https://school.guarddoc.ru/login", "external": True},
            ],
        },
        "hero": {
            "brand": "GuardDoc",
            "title": "Платформа для школ, а не один «монолит»",
            "lead": (
                "Здесь собраны приложения одной экосистемы: GuardSchool уже доступен для экранов и "
                "администрирования, GuardNotes и другие модули дополняют сценарии работы сотрудников. "
                "Регистрация — по кнопке ниже; вход в GuardSchool и пробная песочница — в меню слева."
            ),
            "primary_action": {
                "label": "Войти в GuardSchool",
                "href": "https://school.guarddoc.ru/login",
                "external": True,
            },
            "secondary_actions": [
                {"label": "Регистрация школы", "href": "/register"},
            ],
        },
        "ecosystem": {
            "heading": "Несколько приложений — одна логика доступа",
            "paragraphs": [
                (
                    "Мы не позиционируем GuardDoc как «одну программу со всем сразу». Каждый продукт "
                    "решает свой класс задач; вместе они образуют экосистему для образовательной организации."
                ),
                (
                    "Вы можете начать с GuardSchool (экраны, расписание, звонки), позже подключить GuardNotes "
                    "(заметки и документы для персонала) и следить за появлением новых модулей."
                ),
            ],
        },
        "applications": [
            {
                "id": "guardschool",
                "name": "GuardSchool",
                "tag": "Доступно",
                "tag_style": "live",
                "summary": "Информационные экраны, недельное и полное расписание, объявления, звонки, медиа.",
                "detail": (
                    "Основной продукт для электронных табло и админки контента. Работает в браузере: "
                    "настройка сетки экранов, экстренные шаблоны, импорт расписания."
                ),
                "url": "https://school.guarddoc.ru/login",
                "url_label": "Войти",
            },
            {
                "id": "guardnotes",
                "name": "GuardNotes",
                "tag": "В разработке",
                "tag_style": "soon",
                "summary": "Заметки, черновики и личные материалы для сотрудников школы.",
                "detail": (
                    "Отдельное приложение для документооборота «вне экрана»: проекты, списки, обмен внутри коллектива. "
                    "Планируется как следующий крупный модуль экосистемы."
                ),
                "url": "",
                "url_label": "",
            },
            {
                "id": "guarddoc_core",
                "name": "GuardDoc (ядро)",
                "tag": "Платформа",
                "tag_style": "platform",
                "summary": "Общий вход, учёт лицензий и будущие сервисы на одной инфраструктуре.",
                "detail": (
                    "Техническая и коммерческая оболочка: регистрация, выдача ключей, демо-песочницы. "
                    "Эта страница — часть портала GuardDoc."
                ),
                "url": "",
                "url_label": "",
            },
        ],
        "demo": {
            "heading": "Пробная песочница",
            "intro": (
                "Изолированная копия с примером данных: интерфейс GuardSchool без влияния на реальные школы. "
                "Сессия ограничена по времени; для постоянной работы оформите регистрацию и получите свой поддомен."
            ),
            "bullets": [
                "Отдельный временный тенант — ваши правки не затрагивают продакшн других клиентов.",
                "После теста войдите под логином администратора на школьном хосте (раздел «Вход в GuardSchool»).",
            ],
            "action": {"label": "Открыть песочницу", "href": "/try-demo"},
        },
        "links_column": {
            "heading": "Ещё",
            "items": [],
        },
        "footer": {
            "note": (
                "GuardDoc — экосистема продуктов. Условия и функциональность конкретного приложения "
                "могут отличаться; актуальные сведения — на страницах соответствующих сервисов."
            ),
        },
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
    """Подмена устаревших ссылок school…/ → …/login после merge и при сохранении."""
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
    _normalize_merged_cms_urls(merged)
    return merged


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


def sanitize_portal_cms_payload(raw: Any) -> dict[str, Any]:
    """Принимает произвольный JSON от провайдера и возвращает безопасную структуру."""
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
            out["ecosystem"]["paragraphs"] = [_clip(p) for p in paras[:12] if _clip(p)]

    apps = raw.get("applications")
    if isinstance(apps, list):
        clean: list[dict[str, Any]] = []
        for it in apps[:_MAX_APPS]:
            a = _sanitize_app(it)
            if a:
                clean.append(a)
        if clean:
            out["applications"] = clean

    demo = raw.get("demo")
    if isinstance(demo, dict):
        out["demo"]["heading"] = _clip(demo.get("heading"), 200)
        out["demo"]["intro"] = _clip(demo.get("intro"))
        bl = demo.get("bullets")
        if isinstance(bl, list):
            out["demo"]["bullets"] = [_clip(b) for b in bl[:_MAX_BULLETS] if _clip(b)]
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

    out["version"] = 1
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
