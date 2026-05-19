"""Портал CMS (guarddoc.ru): фасад."""
from __future__ import annotations

from typing import Any

from ._private_facade import facade_dir, facade_getattr

_NAME = "gs_portal_cms"


def __getattr__(name: str) -> Any:
    return facade_getattr(_NAME, name)


def __dir__() -> list[str]:
    return facade_dir(_NAME)
