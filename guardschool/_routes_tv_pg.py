"""SaaS TV pairing: /t/{code}/{slug}, POST /api/tv/pair, admin tv-access."""
from __future__ import annotations

import html
import hmac
import json
import logging
import os
import re
import secrets
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from .app_screen_html import render_screen_html_page
from .app_pwa_manifest import tv_access_lookup_row
from .capabilities import CAP_REMOTE_TV_PAIRING
from .gs_admin_http import session_cookie_secure
from .gs_auth import require_auth
from .gs_capability_http import require_capability
from .gs_deploy import deployment_mode
from .gs_paths import CONFIG_PATH, SAAS_TENANT_COOKIE, STATIC_DIR
from .gs_jsonio import read_json, write_json
from .gs_tv_screen_api import (
    canonical_tv_school_code as _canonical_tv_school_code,
    encode_saas_tenant_cookie_value as _encode_saas_tenant_cookie_value,
    normalize_screen_slug_for_api as _normalize_screen_slug_for_api,
    normalize_tv_pair_text as _normalize_tv_pair_text,
    tv_path_code_segment as _tv_path_code_segment,
    tv_pwa_screen_url as _tv_pwa_screen_url,
)
from .gs_tv_pair import (
    generate_tv_code,
    normalize_tv_pair_pin,
    tv_pair_check_rate_limit,
    tv_pair_client_key,
    tv_pair_gate_notice_html,
    tv_pair_pin_bypass_effective,
    tv_pair_pin_bypass_env,
    tv_pair_pin_entry_file_response,
    tv_pair_record_failure,
    tv_pair_record_success,
    tv_token_active_tenant,
)
from .saas_db import connect_public, saas_db_enabled, tv_code_hash, tv_device_token_hash, tv_pin_hash

_log = logging.getLogger(__name__)
router = APIRouter(tags=["tv-pair"])


def register_routes(app) -> None:
    app.include_router(router)


def load_config() -> dict[str, Any]:
    from .gs_app_config import load_config as _load_config

    return _load_config()


def _sanitize_config(config: dict[str, Any]) -> dict[str, Any]:
    from .gs_app_config import sanitize_config

    return sanitize_config(config)


def _maybe_push_screen_content_if_data_revision_changed(request: Request) -> None:
    from .gs_screen_push import maybe_push_screen_content_if_data_revision_changed

    maybe_push_screen_content_if_data_revision_changed(request)


