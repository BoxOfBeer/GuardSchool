/**
 * Список виджетов, модалка редактора, поля настроек, карусель, изображения.
 */
import { state, elements, GRID } from "./state.js";
import { t, tf } from "./i18n-helpers.js";
import { api } from "./api-client.js";
import { escapeHtml, escapeHtmlAttr } from "./escape-html.js";

const WIDGET_TYPE_KEYS = new Set([
  "date",
  "time",
  "text",
  "bell_status",
  "bell_countdown",
  "schedule",
  "carousel",
  "holidays",
  "announcements",
  "marquee",
  "emergency",
  "image",
]);

let deps = {
  selectedScreen: () => null,
  render: () => {},
  renderPreview: () => {},
  createWidgetId: (/** @type {string} */ _p) => "",
  getCarouselAnimations: () => [],
  isWidgetTypeHiddenInAdminPalette: (/** @type {string} */ _w) => false,
  closeProgramSettingsModal: () => {},
};

export function setWidgetDeps(d) {
  deps = { ...deps, ...d };
}

function screen() {
  return deps.selectedScreen();
}

export function widgetDisplayTitle(widget) {
  if (!widget) return "";
  const typ = widget.type;
  if (typ === "carousel") {
    const raw = String(widget.title || "").trim();
    if (raw && !/^Карусель(\s|$)/.test(raw) && !/^Carousel(\s|$)/i.test(raw)) return raw;
    const m = raw.match(/^(?:Карусель|Carousel)\s*(\d+)\s*$/i);
    if (m) return tf("carousel.nameN", { n: Number(m[1]) });
    return t("widget.type.carousel");
  }
  if (typ && WIDGET_TYPE_KEYS.has(typ)) {
    const tr = t(`widget.type.${typ}`);
    if (tr !== `widget.type.${typ}`) return tr;
  }
  return String(widget.title || typ || "");
}

function widgetInput(label, value, onChange, type = "text", sizeClass = "standard-input") {
  const wide = sizeClass === "wide-input" ? " settings-label--wide" : "";
  return `<label class="settings-label${wide}">${label}<input class="${sizeClass}" data-key="${onChange}" type="${type}" value="${value ?? ""}"></label>`;
}

function widgetTextarea(label, value, onChange, sizeClass = "wide-input") {
  const wide = sizeClass === "wide-input" ? " settings-label--wide" : "";
  return `<label class="settings-label${wide}">${label}<textarea class="${sizeClass}" data-key="${onChange}" rows="4">${value ?? ""}</textarea></label>`;
}

function widgetToggle(label, checked, onChange) {
  return `<label class="toggle-label"><input data-key="${onChange}" type="checkbox" ${checked ? "checked" : ""}> ${label}</label>`;
}

function availableCarouselChildren(currentWidget) {
  const sc = screen();
  if (!sc) return [];
  const list = sc.widgets
    .filter(
      (widget) =>
        widget.id !== currentWidget.id &&
        widget.type !== "carousel" &&
        widget.type !== "emergency" &&
        widget.type !== "image"
    )
    .map((widget) => ({ id: widget.id, title: widget.title, type: widget.type }));
  list.push({ id: "__blank__", title: t("carousel.blankChild"), type: "blank" });
  return list;
}

function coerceWidgetImageSlots(widget) {
  if (!widget || widget.type !== "image") return;
  const s = widget.settings;
  if (!Array.isArray(s.images)) {
    const legacy = String(s.imageUrl || "").trim();
    s.images = legacy ? [{ name: t("w.imageLegacy"), url: legacy }] : [{ name: tf("w.imageDefaultName", { n: 1 }), url: "" }];
  }
  if (s.images.length === 0) s.images.push({ name: tf("w.imageDefaultName", { n: 1 }), url: "" });
  delete s.imageUrl;
}

function clampWidget(widget) {
  if (widget.type === "emergency") {
    widget.x = 0;
    widget.y = 0;
    widget.w = GRID.cols;
    widget.h = GRID.rows;
    return;
  }
  widget.w = Math.max(1, Math.min(Number(widget.w || 1), GRID.cols));
  widget.h = Math.max(1, Math.min(Number(widget.h || 1), GRID.rows));
  widget.x = Math.max(0, Math.min(Number(widget.x || 0), GRID.cols - widget.w));
  widget.y = Math.max(0, Math.min(Number(widget.y || 0), GRID.rows - widget.h));
}

