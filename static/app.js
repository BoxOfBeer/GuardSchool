/* Загружается как модульный dependency до остальных импортов — window.GuardSchoolScreen всегда к моменту init. */
import "./screen_widgets.js?v=1.01.012";
import {
  setPreviewDeps,
  fetchPreviewPayloadOnce,
  renderPreview,
  startDrag,
  handlePointerMove,
  stopDrag,
} from "./admin/preview.js";
import {
  setAudioStreamDeps,
  ensureAudioStreamConfig,
  refreshBellSoundsForStream,
  refreshPcPlayerFiles,
  renderPcPlayerFileList,
  renderBreakMusicPlayback,
  updateStreamStatusBar,
  syncAudioStreamFormFromState,
  readAudioStreamFormIntoState,
  bindAudioStreamFormOnce,
  bindPcPlayerOnce,
  bindSettingsSoundTestsOnce,
} from "./admin/audio-stream.js";
import { enterStatsPanel, leaveStatsPanel } from "./admin/stats.js";
import {
  setDataImportDeps,
  uploadBackground,
  uploadScheduleDated,
  uploadFullSchedule,
  uploadScheduleSample,
  uploadHolidays,
  uploadAnnouncements,
  uploadMarquee,
  exportWeeklyScheduleZip,
  importWeeklyScheduleZip,
  downloadWeeklyScheduleTemplateXlsx,
  importBundle,
} from "./admin/data-import.js";
import {
  setBellDeps,
  renderBellTemplateOptions,
  renderBellEditor,
  addBellTemplate,
  deleteBellTemplate,
  addBellRow,
  flushBellEditorFromDom,
  saveBellEditorToState,
} from "./admin/bells.js";
import {
  setWidgetDeps,
  closeWidgetModal,
  syncWidgetModal,
  bindWidgetModalOnce,
  renderWidgets,
} from "./admin/widgets.js";
import { renderHistory } from "./admin/history.js";
import { state, elements, GRID } from "./admin/state.js";
import { t, tf, getSectionTabs } from "./admin/i18n-helpers.js";
import { api, downloadFile } from "./admin/api-client.js";
import { populateAdminTimezoneSelect } from "./admin/timezone.js";
import { escapeHtml, escapeHtmlAttr } from "./admin/escape-html.js";

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

/** Порядок чекбоксов «показывать в списке виджетов» в настройках программы. */
const PALETTE_TYPES_ORDER = [
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
];

function ensureAdminPaletteHidden() {
  if (!state.config) return;
  if (!Array.isArray(state.config.admin_palette_hidden_types)) {
    state.config.admin_palette_hidden_types = [];
  }
}

function isWidgetTypeHiddenInAdminPalette(wtype) {
  if (!state.config) return false;
  const raw = state.config.admin_palette_hidden_types;
  if (!Array.isArray(raw)) return false;
  return raw.includes(String(wtype || ""));
}

function setWidgetTypeHiddenInPalette(wtype, hidden) {
  ensureAdminPaletteHidden();
  const typ = String(wtype || "");
  if (!WIDGET_TYPE_KEYS.has(typ)) return;
  let arr = [...state.config.admin_palette_hidden_types];
  const idx = arr.indexOf(typ);
  if (hidden && idx < 0) arr.push(typ);
  if (!hidden && idx >= 0) arr.splice(idx, 1);
  arr = arr.filter((x) => WIDGET_TYPE_KEYS.has(x));
  state.config.admin_palette_hidden_types = arr;
  renderWidgets();
}

function syncProgramSettingsFieldsFromState() {
  if (!state.config) return;
  if (elements.adminLocaleSelect) {
    elements.adminLocaleSelect.value = state.config.ui_locale === "en" ? "en" : "ru";
  }
  populateAdminTimezoneSelect();
  if (elements.adminClockOffset) {
    const o = Number(state.config.clock_offset_minutes);
    elements.adminClockOffset.value = String(Number.isFinite(o) ? o : 0);
  }
  if (elements.cloudBaseUrl) elements.cloudBaseUrl.value = String(state.config.cloud_base_url || "");
  if (elements.cloudSyncInterval) {
    const ci = Number(state.config.cloud_sync_interval_minutes);
    elements.cloudSyncInterval.value = String(Number.isFinite(ci) ? ci : 5);
  }
  if (elements.cloudSyncEnabled) elements.cloudSyncEnabled.checked = state.config.cloud_sync_enabled !== false;
  if (elements.cloudSyncToken) elements.cloudSyncToken.value = String(state.config.cloud_sync_token || "");
  if (elements.screenPrimaryBase) elements.screenPrimaryBase.value = String(state.config.screen_primary_base_url || "");
  if (elements.screenFallbackBase) elements.screenFallbackBase.value = String(state.config.screen_fallback_base_url || "");
  if (elements.screenFallbackEnabled) elements.screenFallbackEnabled.checked = Boolean(state.config.screen_fallback_enabled);
  if (elements.screenPollTimeout) {
    const pt = Number(state.config.screen_poll_timeout_sec);
    elements.screenPollTimeout.value = String(Number.isFinite(pt) ? pt : 5);
  }
}

function renderProgramPaletteCheckboxes() {
  const wrap = elements.programSettingsPaletteWrap;
  if (!wrap || !state.config) return;
  ensureAdminPaletteHidden();
  wrap.innerHTML = PALETTE_TYPES_ORDER.filter((typ) => WIDGET_TYPE_KEYS.has(typ))
    .map((typ) => {
      const id = `palette-show-${typ}`;
      const checked = !isWidgetTypeHiddenInAdminPalette(typ);
      const lab = t(`widget.type.${typ}`);
      const label = lab !== `widget.type.${typ}` ? lab : typ;
      return `<label class="toggle-label"><input type="checkbox" id="${escapeHtmlAttr(id)}" data-palette-type="${escapeHtmlAttr(typ)}" ${checked ? "checked" : ""}><span>${escapeHtml(label)}</span></label>`;
    })
    .join("");
  wrap.querySelectorAll("input[data-palette-type]").forEach((inp) => {
    inp.addEventListener("change", () => {
      const typ = inp.getAttribute("data-palette-type");
      if (!typ) return;
      setWidgetTypeHiddenInPalette(typ, !inp.checked);
    });
  });
}

