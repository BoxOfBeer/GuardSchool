"""Community: без SaaS portal demo routes."""
from __future__ import annotations

from fastapi import APIRouter, FastAPI

router = APIRouter(tags=["saas-portal-stub"])


def register_routes(app: FastAPI) -> None:
    return
