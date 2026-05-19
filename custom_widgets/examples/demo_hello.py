"""Пример стороннего виджета — не загружается автоматически (только из custom_widgets/)."""
from guardschool.widget_registry import register_widget

register_widget(
    {
        "type": "demo_hello",
        "title": "Demo Hello",
        "category": "basic",
        "api_version": 1,
        "official": False,
        "permissions": (),
        "render_key": "text",
        "requires_capabilities": [],
    }
)