function settingInputs(widget, index) {
  const parts = [];
  parts.push(widgetToggle(t("w.enabled"), widget.enabled, `widget:${index}:enabled`));
  parts.push(widgetToggle(t("w.backdrop"), widget.settings.backdrop !== false, `widget:${index}:settings.backdrop`));
  if (["date", "time", "text", "bell_status", "holidays", "announcements", "marquee", "emergency"].includes(widget.type)) {
    parts.push(widgetInput(t("w.fontSize"), widget.settings.fontSize, `widget:${index}:settings.fontSize`, "number", "standard-input"));
    parts.push(widgetInput(t("w.color"), widget.settings.color, `widget:${index}:settings.color`, "color", "standard-input"));
    parts.push(widgetToggle(t("w.bold"), widget.settings.bold, `widget:${index}:settings.bold`));
  }
  if (["text", "bell_status", "bell_countdown", "holidays", "announcements", "marquee", "emergency"].includes(widget.type)) {
    parts.push(widgetInput(t("w.blockBg"), widget.settings.background, `widget:${index}:settings.background`, "text", "wide-input"));
  }
  if (widget.type === "text") {
    parts.push(widgetInput(t("w.text"), widget.settings.text, `widget:${index}:settings.text`, "text", "wide-input"));
  }
  if (widget.type === "emergency") {
    parts.push(widgetTextarea(t("w.textLines"), widget.settings.text, `widget:${index}:settings.text`, "wide-input"));
    parts.push(widgetToggle(t("w.emergencySound"), widget.settings.soundEnabled === true, `widget:${index}:settings.soundEnabled`));
    const cur = escapeHtmlAttr(String(widget.settings.soundUrl || ""));
    parts.push(`<label>${t("w.emergencySoundFile")}<input class="wide-input" type="text" value="${cur}" readonly></label>`);
    parts.push(
      `<div class="compact-form-row">
        <label class="bell-file-upload">
          <span class="bell-file-upload-main">${t("w.browse")}</span>
          <span class="bell-file-upload-sub">${t("w.browseSub")}</span>
          <input type="file" accept="audio/*" data-emergency-sound-upload="${index}" hidden>
        </label>
      </div>`
    );
    parts.push(`<p class="hint">${t("w.emergencyHint")}</p>`);
    parts.push(`<p class="hint">${t("w.emergencySoundHint")}</p>`);
  }
  if (widget.type === "image") {
    coerceWidgetImageSlots(widget);
    const imgs = widget.settings.images;
    parts.push(widgetInput(t("w.opacity"), widget.settings.opacity, `widget:${index}:settings.opacity`, "number", "standard-input"));
    parts.push(
      widgetInput(
        t("w.imageRotate"),
        widget.settings.imagesRotateSec,
        `widget:${index}:settings.imagesRotateSec`,
        "number",
        "standard-input"
      )
    );
    const fit = widget.settings.objectFit === "cover" ? "cover" : "contain";
    parts.push(`<label>${t("w.imageFit")}<select class="standard-input" data-key="widget:${index}:settings.objectFit"><option value="contain" ${fit === "contain" ? "selected" : ""}>${t("w.contain")}</option><option value="cover" ${fit === "cover" ? "selected" : ""}>${t("w.cover")}</option></select></label>`);
    const slotRows = imgs
      .map((row, i) => {
        const nm = escapeHtmlAttr(String(row.name ?? ""));
        const ur = escapeHtmlAttr(String(row.url ?? ""));
        return `<div class="widget-image-slot" data-image-slot-row="${i}">
          <div class="widget-image-slot-head"><span class="widget-image-slot-label">${tf("w.imageSlot", { n: i + 1 })}</span>
            <button type="button" class="secondary-btn compact-btn" data-remove-image-slot="${index}:${i}" title="${escapeHtmlAttr(t("w.removeSlot"))}">${t("w.removeSlot")}</button>
          </div>
          <label>${t("w.imageName")}<input class="wide-input" data-key="widget:${index}:settings.images.${i}.name" type="text" value="${nm}"></label>
          <label>${t("w.url")}<input class="wide-input" data-key="widget:${index}:settings.images.${i}.url" type="text" value="${ur}" placeholder="/uploads/widget_images/…"></label>
          <div class="compact-form-row widget-image-upload-row">
            <label class="bell-file-upload"><span class="bell-file-upload-main">${t("w.browse")}</span><span class="bell-file-upload-sub">${t("w.browseSub")}</span>
              <input type="file" accept="image/*" data-widget-image-upload="${index}" data-widget-image-slot="${i}" hidden>
            </label>
          </div>
        </div>`;
      })
      .join("");
    parts.push(`<div class="widget-image-slots">${slotRows}</div>`);
    parts.push(`<button type="button" class="secondary-btn compact-btn" data-add-image-slot="${index}">${t("w.addImage")}</button>`);
    parts.push(`<p class="hint">${t("w.imageHint")}</p>`);
  }
  if (widget.type === "bell_status" || widget.type === "bell_countdown") {
    parts.push(widgetInput(t("w.titleFont"), widget.settings.titleFontSize, `widget:${index}:settings.titleFontSize`, "number", "standard-input"));
  }
  if (widget.type === "holidays" || widget.type === "announcements") {
    parts.push(widgetInput(t("w.titleFont"), widget.settings.titleFontSize, `widget:${index}:settings.titleFontSize`, "number", "standard-input"));
  }
  if (widget.type === "bell_countdown") {
    parts.push(widgetInput(t("w.bodyFont"), widget.settings.fontSize, `widget:${index}:settings.fontSize`, "number", "standard-input"));
    parts.push(widgetInput(t("w.color"), widget.settings.color, `widget:${index}:settings.color`, "color", "standard-input"));
  }
  if (widget.type === "schedule") {
    parts.push(widgetInput(t("w.tableFont"), widget.settings.fontSize, `widget:${index}:settings.fontSize`, "number", "standard-input"));
    parts.push(widgetInput(t("w.titleFont"), widget.settings.titleFontSize, `widget:${index}:settings.titleFontSize`, "number", "standard-input"));
    parts.push(widgetInput(t("w.highlight"), widget.settings.highlightColor, `widget:${index}:settings.highlightColor`, "color", "standard-input"));
    parts.push(widgetInput(t("w.sampleDiff"), widget.settings.sampleDiffColor, `widget:${index}:settings.sampleDiffColor`, "color", "standard-input"));
    parts.push(widgetInput(t("w.headerColor"), widget.settings.headerColor, `widget:${index}:settings.headerColor`, "color", "standard-input"));
    parts.push(widgetInput("Фон таблицы", widget.settings.tableBgColor, `widget:${index}:settings.tableBgColor`, "color", "standard-input"));
    parts.push(widgetInput("Текст таблицы", widget.settings.tableTextColor, `widget:${index}:settings.tableTextColor`, "color", "standard-input"));
    parts.push(widgetInput("Прошедшие (фон)", widget.settings.pastBgColor, `widget:${index}:settings.pastBgColor`, "color", "standard-input"));
    parts.push(widgetInput("Прошедшие (текст)", widget.settings.pastTextColor, `widget:${index}:settings.pastTextColor`, "color", "standard-input"));
    parts.push(widgetInput("Текущий (фон)", widget.settings.currentBgColor, `widget:${index}:settings.currentBgColor`, "color", "standard-input"));
    parts.push(widgetInput("Граница", widget.settings.borderColor, `widget:${index}:settings.borderColor`, "color", "standard-input"));
    parts.push(`<div class="hint">Палитра расписания: header=${escapeHtml(String(widget.settings.headerColor || ""))}, bg=${escapeHtml(String(widget.settings.tableBgColor || ""))}, text=${escapeHtml(String(widget.settings.tableTextColor || ""))}, past=${escapeHtml(String(widget.settings.pastBgColor || ""))}, current=${escapeHtml(String(widget.settings.currentBgColor || ""))}, override=${escapeHtml(String(widget.settings.highlightColor || ""))}</div>`);
    parts.push(widgetToggle("Dev-режим (лог на ТВ)", widget.settings.devMode, `widget:${index}:settings.devMode`));
    parts.push(widgetToggle(t("w.bold"), widget.settings.bold, `widget:${index}:settings.bold`));
  }
  if (widget.type === "carousel") {
    const selectedIds = new Set(widget.settings.childWidgetIds || []);
    const childOptions = availableCarouselChildren(widget)
      .map(
        (item) => `
      <label class="toggle-label carousel-child-option">
        <input data-key="widget:${index}:settings.childWidgetIds" data-value="${escapeHtmlAttr(String(item.id))}" type="checkbox" ${selectedIds.has(item.id) ? "checked" : ""}>
        ${escapeHtml(String(item.title ?? ""))}
      </label>
    `,
      )
      .join("");
    const animationOptions = deps
      .getCarouselAnimations()
      .map((item) => `<option value="${escapeHtmlAttr(String(item.id))}" ${widget.settings.animation === item.id ? "selected" : ""}>${escapeHtml(String(item.label ?? ""))}</option>`)
      .join("");
    const childMeta = Object.fromEntries(availableCarouselChildren(widget).map((item) => [item.id, item]));
    const slideDurRows = (widget.settings.childWidgetIds || [])
      .map((cid) => {
        const meta = childMeta[cid] || { title: cid };
        const val = (widget.settings.childSlideSec || {})[cid];
        const shown = val != null && val !== "" ? val : "";
        return widgetInput(tf("carousel.slideSec", { title: meta.title }), shown, `widget:${index}:settings.childSlideSec.${cid}`, "number", "standard-input");
      })
      .join("");
    parts.push(widgetInput(t("carousel.delay"), widget.settings.startDelaySec, `widget:${index}:settings.startDelaySec`, "number", "standard-input"));
    parts.push(`<div class="carousel-animation-row"><label>${t("carousel.animation")}<select class="standard-input" data-key="widget:${index}:settings.animation">${animationOptions}</select></label><button type="button" class="secondary-btn compact-btn" data-random-animation="${index}">${t("carousel.randomBtn")}</button></div>`);
    parts.push(`<div class="carousel-children-box">${childOptions || `<div class="hint">${t("carousel.noChildren")}</div>`}</div>`);
    if (slideDurRows) parts.push(`<div class="carousel-slide-durations hint">${t("carousel.slideDurHint")}</div>${slideDurRows}`);
  }
  if (widget.type === "holidays") {
    parts.push(widgetInput(t("w.count"), widget.settings.count, `widget:${index}:settings.count`, "number", "standard-input"));
  }
  if (widget.type === "announcements") {
    parts.push(widgetTextarea(t("w.linesManual"), widget.settings.items, `widget:${index}:settings.items`, "wide-input"));
    parts.push(widgetToggle(t("w.useManual"), widget.settings.useManual, `widget:${index}:settings.useManual`));
    parts.push(widgetInput(t("w.rotateExcel"), widget.settings.rotateSec, `widget:${index}:settings.rotateSec`, "number", "standard-input"));
    parts.push(widgetToggle(t("w.advanceCarousel"), widget.settings.advanceOnShow, `widget:${index}:settings.advanceOnShow`));
    parts.push(widgetToggle(t("w.randomOrder"), widget.settings.randomize !== false, `widget:${index}:settings.randomize`));
  }
  if (widget.type === "marquee") {
    parts.push(widgetTextarea(t("w.linesManual"), widget.settings.items, `widget:${index}:settings.items`, "wide-input"));
    parts.push(widgetToggle(t("w.useManual"), widget.settings.useManual, `widget:${index}:settings.useManual`));
    parts.push(
      widgetInput(
        t("w.charsPerMin"),
        widget.settings.charsPerMin != null && widget.settings.charsPerMin !== "" ? widget.settings.charsPerMin : "",
        `widget:${index}:settings.charsPerMin`,
        "number",
        "standard-input"
      )
    );
    parts.push(`<p class="hint">${t("w.charsPerMinHint")}</p>`);
    parts.push(
      widgetInput(
        t("w.speedSecLegacy"),
        widget.settings.speedSec,
        `widget:${index}:settings.speedSec`,
        "number",
        "standard-input"
      )
    );
    parts.push(`<p class="hint">${t("w.speedSecLegacyHint")}</p>`);
  }
  return parts.join("");
}

