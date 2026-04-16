"""Создание первого администратора из env для SaaS (демо без ручного /setup)."""
from __future__ import annotations

import logging
import os
import secrets

from .gs_auth import hash_password, load_auth, password_is_valid
from .gs_ensure_dirs import ensure_dirs
from .gs_jsonio import write_json
from .gs_paths import AUTH_PATH
from .gs_saas_limits import saas_mode

_LOG = logging.getLogger(__name__)


def ensure_saas_bootstrap_admin() -> None:
    """Если GUARDSCHOOL_SAAS_MODE и задан GUARDSCHOOL_ADMIN_PASSWORD — создать auth.json при пустой БД."""
    if not saas_mode():
        return
    if (os.environ.get("GUARDSCHOOL_SKIP_SAAS_BOOTSTRAP") or "").strip().lower() in ("1", "true", "yes"):
        return
    pwd = (os.environ.get("GUARDSCHOOL_ADMIN_PASSWORD") or "").strip()
    if not pwd:
        return
    if load_auth():
        return
    if not password_is_valid(pwd):
        _LOG.warning("GUARDSCHOOL_ADMIN_PASSWORD задан, но не проходит проверку сложности — пропуск bootstrap.")
        return
    ensure_dirs()
    user = (os.environ.get("GUARDSCHOOL_ADMIN_USERNAME") or "admin").strip() or "admin"
    salt = secrets.token_hex(16)
    write_json(
        AUTH_PATH,
        {"username": user, "salt": salt, "password_hash": hash_password(pwd, salt)},
    )
    _LOG.info("SaaS: создан администратор из env (логин: %s).", user)
