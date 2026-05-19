"""Определение Host для портала guarddoc.ru и school.* (open-core)."""
from __future__ import annotations

import os

from fastapi import Request


def request_host_for_routing(request: Request) -> str:
    host = (request.headers.get("host") or "").split(":")[0].strip().lower()
    if host in ("127.0.0.1", "localhost", "[::1]") or host.startswith("127."):
        ff = (request.headers.get("x-forwarded-host") or "").strip()
        if ff:
            return ff.split(",")[0].strip().split(":")[0].strip().lower()
    return host


def portal_request_host(request: Request) -> str:
    return request_host_for_routing(request)


def is_guarddoc_portal_host(host: str) -> bool:
    return host in ("guarddoc.ru", "www.guarddoc.ru")


def is_guarddoc_portal(request: Request) -> bool:
    return is_guarddoc_portal_host(portal_request_host(request))


def public_school_host_normalized() -> str | None:
    raw = (os.environ.get("GUARDSCHOOL_PUBLIC_SCHOOL_HOST") or "").strip().lower()
    if not raw:
        return None
    return raw.split(":")[0]


def is_public_school_host(host: str) -> bool:
    pub = public_school_host_normalized()
    return bool(pub and host.split(":")[0].strip().lower() == pub)
