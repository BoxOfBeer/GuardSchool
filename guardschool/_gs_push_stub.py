"""Community stub: Web Push отключён."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RateLimitDecision:
    should_send: bool = False
    pending_count: int = 0


def ensure_push_tables() -> None:
    return


def try_claim_content_push_revision_change(*, tenant_id: str, new_revision: str) -> bool:
    return False


def utc_iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sanitize_topics(raw: Any) -> dict[str, bool]:
    return {}


def upsert_subscription(**kwargs: Any) -> None:
    return


def delete_subscription(**kwargs: Any) -> int:
    return 0


def webpush_subscription_stale(exc: BaseException) -> bool:
    return False


def list_subscriptions(**kwargs: Any) -> list[dict[str, Any]]:
    return []


def rate_limit_decide(**kwargs: Any) -> RateLimitDecision:
    return RateLimitDecision(False, 0)


def vapid_public_key() -> str:
    return ""


def vapid_private_key() -> str:
    return ""


def vapid_private_key_for_webpush() -> str:
    return ""


def vapid_application_server_key() -> str:
    return ""


def vapid_subject() -> str:
    return "mailto:adm@guarddoc.ru"