function widgetEditorInnerHtml(widget, index) {
  return `
      <div class="inline-grid">
        ${widgetInput("x", widget.x, `widget:${index}:x`, "number", "standard-input")}
        ${widgetInput("y", widget.y, `widget:${index}:y`, "number", "standard-input")}
        ${widgetInput("w", widget.w, `widget:${index}:w`, "number", "standard-input")}
        ${widgetInput("h", widget.h, `widget:${index}:h`, "number", "standard-input")}
      </div>
      <div class="settings-grid">${settingInputs(widget, index)}</div>
  `;
}

export function updateWidgetField(path, value) {
  const m = path.match(/^widget:(\d+):(.+)$/);
  if (!m) return;
  const [, indexRaw, fieldRaw] = m;
  const sc = screen();
  if (!sc) return;
  const widget = sc.widgets[Number(indexRaw)];
  if (!widget) return;
  if (fieldRaw.startsWith("settings.")) {
    const key = fieldRaw.replace("settings.", "");
    if (key === "childWidgetIds") {
      const current = new Set(widget.settings.childWidgetIds || []);
      if (value.checked) current.add(value.value);
      else current.delete(value.value);
      widget.settings.childWidgetIds = [...current];
      const map = { ...(widget.settings.childSlideSec || {}) };
      for (const id of Object.keys(map)) {
        if (!current.has(id)) delete map[id];
      }
      widget.settings.childSlideSec = map;
    } else if (key.startsWith("childSlideSec.")) {
      const childId = key.slice("childSlideSec.".length);
      if (!widget.settings.childSlideSec) widget.settings.childSlideSec = {};
      const num = Number(value);
      if (value === "" || value == null || !Number.isFinite(num)) {
        delete widget.settings.childSlideSec[childId];
      } else {
        widget.settings.childSlideSec[childId] = num;
      }
    } else if (/^images\.\d+\.(name|url)$/.test(key)) {
      const im = key.match(/^images\.(\d+)\.(name|url)$/);
      if (!im) return;
      const idx = Number(im[1]);
      const sub = im[2];
      if (!Array.isArray(widget.settings.images)) widget.settings.images = [];
      while (widget.settings.images.length <= idx) {
        widget.settings.images.push({ name: "", url: "" });
      }
      if (!widget.settings.images[idx] || typeof widget.settings.images[idx] !== "object") {
        widget.settings.images[idx] = { name: "", url: "" };
      }
      widget.settings.images[idx][sub] = value;
    } else if (key === "charsPerMin") {
      const num = Number(value);
      if (value === "" || value == null || !Number.isFinite(num)) {
        delete widget.settings.charsPerMin;
      } else {
        widget.settings.charsPerMin = Math.max(20, Math.min(900, Math.round(num)));
      }
    } else if (["fontSize", "titleFontSize", "startDelaySec", "count", "speedSec", "rotateSec", "opacity", "imagesRotateSec"].includes(key)) {
      const num = Number(value);
      if (key === "opacity") {
        widget.settings[key] = value === "" || !Number.isFinite(num) ? 85 : Math.max(0, Math.min(100, num));
      } else if (key === "imagesRotateSec") {
        widget.settings[key] = value === "" || !Number.isFinite(num) ? 0 : Math.max(0, Math.min(600, Math.round(num)));
      } else {
        widget.settings[key] = num;
      }
    } else if (key === "backdrop" || key === "useManual" || key === "advanceOnShow" || key === "randomize") widget.settings[key] = Boolean(value);
    else widget.settings[key] = value;
  } else {
    widget[fieldRaw] = fieldRaw === "enabled" ? Boolean(value) : Number(value);
  }
  clampWidget(widget);
  deps.render();
}

