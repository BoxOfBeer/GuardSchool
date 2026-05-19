"""Монтирование SaaS HTTP: слой, embedded (_routes_*_pg) или stubs (community local)."""
from __future__ import annotations

from fastapi import FastAPI

from .gs_deploy import deployment_mode
from .layer_loader import is_saas_layer_loaded, saas_layer_mounted_groups

SAAS_ROUTE_GROUP_FEEDBACK = "feedback"
SAAS_ROUTE_GROUP_CLOUD_SYNC = "cloud_sync"
SAAS_ROUTE_GROUP_CLOUD_STATUS = "cloud_status"
SAAS_ROUTE_GROUP_PUSH = "push"
SAAS_ROUTE_GROUP_TV = "tv"

ALL_SAAS_ROUTE_GROUPS = (
    SAAS_ROUTE_GROUP_FEEDBACK,
    SAAS_ROUTE_GROUP_CLOUD_SYNC,
    SAAS_ROUTE_GROUP_CLOUD_STATUS,
    SAAS_ROUTE_GROUP_PUSH,
    SAAS_ROUTE_GROUP_TV,
)


def embedded_saas_modules_present() -> bool:
    """Полные SaaS routes и backend-модули в tree или guardschool_private."""
    from .private_modules import module_present

    return (
        module_present("gs_push")
        and module_present("gs_feedback")
        and module_present("gs_sync_http")
        and module_present("routes_push")
        and module_present("routes_feedback")
        and module_present("routes_cloud_sync")
        and         module_present("routes_cloud_status")
        and module_present("routes_tv")
    )


def should_mount_embedded_saas_routes() -> bool:
    if deployment_mode() == "local":
        return False
    if is_saas_layer_loaded():
        return False
    return embedded_saas_modules_present()


def _mount_router_pg(app: FastAPI, module_basename: str) -> None:
    from .private_modules import module_present

    if not module_present(module_basename):
        return
    from importlib import import_module

    mod = import_module(f"guardschool._{module_basename}_pg")
    app.include_router(mod.router)


def mount_saas_feedback(app: FastAPI) -> None:
    _mount_router_pg(app, "routes_feedback")


def mount_saas_cloud_sync(app: FastAPI) -> None:
    _mount_router_pg(app, "routes_cloud_sync")


def mount_saas_cloud_status(app: FastAPI) -> None:
    _mount_router_pg(app, "routes_cloud_status")


def mount_saas_push(app: FastAPI) -> None:
    _mount_router_pg(app, "routes_push")


def mount_saas_tv(app: FastAPI) -> None:
    _mount_router_pg(app, "routes_tv")


def mount_all_saas_routes(app: FastAPI) -> None:
    mount_saas_feedback(app)
    mount_saas_cloud_sync(app)
    mount_saas_cloud_status(app)
    mount_saas_push(app)
    mount_saas_tv(app)


def mount_saas_stubs(app: FastAPI) -> None:
    from .routes_saas_stubs import router

    app.include_router(router)


def configure_saas_http(app: FastAPI) -> None:
    mounted = saas_layer_mounted_groups()
    if mounted:
        return
    if should_mount_embedded_saas_routes():
        mount_all_saas_routes(app)
        return
    mount_saas_stubs(app)