async function refreshSyncStatusLine() {
  const el = elements.syncStatusLine;
  if (!el) return;
  try {
    const st = await api("/api/admin/sync-status");
    const ss = st.sync_state || {};
    const rev = st.data_revision || "—";
    let msg = "";
    if (ss.last_error) {
      msg = `ошибка: ${String(ss.last_error).slice(0, 200)}`;
    } else if (ss.last_ok_at) {
      const d = new Date(Number(ss.last_ok_at) * 1000);
      msg = `OK, ${d.toLocaleString()}`;
    } else {
      msg = "ещё не было успешной синхронизации";
    }
    el.textContent = `Синхронизация: ${msg} | ревизия данных: ${rev}`;
  } catch (e) {
    el.textContent = `Статус: ${e.message || String(e)}`;
  }
}

function openProgramSettingsModal() {
  if (!elements.programSettingsModal) return;
  closeWidgetModal();
  syncProgramSettingsFieldsFromState();
  renderProgramPaletteCheckboxes();
  refreshSyncStatusLine().catch(() => {});
  try {
    GuardSchoolI18n.applyDom(elements.programSettingsModal);
  } catch (_) {}
  elements.programSettingsModal.hidden = false;
  elements.programSettingsModal.setAttribute("aria-hidden", "false");
}

function closeProgramSettingsModal() {
  const m = elements.programSettingsModal;
  if (!m) return;
  const ae = document.activeElement;
  if (ae && m.contains(ae)) {
    if (elements.programSettingsOpenBtn) elements.programSettingsOpenBtn.focus();
    else ae.blur();
  }
  m.hidden = true;
  m.setAttribute("aria-hidden", "true");
}

function bindProgramSettingsModalOnce() {
  if (bindProgramSettingsModalOnce._done) return;
  bindProgramSettingsModalOnce._done = true;
  elements.programSettingsOpenBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    openProgramSettingsModal();
  });
  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-close-program-settings]")) {
      e.preventDefault();
      closeProgramSettingsModal();
    }
  });
}

function getWeekdayOptions() {
  return ["0", "1", "2", "3", "4", "5", "6"].map((id) => ({
    id,
    label: t(`weekday.short${id}`),
    title: t(`weekday.long${id}`),
  }));
}

function getCarouselAnimations() {
  return [
    { id: "slide", label: t("carousel.slide") },
    { id: "slideUp", label: t("carousel.slideUp") },
    { id: "slideDown", label: t("carousel.slideDown") },
    { id: "slideFromLeft", label: t("carousel.slideFromLeft") },
    { id: "fade", label: t("carousel.fade") },
    { id: "zoom", label: t("carousel.zoom") },
    { id: "blurSoft", label: t("carousel.blurSoft") },
    { id: "flipLight", label: t("carousel.flipLight") },
    { id: "rotateIn", label: t("carousel.rotateIn") },
    { id: "random", label: t("carousel.random") },
  ];
}

function applyUiFontSize(px) {
  const n = Number(px);
  const clamped = Number.isFinite(n) ? Math.max(12, Math.min(24, Math.round(n))) : 14;
  document.documentElement.style.setProperty("--admin-base-font", `${clamped}px`);
  try {
    localStorage.setItem("guardschool_ui_font_px", String(clamped));
  } catch (_) {
    /* ignore */
  }
  if (elements.uiFontSizeInput) elements.uiFontSizeInput.value = String(clamped);
}

function initUiFontSize() {
  let v = 14;
  try {
    const raw = localStorage.getItem("guardschool_ui_font_px");
    if (raw) v = Number(raw);
  } catch (_) {
    /* ignore */
  }
  applyUiFontSize(v);
  if (elements.uiFontSizeInput) {
    elements.uiFontSizeInput.addEventListener("input", () => applyUiFontSize(elements.uiFontSizeInput.value));
    elements.uiFontSizeInput.addEventListener("change", () => applyUiFontSize(elements.uiFontSizeInput.value));
  }
}

function selectedScreenSlug() {
  const screens = state.config?.screens || [];
  const sid = state.selectedScreenId;
  const sc = screens.find((s) => String(s.id) === String(sid)) || screens[0];
  return sc?.slug || "tv-1";
}

function selectedScreen() {
  return state.config.screens.find((screen) => screen.id === state.selectedScreenId);
}

function createTemplateId() {
  return `tpl_${crypto.randomUUID().slice(0, 8)}`;
}

function createWidgetId(prefix = "widget") {
  return `${prefix}_${crypto.randomUUID().slice(0, 8)}`;
}