export async function uploadWidgetImage(file, widgetIndex, slotIndex) {
  const formData = new FormData();
  formData.append("file", file);
  const payload = await api("/api/admin/upload-widget-image", { method: "POST", body: formData });
  const sc = screen();
  if (!sc) return;
  const w = sc.widgets[widgetIndex];
  if (!w || w.type !== "image") return;
  coerceWidgetImageSlots(w);
  const slot = Number(slotIndex);
  const i = Number.isFinite(slot) && slot >= 0 ? slot : 0;
  while (w.settings.images.length <= i) {
    w.settings.images.push({ name: tf("w.imageDefaultName", { n: w.settings.images.length + 1 }), url: "" });
  }
  w.settings.images[i].url = payload.path;
  deps.render();
  if (state.widgetModalWidgetId === w.id) syncWidgetModal();
  deps.renderPreview();
}

export async function uploadEmergencySound(file, widgetIndex) {
  const formData = new FormData();
  formData.append("file", file);
  const payload = await api("/api/admin/upload-emergency-sound", { method: "POST", body: formData });
  const sc = screen();
  if (!sc) return;
  const w = sc.widgets[widgetIndex];
  if (!w || w.type !== "emergency") return;
  if (!w.settings) w.settings = {};
  w.settings.soundUrl = payload.url;
  w.settings.soundFilename = payload.filename;
  deps.render();
  if (state.widgetModalWidgetId === w.id) syncWidgetModal();
  deps.renderPreview();
}

