from guardschool.widget_registry import register_widget

register_widget({
    "type": "bell_countdown",
    "title": "До сигнала",
    "category": "schedule",
    "api_version": 1,
    "official": True,
    "singleton_id": "bell_countdown",
    "render_key": "bell_countdown",
})
