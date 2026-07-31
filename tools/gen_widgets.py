#!/usr/bin/env python3
"""Regenerate widgets/*.py manifests."""
from pathlib import Path

SPECS = [
    ("date", "Дата", "basic", "date", ()),
    ("time", "Время", "basic", "time", ()),
    ("text", "Текст", "basic", "text", ()),
    ("image", "Изображение", "media", "image", ()),
    ("bell_status", "Звонки", "schedule", "bell_status", ()),
    ("bell_countdown", "До звонка", "schedule", "bell_countdown", ()),
    ("schedule", "Расписание", "schedule", "schedule", ()),
    ("carousel", "Карусель", "media", None, ()),
    ("holidays", "События", "schedule", "holidays", ()),
    ("announcements", "Объявления", "schedule", "announcements", ()),
    ("school_news", "Новости школы", "news", "school_news", ()),
    ("rss_news", "RSS-новости", "news", "rss_news", ("rss_feed", "external_news")),
    ("marquee", "Бегущая строка", "media", "marquee", ()),
    ("emergency", "Аварийка", "safety", "emergency", ()),
    ("checkin_submit", "Отметка", "checkin", None, ()),
    ("checkin_monitor", "Монитор отметок", "checkin", None, ()),
]

wd = Path(__file__).resolve().parent.parent / "widgets"
for wtype, title, cat, sid, aliases in SPECS:
    lines = [
        "from guardschool.widget_registry import register_widget",
        "",
        "register_widget({",
        f'    "type": "{wtype}",',
        f'    "title": "{title}",',
        f'    "category": "{cat}",',
        '    "api_version": 1,',
        '    "official": True,',
    ]
    if sid:
        lines.append(f'    "singleton_id": "{sid}",')
    if aliases:
        al = ", ".join(repr(a) for a in aliases)
        lines.append(f'    "aliases": ({al},),')
    lines.append(f'    "render_key": "{wtype}",')
    lines.append("})")
    lines.append("")
    (wd / f"{wtype}.py").write_text("\n".join(lines), encoding="utf-8")
print("wrote", len(SPECS), "files")