function createDefaultScreen(index) {
  return {
    id: crypto.randomUUID().slice(0, 8),
    name: tf("screen.defaultName", { n: index }),
    slug: `tv-${index}`,
    ip_note: "",
    poll_interval_sec: 10,
    background_image: "",
    background_rotate_enabled: false,
    background_rotate_interval_sec: 3600,
    background_rotate_folder: "",
    background_force_image: "",
    background_rotate_cursor: 0,
    background_rotate_epoch: 0,
    tv_text_outline_px: 2,
    tv_text_outline_color: "rgba(0,0,0,0.85)",
    selected_classes: ["5", "6", "7", "8"],
    bell_schedule_template: "standard",
    weekday_bell_templates: {},
    template: "default_schedule",
    is_active: true,
    widgets: [
      {
        id: "date",
        type: "date",
        title: "Дата",
        enabled: true,
        x: 0, y: 0, w: 12, h: 2,
        settings: { fontSize: 32, color: "#ffffff", bold: false },
      },
      {
        id: "time",
        type: "time",
        title: "Время",
        enabled: true,
        x: 12, y: 0, w: 8, h: 2,
        settings: { fontSize: 42, color: "#ffffff", bold: false },
      },
      {
        id: "text",
        type: "text",
        title: "Текст",
        enabled: true,
        x: 20, y: 0, w: 12, h: 2,
        settings: { text: "Добро пожаловать", fontSize: 24, color: "#ffffff", background: "rgba(0,0,0,0.35)", bold: false },
      },
      {
        id: "bell_status",
        type: "bell_status",
        title: "Звонки",
        enabled: true,
        x: 24, y: 10, w: 8, h: 3,
        settings: { fontSize: 18, titleFontSize: 18, color: "#ffffff", background: "rgba(15,23,42,0.55)", bold: false },
      },
      {
        id: "schedule",
        type: "schedule",
        title: "Расписание",
        enabled: true,
        x: 0, y: 2, w: 24, h: 11,
        settings: {
          showTomorrow: true,
          highlightColor: "#8b0000",
          sampleDiffColor: "#fee2e2",
          headerColor: "#1e3a5f",
          bodyColor: "rgba(255,255,255,0.9)",
          fontSize: 16,
          titleFontSize: 20,
          classes: ["5", "6", "7", "8"],
          bold: false,
        },
      },
      {
        id: createWidgetId("carousel"),
        type: "carousel",
        title: "Карусель",
        enabled: false,
        x: 0, y: 2, w: 24, h: 11,
        settings: {
          startDelaySec: 0,
          animation: "slide",
          childWidgetIds: ["schedule", "text"],
          childSlideSec: { schedule: 60, text: 30 },
        },
      },
      {
        id: "holidays",
        type: "holidays",
        title: "События",
        enabled: false,
        x: 24, y: 2, w: 8, h: 5,
        settings: { fontSize: 16, titleFontSize: 18, color: "#ffffff", background: "rgba(15,23,42,0.55)", count: 5, bold: false },
      },
      {
        id: "announcements",
        type: "announcements",
        title: "Объявления",
        enabled: false,
        x: 20, y: 0, w: 12, h: 4,
        settings: {
          items: "",
          useManual: false,
          rotateSec: 30,
          advanceOnShow: true,
          randomize: true,
          fontSize: 18,
          titleFontSize: 18,
          color: "#ffffff",
          background: "rgba(15,23,42,0.55)",
          bold: false,
        },
      },
      {
        id: "marquee",
        type: "marquee",
        title: "Бегущая строка",
        enabled: false,
        x: 0, y: 24, w: 32, h: 2,
        settings: {
          items: "",
          useManual: false,
          fontSize: 22,
          color: "#ffffff",
          background: "rgba(15,23,42,0.7)",
          charsPerMin: 180,
          speedSec: 18,
          bold: false,
        },
      },
      {
        id: "emergency",
        type: "emergency",
        title: "Аварийный",
        enabled: false,
        x: 0,
        y: 0,
        w: GRID.cols,
        h: GRID.rows,
        settings: {
          text: "ВНИМАНИЕ!\nСрочное сообщение.",
          fontSize: 42,
          color: "#ffffff",
          background: "#b91c1c",
          bold: true,
          backdrop: true,
        },
      },
      {
        id: "image",
        type: "image",
        title: "Изображение",
        enabled: false,
        x: 0,
        y: 0,
        w: 8,
        h: 8,
        settings: {
          images: [{ name: "Эмблема", url: "" }],
          imagesRotateSec: 0,
          opacity: 85,
          objectFit: "contain",
          backdrop: false,
        },
      },
    ],
  };
}

function widgetCollapseStorageKey(screenId, widgetId) {
  return `guardschool.widgetCollapsed.${screenId}.${widgetId}`;
}

function isWidgetCollapsed(screenId, widgetId) {
  return localStorage.getItem(widgetCollapseStorageKey(screenId, widgetId)) === "1";
}

function setWidgetCollapsed(screenId, widgetId, collapsed) {
  localStorage.setItem(widgetCollapseStorageKey(screenId, widgetId), collapsed ? "1" : "0");
}

function normalizeClass(value) {
  return String(value || "").trim().toLowerCase();
}

function classSortKey(value) {
  const normalized = normalizeClass(value);
  const match = normalized.match(/^(\d+)\s*([a-zа-я]*)$/i);
  if (match) {
    return [Number(match[1]), match[2]];
  }
  return [10000, normalized];
}

function compareClassNames(a, b) {
  const [aNum, aSuffix] = classSortKey(a);
  const [bNum, bSuffix] = classSortKey(b);
  if (aNum !== bNum) return aNum - bNum;
  return aSuffix.localeCompare(bSuffix, "ru");
}

function availableClassOptions() {
  const classNames = [...new Set((state.schedule || []).map((item) => item.class_name).filter(Boolean))].sort(compareClassNames);
  const gradeNames = [...new Set(classNames
    .map((item) => normalizeClass(item).match(/^(\d+)/)?.[1])
    .filter(Boolean))]
    .sort((a, b) => Number(a) - Number(b));
  return [
    ...gradeNames.map((grade) => ({ value: grade, label: `${grade} (вся параллель)` })),
    ...classNames.map((name) => ({ value: name, label: name })),
  ];
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

/** Как на сервере (app.py) и в screen_widgets: интервал ротации фона 60…86400 с. */
function clampBackgroundRotateIntervalSec(n) {
  if (!Number.isFinite(n)) return 3600;
  return Math.max(60, Math.min(86400, Math.round(n)));
}

const GS_ADMIN_SESSION_TOP = "gs_admin_top";
const GS_ADMIN_SESSION_SCREEN = "gs_admin_screen_id";
const GS_ADMIN_SESSION_SECTION = "gs_admin_section";

function restoreAdminUiFromSession() {
  if (!state.config?.screens?.length) return;
  try {
    const sec = sessionStorage.getItem(GS_ADMIN_SESSION_SECTION);
    if (sec && ["main", "schedule", "preview", "history"].includes(sec)) state.activeSection = sec;
    const top = sessionStorage.getItem(GS_ADMIN_SESSION_TOP);
    const sid = sessionStorage.getItem(GS_ADMIN_SESSION_SCREEN);
    if (top === "audio") {
      state.audioStreamPanelActive = true;
      state.statsPanelActive = false;
    } else if (top === "stats") {
      state.statsPanelActive = true;
      state.audioStreamPanelActive = false;
    } else {
      state.audioStreamPanelActive = false;
      state.statsPanelActive = false;
      if (sid && state.config.screens.some((s) => s.id === sid)) {
        state.selectedScreenId = sid;
      }
    }
  } catch (_) {}
}

function finishTopBarSessionWidgets() {
  syncEmergencyModeCheckbox();
  bindEmergencyModeToggleOnce();
  persistAdminUiToSession();
}

function persistAdminUiToSession() {
  try {
    let top = "screen";
    if (state.audioStreamPanelActive) top = "audio";
    else if (state.statsPanelActive) top = "stats";
    sessionStorage.setItem(GS_ADMIN_SESSION_TOP, top);
    sessionStorage.setItem(GS_ADMIN_SESSION_SCREEN, state.selectedScreenId || "");
    sessionStorage.setItem(GS_ADMIN_SESSION_SECTION, state.activeSection || "main");
  } catch (_) {}
}

function emergencyWidgetTemplate() {
  return {
    id: "emergency",
    type: "emergency",
    title: "Аварийный",
    enabled: false,
    x: 0,
    y: 0,
    w: GRID.cols,
    h: GRID.rows,
    settings: {
      text: "ВНИМАНИЕ!\nСрочное сообщение.",
      fontSize: 42,
      color: "#ffffff",
      background: "#b91c1c",
      bold: true,
      backdrop: true,
      soundEnabled: false,
      soundUrl: "",
    },
  };
}

function ensureEmergencyWidgetOnScreen(screen) {
  const list = screen.widgets || (screen.widgets = []);
  let w = list.find((x) => x.type === "emergency");
  if (!w) {
    list.push(JSON.parse(JSON.stringify(emergencyWidgetTemplate())));
    w = list.find((x) => x.type === "emergency");
  }
  return w;
}

function syncEmergencyModeCheckbox() {
  const el = document.getElementById("admin-emergency-mode");
  if (!el || !state.config?.screens?.length) return;
  const allOn = state.config.screens.every((sc) => {
    const w = sc.widgets?.find((x) => x.type === "emergency");
    return w && w.enabled !== false;
  });
  const anyOn = state.config.screens.some((sc) => {
    const w = sc.widgets?.find((x) => x.type === "emergency");
    return w && w.enabled !== false;
  });
  el.checked = allOn;
  el.indeterminate = !allOn && anyOn;
}

function bindEmergencyModeToggleOnce() {
  const el = document.getElementById("admin-emergency-mode");
  if (!el || el.dataset.gsBoundEmergency === "1") return;
  el.dataset.gsBoundEmergency = "1";
  el.addEventListener("change", async () => {
    if (!state.config?.screens?.length) return;
    const on = Boolean(el.checked);
    el.indeterminate = false;
    state.config.screens.forEach((screen) => {
      const w = ensureEmergencyWidgetOnScreen(screen);
      if (w) {
        w.enabled = on;
        if (!w.settings) w.settings = {};
      }
    });
    try {
      readAudioStreamFormIntoState();
      state.config.templateSystem.grid = GRID;
      await api("/api/admin/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(state.config),
      });
    } catch (e) {
      alert(String(e.message || e));
    }
    render();
  });
}