export function addWidgetImageSlot(widgetIndex) {
  const sc = screen();
  if (!sc) return;
  const w = sc.widgets[widgetIndex];
  if (!w || w.type !== "image") return;
  coerceWidgetImageSlots(w);
  const n = w.settings.images.length + 1;
  w.settings.images.push({ name: tf("w.imageDefaultName", { n }), url: "" });
  deps.render();
  if (state.widgetModalWidgetId === w.id) syncWidgetModal();
  deps.renderPreview();
}

export function removeWidgetImageSlot(widgetIndex, slotIndex) {
  const sc = screen();
  if (!sc) return;
  const w = sc.widgets[widgetIndex];
  if (!w || w.type !== "image") return;
  coerceWidgetImageSlots(w);
  const i = Number(slotIndex);
  if (!Number.isFinite(i) || i < 0 || i >= w.settings.images.length) return;
  if (w.settings.images.length <= 1) {
    w.settings.images[0] = { name: w.settings.images[0].name || tf("w.imageDefaultName", { n: 1 }), url: "" };
  } else {
    w.settings.images.splice(i, 1);
  }
  deps.render();
  if (state.widgetModalWidgetId === w.id) syncWidgetModal();
  deps.renderPreview();
}

function bindWidgetEditorEvents(root, index) {
  const sc = screen();
  if (!sc) return;
  const widget = sc.widgets[index];
  if (!widget || !root) return;
  root.querySelectorAll("input").forEach((input) => {
    input.addEventListener("change", (event) => {
      if (event.target.dataset.widgetImageUpload != null) {
        const f = event.target.files && event.target.files[0];
        if (f) {
          uploadWidgetImage(
            f,
            Number(event.target.dataset.widgetImageUpload),
            Number(event.target.dataset.widgetImageSlot || 0)
          );
          event.target.value = "";
        }
        return;
      }
      if (event.target.dataset.emergencySoundUpload != null) {
        const f = event.target.files && event.target.files[0];
        if (f) {
          uploadEmergencySound(f, Number(event.target.dataset.emergencySoundUpload));
          event.target.value = "";
        }
        return;
      }
      let value = event.target.type === "checkbox" ? event.target.checked : event.target.value;
      if (event.target.dataset.value) value = { checked: event.target.checked, value: event.target.dataset.value };
      updateWidgetField(event.target.dataset.key, value);
    });
  });
  root.querySelectorAll("select").forEach((select) => {
    select.addEventListener("change", (event) => updateWidgetField(event.target.dataset.key, event.target.value));
  });
  root.querySelectorAll("textarea").forEach((textarea) => {
    textarea.addEventListener("change", (event) => updateWidgetField(event.target.dataset.key, event.target.value));
  });
  root.querySelectorAll("[data-add-carousel]").forEach((button) => {
    button.onclick = () => addCarousel(Number(button.dataset.addCarousel));
  });
  root.querySelectorAll("[data-remove-carousel]").forEach((button) => {
    button.onclick = () => removeCarousel(Number(button.dataset.removeCarousel));
  });
  root.querySelectorAll("[data-random-animation]").forEach((button) => {
    button.onclick = () => {
      const s = screen();
      const w = s && s.widgets[index];
      if (w) w.settings.animation = "random";
      deps.render();
      deps.renderPreview();
    };
  });
  root.querySelectorAll("[data-add-image-slot]").forEach((button) => {
    button.onclick = () => addWidgetImageSlot(Number(button.dataset.addImageSlot));
  });
  root.querySelectorAll("[data-remove-image-slot]").forEach((button) => {
    button.onclick = () => {
      const raw = String(button.dataset.removeImageSlot || "");
      const [wi, si] = raw.split(":");
      removeWidgetImageSlot(Number(wi), Number(si));
    };
  });
}

