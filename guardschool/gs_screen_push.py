"""Web Push helpers: content revision, checkin journal, emergency."""
from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import quote

from fastapi import Request

from .gs_app_config import load_config
from .gs_data_revision import compute_data_revision
from .gs_tv_screen_api import normalize_screen_slug_for_api as _normalize_screen_slug_for_api
from .optional_imports import push_module
from .push_notify import notify_push_to_screen, push_enabled_on_server

_log = logging.getLogger(__name__)



from .gs_checkin_screen import (
    checkin_events_screen_slug_for_monitor,
    screen_widgets_ordered_with_carousel_children,
)


def _widgets_ordered(screen: dict[str, Any]):
    return screen_widgets_ordered_with_carousel_children(screen)


def _events_screen_slug_for_monitor(config, mw, display_slug_key):
    return checkin_events_screen_slug_for_monitor(config, mw, display_slug_key)


def _screen_api_tenant_slug(request: Request) -> str:
    from .gs_tv_screen_api import screen_api_tenant_slug
    return screen_api_tenant_slug(request)


def screen_slugs_mobile_active(cfg: dict[str, Any]) -> list[str]:
    """Активные экраны с mobile_mode — рассылка темы content (обновление данных без отметок/аварии)."""
    out: list[str] = []
    for sc in (cfg.get("screens") or []) if isinstance(cfg, dict) else []:
        if not isinstance(sc, dict) or sc.get("is_active", True) is False:
            continue
        if not bool(sc.get("mobile_mode")):
            continue
        slug = _normalize_screen_slug_for_api(str(sc.get("slug") or ""))
        if slug and slug not in out:
            out.append(slug)
    return out


def notify_push_screen_content_refresh_for_mobile_screens(
    *,
    tenant_id: str,
    cfg: dict[str, Any],
    title: str,
    body: str,
    tag_suffix: str,
) -> None:
    """
    Тема content: на экране появились новые данные (расписание и т.п.).
    Уходит только на slug с mobile_mode; подписка opt-in (чекбокс в панели устройства).
    """
    tid = (tenant_id or "local").strip() or "local"
    ts = int(time.time())
    suf = (tag_suffix or "data").strip().lower().replace(" ", "_")[:32] or "data"
    for slug in screen_slugs_mobile_active(cfg):
        url = f"/screen/{quote(slug, safe='')}"
        _notify_push_to_screen(
            tenant_id=tid,
            screen_slug=slug,
            topic="content",
            title=title,
            body=body,
            url=url,
            notification_tag=f"{slug}:content:{suf}:{ts}",
        )


def maybe_push_screen_content_if_data_revision_changed(request: Request) -> None:
    """
    Пуш темы «content» при любом изменении данных, входящих в compute_data_revision()
    (config.json, расписания, праздники, объявления, бегущая строка, замены, звонки, changelog).

    Журнал сводки и аварийный режим остаются отдельными темами (checkin / emergency).
    """
    try:
        if not _push_enabled_on_server():
            return
        tid = _screen_api_tenant_slug(request)
        push = push_module()
        if push is None:
            return
        new_rev = compute_data_revision()
        if not push.try_claim_content_push_revision_change(tenant_id=tid, new_revision=new_rev):
            return
        cfg = load_config()
        notify_push_screen_content_refresh_for_mobile_screens(
            tenant_id=tid,
            cfg=cfg,
            title="Обновление на экране",
            body="На странице появились новые данные. Откройте экран, чтобы обновить.",
            tag_suffix=f"rev_{new_rev[:12]}",
        )
    except Exception:
        _log.exception("content push after data revision change")


def checkin_monitor_screens_for_events_slug(cfg: dict[str, Any], events_slug: str) -> list[str]:
    """
    Возвращает slug экранов, где есть checkin_monitor, который смотрит на events_slug.
    Нужен кейс: отметки создаются на tv-1, а сводка/уведомления — на tv-2.
    """
    want = (events_slug or "").strip().lower()
    if not want:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for sc in (cfg.get("screens") or []) if isinstance(cfg, dict) else []:
        if not isinstance(sc, dict) or sc.get("is_active", True) is False:
            continue
        disp_slug = _normalize_screen_slug_for_api(str(sc.get("slug") or ""))
        if not disp_slug or disp_slug in seen:
            continue
        for w in _widgets_ordered(sc):
            if not isinstance(w, dict) or w.get("enabled") is False:
                continue
            if str(w.get("type") or "") != "checkin_monitor":
                continue
            event_slug = _events_screen_slug_for_monitor(cfg, w, disp_slug)
            if (event_slug or "").strip().lower() == want:
                out.append(disp_slug)
                seen.add(disp_slug)
                break
    return out