@router.get("/t/{code}/{screen_slug}", response_class=HTMLResponse)
def tv_pair_page(request: Request, code: str, screen_slug: str) -> Response:
    """
    Вход по ссылке /t/…: при обходе PIN — сразу экран с токеном; при обычном режиме — только тогда
    отдаём страницу ввода PIN (никогда не подставляем форму PIN «вслепую» при неверном коде или обходе).
    """
    require_capability(CAP_REMOTE_TV_PAIRING)
    if deployment_mode() != "saas" or not saas_db_enabled():
        return tv_pair_gate_notice_html(
            title="Подключение экрана",
            message="В этой конфигурации сервера автоматическое подключение по ссылке недоступно.",
            status=503,
        )
    code_raw = _normalize_tv_pair_text(_tv_path_code_segment(code)).lower()
    code_canon = _canonical_tv_school_code(code_raw)
    if not code_canon:
        return tv_pair_gate_notice_html(
            title="Неверная ссылка",
            message="Формат кода в адресе не распознан. Попросите администратора прислать ссылку для этого устройства ещё раз.",
        )
    slug_n = _normalize_screen_slug_for_api(str(screen_slug or ""))
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", slug_n):
        return tv_pair_gate_notice_html(
            title="Неверная ссылка",
            message="Имя экрана в адресе не распознано. Попросите администратора прислать ссылку ещё раз.",
        )
    now_ts = time.time()
    pair_key = tv_pair_client_key(request, code_canon)
    retry_after = tv_pair_check_rate_limit(pair_key, now_ts)
    if retry_after > 0:
        return HTMLResponse(
            "<!doctype html><html lang='ru'><head><meta charset='utf-8' /><title>GuardSchool</title></head>"
            f"<body style='font-family:system-ui;padding:24px'>Слишком много попыток. Подождите {retry_after} с.</body></html>",
            status_code=429,
            headers={"Cache-Control": "no-store"},
        )
    with connect_public() as conn:
        with conn.cursor() as cur:
            row = tv_access_lookup_row(cur, code_canon=code_canon)
            if not row:
                tv_pair_record_failure(pair_key, now_ts)
                return tv_pair_gate_notice_html(
                    title="Ссылка недействительна",
                    message="Код в ссылке не найден или был обновлён. Попросите администратора в программе снова сгенерировать код для устройства и прислать новую ссылку.",
                )
            tenant_slug, _pin_salt, _pin_hash, pin_bypass_db = row[0], row[1], row[2], bool(row[3])
            ts = str(tenant_slug or "").strip()
            tok_in = str(request.query_params.get("gs_tv_token") or "").strip()
            # Валидный device-token должен открывать экран даже при выключенном обходе PIN
            # (иначе после POST /api/tv/pair снова форма PIN на /t/…?gs_tv_token=…).
            if tok_in:
                tenant_tok = tv_token_active_tenant(tok_in, slug_n)
                if tenant_tok and tenant_tok == str(ts or "").strip().lower():
                    return render_screen_html_page(
                        request, slug_n, tv_code_for_manifest=code_canon
                    )
                if not tv_pair_pin_bypass_effective(ts, pin_bypass_db):
                    return tv_pair_pin_entry_file_response()
                return tv_pair_gate_notice_html(
                    title="Сессия устарела",
                    message=(
                        "Токен подключения экрана не принят (отозван, другой экран или устарел). "
                        "Откройте новую ссылку из панели управления с ?gs_tv_token=… или обновите ярлык (?pwa_pair=1)."
                    ),
                )
            if not tv_pair_pin_bypass_effective(ts, pin_bypass_db):
                return tv_pair_pin_entry_file_response()
            # Установка ярлыка (PWA): если приложение уже установлено, нельзя каждый запуск создавать новый device-token.
            # В режиме pwa=1 сначала пытаемся взять сохранённый токен из localStorage и остаться на /t/{code}/{slug}.
            if str(request.query_params.get("pwa") or "").strip() in ("1", "true", "yes"):
                # Manifest иконки/тенант-uploads требует cookie тенанта.
                sec = session_cookie_secure(request)
                resp = HTMLResponse(
                    content=(
                        "<!doctype html><html lang='ru'><head><meta charset='utf-8'/>"
                        "<meta name='viewport' content='width=device-width, initial-scale=1'/>"
                        "<meta http-equiv='Cache-Control' content='no-store'/>"
                        "<title>GuardSchool</title>"
                        f"<link rel='manifest' href='/pwa/t/{html.escape(code_canon, quote=True)}/{html.escape(slug_n, quote=True)}.webmanifest'/>"
                        "</head><body style='margin:0;font-family:system-ui;background:#0f172a;color:#e2e8f0'>"
                        "<div style='padding:24px;font-size:18px'>Запуск экрана…</div>"
                        "<script>(function(){try{"
                        f"var code={json.dumps(code_canon)}; var slug={json.dumps(slug_n)};"
                        "var k='gs_pwa_tv_token__'+code+'__'+slug;"
                        "var tok=localStorage.getItem(k)||'';"
                        "if(tok&&tok.length>10){location.replace('/t/'+encodeURIComponent(code)+'/'+encodeURIComponent(slug)+'?gs_tv_token='+encodeURIComponent(tok)+'&pwa=1');return;}"
                        "location.replace('/t/'+encodeURIComponent(code)+'/'+encodeURIComponent(slug)+'?pwa_pair=1');"
                        "}catch(e){location.replace('/t/"+ html.escape(code_canon, quote=True) + "/" + html.escape(slug_n, quote=True) + "?pwa_pair=1');}})();</script>"
                        "</body></html>"
                    ),
                    status_code=200,
                    headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache"},
                )
                resp.set_cookie(
                    SAAS_TENANT_COOKIE,
                    _encode_saas_tenant_cookie_value(ts),
                    max_age=3600 * 24 * 365,
                    httponly=True,
                    samesite="lax",
                    secure=sec,
                    path="/",
                )
                return resp
            lab = str(request.query_params.get("gs_label") or "").strip()[:120]
            tv_pair_record_success(pair_key)
            token = secrets.token_urlsafe(24)
            th = tv_device_token_hash(token)
            cur.execute(
                """
                INSERT INTO tv_devices (token_hash, tenant_slug, screen_slug, label, status)
                VALUES (%s,%s,%s,%s,'active')
                ON CONFLICT (token_hash) DO NOTHING
                """,
                (th, ts, slug_n, lab),
            )
        conn.commit()
    is_pwa_pair = str(request.query_params.get("pwa_pair") or "").strip() in ("1", "true", "yes")
    loc = _tv_pwa_screen_url(code_canon, slug_n, token, pwa=is_pwa_pair)
    # Часть ТВ-WebView даёт пустой экран на HTTP 302 с длинным Location — отдаём HTML и делаем переход из JS.
    loc_js = json.dumps(loc, ensure_ascii=False)
    loc_attr = html.escape(loc, quote=True)
    # Для PWA: сохранить токен 1 раз (если пришли из pwa_pair=1), чтобы последующие запуски ярлыка не плодили tv_devices.
    store_js = ""
    if is_pwa_pair:
        store_js = (
            "<script>(function(){try{"
            f"var k='gs_pwa_tv_token__'+{json.dumps(code_canon)}+'__'+{json.dumps(slug_n)};"
            f"localStorage.setItem(k,{json.dumps(token)});"
            f"localStorage.setItem('gs_pwa_tv_code__'+{json.dumps(slug_n)},{json.dumps(code_canon)});"
            "}catch(e){}})();</script>"
        )
    jump_html = (
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'/>"
        "<meta http-equiv='Cache-Control' content='no-store'/>"
        f"<link rel='manifest' href='/pwa/t/{html.escape(code_canon, quote=True)}/{html.escape(slug_n, quote=True)}.webmanifest'/>"
        f"<meta http-equiv='refresh' content='0;url={loc_attr}'/>"
        "<title>GuardSchool — подключение ТВ</title></head>"
        "<body style='margin:0;font-family:system-ui;background:#0f172a;color:#e2e8f0'>"
        "<div style='padding:24px;font-size:18px'>Переход на экран…</div>"
        f"{store_js}"
        f"<script>location.replace({loc_js});</script>"
        f"<noscript><div style='padding:24px'><a href='{loc_attr}' style='color:#38bdf8'>Открыть экран</a></div>"
        f"<meta http-equiv='refresh' content='0;url={loc_attr}'/></noscript></body></html>"
    )
    resp2 = HTMLResponse(
        content=jump_html,
        status_code=200,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache"},
    )
    sec = session_cookie_secure(request)
    resp2.set_cookie(
        SAAS_TENANT_COOKIE,
        _encode_saas_tenant_cookie_value(ts),
        max_age=3600 * 24 * 365,
        httponly=True,
        samesite="lax",
        secure=sec,
        path="/",
    )
    return resp2


