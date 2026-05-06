/**
 * Список виджетов, модалка редактора, поля настроек, карусель, изображения.
 */
import { state, elements, GRID } from "./state.js";
import { t, tf } from "./i18n-helpers.js";
import { api } from "./api-client.js";
import { escapeHtml, escapeHtmlAttr } from "./escape-html.js";
import { MAX_WIDGET_IMAGE_UPLOAD_BYTES } from "./upload-limits.js";

/** Как на сервере gs_checkin._PLACE_ID_RE — только допустимые id мест. */
const CHECKIN_PLACE_ID_RE = /^[a-zA-Z0-9_-]{1,64}$/;

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
  "school_news",
  "rss_news",
  "marquee",
  "emergency",
  "image",
  "checkin_submit",
  "checkin_monitor",
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
  parts.push(widgetToggle("Только в меню", widget.menu_only === true, `widget:${index}:menu_only`));
  if (["date", "time", "text", "bell_status", "holidays", "announcements", "school_news", "rss_news", "marquee", "emergency"].includes(widget.type)) {
    parts.push(widgetInput(t("w.fontSize"), widget.settings.fontSize, `widget:${index}:settings.fontSize`, "number", "standard-input"));
    parts.push(widgetInput(t("w.color"), widget.settings.color, `widget:${index}:settings.color`, "color", "standard-input"));
    parts.push(widgetToggle(t("w.bold"), widget.settings.bold, `widget:${index}:settings.bold`));
  }
  if (["text", "bell_status", "bell_countdown", "holidays", "announcements", "school_news", "rss_news", "marquee", "emergency"].includes(widget.type)) {
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
    const eiu = escapeHtmlAttr(String(widget.settings.imageUrl || ""));
    const eic = escapeHtmlAttr(String(widget.settings.imageCaption || ""));
    parts.push(
      `<label>${t("w.emergencyImageUrl")}<input class="wide-input" type="text" data-key="widget:${index}:settings.imageUrl" value="${eiu}" placeholder="/uploads/…"></label>`
    );
    parts.push(
      `<label>${t("w.emergencyImageCaption")}<input class="wide-input" type="text" data-key="widget:${index}:settings.imageCaption" value="${eic}"></label>`
    );
    parts.push(
      `<div class="compact-form-row">
        <label class="bell-file-upload">
          <span class="bell-file-upload-main">${t("w.emergencyImageBrowse")}</span>
          <span class="bell-file-upload-sub">${t("w.browseSub")}</span>
          <input type="file" accept="image/*" data-emergency-image-upload="${index}" hidden>
        </label>
      </div>`
    );
    parts.push(`<p class="hint">${t("w.emergencyHint")}</p>`);
    parts.push(`<p class="hint">${t("w.emergencySoundHint")}</p>`);
    parts.push(`<p class="hint">${t("w.emergencyLocalImageHint")}</p>`);
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
  if (widget.type === "holidays" || widget.type === "announcements" || widget.type === "school_news" || widget.type === "rss_news") {
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
  if (widget.type === "school_news" || widget.type === "rss_news") {
    parts.push(widgetInput("Интервал автопереключения, сек", widget.settings.rotateSec, `widget:${index}:settings.rotateSec`, "number", "standard-input"));
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
  if (widget.type === "checkin_monitor") {
    parts.push(widgetInput(t("w.checkinPanelTitle"), widget.settings.panel_title || "", `widget:${index}:settings.panel_title`, "text", "standard-input"));
    parts.push(widgetInput(t("w.checkinEventsScreenSlug"), widget.settings.events_screen_slug || "", `widget:${index}:settings.events_screen_slug`, "text", "standard-input"));
    parts.push(`<p class="hint">${t("w.checkinEventsScreenSlugHint")}</p>`);
    parts.push(`<p class="hint">${t("w.checkinPlacesHintMonitor")}</p>`);
  }
  if (widget.type === "checkin_submit") {
    parts.push(widgetInput(t("w.checkinMonitorWidgetId"), widget.settings.monitor_widget_id || "", `widget:${index}:settings.monitor_widget_id`, "text", "standard-input"));
    parts.push(`<p class="hint">${t("w.checkinSubmitLinkHint")}</p>`);
    parts.push(`<p class="hint">${t("w.checkinSubmitPlacesFromMonitorOnly")}</p>`);
    parts.push(widgetInput(t("w.checkinLabelModuleTitle"), (widget.settings.labels || {}).module_title || "", `widget:${index}:settings.labels.module_title`, "text", "wide-input"));
    parts.push(widgetInput(t("w.checkinLabelPlace"), (widget.settings.labels || {}).place || "", `widget:${index}:settings.labels.place`, "text", "standard-input"));
    parts.push(widgetInput(t("w.checkinLabelDevice"), (widget.settings.labels || {}).device_name || "", `widget:${index}:settings.labels.device_name`, "text", "standard-input"));
    parts.push(widgetInput(t("w.checkinLabelSave"), (widget.settings.labels || {}).save || "", `widget:${index}:settings.labels.save`, "text", "standard-input"));
  }
  if (widget.type === "checkin_monitor") {
    const places = Array.isArray(widget.settings.places) ? widget.settings.places : [];
    const syncSlug = String(widget.settings.events_screen_slug || "").trim();
    const placesLocked = Boolean(syncSlug);
    const syncMsg = placesLocked
      ? t("w.checkinPlacesSyncLocked").replace(/\{\{slug\}\}/g, escapeHtml(syncSlug))
      : "";
    const dis = placesLocked ? " disabled" : "";
    const bodyRows = places.length
      ? places
          .map((p, i) => {
            const idAttr = escapeHtmlAttr(String(p?.id ?? ""));
            const titleAttr = escapeHtmlAttr(String(p?.title ?? ""));
            const del = placesLocked
              ? ""
              : `<td class="checkin-places-actions-col"><button type="button" class="secondary-btn compact-btn" data-remove-checkin-place="${index}:${i}">${t(
                  "w.checkinPlaceRemove",
                )}</button></td>`;
            return `<tr>
            <td class="checkin-places-code-col"><input class="standard-input" data-key="widget:${index}:settings.places.${i}.id" type="text" value="${idAttr}" placeholder="gate_a" maxlength="64"${dis} aria-label="${escapeHtmlAttr(t("w.checkinPlacesTableCode"))}"></td>
            <td class="checkin-places-title-col"><input class="standard-input" data-key="widget:${index}:settings.places.${i}.title" type="text" value="${titleAttr}" maxlength="200"${dis} aria-label="${escapeHtmlAttr(t("w.checkinPlacesTableTitle"))}"></td>
            ${del}
          </tr>`;
          })
          .join("")
      : `<tr><td colspan="${placesLocked ? 2 : 3}" class="checkin-places-empty"><span class="hint">${escapeHtml(t("w.checkinNoPlaces"))}</span></td></tr>`;
    const headDel = placesLocked ? "" : `<th class="checkin-places-actions-col" scope="col"></th>`;
    parts.push(`<div class="checkin-places-editor">
      ${
        placesLocked
          ? `<div class="checkin-places-sync-notice" role="status">${syncMsg}</div>
      <div class="checkin-places-sync-toolbar">
        <button type="button" class="secondary-btn compact-btn" data-sync-checkin-places="${index}">${escapeHtml(t("w.checkinPlacesSyncButton"))}</button>
        <span class="hint checkin-places-sync-hint">${escapeHtml(t("w.checkinPlacesSyncButtonHint"))}</span>
      </div>`
          : ""
      }
      <table class="checkin-places-table">
        <thead><tr>
          <th scope="col" class="checkin-places-code-col">${escapeHtml(t("w.checkinPlacesTableCode"))}</th>
          <th scope="col" class="checkin-places-title-col">${escapeHtml(t("w.checkinPlacesTableTitle"))}</th>
          ${headDel}
        </tr></thead>
        <tbody>${bodyRows}</tbody>
      </table>
      ${
        placesLocked
          ? ""
          : `<div class="checkin-places-toolbar"><button type="button" class="secondary-btn compact-btn" data-add-checkin-place="${index}">${t("w.checkinPlaceAdd")}</button></div>`
      }
    </div>`);
  }
  if (widget.type === "checkin_submit" || widget.type === "checkin_monitor") {
    parts.push(
      widgetInput(
        t("w.checkinFontSize"),
        widget.settings.fontSize ?? 0,
        `widget:${index}:settings.fontSize`,
        "number",
        "standard-input",
      ),
    );
    parts.push(`<p class="hint">${t("w.checkinFontSizeHint")}</p>`);
    parts.push(widgetToggle(t("w.bold"), widget.settings.bold === true, `widget:${index}:settings.bold`));
    const pwaTitle = escapeHtmlAttr(String(widget.settings?.pwa_title || ""));
    parts.push(`<div class="settings-row">
      <label class="compact-field">
        <span>${escapeHtml(t("w.pwaTitle"))}</span>
        <input type="text" class="standard-input wide-input" data-key="widget:${index}:settings.pwa_title" value="${pwaTitle}" placeholder="Например: Школа, Личка…" maxlength="64">
      </label>
      <div class="hint">${escapeHtml(t("w.pwaTitleHint"))}</div>
    </div>`);
    const iconUrl = escapeHtmlAttr(String(widget.settings?.pwa_icon_url || ""));
    parts.push(`<div class="settings-row">
      <label class="compact-field">
        <span>${escapeHtml(t("w.pwaIconUrl"))}</span>
        <input type="text" class="standard-input wide-input" data-key="widget:${index}:settings.pwa_icon_url" value="${iconUrl}" placeholder="/uploads/widget_images/...">
      </label>
      <div class="settings-row-actions">
        <button type="button" class="secondary-btn compact-btn" data-checkin-pwa-icon-browse="${index}">${escapeHtml(t("w.pwaIconBrowse"))}</button>
        <input type="file" accept="image/*" data-checkin-pwa-icon-upload="${index}" hidden>
      </div>
      <div class="hint">${escapeHtml(t("w.pwaIconHint"))}</div>
    </div>`);
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
    } else if (/^places\.\d+\.(id|title)$/.test(key)) {
      const im = key.match(/^places\.(\d+)\.(id|title)$/);
      if (!im) return;
      const idx = Number(im[1]);
      const sub = im[2];
      if (!Array.isArray(widget.settings.places)) widget.settings.places = [];
      while (widget.settings.places.length <= idx) {
        widget.settings.places.push({ id: "", title: "" });
      }
      if (!widget.settings.places[idx] || typeof widget.settings.places[idx] !== "object") {
        widget.settings.places[idx] = { id: "", title: "" };
      }
      widget.settings.places[idx][sub] = value;
    } else if (/^labels\.[a-zA-Z0-9_]+$/.test(key)) {
      const sub = key.slice("labels.".length);
      if (!widget.settings.labels || typeof widget.settings.labels !== "object") widget.settings.labels = {};
      widget.settings.labels[sub] = value;
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
      } else if (
        (widget.type === "checkin_submit" || widget.type === "checkin_monitor") &&
        key === "fontSize"
      ) {
        widget.settings.fontSize =
          value === "" || value == null || !Number.isFinite(num)
            ? 0
            : Math.max(0, Math.min(48, Math.round(num)));
      } else {
        widget.settings[key] = num;
      }
    } else if (key === "backdrop" || key === "useManual" || key === "advanceOnShow" || key === "randomize") widget.settings[key] = Boolean(value);
    else widget.settings[key] = value;
  } else {
    if (fieldRaw === "enabled" || fieldRaw === "menu_only") widget[fieldRaw] = Boolean(value);
    else widget[fieldRaw] = Number(value);
  }
  if (fieldRaw === "enabled" && widget.enabled === false && Array.isArray(sc.mobile_widget_ids)) {
    const idStr = String(widget.id);
    sc.mobile_widget_ids = sc.mobile_widget_ids.filter((x) => String(x) !== idStr);
  }
  clampWidget(widget);
  deps.render();
}