def checkin_count_unconfirmed(*, tenant_id: str, events_screen_slug: str) -> int:
    try:
        import sqlite3

        from .gs_paths import DATA_DIR
        from .tenant_ctx import map_data_path

        db_path = map_data_path(DATA_DIR) / "checkin.sqlite3"
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.execute(
                """
                SELECT COUNT(1) AS n
                FROM checkin_events
                WHERE tenant_id=? AND lower(trim(screen_slug))=?
                  AND (confirmed_at IS NULL OR trim(confirmed_at) = '')
                """,
                ((tenant_id or "local").strip() or "local", (events_screen_slug or "").strip().lower()),
            )
            row = cur.fetchone()
            return int(row[0] or 0) if row else 0
        finally:
            conn.close()
    except Exception:
        return 0


def checkin_push_target_slugs_for_events_screen(cfg: dict[str, Any], events_screen_slug: str) -> list[str]:
    """Экран записи событий + все экраны со сводкой, смотрящие на этот slug."""
    root = (events_screen_slug or "").strip().lower()
    if not root:
        return []
    out: list[str] = [root]
    for m in checkin_monitor_screens_for_events_slug(cfg, root):
        if m and m not in out:
            out.append(m)
    return out


def checkin_level_display_label(cfg: dict[str, Any], mw: dict[str, Any] | None, level: str) -> str:
    lv = (level or "").strip().lower()
    merged: dict[str, str] = {}
    ch = (cfg.get("checkin") or {}) if isinstance(cfg, dict) else {}
    raw = ch.get("labels") if isinstance(ch.get("labels"), dict) else {}
    for k, v in raw.items():
        key = str(k).strip().lower()
        if key:
            merged[key] = str(v).strip()
    if isinstance(mw, dict):
        raw2 = (mw.get("settings") or {}).get("labels")
        if isinstance(raw2, dict):
            for k, v in raw2.items():
                key = str(k).strip().lower()
                if key:
                    merged[key] = str(v).strip()
    return merged.get(lv) or {"ok": "Норма", "warn": "Внимание", "alert": "Проблема"}.get(lv, lv or "—")


def checkin_monitor_widget_for_submit(screen: dict[str, Any], submit_w: dict[str, Any]) -> dict[str, Any] | None:
    st = submit_w.get("settings") or {}
    link = str(st.get("monitor_widget_id") or "").strip()
    if link:
        mw = _find_monitor_widget(screen, link)
        if mw:
            return mw
    mons = [
        w
        for w in _widgets_ordered(screen)
        if isinstance(w, dict) and w.get("type") == "checkin_monitor"
    ]
    return mons[0] if len(mons) == 1 else None


def checkin_place_title_from_submit_places(places: list[dict[str, str]], place_id: str) -> str:
    for p in places or []:
        if str(p.get("id") or "") == str(place_id):
            t = str(p.get("title") or "").strip()
            return t or str(place_id)
    return str(place_id)


def checkin_place_title_from_monitor(mw: dict[str, Any], place_id: str) -> str:
    for p in sanitize_places_list((mw.get("settings") or {}).get("places")):
        if str(p.get("id") or "") == str(place_id):
            t = str(p.get("title") or "").strip()
            return t or str(place_id)
    return str(place_id)


def notify_push_checkin_journal_new_row(
    *,
    cfg: dict[str, Any],
    tenant_id: str,
    screen: dict[str, Any],
    submit_w: dict[str, Any],
    events_screen_slug: str,
    saved: dict[str, Any],
    place_id: str,
    level: str,
    device_name: str,
    comment: str,
) -> None:
    """Пуш при новой строке журнала сводки (тема «Новые отметки» в подписке)."""
    places = _resolve_checkin_submit_places(screen, submit_w)
    place_title = checkin_place_title_from_submit_places(places, place_id)
    mw = checkin_monitor_widget_for_submit(screen, submit_w)
    lvl = checkin_level_display_label(cfg, mw, level)
    parts = [place_title, lvl]
    dn = (device_name or "").strip()
    if dn:
        parts.append(dn)
    body = " · ".join(parts)
    cm = (comment or "").strip()
    if cm:
        body += " — " + cm[:180]
    try:
        eid = int(saved.get("id") or 0)
    except (TypeError, ValueError):
        eid = 0
    n_unc = _checkin_count_unconfirmed(tenant_id=tenant_id, events_screen_slug=events_screen_slug)
    if n_unc > 1:
        body += f" (неподтверждённых: {n_unc})"
    title = "Сводка: новая отметка"
    for disp in checkin_push_target_slugs_for_events_screen(cfg, events_screen_slug):
        if not disp:
            continue
        url = f"/screen/{quote(str(disp).strip().lower(), safe='')}"
        tag = f"{disp}:checkin:new:{eid}" if eid else f"{disp}:checkin:new:{int(time.time())}"
        _notify_push_to_screen(
            tenant_id=tenant_id,
            screen_slug=disp,
            topic="checkin",
            title=title,
            body=body,
            url=url,
            notification_tag=tag,
        )


