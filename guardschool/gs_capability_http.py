"""HTTP-хелперы для проверки capabilities."""
from __future__ import annotations

from fastapi import HTTPException

from .capabilities import explain_capability_status, has_capability


def require_capability(cap_id: str, *, status_code: int = 503) -> None:
    if has_capability(cap_id):
        return
    raise HTTPException(
        status_code=status_code,
        detail=explain_capability_status(cap_id),
    )