export async function uploadWidgetImage(file, widgetIndex, slotIndex) {
  if (!file) return;
  if (file.size > MAX_WIDGET_IMAGE_UPLOAD_BYTES) {
    alert(t("w.widgetImageTooLarge"));
    return;
  }
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

export async function uploadEmergencyWidgetImage(file, widgetIndex) {
  if (!file) return;
  if (file.size > MAX_WIDGET_IMAGE_UPLOAD_BYTES) {
    alert(t("w.widgetImageTooLarge"));
    return;
  }
  const formData = new FormData();
  formData.append("file", file);
  const payload = await api("/api/admin/upload-widget-image", { method: "POST", body: formData });
  const sc = screen();
  if (!sc) return;
  const w = sc.widgets[widgetIndex];
  if (!w || w.type !== "emergency") return;
  if (!w.settings) w.settings = {};
  w.settings.imageUrl = payload.path || "";
  deps.render();
  if (state.widgetModalWidgetId === w.id) syncWidgetModal();
  deps.renderPreview();
}

export async function uploadCheckinPwaIcon(file, widgetIndex) {
  if (!file) return;
  if (file.size > MAX_WIDGET_IMAGE_UPLOAD_BYTES) {
    alert(t("w.widgetImageTooLarge"));
    return;
  }
  const formData = new FormData();
  formData.append("file", file);
  const payload = await api("/api/admin/upload-widget-image", { method: "POST", body: formData });
  const sc = screen();
  if (!sc) return;
  const w = sc.widgets[widgetIndex];
  if (!w || (w.type !== "checkin_submit" && w.type !== "checkin_monitor")) return;
  if (!w.settings) w.settings = {};
  w.settings.pwa_icon_url = payload.path || "";
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

/**
 * Скопировать места из первого виджета «Сводка отметок» на экране с slug = settings.events_screen_slug.
 */
export function syncCheckinPlacesFromLinkedScreen(widgetIndex) {
  const sc = screen();
  if (!sc || !state.config?.screens?.length) return;
  const w = sc.widgets[widgetIndex];
  if (!w || w.type !== "checkin_monitor") return;
  const syncSlug = String(w.settings?.events_screen_slug || "").trim();
  if (!syncSlug) return;
  const want = syncSlug.toLowerCase();
  const srcScreen = state.config.screens.find((s) => String(s?.slug || "").trim().toLowerCase() === want);
  if (!srcScreen) {
    window.alert(t("w.checkinPlacesSyncNoScreen"));
    return;
  }
  const monitors = (srcScreen.widgets || []).filter((x) => x && x.type === "checkin_monitor");
  const srcMw = monitors[0];
  if (!srcMw) {
    window.alert(t("w.checkinPlacesSyncNoMonitor"));
    return;
  }
  const raw = Array.isArray(srcMw.settings?.places) ? srcMw.settings.places : [];
  const places = [];
  const seen = new Set();
  for (const p of raw) {
    const id = String(p?.id ?? "").trim().slice(0, 64);
    const title = String(p?.title ?? "").trim().slice(0, 200);
    if (!id || !CHECKIN_PLACE_ID_RE.test(id) || seen.has(id)) continue;
    seen.add(id);
    places.push({ id, title: title || id });
    if (places.length >= 500) break;
  }
  if (!places.length) {
    window.alert(t("w.checkinPlacesSyncEmpty"));
    return;
  }
  const confirmText = t("w.checkinPlacesSyncConfirm").replace(/\{\{slug\}\}/g, syncSlug);
  if (!window.confirm(confirmText)) return;
  if (!w.settings) w.settings = {};
  w.settings.places = places.map((p) => ({ ...p }));
  deps.render();
  if (state.widgetModalWidgetId === w.id) syncWidgetModal();
  deps.renderPreview();
}

export function addCheckinPlaceSlot(widgetIndex) {
  const sc = screen();
  if (!sc) return;
  const w = sc.widgets[widgetIndex];
  if (!w || w.type !== "checkin_monitor") return;
  if (!w.settings) w.settings = {};
  if (!Array.isArray(w.settings.places)) w.settings.places = [];
  if (w.settings.places.length >= 500) return;
  w.settings.places.push({ id: "", title: "" });
  deps.render();
  if (state.widgetModalWidgetId === w.id) syncWidgetModal();
  deps.renderPreview();
}

export function removeCheckinPlaceSlot(widgetIndex, slotIndex) {
  const sc = screen();
  if (!sc) return;
  const w = sc.widgets[widgetIndex];
  if (!w || w.type !== "checkin_monitor") return;
  if (!w.settings || !Array.isArray(w.settings.places)) return;
  const i = Number(slotIndex);
  if (!Number.isFinite(i) || i < 0 || i >= w.settings.places.length) return;
  w.settings.places.splice(i, 1);
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
      if (event.target.dataset.emergencyImageUpload != null) {
        const f = event.target.files && event.target.files[0];
        if (f) {
          uploadEmergencyWidgetImage(f, Number(event.target.dataset.emergencyImageUpload));
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
  root.querySelectorAll("[data-add-checkin-place]").forEach((button) => {
    button.onclick = () => addCheckinPlaceSlot(Number(button.dataset.addCheckinPlace));
  });
  root.querySelectorAll("[data-remove-checkin-place]").forEach((button) => {
    button.onclick = () => {
      const raw = String(button.dataset.removeCheckinPlace || "");
      const [wi, si] = raw.split(":");
      removeCheckinPlaceSlot(Number(wi), Number(si));
    };
  });
  root.querySelectorAll("[data-sync-checkin-places]").forEach((button) => {
    button.onclick = () => syncCheckinPlacesFromLinkedScreen(Number(button.dataset.syncCheckinPlaces));
  });

  root.querySelectorAll("[data-checkin-pwa-icon-browse]").forEach((button) => {
    button.onclick = () => {
      const idx = Number(button.dataset.checkinPwaIconBrowse);
      const inp = root.querySelector(`[data-checkin-pwa-icon-upload="${idx}"]`);
      if (inp) inp.click();
    };
  });
  root.querySelectorAll("[data-checkin-pwa-icon-upload]").forEach((input) => {
    input.onchange = async (e) => {
      try {
        const idx = Number(input.dataset.checkinPwaIconUpload);
        const file = e?.target?.files?.[0];
        if (!file) return;
        await uploadCheckinPwaIcon(file, idx);
      } catch (err) {
        window.alert(err?.message || String(err));
      } finally {
        try { input.value = ""; } catch (_) {}
      }
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
    else if (state.programSettingsPanelActive) deps.closeProgramSettingsModal();
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
      const cfgTitle = escapeHtmlAttr(t("widget.configure"));
      div.innerHTML = `
      <div class="widget-title-row">
        <h3>${escapeHtmlAttr(widgetDisplayTitle(widget))}</h3>
        <div class="widget-actions">
          <button type="button" class="widget-card-config-btn" data-open-widget-editor="${wid}" data-i18n-title="widget.configure" data-i18n-aria-label="widget.configure" title="${cfgTitle}" aria-label="${cfgTitle}">
            <svg class="widget-card-config-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false"><path fill="currentColor" d="M19.14 12.94c.04-.31.06-.63.06-.94 0-.31-.02-.63-.06-.94l2.03-1.58a.49.49 0 0 0 .12-.61l-1.92-3.32a.488.488 0 0 0-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.49.49 0 0 0-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96a.488.488 0 0 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94l-2.03 1.58a.49.49 0 0 0-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6a3.6 3.6 0 1 1 0-7.2 3.6 3.6 0 0 1 0 7.2z"/></svg>
          </button>
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