function renderTabs() {
  elements.tabs.innerHTML = "";
  const audioBtn = document.createElement("button");
  audioBtn.type = "button";
  audioBtn.className = `top-nav-btn ${state.audioStreamPanelActive ? "active" : ""}`;
  audioBtn.textContent = t("tabs.pcAudio");
  audioBtn.onclick = () => {
    closeWidgetModal();
    state.audioStreamPanelActive = true;
    state.statsPanelActive = false;
    render();
  };
  elements.tabs.appendChild(audioBtn);

  const statsBtn = document.createElement("button");
  statsBtn.type = "button";
  statsBtn.className = `top-nav-btn ${state.statsPanelActive ? "active" : ""}`;
  statsBtn.textContent = t("tabs.stats");
  statsBtn.onclick = () => {
    closeWidgetModal();
    state.statsPanelActive = true;
    state.audioStreamPanelActive = false;
    render();
  };
  elements.tabs.appendChild(statsBtn);

  state.config.screens.forEach((screen) => {
    const button = document.createElement("button");
    button.className = `top-nav-btn ${!state.audioStreamPanelActive && !state.statsPanelActive && screen.id === state.selectedScreenId ? "active" : ""}`;
    button.textContent = screen.name;
    button.onclick = () => {
      state.audioStreamPanelActive = false;
      state.statsPanelActive = false;
      closeWidgetModal();
      state.selectedScreenId = screen.id;
      render();
    };
    elements.tabs.appendChild(button);
  });
  const plus = document.createElement("button");
  plus.className = "top-nav-btn";
  plus.textContent = t("tabs.addScreen");
  plus.onclick = addScreen;
  elements.tabs.appendChild(plus);
}

function renderSectionTabs() {
  elements.sectionTabs.innerHTML = "";
  getSectionTabs().forEach((section) => {
    const button = document.createElement("button");
    button.className = `section-tab-btn ${state.activeSection === section.id ? "active" : ""}`;
    button.textContent = section.label;
    button.onclick = () => {
      state.activeSection = section.id;
      if (section.id !== "main") closeWidgetModal();
      renderSectionVisibility();
      renderSectionTabs();
      if (section.id === "preview") {
        renderPreview();
        clearTimeout(window.__previewCfgDebounce);
        window.__previewCfgDebounce = setTimeout(() => fetchPreviewPayloadOnce(), 80);
      } else if (section.id === "schedule") {
        renderBellEditor();
      } else {
        window.GuardSchoolScreen?.clearAllTimers();
      }
      persistAdminUiToSession();
    };
    elements.sectionTabs.appendChild(button);
  });
}

function renderSectionVisibility() {
  document.querySelectorAll("[data-section]").forEach((block) => {
    block.hidden = block.dataset.section !== state.activeSection;
  });
}

function renderForm() {
  const screen = selectedScreen();
  elements.screenName.value = screen.name;
  elements.screenSlug.value = screen.slug;
  elements.screenIpNote.value = screen.ip_note;
  elements.screenPollInterval.value = screen.poll_interval_sec;
  elements.screenBackground.value = screen.background_image || "";
  if (elements.screenBgRotate) elements.screenBgRotate.checked = Boolean(screen.background_rotate_enabled);
  if (elements.screenBgRotateInterval) {
    const iv = Number(screen.background_rotate_interval_sec);
    elements.screenBgRotateInterval.value = String(clampBackgroundRotateIntervalSec(Number.isFinite(iv) ? iv : 3600));
  }
  if (elements.screenBgFolder) {
    elements.screenBgFolder.value = String(screen.background_rotate_folder || "");
  }
  if (elements.screenTextOutline) {
    const px = Number(screen.tv_text_outline_px);
    elements.screenTextOutline.value = String(Number.isFinite(px) ? px : 2);
  }
  if (elements.screenTextOutlineColor) {
    elements.screenTextOutlineColor.value = String(screen.tv_text_outline_color || "rgba(0,0,0,0.85)");
  }
  renderBellTemplateOptions();
  renderClassCheckboxes();
  renderBackgroundGallery().catch(() => {});
  syncProgramSettingsFieldsFromState();
  renderProgramPaletteCheckboxes();
}

