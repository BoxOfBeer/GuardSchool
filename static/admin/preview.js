/**
 * Предпросмотр экрана в админке: сетка, drag/resize, POST /api/admin/preview-payload.
 * Зависимости из app.js передаются через setPreviewDeps (без циклического импорта).
 */
import { state, elements, GRID } from "./state.js";
import { t, tf } from "./i18n-helpers.js";
import { api } from "./api-client.js";
import { escapeHtml, escapeHtmlAttr } from "./escape-html.js";

/** @type {{ selectedScreen: () => any, clampWidget: (widget: any) => void, render: () => void } | null} */
let deps = null;

/** Вызвать из app.js после объявления selectedScreen, clampWidget, render. */
export function setPreviewDeps(d) {
  deps = d;
}

function d() {
  return deps;
}

export function pointerToGrid(event, rect) {
  return {
    col: Math.max(0, Math.min(GRID.cols - 1, Math.floor(((event.clientX - rect.left) / rect.width) * GRID.cols))),
    row: Math.max(0, Math.min(GRID.rows - 1, Math.floor(((event.clientY - rect.top) / rect.height) * GRID.rows))),
  };
}

export function startDrag(event, widgetIndex) {
  const getScreen = d()?.selectedScreen;
  if (!getScreen) return;
  const screen = getScreen();
  if (!screen) return;
  const widget = screen.widgets[widgetIndex];
  if (!widget || widget.type === "emergency") return;
  const rect = elements.preview.getBoundingClientRect();
  const start = pointerToGrid(event, rect);
  state.drag = {
    widgetIndex,
    mode: event.shiftKey ? "resize" : "move",
    startCol: start.col,
    startRow: start.row,
    origin: { x: widget.x, y: widget.y, w: widget.w, h: widget.h },
  };
}

export function handlePointerMove(event) {
  if (!state.drag) return;
  const getScreen = d()?.selectedScreen;
  const clampWidget = d()?.clampWidget;
  const render = d()?.render;
  if (!getScreen || !clampWidget || !render) return;
  const screen = getScreen();
  if (!screen) return;
  const rect = elements.preview.getBoundingClientRect();
  const point = pointerToGrid(event, rect);
  const widget = screen.widgets[state.drag.widgetIndex];
  if (state.drag.mode === "move") {
    widget.x = state.drag.origin.x + (point.col - state.drag.startCol);
    widget.y = state.drag.origin.y + (point.row - state.drag.startRow);
  } else {
    widget.w = state.drag.origin.w + (point.col - state.drag.startCol);
    widget.h = state.drag.origin.h + (point.row - state.drag.startRow);
  }
  clampWidget(widget);
  render();
}

export function stopDrag() {
  state.drag = null;
  renderPreview();
}

