from guardschool.widget_registry import register_widget

register_widget({
    "type": "school_news",
    "title": "Новости",
    "category": "news",
    "api_version": 1,
    "official": True,
    "singleton_id": "school_news",
    "render_key": "school_news",
})
