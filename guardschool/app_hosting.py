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
    if bound:
        _tpl, iso = bound
        # v3 token подписан сервером и уже содержит единственный допустимый
        # isolated_slug. Технический host редиректа не является источником tenant.
        if not tenant_data_dir(iso).is_dir():
            return None
        return iso

    # Старые токены без isolated_slug допускаются только к отдельному sandbox,
    # никогда к slug из пользовательской cookie.
    from .app_try_demo import try_demo_sandbox_slug

    sandbox = try_demo_sandbox_slug()
    host = request_host_for_routing(request)
    if host_slug != sandbox and not is_public_school_host(host):
        return None
    if not tenant_data_dir(sandbox).is_dir():
        return None
    return sandbox

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
        host_slug: str | None = None
        if host.endswith(".guarddoc.ru"):
            left = host[: -len(".guarddoc.ru")]
            if (
                left
                and left not in ("www", "admin")
                and left != "school"
                and not is_public_school_host(host)
            ):
                host_slug = left
        slug: str | None = None
        demo_token = request.cookies.get(SESSION_COOKIE) or ""
        looks_like_demo = str(demo_token).startswith(("__gsdemo__:", "__gsdemo_v3__:"))
        if looks_like_demo:
            # Для демо cookie выбора тенанта не является доверенным источником.
            # Контекст берём только из действительного подписанного demo token.
            # Просроченный/повреждённый токен не должен откатываться к tenant-cookie.
            slug = demo_middleware_binding_slug(request, host_slug)
        else:
            # Обычная сессия: tenant из cookie, затем резерв из поддомена.
            cook_raw = request.cookies.get(SAAS_TENANT_COOKIE) or ""
            cook = decode_saas_tenant_cookie_value(cook_raw)
            if cook and 1 <= len(cook) <= 64 and cook not in ("www", "admin"):
                slug = cook
            if not slug:
                slug = host_slug
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
