/**
 * Подсказки и ограничения полей настроек виджета по JSON Schema из /api/widgets/registry.
 */
import { widgetSettingsSchema } from "./widget-registry.js";
import { t, tf } from "./i18n-helpers.js";

/** Поля settings → ключи i18n (w.schemaProp.*). */
const SCHEMA_PROP_I18N = {
  fontSize: "w.schemaProp.fontSize",
  titleFontSize: "w.schemaProp.titleFontSize",
  bodyFontSize: "w.schemaProp.bodyFontSize",
  color: "w.schemaProp.color",
  background: "w.schemaProp.background",
  bold: "w.schemaProp.bold",
  text: "w.schemaProp.text",
  showTomorrow: "w.schemaProp.showTomorrow",
  compact: "w.schemaProp.compact",
  count: "w.schemaProp.count",
  rotateSec: "w.schemaProp.rotateSec",
  speed: "w.schemaProp.speed",
  direction: "w.schemaProp.direction",
  feedUrl: "w.schemaProp.feedUrl",
  maxItems: "w.schemaProp.maxItems",
  showQr: "w.schemaProp.showQr",
  opacity: "w.schemaProp.opacity",
  objectFit: "w.schemaProp.objectFit",
};

function propLabel(path, prop) {
  const key = SCHEMA_PROP_I18N[path];
  if (key) {
    const tr = t(key);
    if (tr !== key) return tr;
  }
  const title = prop && prop.title ? String(prop.title) : "";
  return title || path;
}

/**
 * @param {Record<string, unknown>} prop
 * @returns {string}
 */
function propHintText(prop) {
  if (!prop || typeof prop !== "object") return "";
  const parts = [];
  const typ = String(prop.type || "");
  if (typ === "integer" || typ === "number") {
    const min = prop.minimum;
    const max = prop.maximum;
    if (min != null || max != null) {
      parts.push(tf("w.schemaRange", { min: min ?? "…", max: max ?? "…" }));
    }
  }
  if (Array.isArray(prop.enum) && prop.enum.length) {
    parts.push(tf("w.schemaEnum", { values: prop.enum.join(", ") }));
  }
  return parts.join(" · ");
}

/**
 * @param {HTMLElement} root
 * @param {string} widgetType
 */
export function applyWidgetSettingsSchemaHints(root, widgetType) {
  const schema = widgetSettingsSchema(widgetType);
  if (!schema || !root) return;
  const props = schema.properties;
  if (!props || typeof props !== "object") return;

  root.querySelectorAll("[data-key]").forEach((el) => {
    const raw = el.getAttribute("data-key") || "";
    const m = raw.match(/:settings\.(.+)$/);
    if (!m) return;
    const path = m[1];
    const prop = props[path];
    if (!prop || typeof prop !== "object") return;

    const typ = String(prop.type || "");
    if ((typ === "integer" || typ === "number") && el instanceof HTMLInputElement && el.type === "number") {
      if (prop.minimum != null) el.min = String(prop.minimum);
      if (prop.maximum != null) el.max = String(prop.maximum);
    }

    const labelText = propLabel(path, prop);
    const hint = propHintText(prop);
    const fullTip = hint ? `${labelText}: ${hint}` : labelText;
    el.setAttribute("aria-label", labelText);
    const label = el.closest("label.settings-label, label.toggle-label, label.compact-field");
    if (!label) {
      if (hint) el.title = fullTip;
      return;
    }
    if (hint) {
      let hintEl = label.querySelector(".widget-schema-hint");
      if (!hintEl) {
        hintEl = document.createElement("span");
        hintEl.className = "hint widget-schema-hint";
        label.appendChild(hintEl);
      }
      hintEl.textContent = hint;
    }
  });
}
