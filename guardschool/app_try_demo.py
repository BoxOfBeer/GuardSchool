"""Песочница и токены публичного /try-demo (SaaS)."""
from __future__ import annotations

import os
import secrets
import shutil
from datetime import timedelta
from pathlib import Path

from .gs_auth import hash_password, load_auth, password_is_valid
from .gs_deploy import deployment_mode
from .gs_ensure_dirs import ensure_dirs
from .gs_jsonio import read_json, write_json
from .gs_paths import (
    ANNOUNCEMENTS_PATH,
    AUTH_PATH,
    BELL_SCHEDULES_PATH,
    BREAK_MUSIC_DIR,
    CONFIG_PATH,
    FULL_SCHEDULE_PATH,
    HOLIDAYS_PATH,
    MARQUEE_PATH,
    OVERRIDES_PATH,
    SCHEDULE_PATH,
    SCHEDULE_SAMPLE_PATH,
    SCHOOL_NEWS_PATH,
    UPLOADS_DIR,
)
from .saas_db import ensure_tenant_schema, saas_db_enabled, schema_name_for_slug, utcnow
from .tenant_ctx import set_tenant_slug, tenant_slug as current_tenant_slug


def try_demo_redirect_host(slug: str) -> str:
    explicit = (os.environ.get("GUARDSCHOOL_TRY_DEMO_REDIRECT_HOST") or "").strip().lower()
    if explicit:
        return explicit.split(":")[0]
    if (os.environ.get("GUARDSCHOOL_TRY_DEMO_USE_PUBLIC_SCHOOL_HOST") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        fixed = (os.environ.get("GUARDSCHOOL_PUBLIC_SCHOOL_HOST") or "").strip().lower()
        if fixed:
            return fixed.split(":")[0]
    s = (slug or "demo").strip().lower()
    return f"{s}.guarddoc.ru"


def try_demo_sandbox_slug() -> str:
    return (os.environ.get("GUARDSCHOOL_DEMO_TENANT_SLUG") or "demo").strip().lower()


def seed_try_demo_library_from_env() -> None:
    from .tenant_ctx import map_data_path

    raw = (os.environ.get("GUARDSCHOOL_TRY_DEMO_LIBRARY_DIR") or "").strip()
    if not raw:
        return
    src_root = Path(raw).resolve()
    if not src_root.is_dir():
        return
    for sub, dest_base in (("uploads", UPLOADS_DIR), ("break_music", BREAK_MUSIC_DIR)):
        sub_path = src_root / sub
        if not sub_path.is_dir():
            continue
        dest = map_data_path(dest_base)
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(sub_path, dest, dirs_exist_ok=True)


def ensure_try_demo_sandbox_tenant_data() -> None:
    if deployment_mode() != "saas" or not saas_db_enabled():
        return
    slug = try_demo_sandbox_slug()
    if not slug:
        return
    prev = current_tenant_slug()
    set_tenant_slug(slug)
    try:
        ensure_tenant_schema(schema_name_for_slug(slug))
        ensure_dirs()
        try:
            seed_try_demo_library_from_env()
        except Exception:
            pass
        if not AUTH_PATH.exists() or not load_auth():
            salt = secrets.token_hex(16)
            pwd = (os.environ.get("GUARDSCHOOL_TRY_DEMO_ADMIN_PASSWORD") or "").strip()
            if not pwd or not password_is_valid(pwd):
                pwd = secrets.token_urlsafe(14) + "Xa9"
                if not password_is_valid(pwd):
                    pwd = "TryDemoSandbox1a"
            user = (os.environ.get("GUARDSCHOOL_TRY_DEMO_ADMIN_USERNAME") or "try-demo").strip() or "try-demo"
            write_json(AUTH_PATH, {"username": user, "salt": salt, "password_hash": hash_password(pwd, salt)})
        reset_demo = (os.environ.get("GUARDSCHOOL_TRY_DEMO_RESET_ON_START") or "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        if reset_demo:
            write_json(CONFIG_PATH, {"ui_locale": "ru", "screens": []})
            write_json(SCHEDULE_PATH, [])
            write_json(FULL_SCHEDULE_PATH, [])
            write_json(SCHEDULE_SAMPLE_PATH, [])
            write_json(HOLIDAYS_PATH, [])
            write_json(ANNOUNCEMENTS_PATH, [])
            write_json(SCHOOL_NEWS_PATH, [])
            write_json(MARQUEE_PATH, [])
            write_json(OVERRIDES_PATH, [])
            write_json(BELL_SCHEDULES_PATH, {})
        elif not CONFIG_PATH.exists():
            write_json(CONFIG_PATH, {"ui_locale": "ru", "screens": []})
    finally:
        set_tenant_slug(prev)


def try_demo_ttl_minutes() -> int:
    try:
        n = int((os.environ.get("GUARDSCHOOL_TRY_DEMO_MINUTES") or "60").strip())
    except Exception:
        n = 60
    return max(5, min(180, n))


def try_demo_public_enabled() -> bool:
    return (os.environ.get("GUARDSCHOOL_TRY_DEMO_DISABLE") or "").strip().lower() not in ("1", "true", "yes", "on")


def demo_allow_any_tenant_token() -> bool:
    return (os.environ.get("GUARDSCHOOL_DEMO_ALLOW_ANY_TENANT") or "").strip().lower() in ("1", "true", "yes", "on")


def demo_exit_redirect_url() -> str:
    u = (os.environ.get("GUARDSCHOOL_DEMO_EXIT_URL") or os.environ.get("GUARDSCHOOL_PORTAL_PUBLIC_URL") or "").strip()
    if u:
        return u.rstrip("/")
    return "https://guarddoc.ru"
