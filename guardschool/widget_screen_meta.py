"""Обогащение виджетов на экране метаданными из registry (render_key)."""
from __future__ import annotations

from typing import Any

from .widget_loader import load_all_widgets
from .widget_registry import get_widget, resolve_type


def enrich_screen_widgets_meta(screen: dict[str, Any]) -> dict[str, Any]:
  load_all_widgets()
  widgets = screen.get("widgets")
  if not isinstance(widgets, list):
    return screen
  for raw in widgets:
    if not isinstance(raw, dict):
      continue
    wtype = resolve_type(str(raw.get("type") or ""))
    m = get_widget(wtype)
    if m is None:
      continue
    raw["render_key"] = m.render_key
    if m.requires_capabilities:
      raw["requires_capabilities"] = list(m.requires_capabilities)
  return screen