export async function fetchPreviewPayloadOnce() {
  const getScreen = d()?.selectedScreen;
  if (!getScreen) return;
  const screen = getScreen();
  if (!screen || !window.GuardSchoolScreen) return;
  try {
    const body = { screen };
    if (state.config && Array.isArray(state.config.emergency_templates)) {
      body.emergency_templates = state.config.emergency_templates;
      body.emergency_active_template_id = state.config.emergency_active_template_id ?? "";
    }
    const res = await api("/api/admin/preview-payload", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    state.previewCache = {
      schedule: res.schedule,
      holidays: res.holidays,
      background_gallery: res.background_gallery || [],
      announcements: res.announcements || [],
      marquee: res.marquee || [],
      pc_audio_preview: res.pc_audio_preview || null,
      display: res.display || null,
      displayScreen: res.screen && typeof res.screen === "object" ? res.screen : null,
    };
    state.previewCacheScreenId = screen.id;
    if (state.activeSection === "preview") {
      renderPreview();
    }
  } catch (e) {
    state.previewCache = null;
    if (state.activeSection === "preview") {
      elements.preview.innerHTML = `<p class="hint preview-hint-banner preview-hint-overlay">${tf("preview.errorDetail", { base: t("preview.error"), msg: escapeHtmlAttr(String(e.message || e)) })}</p>`;
      elements.preview.classList.add("screen-preview--hint-only");
    }
  }
}

export function renderGridHighlight(preview) {
  if (!state.drag) return;
  const getScreen = d()?.selectedScreen;
  if (!getScreen) return;
  const screen = getScreen();
  if (!screen) return;
  const widget = screen.widgets[state.drag.widgetIndex];
  const highlight = document.createElement("div");
  highlight.className = "grid-highlight";
  highlight.style.gridColumn = `${widget.x + 1} / span ${widget.w}`;
  highlight.style.gridRow = `${widget.y + 1} / span ${widget.h}`;
  preview.appendChild(highlight);
}

/** Сборка строк предпросмотра звука: i18n-события с бэкенда или fallback на legacy lines. */
export function formatPreviewPcAudioLines(soundDiag) {
  if (!soundDiag) return [];
  if (Array.isArray(soundDiag.events) && soundDiag.events.length) {
    return soundDiag.events
      .map((e) => {
        if (!e || !e.key) return "";
        const raw = e.params && typeof e.params === "object" ? { ...e.params } : {};
        if (raw.enabled === true) raw.enabledLabel = t("common.on");
        if (raw.enabled === false) raw.enabledLabel = t("common.off");
        delete raw.enabled;
        if ("useSchedule" in raw) {
          raw.useScheduleLabel = raw.useSchedule ? t("common.yes") : t("common.no");
          delete raw.useSchedule;
        }
        if ("useFiles" in raw) {
          raw.useFilesLabel = raw.useFiles ? t("common.yes") : t("common.no");
          delete raw.useFiles;
        }
        if ("breakMusic" in raw) {
          raw.breakMusicLabel = raw.breakMusic ? t("common.yes") : t("common.no");
          delete raw.breakMusic;
        }
        if (raw.bellKind === "start") raw.bellKindLabel = t("preview.pcAudio.bellStart");
        if (raw.bellKind === "end") raw.bellKindLabel = t("preview.pcAudio.bellEnd");
        delete raw.bellKind;
        return tf(e.key, raw);
      })
      .filter(Boolean);
  }
  if (Array.isArray(soundDiag.lines) && soundDiag.lines.length) return soundDiag.lines;
  return [];
}

export function renderPreview() {
  const getScreen = d()?.selectedScreen;
  if (!getScreen) return;
  const screenBase = getScreen();
  if (!screenBase) return;
  const screen =
    state.previewCache?.displayScreen &&
    state.previewCache.displayScreen.id === screenBase.id &&
    state.previewCacheScreenId === screenBase.id
      ? state.previewCache.displayScreen
      : screenBase;
  const G = window.GuardSchoolScreen;
  if (!G) {
    if (state.activeSection === "preview" && elements.preview) {
      elements.preview.innerHTML = `<p class="hint preview-hint-banner preview-hint-overlay">${escapeHtml(t("preview.noScript"))}</p>`;
      elements.preview.classList.add("screen-preview--hint-only");
      elements.preview.style.background = "";
    }
    return;
  }
  if (state.activeSection !== "preview") {
    G.clearAllTimers();
    return;
  }

  if (state.previewCacheScreenId !== screen.id) {
    state.previewCache = null;
    state.previewCacheScreenId = screen.id;
  }

  if (!state.previewCache) {
    const G0 = window.GuardSchoolScreen;
    const u0 =
      G0 && G0.resolveBackgroundImageUrl
        ? G0.resolveBackgroundImageUrl(screen, [])
        : screen.background_image || "";
    elements.preview.style.background = u0 ? `url(${u0}) center/cover` : "";
    elements.preview.innerHTML = `<p class="hint preview-hint-banner preview-hint-overlay">${escapeHtml(t("preview.loading"))}</p>`;
    elements.preview.classList.add("screen-preview--hint-only");
    fetchPreviewPayloadOnce();
    return;
  }

  const { schedule, holidays, announcements, marquee, rss_news: rssNews, background_gallery: previewGallery, pc_audio_preview: soundDiag } = state.previewCache;
  if (elements.previewSoundDiag) {
    const diagLines = formatPreviewPcAudioLines(soundDiag);
    if (diagLines.length) {
      elements.previewSoundDiag.hidden = false;
      elements.previewSoundDiag.textContent = [t("preview.soundDiag"), ...diagLines].join("\n");
    } else {
      elements.previewSoundDiag.hidden = true;
      elements.previewSoundDiag.textContent = "";
    }
  }
  (G.pruneStaleWidgetState || G.pruneStaleCarouselState)(screen);
  G.clearAllTimers();

  const gal = previewGallery || [];
  elements.preview.style.background = "";
  elements.preview.classList.remove("screen-preview--hint-only");

  const hiddenWidgetIds = G.widgetIdsHiddenByCarousel(screen);
  const preview = document.createElement("div");
  preview.className = "screen-grid";
  const isPortrait = String(screen.orientation || "").toLowerCase() === "portrait";
  const cols = GRID.cols;
  const rows = GRID.rows;
  preview.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
  preview.style.gridTemplateRows = `repeat(${rows}, 1fr)`;
  // Контейнер превью по умолчанию 16:9 — для портрета выставляем 9:16.
  if (elements.preview && elements.preview.style) {
    elements.preview.style.aspectRatio = isPortrait ? "9 / 16" : "16 / 9";
  }
  if (state.drag) {
    preview.classList.add("show-grid");
  }
  renderGridHighlight(preview);
  const ordered = G.sortWidgetsForDom ? G.sortWidgetsForDom(screen) : screen.widgets;
  let placedWidgetCount = 0;
  ordered.forEach((widget) => {
    if (widget.enabled === false) return;
    if (hiddenWidgetIds.has(widget.id) && widget.type !== "carousel") return;
    placedWidgetCount += 1;
    const index = screen.widgets.findIndex((w) => w.id === widget.id);
    const item = document.createElement("div");
    item.className = `screen-widget draggable ${state.drag?.widgetIndex === index ? "dragging" : ""}`;
    if (widget.type === "emergency") {
      item.classList.add("screen-widget--emergency");
      item.style.gridColumn = "1 / -1";
      item.style.gridRow = "1 / -1";
    } else if (widget.type === "image") {
      item.classList.add("screen-widget--image");
      item.style.gridColumn = `${widget.x + 1} / span ${widget.w}`;
      item.style.gridRow = `${widget.y + 1} / span ${widget.h}`;
      item.style.zIndex = "0";
    } else {
      item.style.gridColumn = `${widget.x + 1} / span ${widget.w}`;
      item.style.gridRow = `${widget.y + 1} / span ${widget.h}`;
    }
    if (widget.type === "text") item.style.background = widget.settings.background;
    if (widget.type === "carousel") {
      item.classList.add("carousel-widget");
      const childWidgets = G.orderedCarouselChildWidgets
        ? G.orderedCarouselChildWidgets(screen, widget)
        : screen.widgets.filter((w) => (widget.settings.childWidgetIds || []).includes(w.id));
      G.startCarousel(item, widget, childWidgets, schedule, screen, holidays, announcements || [], marquee || [], rssNews || []);
    } else {
      item.innerHTML = G.renderWidgetHtml(widget, schedule, screen, holidays, announcements || [], marquee || [], rssNews || []);
    }
    if (G.applyWidgetBackdropClass) G.applyWidgetBackdropClass(item, widget);
    if (widget.type !== "emergency") item.onpointerdown = (event) => startDrag(event, index);
    preview.appendChild(item);
  });
  elements.preview.innerHTML = "";
  if (placedWidgetCount === 0) {
    const emptyHint = document.createElement("p");
    emptyHint.className = "hint preview-hint-banner preview-hint-overlay";
    emptyHint.textContent = t("preview.emptyWidgets");
    elements.preview.appendChild(emptyHint);
    elements.preview.classList.add("screen-preview--hint-only");
  } else {
    elements.preview.appendChild(preview);
  }
  if (G.applyTvScreenBackground) G.applyTvScreenBackground(elements.preview, screen, gal);
  if (G.applyTvTextOutline) G.applyTvTextOutline(elements.preview, screen);

  const display =
    state.previewCache?.display ||
    ({
      timezone: state.config?.timezone || "Europe/Moscow",
      clock_offset_minutes: Number(state.config?.clock_offset_minutes) || 0,
      ui_locale: state.config?.ui_locale || "ru",
    });
  window.__lastScreenPayload = {
    screen,
    schedule,
    holidays,
    announcements,
    marquee,
    display,
    background_gallery: previewGallery,
  };
  G.updateAllClocks(elements.preview);

  clearTimeout(window.__previewResyncTimer);
  if (!document.hidden) {
    window.__previewResyncTimer = setTimeout(fetchPreviewPayloadOnce, 5000);
  }
}