@router.post("/api/tv/pair")
async def tv_pair(request: Request) -> dict[str, Any]:
    """
    Pairing экрана по короткому коду организации + PIN.
    Возвращает device-token (Bearer) и URL для перехода на /screen/{slug}.
    """
    require_capability(CAP_REMOTE_TV_PAIRING)
    if deployment_mode() != "saas" or not saas_db_enabled():
        raise HTTPException(status_code=404, detail="Not found.")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    code_raw = _normalize_tv_pair_text(str(body.get("code") or "")).lower()
    code = _canonical_tv_school_code(code_raw) or ""
    screen_slug = _normalize_screen_slug_for_api(str(body.get("screen_slug") or ""))
    label = str(body.get("label") or "").strip()[:120]
    if not code_raw or not screen_slug:
        raise HTTPException(status_code=400, detail="code, pin, screen_slug required")
    if not code:
        raise HTTPException(status_code=400, detail="Invalid code format")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", screen_slug):
        raise HTTPException(status_code=400, detail="Invalid screen_slug")
    now_ts = time.time()
    pair_key = tv_pair_client_key(request, code)
    retry_after = tv_pair_check_rate_limit(pair_key, now_ts)
    if retry_after > 0:
        raise HTTPException(status_code=429, detail=f"Too many attempts. Retry after {retry_after}s")

    with connect_public() as conn:
        with conn.cursor() as cur:
            row = tv_access_lookup_row(cur, code_canon=code)
            if not row:
                tv_pair_record_failure(pair_key, now_ts)
                raise HTTPException(status_code=403, detail="Invalid code or PIN")
            tenant_slug, pin_salt, pin_hash_db, pin_bypass_db = row[0], row[1], row[2], bool(row[3])
            ts = str(tenant_slug or "").strip()
            pin_bypass = tv_pair_pin_bypass_effective(ts, pin_bypass_db)
            if pin_bypass:
                pin = _normalize_tv_pair_text(str(body.get("pin") or "")).strip()
                if len(pin) > 48:
                    raise HTTPException(status_code=400, detail="PIN too long (bypass mode)")
                if not pin:
                    pin = "."
            else:
                pin = normalize_tv_pair_pin(str(body.get("pin") or ""))
                if not re.fullmatch(r"[0-9]{4,12}", pin):
                    raise HTTPException(status_code=400, detail="PIN must be 4..12 digits")
            if not pin_bypass:
                got = tv_pin_hash(pin, pin_salt)
                if not hmac.compare_digest(got, str(pin_hash_db or "")):
                    tv_pair_record_failure(pair_key, now_ts)
                    raise HTTPException(status_code=403, detail="Invalid code or PIN")

            tv_pair_record_success(pair_key)
            token = secrets.token_urlsafe(24)
            th = tv_device_token_hash(token)
            cur.execute(
                """
                INSERT INTO tv_devices (token_hash, tenant_slug, screen_slug, label, status)
                VALUES (%s,%s,%s,%s,'active')
                ON CONFLICT (token_hash) DO NOTHING
                """,
                (th, tenant_slug, screen_slug, label),
            )
        conn.commit()
    screen_path = _tv_pwa_screen_url(code, screen_slug, token, pwa=False)
    return {
        "status": "ok",
        "token": token,
        "tenant_slug": tenant_slug,
        "screen_slug": screen_slug,
        "screen_path": screen_path,
    }