function renderClassCheckboxes() {
  const screen = selectedScreen();
  const selected = new Set((screen.selected_classes || []).map(normalizeClass));
  const options = availableClassOptions();
  if (!options.length) {
    elements.screenClassesSummary.textContent = t("screen.classesSummary");
    elements.screenClasses.innerHTML = `<div class="hint">${t("screen.classesEmpty")}</div>`;
    return;
  }
  const selectedLabels = options.filter((item) => selected.has(normalizeClass(item.value))).map((item) => item.label);
  if (!selectedLabels.length) {
    elements.screenClassesSummary.textContent = t("screen.classesSummary");
  } else if (selectedLabels.length <= 2) {
    elements.screenClassesSummary.textContent = selectedLabels.join(", ");
  } else {
    elements.screenClassesSummary.textContent = tf("screen.classesSelected", { n: selectedLabels.length });
  }
  elements.screenClasses.innerHTML = options.map((item) => `
    <label class="toggle-label class-option">
      <input type="checkbox" value="${escapeHtmlAttr(item.value)}" ${selected.has(normalizeClass(item.value)) ? "checked" : ""}>
      <span>${escapeHtml(item.label)}</span>
    </label>
  `).join("");
  elements.screenClasses.querySelectorAll('input[type="checkbox"]').forEach((input) => {
    input.addEventListener("change", () => {
      const values = [...elements.screenClasses.querySelectorAll('input[type="checkbox"]:checked')].map((item) => item.value);
      selectedScreen().selected_classes = values;
      const scheduleWidget = selectedScreen().widgets.find((item) => item.type === "schedule");
      if (scheduleWidget) scheduleWidget.settings.classes = [...values];
      renderPreview();
    });
  });
}

async function fetchBackgroundGallery(folder) {
  const q = folder ? `?folder=${encodeURIComponent(folder)}` : "";
  return api(`/api/admin/background-gallery${q}`);
}

function renderBackgroundGalleryItems(images, activeUrl) {
  if (!elements.screenBgGallery) return;
  const act = String(activeUrl || "");
  const safe = (u) => escapeHtmlAttr(String(u || ""));
  elements.screenBgGallery.innerHTML = (images || []).map((u) => {
    const isActive = act && u === act;
    const name = String(u).split("/").pop() || u;
    return `
      <div class="bg-gallery-item ${isActive ? "active" : ""}" data-bg-url="${safe(u)}" title="${safe(u)}">
        <img src="${safe(u)}" loading="lazy" alt="${safe(name)}">
        <div class="bg-gallery-cap">${escapeHtml(name)}</div>
      </div>
    `;
  }).join("") || `<div class="hint">${t("bg.galleryEmpty")}</div>`;
  elements.screenBgGallery.querySelectorAll("[data-bg-url]").forEach((el) => {
    el.onclick = () => {
      const u = el.dataset.bgUrl;
      const sc = selectedScreen();
      sc.background_force_image = u;
      sc.background_rotate_enabled = false;
      render();
      renderPreview();
    };
  });
}

async function renderBackgroundGallery() {
  const sc = selectedScreen();
  if (!elements.screenBgFolder) return null;
  const folder = String(sc.background_rotate_folder || "");
  // безопасный дефолт, чтобы select не был «пустым» даже при сбое API
  if (!elements.screenBgFolder.options.length) {
    elements.screenBgFolder.innerHTML = `<option value="">${t("bg.loading")}</option>`;
  }
  let payload;
  try {
    payload = await fetchBackgroundGallery(folder);
  } catch (e) {
    elements.screenBgFolder.innerHTML = `<option value="">${t("bg.folderRoot")}</option>`;
    if (elements.screenBgGallery) {
      elements.screenBgGallery.innerHTML = `<div class="hint">${tf("bg.galleryError", { msg: escapeHtmlAttr(String(e.message || e)) })}</div>`;
    }
    return null;
  }
  const folders = payload.folders && payload.folders.length ? payload.folders : [""];
  const images = payload.images || [];
  elements.screenBgFolder.innerHTML = folders.map((f) => {
    const v = String(f || "");
    const lab = v ? v : t("bg.folderRoot");
    return `<option value="${escapeHtmlAttr(v)}">${escapeHtml(lab)}</option>`;
  }).join("");
  elements.screenBgFolder.value = String(payload.folder || "");
  renderBackgroundGalleryItems(images, sc.background_force_image || "");
  return payload;
}

function nextUniqueScreenSlug() {
  const n0 = state.config.screens.length + 1;
  for (let n = n0; n < n0 + 500; n += 1) {
    const slug = `tv-${n}`;
    if (!state.config.screens.some((s) => String(s.slug) === slug)) return slug;
  }
  return `tv-${crypto.randomUUID().slice(0, 6)}`;
}

function duplicateCurrentScreen() {
  const src = selectedScreen();
  if (!src) return;
  const idx = state.config.screens.findIndex((s) => s.id === src.id);
  const defaults = createDefaultScreen(1);
  const idMap = new Map();
  const widgets = (src.widgets || []).map((w) => {
    const nw = JSON.parse(JSON.stringify(w));
    const nid = createWidgetId(w.type === "carousel" ? "carousel" : "widget");
    idMap.set(w.id, nid);
    nw.id = nid;
    return nw;
  });
  widgets.forEach((w) => {
    if (w.type === "carousel" && Array.isArray(w.settings?.childWidgetIds)) {
      w.settings.childWidgetIds = w.settings.childWidgetIds.map((cid) => idMap.get(cid) || cid);
      const cs = w.settings.childSlideSec;
      if (cs && typeof cs === "object") {
        const ncs = {};
        Object.keys(cs).forEach((k) => {
          ncs[idMap.get(k) || k] = cs[k];
        });
        w.settings.childSlideSec = ncs;
      }
    }
  });
  const ns = JSON.parse(JSON.stringify(src));
  ns.id = crypto.randomUUID().slice(0, 8);
  ns.name = tf("screen.defaultName", { n: state.config.screens.length + 1 });
  ns.slug = nextUniqueScreenSlug();
  ns.ip_note = "";
  ns.poll_interval_sec = defaults.poll_interval_sec;
  ns.selected_classes = [...defaults.selected_classes];
  ns.bell_schedule_template = defaults.bell_schedule_template;
  ns.weekday_bell_templates = { ...(src.weekday_bell_templates || {}) };
  ns.widgets = widgets;
  state.config.screens.splice(idx + 1, 0, ns);
  state.selectedScreenId = ns.id;
  render();
}

