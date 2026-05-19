from guardschool.widget_registry import register_widget

register_widget({
    "type": "rss_news",
    "title": "RSS-новости",
    "category": "news",
    "api_version": 1,
    "official": True,
    "singleton_id": "rss_news",
    "aliases": ('rss_feed', 'external_news',),
    "render_key": "rss_news",
})