def notify_push_checkin_journal_confirmed(
    *,
    cfg: dict[str, Any],
    tenant_id: str,
    mw: dict[str, Any],
    events_screen_slug: str,
    row: dict[str, Any],
) -> None:
    pid = str(row.get("place_id") or "")
    place_title = checkin_place_title_from_monitor(mw, pid)
    lvl = checkin_level_display_label(cfg, mw, str(row.get("level") or ""))
    dn = str(row.get("device_name") or "").strip()
    parts = [place_title, lvl]
    if dn:
        parts.append(dn)
    body = " · ".join(parts)
    title = "Сводка: отметка подтверждена"
    try:
        eid = int(row.get("id") or 0)
    except (TypeError, ValueError):
        eid = 0
    root = (events_screen_slug or "").strip().lower()
    if not root:
        return
    for disp in checkin_push_target_slugs_for_events_screen(cfg, root):
        if not disp:
            continue
        url = f"/screen/{quote(str(disp).strip().lower(), safe='')}"
        tag = f"{disp}:checkin:ok:{eid}" if eid else f"{disp}:checkin:ok:{int(time.time())}"
        _notify_push_to_screen(
            tenant_id=tenant_id,
            screen_slug=disp,
            topic="checkin",
            title=title,
            body=body,
            url=url,
            notification_tag=tag,
        )


def notify_push_checkin_journal_bulk_confirm(
    *, cfg: dict[str, Any], tenant_id: str, events_screen_slug: str, count: int
) -> None:
    if count <= 0:
        return
    title = "Сводка: журнал"
    body = f"Подтверждено записей: {count}"
    ts = int(time.time())
    root = (events_screen_slug or "").strip().lower()
    if not root:
        return
    for disp in checkin_push_target_slugs_for_events_screen(cfg, root):
        if not disp:
            continue
        url = f"/screen/{quote(str(disp).strip().lower(), safe='')}"
        tag = f"{disp}:checkin:bulk:{ts}:{count}"
        _notify_push_to_screen(
            tenant_id=tenant_id,
            screen_slug=disp,
            topic="checkin",
            title=title,
            body=body,
            url=url,
            notification_tag=tag,
        )


def notify_push_emergency_change(*, tenant_id: str, cfg: dict[str, Any], prev_tid: str, new_tid: str) -> None:
    """
    Пуш по смене аварийного режима: prev_tid -> new_tid.
    new_tid == '' означает «выключено».
    """
    prev = str(prev_tid or "").strip()
    new = str(new_tid or "").strip()
    if prev == new:
        return
    # Найти title шаблона для текста уведомления.
    tname = ""
    try:
        templates = cfg.get("emergency_templates") if isinstance(cfg, dict) else None
        if isinstance(templates, list) and new:
            tpl = next((x for x in templates if isinstance(x, dict) and str(x.get("id") or "") == new), None)
            if isinstance(tpl, dict):
                tname = str(tpl.get("title") or tpl.get("name") or "").strip()[:120]
    except Exception:
        tname = ""
    title = "Аварийный режим" if new else "Аварийный режим выключен"
    body = (tname and f"Шаблон: {tname}") or ("Включён" if new else "Выключен")
    for sc in (cfg.get("screens") or []) if isinstance(cfg, dict) else []:
        if not isinstance(sc, dict) or sc.get("is_active", True) is False:
            continue
        slug = _normalize_screen_slug_for_api(str(sc.get("slug") or ""))
        if not slug:
            continue
        url = f"/screen/{quote(slug, safe='')}"
        _notify_push_to_screen(
            tenant_id=tenant_id,
            screen_slug=slug,
            topic="emergency",
            title=title,
            body=body,
            url=url,
        )