function renderOverrides() {
  elements.overrideList.innerHTML = "";
  state.overrides.forEach((item, index) => {
    const div = document.createElement("div");
    div.className = "override-item";
    div.innerHTML = `<span class="override-row-text">${tf("override.row", {
      date: escapeHtmlAttr(String(item.date)),
      class: escapeHtmlAttr(String(item.class_name)),
      lesson: escapeHtmlAttr(String(item.lesson_index)),
      subject: escapeHtmlAttr(String(item.subject)),
    })}</span>`;

    const color = document.createElement("input");
    color.type = "color";
    color.className = "override-color";
    color.value = /^#[0-9a-fA-F]{6}$/.test(String(item.color || "")) ? String(item.color) : "#bbf7d0";
    color.oninput = () => {
      item.color = String(color.value || "").trim();
    };
    div.appendChild(color);

    const button = document.createElement("button");
    button.textContent = "×";
    button.className = "compact-btn override-delete-btn";
    button.onclick = () => {
      state.overrides.splice(index, 1);
      renderOverrides();
    };
    div.appendChild(button);
    elements.overrideList.appendChild(div);
  });
}

function render() {
  const tabPanel = document.getElementById("section-tabs-panel");
  const screenWrap = document.getElementById("screen-editor-wrap");
  const audioPanel = document.getElementById("audio-stream-panel");
  const statsPanel = document.getElementById("stats-panel");

  renderTabs();

  if (state.statsPanelActive) {
    leaveStatsPanel();
    clearInterval(window.__streamStatusInterval);
    if (elements.deleteScreenBtn) {
      elements.deleteScreenBtn.hidden = true;
      elements.deleteScreenBtn.disabled = true;
    }
    if (elements.duplicateScreenBtn) elements.duplicateScreenBtn.hidden = true;
    if (tabPanel) tabPanel.style.display = "none";
    if (screenWrap) screenWrap.hidden = true;
    if (audioPanel) audioPanel.hidden = true;
    if (statsPanel) statsPanel.hidden = false;
    enterStatsPanel();
    window.GuardSchoolScreen?.clearAllTimers();
    finishTopBarSessionWidgets();
    return;
  }
  leaveStatsPanel();

  if (state.audioStreamPanelActive) {
    if (elements.deleteScreenBtn) {
      elements.deleteScreenBtn.hidden = true;
      elements.deleteScreenBtn.disabled = true;
    }
    if (elements.duplicateScreenBtn) elements.duplicateScreenBtn.hidden = true;
    if (tabPanel) tabPanel.style.display = "none";
    if (screenWrap) screenWrap.hidden = true;
    if (statsPanel) statsPanel.hidden = true;
    if (audioPanel) audioPanel.hidden = false;
    syncAudioStreamFormFromState();
    refreshBellSoundsForStream();
    refreshPcPlayerFiles();
    clearInterval(window.__streamStatusInterval);
    window.__streamStatusInterval = setInterval(updateStreamStatusBar, 2000);
    updateStreamStatusBar();
    renderBreakMusicPlayback();
    renderPcPlayerFileList();
    window.GuardSchoolScreen?.clearAllTimers();
    finishTopBarSessionWidgets();
    return;
  }

  clearInterval(window.__streamStatusInterval);
  if (tabPanel) tabPanel.style.display = "";
  if (screenWrap) screenWrap.hidden = false;
  if (statsPanel) statsPanel.hidden = true;
  if (audioPanel) audioPanel.hidden = true;

  renderSectionTabs();
  renderSectionVisibility();
  renderForm();
  renderWidgets();
  if (state.widgetModalWidgetId) syncWidgetModal();
  renderPreview();
  renderOverrides();
  renderLessonImportStats();
  if (state.activeSection === "schedule") {
    renderBellEditor();
  }
  renderHistory();
  if (state.activeSection === "preview" && !state.drag) {
    clearTimeout(window.__previewCfgDebounce);
    window.__previewCfgDebounce = setTimeout(() => fetchPreviewPayloadOnce(), 450);
  }

  if (elements.deleteScreenBtn) {
    elements.deleteScreenBtn.hidden = false;
    elements.deleteScreenBtn.disabled = state.config.screens.length <= 1;
  }
  if (elements.duplicateScreenBtn) elements.duplicateScreenBtn.hidden = false;
  finishTopBarSessionWidgets();
}

