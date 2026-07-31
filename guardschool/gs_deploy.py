"""Режим развертывания (local/hybrid/saas) для условного UI/API."""
from __future__ import annotations

import os
from typing import Literal

DeploymentMode = Literal["local", "hybrid", "saas"]


def deployment_mode() -> DeploymentMode:
    """
    local  - автономная установка (файлы в data/, без облака)
    hybrid - автономная установка + опциональная синхронизация с облаком
    saas   - облако (мульти-тенант), синхра "с SaaS" не нужна
    """
    raw = (os.environ.get("GUARDSCHOOL_DEPLOYMENT_MODE") or "").strip().lower()
    if raw in ("local", "offline"):
        return "local"
    if raw in ("saas", "cloud"):
        return "saas"
    return "hybrid"

