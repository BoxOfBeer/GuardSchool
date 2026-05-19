"""Регистрация встроенных (official) виджетов поставки."""
from __future__ import annotations

from .widget_registry import WidgetManifest, register_widget

_BUILTIN_SPECS: list[dict] = [
    {"type": "date", "title": "Дата", "category": "basic", "singleton_id": "date"},
    {"type": "time", "title": "Время", "category": "basic", "singleton_id": "time"},
    {"type": "text", "title": "Текст", "category": "basic", "singleton_id": "text"},
    {"type": "bell_status", "title": "Сигналы", "category": "schedule", "singleton_id": "bell_status"},
    {"type": "bell_countdown", "title": "До сигнала", "category": "schedule", "singleton_id": "bell_countdown"},
    {"type": "schedule", "title": "Расписание", "category": "schedule", "singleton_id": "schedule"},
    {"type": "carousel", "title": "Карусель", "category": "media"},
    {"type": "holidays", "title": "События", "category": "schedule", "singleton_id": "holidays"},
    {"type": "announcements", "title": "Объявления", "category": "schedule", "singleton_id": "announcements"},
    {"type": "school_news", "title": "Новости", "category": "news", "singleton_id": "school_news"},
    {
        "type": "rss_news",
        "title": "RSS-новости",
        "category": "news",
        "singleton_id": "rss_news",
        "aliases": ("rss_feed", "external_news"),
    },
    {"type": "marquee", "title": "Бегущая строка", "category": "media", "singleton_id": "marquee"},
    {"type": "emergency", "title": "Аварийка", "category": "safety", "singleton_id": "emergency"},
    {"type": "image", "title": "Изображение", "category": "media", "singleton_id": "image"},
    {"type": "checkin_submit", "title": "Отметка", "category": "checkin"},
    {"type": "checkin_monitor", "title": "Монитор отметок", "category": "checkin"},
]


def register_builtin_widgets() -> None:
    for spec in _BUILTIN_SPECS:
        sid = spec.get("singleton_id")
        register_widget(
            WidgetManifest(
                type=spec["type"],
                title=spec["title"],
                category=spec.get("category", "basic"),
                api_version=1,
                official=True,
                singleton_id=sid,
                aliases=tuple(spec.get("aliases") or ()),
                render_key=spec["type"],
            )
        )