function releaseFocusFromModal(modal) {
  if (!modal) return;
  const ae = document.activeElement;
  if (ae && modal.contains(ae)) ae.blur();
}

export function closeWidgetModal() {
  state.widgetModalWidgetId = null;
  const modal = elements.widgetEditorModal;
  if (modal) {
    releaseFocusFromModal(modal);
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
  }
}

export function syncWidgetModal() {
  const id = state.widgetModalWidgetId;
  const modal = elements.widgetEditorModal;
  const body = elements.widgetEditorModalBody;
  const titleEl = elements.widgetEditorModalTitle;
  if (!modal || !body || !titleEl) return;
  if (!id) {
    releaseFocusFromModal(modal);
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
    return;
  }
  const sc = screen();
  if (!sc) {
    closeWidgetModal();
    return;
  }
  const index = sc.widgets.findIndex((w) => w.id === id);
  if (index < 0) {
    closeWidgetModal();
    return;
  }
  const widget = sc.widgets[index];
  titleEl.textContent = `${widgetDisplayTitle(widget)} · ${widget.type}`;
  body.innerHTML = widgetEditorInnerHtml(widget, index);
  bindWidgetEditorEvents(body, index);
  modal.hidden = false;
  modal.setAttribute("aria-hidden", "false");
}

export function openWidgetModal(widgetId) {
  state.widgetModalWidgetId = widgetId;
  syncWidgetModal();
}

