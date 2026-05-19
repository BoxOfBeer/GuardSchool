"""FastAPI SaaS tenant middleware (cookie/host → tenant_ctx)."""
from __future__ import annotations

from fastapi import FastAPI, Request

from .app_host_routing import (
    is_public_school_host,
    request_host_for_routing,
)
from .gs_auth import demo_v3_binding_from_token, verify_demo_session_token
from .gs_deploy import deployment_mode
from .gs_paths import SAAS_TENANT_COOKIE, SESSION_COOKIE
from .gs_tv_screen_api import decode_saas_tenant_cookie_value


def register_hosting_middleware(app: FastAPI) -> None:
    app.middleware("http")(tenant_middleware)


def demo_middleware_binding_slug(request: Request, host_slug: str | None) -> str | None:
    """
    Если активна демо-сессия v3, подменяем tenant_slug на изолированную копию,
    но только когда Host/cookie указывают на тот же шаблонный тенант (защита от подстановки чужого slug).
    """
    from .tenant_ctx import tenant_data_dir

    tok = request.cookies.get(SESSION_COOKIE) or ""
    if not verify_demo_session_token(tok):
        return None
    bound = demo_v3_binding_from_token(tok)
    if not bound:
        return None
    tpl, iso = bound
    if not host_slug or tpl != host_slug:
        return None
    if not tenant_data_dir(iso).is_dir():
        return None
    return iso

async def tenant_middleware(request: Request, call_next):
    """
    SaaS: каталог данных schools → tenants/<slug>/data.

    На проде один входной хост school.guarddoc.ru; поддомены под каждого клиента нет —
    внутренний slug школы (папка тенанта, связка с лицензией в БД) задаётся cookie gs_saas_tenant
    после авторизации/выбора школы, либо контекстом ТВ (Bearer / ?gs_tv_token= и т.д.).

    Имя поддомена «school» никогда не становится tenant slug: иначе подтягивается устаревшая tenants/school/.
    Дополнительно: если задан GUARDSCHOOL_PUBLIC_SCHOOL_HOST и Host ему совпадает — из поддомена slug не берём.
    Резерв «tenant = левая часть *.guarddoc.ru» оставлен для редких отладочных/кастомных хостов.
    """
    from .tenant_ctx import set_tenant_slug

    if deployment_mode() == "saas":
        host = request_host_for_routing(request)
        slug: str | None = None
        # 1) Если cookie gs_saas_tenant уже есть — используем её для tenant routing,
        # даже при доступе по IP/локальному хосту (на ТВ часто открывают прямой адрес).
        cook_raw = request.cookies.get(SAAS_TENANT_COOKIE) or ""
        cook = decode_saas_tenant_cookie_value(cook_raw)
        if cook and 1 <= len(cook) <= 64 and cook not in ("www", "admin"):
            slug = cook
        # 2) Если cookie нет, на публичном school.* тоже смотрим cookie (исторически).
        if not slug and is_public_school_host(host):
            cook2_raw = request.cookies.get(SAAS_TENANT_COOKIE) or ""
            cook2 = decode_saas_tenant_cookie_value(cook2_raw)
            if cook2 and 1 <= len(cook2) <= 64 and cook2 not in ("www", "admin"):
                slug = cook2
        # 3) Резерв: tenant из поддомена *.guarddoc.ru (не основной сценарий: у вас только school.*).
        # «school» не маппим в slug — общий вход; без cookie slug остаётся None (не подмешивать legacy tenants/school).
        # Совпадение с GUARDSCHOOL_PUBLIC_SCHOOL_HOST тоже отключает вывод slug из Host.
        if not slug and host.endswith(".guarddoc.ru"):
            left = host[: -len(".guarddoc.ru")]
            if (
                left
                and left not in ("www", "admin")
                and left != "school"
                and not is_public_school_host(host)
            ):
                slug = left
        # portal: guarddoc.ru / www.guarddoc.ru -> slug остаётся None
        bound = demo_middleware_binding_slug(request, slug)
        if bound:
            slug = bound
        set_tenant_slug(slug)
        if slug:
            try:
                from .saas_db import ensure_tenant_schema, saas_db_enabled, schema_name_for_slug

                if saas_db_enabled():
                    ensure_tenant_schema(schema_name_for_slug(slug))
            except Exception:
                pass
    try:
        return await call_next(request)
    finally:
        if deployment_mode() == "saas":
            set_tenant_slug(None)