@router.get("/api/admin/tv-access")
def admin_tv_access_get(request: Request) -> dict[str, Any]:
    require_capability(CAP_REMOTE_TV_PAIRING)
    require_auth(request)
    if deployment_mode() != "saas" or not saas_db_enabled():
        raise HTTPException(status_code=404, detail="Not found.")
    from .tenant_ctx import tenant_slug as current_tenant

    slug = current_tenant()
    if not slug:
        raise HTTPException(status_code=400, detail="Tenant is not resolved.")
    pin_db = False
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT code_plaintext, COALESCE(pin_bypass, false) FROM tv_access WHERE tenant_slug=%s",
                (slug,),
            )
            row = cur.fetchone()
            ok = bool(row)
            code = str(row[0] or "").strip() if row else ""
            pin_db = bool(row[1]) if row else False
        conn.commit()
    cfg = load_config()
    pin_cfg = bool(cfg.get("tv_pair_pin_bypass"))
    pin_env = tv_pair_pin_bypass_env()
    return {
        "status": "ok",
        "tenant_slug": slug,
        "configured": ok,
        "code": code,
        "pin_bypass_from_db": pin_db,
        "pin_bypass_from_config": pin_cfg,
        "pin_bypass_from_env": pin_env,
        "pin_bypass_effective": pin_env or pin_db or pin_cfg,
    }


