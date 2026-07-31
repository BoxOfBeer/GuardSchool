"""Монтирование commercial HTTP: слой, embedded (_routes_commercial_pg) или stubs."""
from __future__ import annotations

from fastapi import FastAPI

from .gs_deploy import deployment_mode
from .layer_loader import commercial_routes_mounted_by_layer, is_commercial_layer_loaded

COMMERCIAL_ROUTE_GROUP = "commercial"


def embedded_commercial_modules_present() -> bool:
    from .private_modules import module_present

    return (
        module_present("saas_db")
        and module_present("provider_licenses")
        and module_present("routes_commercial")
    )


def should_mount_embedded_commercial_routes() -> bool:
    if deployment_mode() == "local":
        return False
    if is_commercial_layer_loaded():
        return False
    return embedded_commercial_modules_present()


def mount_commercial_routes(app: FastAPI) -> None:
    from .private_modules import module_present

    if not module_present("routes_commercial"):
        return
    from importlib import import_module

    mod = import_module("guardschool._routes_commercial_pg")
    app.include_router(mod.router)


def mount_commercial_stubs(app: FastAPI) -> None:
    from .routes_commercial_stubs import router

    app.include_router(router)


def configure_commercial_http(app: FastAPI) -> None:
    if commercial_routes_mounted_by_layer():
        return
    if should_mount_embedded_commercial_routes():
        mount_commercial_routes(app)
        return
    mount_commercial_stubs(app)
