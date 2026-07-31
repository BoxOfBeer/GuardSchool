"""SaaS portal demo routes: фасад register_routes."""
from __future__ import annotations

from fastapi import FastAPI

from .private_modules import module_present


def register_saas_portal_routes(app: FastAPI) -> None:
    if not module_present("app_saas_portal"):
        return
    from importlib import import_module

    mod = import_module("guardschool._app_saas_portal_pg")
    mod.register_routes(app)
