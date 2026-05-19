/**
 * Список плагинов ТВ (порядок после screen_widgets.js).
 * Classic TV: window.GUARD_SCHOOL_TV_WIDGET_PLUGINS
 * Admin (ESM): import { TV_WIDGET_PLUGIN_SCRIPTS } from "./widgets/plugins-manifest.js"
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

export const TV_WIDGET_PLUGIN_SCRIPTS =
  (typeof globalThis !== "undefined" && globalThis.GUARD_SCHOOL_TV_WIDGET_PLUGINS) || [
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