function bindForm() {
  elements.screenName.oninput = (event) => { selectedScreen().name = event.target.value; renderTabs(); };
  elements.screenSlug.oninput = (event) => { selectedScreen().slug = event.target.value; };
  elements.screenIpNote.oninput = (event) => { selectedScreen().ip_note = event.target.value; };
  elements.screenPollInterval.oninput = (event) => { selectedScreen().poll_interval_sec = Number(event.target.value); };
  if (elements.screenOpenTvBtn) {
    elements.screenOpenTvBtn.onclick = () => {
      const sc = selectedScreen();
      if (!sc) return;
      const slug = String(sc.slug || "").trim();
      if (!slug) {
        alert(t("alert.screenNoSlug"));
        return;
      }
      window.open(new URL(`/screen/${encodeURIComponent(slug)}`, window.location.origin).href, "_blank", "noopener,noreferrer");
    };
  }
  if (elements.screenBgRotate) {
    elements.screenBgRotate.onchange = () => {
      selectedScreen().background_rotate_enabled = Boolean(elements.screenBgRotate.checked);
      renderPreview();
    };
  }
  if (elements.screenBgRotateInterval) {
    elements.screenBgRotateInterval.oninput = (event) => {
      const n = Number(event.target.value);
      selectedScreen().background_rotate_interval_sec = Number.isFinite(n) ? n : 3600;
      renderPreview();
    };
    elements.screenBgRotateInterval.onchange = () => {
      const n = Number(elements.screenBgRotateInterval.value);
      const c = clampBackgroundRotateIntervalSec(Number.isFinite(n) ? n : 3600);
      selectedScreen().background_rotate_interval_sec = c;
      elements.screenBgRotateInterval.value = String(c);
      renderPreview();
    };
  }
  if (elements.screenBgFolder) {
    elements.screenBgFolder.onchange = () => {
      selectedScreen().background_rotate_folder = String(elements.screenBgFolder.value || "");
      selectedScreen().background_force_image = "";
      render();
      renderPreview();
      renderBackgroundGallery().catch(() => {});
    };
  }
  if (elements.screenBgResetBtn) {
    elements.screenBgResetBtn.onclick = () => {
      const sc = selectedScreen();
      sc.background_force_image = "";
      render();
      renderPreview();
      renderBackgroundGallery().catch(() => {});
    };
  }
  if (elements.screenBgNextBtn) {
    elements.screenBgNextBtn.onclick = async () => {
      const sc = selectedScreen();
      try {
        await api("/api/admin/screen-bg-next", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ screen_id: sc.id }),
        });
        const cfg = await api("/api/admin/config");
        state.config = cfg;
        state.selectedScreenId = sc.id;
        render();
        renderPreview();
      } catch (e) {
        alert(e.message || String(e));
      }
    };
  }
  if (elements.screenTextOutline) {
    elements.screenTextOutline.oninput = (event) => {
      const n = Number(event.target.value);
      selectedScreen().tv_text_outline_px = Number.isFinite(n) ? n : 2;
      renderPreview();
    };
  }
  if (elements.screenTextOutlineColor) {
    elements.screenTextOutlineColor.oninput = (event) => {
      selectedScreen().tv_text_outline_color = String(event.target.value || "").trim();
      renderPreview();
    };
  }
  elements.screenBellTemplate.onchange = (event) => {
    selectedScreen().bell_schedule_template = event.target.value;
    renderBellEditor();
    renderPreview();
  };
  if (elements.adminLocaleSelect) {
    elements.adminLocaleSelect.onchange = async () => {
      state.config.ui_locale = elements.adminLocaleSelect.value === "en" ? "en" : "ru";
      try {
        await GuardSchoolI18n.init(state.config.ui_locale);
        GuardSchoolI18n.applyDom(document);
        document.documentElement.lang = state.config.ui_locale === "en" ? "en" : "ru";
        render();
      } catch (_) {}
      renderPreview();
    };
  }
  if (elements.adminTimezone) {
    elements.adminTimezone.onchange = () => {
      state.config.timezone = String(elements.adminTimezone.value || "Europe/Moscow");
      renderPreview();
    };
  }
  if (elements.adminClockOffset) {
    elements.adminClockOffset.oninput = () => {
      const n = Number(elements.adminClockOffset.value);
      state.config.clock_offset_minutes = Number.isFinite(n) ? Math.max(-720, Math.min(720, Math.round(n))) : 0;
      renderPreview();
    };
  }
  if (elements.cloudBaseUrl) {
    elements.cloudBaseUrl.oninput = (e) => {
      state.config.cloud_base_url = String(e.target.value || "").trim();
    };
  }
  if (elements.cloudSyncInterval) {
    elements.cloudSyncInterval.oninput = (e) => {
      const n = Number(e.target.value);
      state.config.cloud_sync_interval_minutes = Number.isFinite(n) ? Math.max(1, Math.min(1440, Math.round(n))) : 5;
    };
  }
  if (elements.cloudSyncEnabled) {
    elements.cloudSyncEnabled.onchange = () => {
      state.config.cloud_sync_enabled = Boolean(elements.cloudSyncEnabled.checked);
    };
  }
  if (elements.cloudSyncToken) {
    elements.cloudSyncToken.oninput = (e) => {
      state.config.cloud_sync_token = String(e.target.value || "");
    };
  }
  if (elements.screenPrimaryBase) {
    elements.screenPrimaryBase.oninput = (e) => {
      state.config.screen_primary_base_url = String(e.target.value || "").trim();
    };
  }
  if (elements.screenFallbackBase) {
    elements.screenFallbackBase.oninput = (e) => {
      state.config.screen_fallback_base_url = String(e.target.value || "").trim();
    };
  }
  if (elements.screenFallbackEnabled) {
    elements.screenFallbackEnabled.onchange = () => {
      state.config.screen_fallback_enabled = Boolean(elements.screenFallbackEnabled.checked);
    };
  }
  if (elements.screenPollTimeout) {
    elements.screenPollTimeout.oninput = (e) => {
      const n = Number(e.target.value);
      state.config.screen_poll_timeout_sec = Number.isFinite(n) ? Math.max(2, Math.min(60, Math.round(n))) : 5;
    };
  }
  if (elements.syncNowBtn) {
    elements.syncNowBtn.onclick = async () => {
      try {
        const r = await api("/api/admin/sync-now", { method: "POST" });
        alert(JSON.stringify(r, null, 2));
        await refreshSyncStatusLine();
      } catch (e) {
        alert(e.message || String(e));
      }
    };
  }
}

function addScreen() {
  const index = state.config.screens.length + 1;
  const screen = createDefaultScreen(index);
  state.config.screens.push(screen);
  state.audioStreamPanelActive = false;
  state.statsPanelActive = false;
  closeWidgetModal();
  state.selectedScreenId = screen.id;
  render();
}

function renderLessonImportStats() {
  const el = elements.lessonImportStats;
  if (!el) return;
  const d = (state.schedule || []).length;
  const f = state.fullScheduleRows ?? 0;
  const s = state.scheduleSampleRows ?? 0;
  el.textContent = tf("lesson.stats", { d, f, s });
}

async function saveAll() {
  readAudioStreamFormIntoState();
  state.config.templateSystem.grid = GRID;
  if (!state.audioStreamPanelActive) saveBellEditorToState();
  await api("/api/admin/config", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(state.config) });
  await api("/api/admin/overrides", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(state.overrides) });
  await api("/api/admin/bells", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(state.bells) });
  const hist = await api("/api/admin/history");
  state.history = hist.history || [];
  state.appVersion = hist.app_version || state.appVersion;
  alert(t("alert.saved"));
}

function deleteScreen() {
  if (state.config.screens.length === 1) {
    alert(t("alert.oneScreen"));
    return;
  }
  closeWidgetModal();
  state.config.screens = state.config.screens.filter((item) => item.id !== state.selectedScreenId);
  state.selectedScreenId = state.config.screens[0].id;
  render();
}

