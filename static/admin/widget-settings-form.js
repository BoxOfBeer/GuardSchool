/**
 * Генерация полей settings из JSON Schema (registry) + дополнение ручных блоков в widgets.js.
 */
import { widgetSettingsSchema } from "./widget-registry.js";
import { t, tf } from "./i18n-helpers.js";
import { escapeHtml, escapeHtmlAttr } from "./escape-html.js";

/** Только schema + общие переключатели (enabled, backdrop, menu_only). */
export const SCHEMA_SIMPLE_WIDGET_TYPES = new Set(["blank", "date", "time"]);

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
  imagesRotateSec: "w.schemaProp.imagesRotateSec",
  useManual: "w.schemaProp.useManual",
  items: "w.schemaProp.items",
  randomize: "w.schemaProp.randomize",
  advanceOnShow: "w.schemaProp.advanceOnShow",
  startDelaySec: "w.schemaProp.startDelaySec",
  slideDurationSec: "w.schemaProp.slideDurationSec",
  animation: "w.schemaProp.animation",
  randomAnimation: "w.schemaProp.randomAnimation",
  panel_title: "w.schemaProp.panelTitle",
  imageUrl: "w.schemaProp.imageUrl",
  imageCaption: "w.schemaProp.imageCaption",
  timerRemainingSec: "w.schemaProp.timerRemainingSec",
  timerShowZero: "w.schemaProp.timerShowZero",
};

/** Ключи settings, которые рисуются вручную в widgets.js (не дублировать). */
const EXCLUDE_BY_TYPE = {
  text: ["text", "fontSize", "color", "bold", "background"],
  bell_status: ["fontSize", "color", "bold", "background", "titleFontSize"],
  bell_countdown: ["fontSize", "color", "bold", "background", "titleFontSize"],
  schedule: [
    "fontSize",
    "titleFontSize",
    "bold",
    "highlightColor",
    "sampleDiffColor",
    "headerColor",
    "tableBgColor",
    "tableTextColor",
    "pastBgColor",
    "pastTextColor",
    "currentBgColor",
    "borderColor",
    "devMode",
  ],
  holidays: ["count", "titleFontSize", "fontSize", "color", "bold", "background"],
  announcements: ["items", "useManual", "rotateSec", "advanceOnShow", "randomize", "titleFontSize", "fontSize", "color", "bold", "background"],
  school_news: ["rotateSec", "titleFontSize", "bodyFontSize", "fontSize", "color", "bold", "background"],
  rss_news: ["rotateSec", "titleFontSize", "bodyFontSize", "fontSize", "color", "bold", "background", "feedUrl", "maxItems"],
  marquee: ["items", "useManual", "charsPerMin", "speedSec", "fontSize", "color", "bold", "background"],
  emergency: ["text", "soundEnabled", "soundUrl", "imageUrl", "imageCaption", "fontSize", "color", "bold", "background"],
  image: ["opacity", "imagesRotateSec", "objectFit", "images", "imageUrl"],
  carousel: ["startDelaySec", "animation", "childWidgetIds", "childSlideSec", "randomAnimation"],
  checkin_submit: ["fontSize", "bold", "labels", "monitor_widget_id", "pwa_title", "pwa_icon_url"],
  checkin_monitor: [
    "fontSize",
    "bold",
    "panel_title",
    "events_screen_slug",
    "places",
    "pwa_title",
    "pwa_icon_url",
  ],
};

export function schemaExcludeKeysForType(widgetType) {
  return new Set(EXCLUDE_BY_TYPE[widgetType] || []);
}

export function propLabel(path, prop) {
  const key = SCHEMA_PROP_I18N[path];
  if (key) {
    const tr = t(key);
    if (tr !== key) return tr;
  }
  const title = prop && prop.title ? String(prop.title) : "";
  return title || path;
}

function isColorField(path) {
  return /color$/i.test(path) || path === "background";
}

function isLongTextField(path, prop) {
  if (path === "text" || path === "items" || path === "feedUrl") return true;
  const maxLen = prop && prop.maxLength;
  return typeof maxLen === "number" && maxLen > 120;
}

/**
 * @param {string} label
 * @param {unknown} value
 * @param {string} dataKey
 * @param {string} type
 * @param {string} sizeClass
 */
function fieldInput(label, value, dataKey, type, sizeClass) {
  const wide = sizeClass === "wide-input" ? " settings-label--wide" : "";
  const val = escapeHtmlAttr(value == null ? "" : String(value));
  return `<label class="settings-label${wide}">${label}<input class="${sizeClass}" data-key="${dataKey}" type="${type}" value="${val}"></label>`;
}

function fieldTextarea(label, value, dataKey, sizeClass) {
  const wide = sizeClass === "wide-input" ? " settings-label--wide" : "";
  return `<label class="settings-label${wide}">${label}<textarea class="${sizeClass}" data-key="${dataKey}" rows="4">${escapeHtml(String(value ?? ""))}</textarea></label>`;
}

function fieldToggle(label, checked, dataKey) {
  return `<label class="toggle-label"><input data-key="${dataKey}" type="checkbox" ${checked ? "checked" : ""}> ${label}</label>`;
}

