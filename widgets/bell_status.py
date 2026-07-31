from guardschool.widget_registry import register_widget

register_widget({
    "type": "bell_status",
    "title": "Сигналы",
    "category": "schedule",
    "api_version": 1,
    "official": True,
    "singleton_id": "bell_status",
    "render_key": "bell_status",
})