function addOverride() {
  const date = elements.overrideDate.value;
  const className = elements.overrideClass.value.trim();
  const lessonIndex = Number(elements.overrideLesson.value);
  const subject = elements.overrideSubject.value.trim();
  const color = (document.getElementById("override-color")?.value || "").trim();
  if (!date || !className || !lessonIndex || !subject) return alert(t("alert.fillOverride"));
  const o = { date, class_name: className, class_key: className.toLowerCase(), lesson_index: lessonIndex, subject };
  if (/^#[0-9a-fA-F]{6}$/.test(color)) o.color = color;
  state.overrides.push(o);
  renderOverrides();
}

async function init() {
  initUiFontSize();
  const [config, schedule, sounds] = await Promise.all([
    api("/api/admin/config"),
    api("/api/admin/schedule"),
    api("/api/admin/bell-sounds").catch(() => ({ files: [] })),
  ]);
  state.config = config;
  ensureAdminPaletteHidden();
  ensureAudioStreamConfig();
  /* Иначе скрытые поля «Стрим» остаются пустыми до первого открытия вкладки — сохранение с ТВ затирало бы audio_stream */
  syncAudioStreamFormFromState();
  state.schedule = schedule.schedule || [];
  state.fullScheduleRows = schedule.full_schedule_rows ?? 0;
  state.scheduleSampleRows = schedule.schedule_sample_rows ?? 0;
  state.overrides = schedule.overrides || [];
  state.announcements = schedule.announcements || [];
  state.marquee = schedule.marquee || [];
  state.bells = schedule.bells || { templates: [], weekday_overrides: {}, date_overrides: [], sound_defaults: { start: null, end: null } };
  state.bells.sound_defaults = state.bells.sound_defaults || { start: null, end: null };
  state.bellSoundFiles = sounds.files || [];
  state.history = schedule.history || [];
  state.appVersion = schedule.app_version || "";
  state.selectedScreenId = config.screens[0].id;
  restoreAdminUiFromSession();
  try {
    await GuardSchoolI18n.init(state.config.ui_locale || "ru");
    GuardSchoolI18n.applyDom(document);
    document.documentElement.lang = state.config.ui_locale === "en" ? "en" : "ru";
  } catch (_) {}
  bindForm();
  bindAudioStreamFormOnce();
  bindPcPlayerOnce();
  bindSettingsSoundTestsOnce();
  bindWidgetModalOnce();
  bindProgramSettingsModalOnce();
  render();
  setInterval(() => {
    if (window.GuardSchoolScreen && state.activeSection === "preview") {
      window.GuardSchoolScreen.updateAllClocks(elements.preview);
    }
  }, 1000);
  setInterval(() => {
    if (state.activeSection !== "preview" || !elements.preview || !window.GuardSchoolScreen) return;
    const sc = selectedScreen();
    if (!sc || !window.GuardSchoolScreen.applyTvScreenBackground) return;
    const gal = state.previewCache?.background_gallery || [];
    window.GuardSchoolScreen.applyTvScreenBackground(elements.preview, sc, gal);
    if (window.GuardSchoolScreen.applyTvTextOutline) window.GuardSchoolScreen.applyTvTextOutline(elements.preview, sc);
  }, 15000);
}

elements.saveConfigBtn.onclick = saveAll;
elements.exportDataBtn.onclick = async () => {
  await downloadFile("/api/admin/export", "gorniitv_export");
};
elements.importDataBtn.onclick = () => elements.importDataInput.click();
elements.importDataInput.onchange = (event) => event.target.files[0] && importBundle(event.target.files[0]);
elements.deleteScreenBtn.onclick = deleteScreen;
if (elements.duplicateScreenBtn) elements.duplicateScreenBtn.onclick = duplicateCurrentScreen;
elements.addOverrideBtn.onclick = addOverride;
elements.addBellTemplateBtn.onclick = addBellTemplate;
elements.addBellRowBtn.onclick = addBellRow;
elements.deleteBellTemplateBtn.onclick = deleteBellTemplate;
elements.saveBellTemplateBtn.onclick = async () => {
  saveBellEditorToState();
  await api("/api/admin/bells", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(state.bells) });
  const histBell = await api("/api/admin/history");
  state.history = histBell.history || [];
  state.appVersion = histBell.app_version || state.appVersion;
  renderBellEditor();
  alert(t("alert.bellsSaved"));
};
elements.backgroundInput.onchange = (event) => event.target.files[0] && uploadBackground(event.target.files[0]);
elements.pickBackgroundBtn.onclick = () => elements.backgroundInput.click();
if (elements.scheduleInputDated) {
  elements.scheduleInputDated.onchange = (event) => {
    const f = event.target.files?.[0];
    if (f) uploadScheduleDated(f);
    event.target.value = "";
  };
}
if (elements.fullScheduleInput) {
  elements.fullScheduleInput.onchange = (event) => {
    const f = event.target.files?.[0];
    if (f) uploadFullSchedule(f);
    event.target.value = "";
  };
}
if (elements.scheduleSampleInput) {
  elements.scheduleSampleInput.onchange = (event) => {
    const f = event.target.files?.[0];
    if (f) uploadScheduleSample(f);
    event.target.value = "";
  };
}
if (elements.holidaysInput) {
  elements.holidaysInput.onchange = (event) => {
    const f = event.target.files?.[0];
    if (f) uploadHolidays(f);
    event.target.value = "";
  };
}
if (elements.announcementsInput) {
  elements.announcementsInput.onchange = (event) => {
    const f = event.target.files?.[0];
    if (f) uploadAnnouncements(f);
    event.target.value = "";
  };
}
if (elements.marqueeInput) {
  elements.marqueeInput.onchange = (event) => {
    const f = event.target.files?.[0];
    if (f) uploadMarquee(f);
    event.target.value = "";
  };
}
if (elements.weeklyScheduleExportBtn) {
  elements.weeklyScheduleExportBtn.onclick = () =>
    exportWeeklyScheduleZip().catch((e) => alert(e.message || String(e)));
}
if (elements.weeklyScheduleImportBtn && elements.weeklyScheduleImportInput) {
  elements.weeklyScheduleImportBtn.onclick = () => elements.weeklyScheduleImportInput.click();
  elements.weeklyScheduleImportInput.onchange = (event) => {
    const f = event.target.files?.[0];
    if (f) importWeeklyScheduleZip(f).catch((e) => alert(e.message || String(e)));
    event.target.value = "";
  };
}
if (elements.weeklyScheduleTemplateBtn) {
  elements.weeklyScheduleTemplateBtn.onclick = () =>
    downloadWeeklyScheduleTemplateXlsx().catch((e) => alert(e.message || String(e)));
}
elements.logoutBtn.onclick = async () => {
  await api("/api/logout", { method: "POST" });
  window.location.href = "/login";
};

setPreviewDeps({ selectedScreen, clampWidget, render });
setAudioStreamDeps({ selectedScreenSlug });
setDataImportDeps({ selectedScreen, render });
setBellDeps({ selectedScreen, render, getWeekdayOptions, createTemplateId });
setWidgetDeps({
  selectedScreen,
  render,
  renderPreview,
  createWidgetId,
  getCarouselAnimations,
  isWidgetTypeHiddenInAdminPalette,
  closeProgramSettingsModal,
});

window.addEventListener("pointermove", handlePointerMove);
window.addEventListener("pointerup", stopDrag);

init().catch((error) => {
  const msg = String(error.message || "");
  alert(msg);
  if (/вход|Sign in|Session/i.test(msg)) window.location.href = "/login";
});