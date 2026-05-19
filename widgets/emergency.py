from guardschool.widget_registry import register_widget

register_widget({
    "type": "emergency",
    "title": "Аварийка",
    "category": "safety",
    "api_version": 1,
    "official": True,
    "singleton_id": "emergency",
    "render_key": "emergency",
})
