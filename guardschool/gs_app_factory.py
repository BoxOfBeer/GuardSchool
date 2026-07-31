"""Сборка FastAPI-приложения GuardSchool (роутеры, middleware, static)."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .app_hosting import register_hosting_middleware
from .app_lifecycle import guard_school_lifespan
from .app_portal_web import register_portal_web_routes
from .app_pwa_manifest import register_pwa_manifest_routes
from .app_saas_portal import register_saas_portal_routes
from .commercial_routes import configure_commercial_http
from .gs_paths import STATIC_DIR
from .layer_loader import apply_layer_routes
from .routes_admin import register_admin_routes
from .routes_auth import register_auth_routes
from .routes_pages import register_page_routes
from .routes_public import register_public_routes
from .routes_screen import register_screen_routes
from .routes_booking import router as booking_router
from .saas_routes import configure_saas_http


def create_app() -> FastAPI:
    application = FastAPI(title="GuardSchool", lifespan=guard_school_lifespan)
    apply_layer_routes(application)
    configure_saas_http(application)
    configure_commercial_http(application)
    register_saas_portal_routes(application)
    register_pwa_manifest_routes(application)
    register_portal_web_routes(application)
    register_admin_routes(application)
    register_screen_routes(application)
    application.include_router(booking_router)
    register_public_routes(application)
    register_auth_routes(application)
    register_page_routes(application)
    register_hosting_middleware(application)
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return application