export function bindWidgetModalOnce() {
  if (bindWidgetModalOnce._done) return;
  bindWidgetModalOnce._done = true;
  document.addEventListener("click", (e) => {
    const openEl = e.target.closest("[data-open-widget-editor]");
    if (openEl) {
      e.preventDefault();
      const id = openEl.getAttribute("data-open-widget-editor");
      if (id) openWidgetModal(id);
    }
    if (e.target.closest("[data-close-widget-modal]")) {
      e.preventDefault();
      closeWidgetModal();
    }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (state.widgetModalWidgetId) closeWidgetModal();
    else if (elements.programSettingsModal && !elements.programSettingsModal.hidden) deps.closeProgramSettingsModal();
  });
}

export function renderWidgets() {
  const sc = screen();
  if (!sc) return;
  elements.widgetList.innerHTML = "";
  sc.widgets
    .filter((widget) => !deps.isWidgetTypeHiddenInAdminPalette(widget.type))
    .forEach((widget) => {
      const div = document.createElement("div");
      div.className = "widget-item widget-item-compact";
      const wid = escapeHtmlAttr(String(widget.id));
      const w = Number(widget.w);
      const h = Number(widget.h);
      const wh = `${Number.isFinite(w) ? w : "?"}×${Number.isFinite(h) ? h : "?"}`;
      div.innerHTML = `
      <div class="widget-title-row">
        <h3>${escapeHtmlAttr(widgetDisplayTitle(widget))}</h3>
        <div class="widget-actions">
          <button type="button" class="primary-btn compact-btn" data-open-widget-editor="${wid}">${t("widget.configure")}</button>
        </div>
      </div>
      <div class="widget-item-meta"><span class="widget-item-type">${escapeHtmlAttr(String(widget.type))}</span> · ${tf("widget.gridMeta", { wh: escapeHtmlAttr(wh) })}</div>
    `;
      elements.widgetList.appendChild(div);
    });
}

export function addCarousel(sourceIndex) {
  const sc = screen();
  if (!sc) return;
  const source = sc.widgets[sourceIndex];
  const copy = JSON.parse(JSON.stringify(source));
  copy.id = deps.createWidgetId("carousel");
  copy.title = tf("carousel.nameN", { n: sc.widgets.filter((item) => item.type === "carousel").length + 1 });
  copy.x = Math.min(copy.x + 1, GRID.cols - copy.w);
  copy.y = Math.min(copy.y + 1, GRID.rows - copy.h);
  copy.settings.startDelaySec = Number(copy.settings.startDelaySec || 0) + 15;
  sc.widgets.splice(sourceIndex + 1, 0, copy);
  deps.render();
}

export function removeCarousel(sourceIndex) {
  const sc = screen();
  if (!sc) return;
  const carouselCount = sc.widgets.filter((item) => item.type === "carousel").length;
  if (carouselCount <= 1) {
    alert(t("alert.oneCarousel"));
    return;
  }
  sc.widgets.splice(sourceIndex, 1);
  deps.render();
}
