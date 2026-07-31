from guardschool.widget_registry import register_widget

register_widget({
    "type": "announcements",
    "title": "Объявления",
    "category": "schedule",
    "api_version": 1,
    "official": True,
    "singleton_id": "announcements",
    "render_key": "announcements",
})