function fieldSelect(label, value, dataKey, enumValues) {
  const opts = enumValues
    .map((v) => {
      const sv = String(v);
      return `<option value="${escapeHtmlAttr(sv)}" ${String(value) === sv ? "selected" : ""}>${escapeHtml(sv)}</option>`;
    })
    .join("");
  return `<label class="settings-label">${label}<select class="standard-input" data-key="${dataKey}">${opts}</select></label>`;
}

/**
 * @param {object} widget
 * @param {number} index
 * @param {{ exclude?: Set<string> }} [opts]
 * @returns {string}
 */
export function renderSchemaSettingsFields(widget, index, opts = {}) {
  const schema = widgetSettingsSchema(widget.type);
  if (!schema || !schema.properties || typeof schema.properties !== "object") {
    return "";
  }
  const exclude = opts.exclude || new Set();
  const settings = widget.settings || {};
  const parts = [];
  const keys = Object.keys(schema.properties)
    .filter((k) => !exclude.has(k))
    .sort((a, b) => propLabel(a, schema.properties[a]).localeCompare(propLabel(b, schema.properties[b]), "ru"));

  if (!keys.length) return "";

  parts.push(`<div class="widget-schema-fields" data-schema-widget-type="${escapeHtmlAttr(widget.type)}">`);
  parts.push(`<p class="hint widget-schema-fields-title">${escapeHtml(t("w.schemaSection"))}</p>`);

  for (const path of keys) {
    const prop = schema.properties[path];
    if (!prop || typeof prop !== "object") continue;
    const typ = String(prop.type || "");
    const dataKey = `widget:${index}:settings.${path}`;
    const val = settings[path];
    const label = propLabel(path, prop);

    if (typ === "boolean") {
      parts.push(fieldToggle(label, Boolean(val), dataKey));
      continue;
    }
    if (typ === "integer" || typ === "number") {
      parts.push(fieldInput(label, val ?? "", dataKey, "number", "standard-input"));
      continue;
    }
    if (typ === "string" && Array.isArray(prop.enum) && prop.enum.length) {
      parts.push(fieldSelect(label, val ?? prop.enum[0], dataKey, prop.enum));
      continue;
    }
    if (typ === "string") {
      if (isLongTextField(path, prop)) {
        parts.push(fieldTextarea(label, val, dataKey, "wide-input"));
      } else {
        const inputType = isColorField(path) ? "color" : "text";
        const size = path === "background" || path === "feedUrl" ? "wide-input" : "standard-input";
        parts.push(fieldInput(label, val, dataKey, inputType, size));
      }
      continue;
    }
    // object / array — только ручные редакторы в widgets.js
  }

  parts.push("</div>");
  return parts.join("");
}

/**
 * @param {string} dataKey
 * @param {unknown} value
 * @param {object | null} schema
 * @returns {string | null} сообщение об ошибке или null
 */
export function validateSettingValue(dataKey, value, schema) {
  if (!schema || !schema.properties) return null;
  const m = String(dataKey || "").match(/:settings\.(.+)$/);
  if (!m) return null;
  const path = m[1];
  const prop = schema.properties[path];
  if (!prop || typeof prop !== "object") return null;
  const typ = String(prop.type || "");
  if (typ === "integer" || typ === "number") {
    if (value === "" || value == null) return null;
    const n = Number(value);
    if (!Number.isFinite(n)) return t("w.schemaInvalidNumber");
    if (prop.minimum != null && n < prop.minimum) {
      return tf("w.schemaMin", { min: prop.minimum });
    }
    if (prop.maximum != null && n > prop.maximum) {
      return tf("w.schemaMax", { max: prop.maximum });
    }
  }
  if (typ === "string" && Array.isArray(prop.enum) && prop.enum.length) {
    const s = String(value);
    if (!prop.enum.map(String).includes(s)) return t("w.schemaInvalidEnum");
  }
  return null;
}

/**
 * @param {HTMLElement} root
 * @param {string} widgetType
 */
export function bindSchemaValidation(root, widgetType) {
  const schema = widgetSettingsSchema(widgetType);
  if (!schema || !root) return;
  const showErr = (el, msg) => {
    let box = el.closest("label")?.querySelector(".widget-schema-error");
    if (!msg) {
      box?.remove();
      el.classList.remove("widget-schema-invalid");
      return;
    }
    el.classList.add("widget-schema-invalid");
    if (!box) {
      box = document.createElement("span");
      box.className = "hint widget-schema-error";
      el.closest("label")?.appendChild(box);
    }
    if (box) box.textContent = msg;
  };
  root.querySelectorAll("[data-key]").forEach((el) => {
    const validate = () => {
      const raw = el.type === "checkbox" ? el.checked : el.value;
      showErr(el, validateSettingValue(el.getAttribute("data-key") || "", raw, schema));
    };
    el.addEventListener("change", validate);
    if (el instanceof HTMLInputElement && el.type === "number") {
      el.addEventListener("blur", validate);
    }
  });
}
