"""RSS-новости: загрузка, кэш, нормализация полей для виджета."""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from .gs_jsonio import read_json, write_json
from .gs_paths import RSS_NEWS_CACHE_PATH

MAX_WIDGET_ITEMS = 5
HTTP_TIMEOUT_SEC = 8
USER_AGENT = "GuardSchoolRSS/1.0 (+https://guarddoc.ru)"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _safe_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return "".join(node.itertext()).strip()


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _parse_dt(raw: str) -> datetime | None:
    s = str(raw or "").strip()
    if not s:
        return None
    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _source_signature(sources: list[dict[str, Any]]) -> str:
    normalized = []
    for item in sources:
        normalized.append(
            {
                "name": str(item.get("name") or "").strip()[:120],
                "rss_url": str(item.get("rss_url") or "").strip()[:2000],
                "enabled": bool(item.get("enabled", True)),
            }
        )
    payload = str(sorted(normalized, key=lambda x: (x["name"], x["rss_url"])))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sanitize_rss_sources(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()[:120]
        rss_url = str(item.get("rss_url") or "").strip()[:2000]
        enabled = bool(item.get("enabled", True))
        parsed = urlparse(rss_url)
        if parsed.scheme not in ("http", "https"):
            continue
        if not parsed.netloc:
            continue
        if not name:
            name = parsed.netloc[:120]
        out.append({"name": name, "rss_url": rss_url, "enabled": enabled})
    return out


def sanitize_rss_refresh_minutes(raw: Any) -> int:
    try:
        val = int(raw)
    except (TypeError, ValueError):
        val = 45
    return max(30, min(60, val))


def _xml_items(xml_bytes: bytes, source_name: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_bytes)
    items: list[dict[str, Any]] = []

    channel = root.find("channel")
    if channel is not None:
        for node in channel.findall("item"):
            title = _safe_text(node.find("title"))
            link = _safe_text(node.find("link"))
            published = _parse_dt(_safe_text(node.find("pubDate")) or _safe_text(node.find("dc:date")))
            if not title or not link:
                continue
            items.append(
                {
                    "title": title[:300],
                    "link": link[:2000],
                    "source": source_name[:120],
                    "published_at": _iso_utc(published or _now_utc()),
                    "_sort_dt": published or datetime(1970, 1, 1, tzinfo=timezone.utc),
                }
            )
        return items

    # Atom (часто с namespace).
    for node in root.findall(".//{*}entry"):
        title = _safe_text(node.find("{*}title"))
        link_node = node.find("{*}link")
        link = ""
        if link_node is not None:
            link = str(link_node.attrib.get("href") or "").strip()
            if not link:
                link = _safe_text(link_node)
        published = _parse_dt(_safe_text(node.find("{*}published")) or _safe_text(node.find("{*}updated")))
        if not title or not link:
            continue
        items.append(
            {
                "title": title[:300],
                "link": link[:2000],
                "source": source_name[:120],
                "published_at": _iso_utc(published or _now_utc()),
                "_sort_dt": published or datetime(1970, 1, 1, tzinfo=timezone.utc),
            }
        )
    return items


def _fetch_source(rss_url: str, source_name: str) -> list[dict[str, Any]]:
    req = Request(rss_url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=HTTP_TIMEOUT_SEC) as resp:
        xml = resp.read()
    return _xml_items(xml, source_name)


def load_rss_news(config: dict[str, Any], *, force_refresh: bool = False) -> list[dict[str, Any]]:
    sources = sanitize_rss_sources(config.get("rss_sources"))
    refresh_minutes = sanitize_rss_refresh_minutes(config.get("rss_refresh_minutes", 45))
    sig = _source_signature(sources)
    cache = read_json(RSS_NEWS_CACHE_PATH, {"fetched_at": "", "sources_hash": "", "items": []})
    now = _now_utc()
    fetched_at = _parse_dt(cache.get("fetched_at"))
    cache_items = cache.get("items") if isinstance(cache.get("items"), list) else []
    if (
        not force_refresh
        and fetched_at is not None
        and (now - fetched_at).total_seconds() < refresh_minutes * 60
        and str(cache.get("sources_hash") or "") == sig
    ):
        return cache_items[:MAX_WIDGET_ITEMS]

    merged: list[dict[str, Any]] = []
    for src in sources:
        if not src.get("enabled", True):
            continue
        try:
            merged.extend(_fetch_source(src["rss_url"], src["name"]))
        except Exception:
            continue
    merged.sort(key=lambda x: x.get("_sort_dt") or datetime(1970, 1, 1, tzinfo=timezone.utc), reverse=True)
    out = []
    for item in merged[:MAX_WIDGET_ITEMS]:
        out.append(
            {
                "title": str(item.get("title") or "").strip()[:300],
                "link": str(item.get("link") or "").strip()[:2000],
                "source": str(item.get("source") or "").strip()[:120],
                "published_at": str(item.get("published_at") or ""),
            }
        )
    write_json(
        RSS_NEWS_CACHE_PATH,
        {
            "fetched_at": _iso_utc(now),
            "sources_hash": sig,
            "items": out,
        },
    )
    return out
