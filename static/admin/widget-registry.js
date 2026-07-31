/**
 * Кэш реестра виджетов с сервера (GET /api/widgets/registry или config._meta.widget_registry).
 */
let _registry = null;

const FALLBACK_TYPES = [
  "date",
  "time",
  "text",
  "bell_status",
  "bell_countdown",
  "schedule",
  "carousel",
  "holidays",
  "announcements",
  "school_news",
  "rss_news",
  "marquee",
  "emergency",
  "image",
  "checkin_submit",
  "checkin_monitor",
  "booking_public",
  "booking_manager",
];

const FALLBACK_ORDER = [...FALLBACK_TYPES];

export function applyWidgetRegistry(data) {
  if (data && typeof data === "object") {
    _registry = data;
  }
}

export function getWidgetRegistry() {
  return _registry;
}

export function getWidgetTypeKeys() {
  const widgets = (_registry && _registry.widgets) || [];
  if (widgets.length) {
    return new Set(widgets.map((w) => w.type).filter(Boolean));
  }
  return new Set(FALLBACK_TYPES);
}

export function getPaletteTypesOrder() {
  const order = (_registry && _registry.palette_order) || [];
  if (order.length) return [...order];
  return [...FALLBACK_ORDER];
}

export function getSingletonIds() {
  const ids = (_registry && _registry.singleton_ids) || {};
  if (Object.keys(ids).length) return { ...ids };
  return {
    date: "date",
    time: "time",
    text: "text",
    bell_status: "bell_status",
    bell_countdown: "bell_countdown",
    schedule: "schedule",
    holidays: "holidays",
    announcements: "announcements",
    school_news: "school_news",
    rss_news: "rss_news",
    marquee: "marquee",
    emergency: "emergency",
    image: "image",
  };
}

export function isKnownWidgetType(typ) {
  return getWidgetTypeKeys().has(typ);
}

export function widgetManifest(typ) {
  const widgets = (_registry && _registry.widgets) || [];
  return widgets.find((w) => w.type === typ) || null;
}

/** JSON Schema для settings (из GET /api/widgets/registry). */
export function widgetSettingsSchema(typ) {
  const m = widgetManifest(typ);
  if (!m || !m.settings_schema || typeof m.settings_schema !== "object") return null;
  return m.settings_schema;
}

export function widgetStatusMessage(typ) {
  const m = widgetManifest(typ);
  if (!m) return "";
  return String(m.status_message || "");
}

export function widgetStatus(typ) {
  const m = widgetManifest(typ);
  return m ? String(m.status || "loaded") : "missing";
}

/**
 * Виджет можно добавить из палитры (loaded + capabilities из meta).
 * @param {string} typ
 * @param {Record<string, { status?: string }>} [capabilities]
 */
export function isWidgetAvailableInPalette(typ, capabilities) {
  const m = widgetManifest(typ);
  if (!m || m.status !== "loaded") return false;
  const reqs = m.requires_capabilities || [];
  if (!reqs.length || !capabilities) return true;
  return reqs.every((c) => capabilities[c] && capabilities[c].status === "available");
}
