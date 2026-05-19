"""JSON Schema (draft-07 subset) для settings виджетов — админка и API registry."""
from __future__ import annotations

from typing import Any

_SCHEMA_VERSION = "https://json-schema.org/draft/2020-12/schema"

_FONT = {
    "fontSize": {"type": "integer", "minimum": 8, "maximum": 200},
    "color": {"type": "string"},
    "bold": {"type": "boolean"},
    "background": {"type": "string"},
}

_TITLE_FONT = {
    "titleFontSize": {"type": "integer", "minimum": 8, "maximum": 120},
    **_FONT,
}


def _obj(props: dict[str, Any], *, required: list[str] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "$schema": _SCHEMA_VERSION,
        "type": "object",
        "additionalProperties": True,
        "properties": props,
    }
    if required:
        out["required"] = required
    return out


_SCHEMAS: dict[str, dict[str, Any]] = {
    "date": _obj(_FONT),
    "time": _obj(_FONT),
    "text": _obj({**_FONT, "text": {"type": "string"}}, required=["text"]),
    "blank": _obj({}),
    "bell_status": _obj(_TITLE_FONT),
    "bell_countdown": _obj(_TITLE_FONT),
    "schedule": _obj(
        {
            **_FONT,
            "showTomorrow": {"type": "boolean"},
            "compact": {"type": "boolean"},
        },
    ),
    "holidays": _obj({**_TITLE_FONT, "count": {"type": "integer", "minimum": 1, "maximum": 30}}),
    "announcements": _obj(
        {
            **_FONT,
            "items": {"type": "string"},
            "useManual": {"type": "boolean"},
            "rotateSec": {"type": "integer", "minimum": 5, "maximum": 3600},
            "randomize": {"type": "boolean"},
            "advanceOnShow": {"type": "boolean"},
        },
    ),
    "marquee": _obj(
        {
            **_FONT,
            "speed": {"type": "number", "minimum": 0.1, "maximum": 20},
            "direction": {"type": "string", "enum": ["left", "right"]},
        },
    ),
    "school_news": _obj(
        {
            **_FONT,
            "rotateSec": {"type": "integer", "minimum": 5, "maximum": 3600},
            "showQr": {"type": "boolean"},
        },
    ),
    "rss_news": _obj(
        {
            **_FONT,
            "feedUrl": {"type": "string"},
            "maxItems": {"type": "integer", "minimum": 1, "maximum": 50},
        },
    ),
    "emergency": _obj(
        {
            "text": {"type": "string"},
            "fontSize": {"type": "integer", "minimum": 10, "maximum": 200},
            "color": {"type": "string"},
            "background": {"type": "string"},
            "bold": {"type": "boolean"},
            "imageUrl": {"type": "string"},
            "imageCaption": {"type": "string"},
            "timerRemainingSec": {"type": "integer", "minimum": 0},
            "timerShowZero": {"type": "boolean"},
        },
    ),
    "image": _obj(
        {
            "imageUrl": {"type": "string"},
            "images": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "url": {"type": "string"},
                    },
                },
            },
            "opacity": {"type": "integer", "minimum": 0, "maximum": 100},
            "objectFit": {"type": "string", "enum": ["contain", "cover"]},
            "imagesRotateSec": {"type": "integer", "minimum": 0, "maximum": 86400},
        },
    ),
    "carousel": _obj(
        {
            "startDelaySec": {"type": "number", "minimum": 0},
            "slideDurationSec": {"type": "number", "minimum": 1},
            "animation": {"type": "string"},
            "randomAnimation": {"type": "boolean"},
        },
    ),
    "checkin_submit": _obj(
        {
            "fontSize": {"type": "integer", "minimum": 10, "maximum": 48},
            "bold": {"type": "boolean"},
            "labels": {"type": "object", "additionalProperties": {"type": "string"}},
        },
    ),
    "checkin_monitor": _obj(
        {
            "fontSize": {"type": "integer", "minimum": 10, "maximum": 48},
            "bold": {"type": "boolean"},
            "panel_title": {"type": "string"},
        },
    ),
}


def schema_for_type(wtype: str) -> dict[str, Any]:
    from .widget_registry import resolve_type

    key = resolve_type(wtype)
    base = _SCHEMAS.get(key)
    if base is None:
        return _obj({})
    return dict(base)


def apply_default_schema(manifest_dict: dict[str, Any]) -> dict[str, Any]:
    """Если settings_schema пуст — подставить из каталога."""
    if manifest_dict.get("settings_schema"):
        return manifest_dict
    wtype = str(manifest_dict.get("type") or "")
    manifest_dict = dict(manifest_dict)
    manifest_dict["settings_schema"] = schema_for_type(wtype)
    return manifest_dict
