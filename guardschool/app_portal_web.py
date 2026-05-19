"""Portal web (guarddoc.ru): фасад register_routes."""
from __future__ import annotations

from fastapi import FastAPI

from ._private_facade import load_private_backend


def register_portal_web_routes(app: FastAPI) -> None:
    load_private_backend("app_portal_web").register_routes(app)