@router.post("/api/admin/tv-access/rotate-code")
async def admin_tv_access_rotate_code(request: Request) -> dict[str, Any]:
    require_capability(CAP_REMOTE_TV_PAIRING)
    require_auth(request)
    if deployment_mode() != "saas" or not saas_db_enabled():
        raise HTTPException(status_code=404, detail="Not found.")
    from .tenant_ctx import tenant_slug as current_tenant

    slug = current_tenant()
    if not slug:
        raise HTTPException(status_code=400, detail="Tenant is not resolved.")
    # При первой записи задаём случайный PIN (не 0000) и возвращаем его один раз в ответе.
    code = generate_tv_code()
    ch = tv_code_hash(code)
    initial_pin: str | None = None
    pin_hint = "PIN не изменён."
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pin_salt, pin_hash FROM tv_access WHERE tenant_slug=%s", (slug,))
            row = cur.fetchone()
            if not row:
                pin_salt = secrets.token_hex(8)
                initial_pin = f"{secrets.randbelow(900_000) + 100_000:06d}"
                pin_hash_db = tv_pin_hash(initial_pin, pin_salt)
                pin_bypass_init = bool(load_config().get("tv_pair_pin_bypass"))
                cur.execute(
                    """
                    INSERT INTO tv_access (tenant_slug, code_plaintext, code_hash, pin_salt, pin_hash, pin_bypass, created_at, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,now(),now())
                    """,
                    (slug, code, ch, pin_salt, pin_hash_db, pin_bypass_init),
                )
                pin_hint = "Сохраните PIN — он показан один раз. При необходимости смените в настройках."
            else:
                pin_salt, pin_hash_db = row[0], row[1]
                cur.execute(
                    "UPDATE tv_access SET code_plaintext=%s, code_hash=%s, updated_at=now() WHERE tenant_slug=%s",
                    (code, ch, slug),
                )
        conn.commit()
    out: dict[str, Any] = {
        "status": "ok",
        "tenant_slug": slug,
        "code": code,
        "pin_hint": pin_hint,
    }
    if initial_pin is not None:
        out["initial_pin"] = initial_pin
    return out


@router.post("/api/admin/tv-access/set-pin")
async def admin_tv_access_set_pin(request: Request) -> dict[str, Any]:
    require_capability(CAP_REMOTE_TV_PAIRING)
    require_auth(request)
    if deployment_mode() != "saas" or not saas_db_enabled():
        raise HTTPException(status_code=404, detail="Not found.")
    from .tenant_ctx import tenant_slug as current_tenant

    slug = current_tenant()
    if not slug:
        raise HTTPException(status_code=400, detail="Tenant is not resolved.")
    body = await request.json()
    pin = normalize_tv_pair_pin(str(body.get("pin") or ""))
    if not re.fullmatch(r"[0-9]{4,12}", pin):
        raise HTTPException(status_code=400, detail="PIN must be 4..12 digits")
    pin_salt = secrets.token_hex(8)
    ph = tv_pin_hash(pin, pin_salt)
    with connect_public() as conn:
        with conn.cursor() as cur:
            # Требуем, чтобы код уже был сгенерен (иначе админ сначала rotate-code).
            cur.execute("SELECT code_hash FROM tv_access WHERE tenant_slug=%s", (slug,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=409, detail="TV code is not generated yet.")
            cur.execute(
                "UPDATE tv_access SET pin_salt=%s, pin_hash=%s, updated_at=now() WHERE tenant_slug=%s",
                (pin_salt, ph, slug),
            )
        conn.commit()
    return {"status": "ok"}


@router.post("/api/admin/tv-access/pin-bypass")
async def admin_tv_access_pin_bypass(request: Request) -> dict[str, Any]:
    """Включить/выключить обход PIN: tv_access.pin_bypass (источник для /t/…) + tv_pair_pin_bypass в config.json."""
    require_capability(CAP_REMOTE_TV_PAIRING)
    require_auth(request)
    if deployment_mode() != "saas" or not saas_db_enabled():
        raise HTTPException(status_code=404, detail="Not found.")
    from .tenant_ctx import tenant_slug as current_tenant

    slug = current_tenant()
    if not slug:
        raise HTTPException(status_code=400, detail="Tenant is not resolved.")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    if "enabled" not in body:
        raise HTTPException(status_code=400, detail="enabled required")
    enabled = bool(body.get("enabled"))
    db_written = False
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tv_access SET pin_bypass=%s, updated_at=now() WHERE tenant_slug=%s",
                (enabled, slug),
            )
            db_written = int(cur.rowcount or 0) > 0
        conn.commit()
    cfg = load_config()
    cfg["tv_pair_pin_bypass"] = enabled
    write_json(CONFIG_PATH, sanitize_config(cfg))
    _maybe_push_screen_content_if_data_revision_changed(request)
    return {
        "status": "ok",
        "pin_bypass_from_db": enabled if db_written else False,
        "pin_bypass_from_config": enabled,
    }
