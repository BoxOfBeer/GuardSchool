/**
 * Список плагинов ТВ (порядок после screen_widgets.js).
 * Classic TV: <script src="plugins-manifest.js"> → window.GUARD_SCHOOL_TV_WIDGET_PLUGINS
 * Admin (ESM): import "./widgets/plugins-manifest.js" → тот же global (без export — иначе SyntaxError на ТВ).
 */
(function (global) {
  const list = [
    "date.js",
    "time.js",
    "text.js",
    "blank.js",
    "emergency.js",
    "image.js",
    "bell_status.js",
    "bell_countdown.js",
    "holidays.js",
    "schedule.js",
    "announcements.js",
    "marquee.js",
    "school_news.js",
    "rss_news.js",
    "checkin_submit.js",
    "checkin_monitor.js",
  ];
  global.GUARD_SCHOOL_TV_WIDGET_PLUGINS = list;
})(typeof window !== "undefined" ? window : globalThis);
