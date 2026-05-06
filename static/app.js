/* Загружается как модульный dependency до остальных импортов — window.GuardSchoolScreen всегда к моменту init. */
import "./screen_widgets.js?v=1.02.045";
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
import { enterStatsPanel, leaveStatsPanel, refreshFeedbackAdminPanel, bindFeedbackAdminPanelOnce } from "./admin/stats.js";
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
  downloadImportExcelSample,
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
import { MAX_WIDGET_IMAGE_UPLOAD_BYTES } from "./admin/upload-limits.js";

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
  "school_news",
  "rss_news",
  "marquee",
  "emergency",
  "image",
  "checkin_submit",
  "checkin_monitor",
];

/** Как SINGLETON_WIDGET_IDS на сервере — один экземпляр типа с фиксированным id. */
const WIDGET_SINGLETON_IDS = {
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
  ensurePaletteWidgetInstancesOnSelectedScreen();
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
  if (elements.rssRefreshMinutes) {
    const rm = Number(state.config.rss_refresh_minutes);
    elements.rssRefreshMinutes.value = String(Number.isFinite(rm) ? rm : 45);
  }
  renderRssSourcesEditor();
}

function renderRssSourcesEditor() {
  const wrap = elements.rssSourcesList;
  if (!wrap || !state.config) return;
  if (!Array.isArray(state.config.rss_sources)) state.config.rss_sources = [];
  wrap.innerHTML = state.config.rss_sources
    .map((src, index) => {
      const name = escapeHtmlAttr(String(src?.name || ""));
      const rssUrl = escapeHtmlAttr(String(src?.rss_url || ""));
      const enabled = src?.enabled !== false;
      return `<div class="settings-row rss-source-row" data-rss-index="${index}">
        <input type="text" class="standard-input" data-rss-key="name" value="${name}" placeholder="Название">
        <input type="url" class="standard-input wide-input" data-rss-key="rss_url" value="${rssUrl}" placeholder="https://example.com/rss.xml">
        <label class="toggle-label"><input type="checkbox" data-rss-key="enabled" ${enabled ? "checked" : ""}><span>Включено</span></label>
        <button type="button" class="secondary-btn compact-btn" data-rss-remove="${index}">${escapeHtml(t("programSettings.rssRemove"))}</button>
      </div>`;
    })
    .join("");
  wrap.querySelectorAll("[data-rss-remove]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const i = Number(btn.getAttribute("data-rss-remove"));
      if (!Number.isFinite(i)) return;
      state.config.rss_sources.splice(i, 1);
      renderRssSourcesEditor();
    });
  });
  wrap.querySelectorAll(".rss-source-row").forEach((row) => {
    const i = Number(row.getAttribute("data-rss-index"));
    row.querySelectorAll("[data-rss-key]").forEach((input) => {
      input.addEventListener("input", () => {
        const key = input.getAttribute("data-rss-key");
        if (!key) return;
        const src = state.config.rss_sources[i] || { name: "", rss_url: "", enabled: true };
        if (key === "enabled") src.enabled = Boolean(input.checked);
        else src[key] = String(input.value || "").trim();
        state.config.rss_sources[i] = src;
      });
      input.addEventListener("change", () => input.dispatchEvent(new Event("input")));
    });
  });
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

async function refreshAdminFooterStats() {
  const elToday = document.getElementById("admin-footer-line-today");
  const elMonth = document.getElementById("admin-footer-line-month");
  const elTotal = document.getElementById("admin-footer-line-total");
  if (!elToday || !elMonth || !elTotal) return;
  if (state.meta?.demo_session) {
    elToday.innerHTML = "";
    elMonth.textContent = t("admin.footerDemo");
    elTotal.innerHTML = "";
    return;
  }
  try {
    const data = await api("/api/admin/screen-watch");
    const visits = (data && data.visits) || {};
    const map =
      visits.today_unique_by_device && typeof visits.today_unique_by_device === "object"
        ? visits.today_unique_by_device
        : {};
    const todayN = Object.keys(map).reduce((acc, k) => acc + (Number(map[k]) || 0), 0);
    const monthUsers = Number.isFinite(Number(visits.month_unique_users)) ? Number(visits.month_unique_users) : 0;
    const totalConn = Number.isFinite(Number(visits.total_connections)) ? Number(visits.total_connections) : 0;
    elToday.innerHTML = tf("admin.footerToday", { n: String(todayN) });
    elMonth.innerHTML = tf("stats.monthUnique", { n: String(monthUsers) });
    elTotal.innerHTML = tf("stats.totalConnections", { n: String(totalConn) });
  } catch (e) {
    elToday.innerHTML = "";
    elMonth.textContent = tf("admin.footerError", { msg: String(e.message || e) });
    elTotal.innerHTML = "";
  }
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

let _tvLastCode = "";

function renderTvLinks(code) {
  const wrap = elements.tvLinksWrap;
  if (!wrap) return;
  const c = String(code || "").trim();
  if (!state.config || !Array.isArray(state.config.screens)) {
    wrap.innerHTML = "";
    return;
  }
  const items = (state.config.screens || []).filter((s) => s && s.slug && s.is_active !== false);
  if (!c) {
    wrap.innerHTML = '<div class="hint">Ссылки появятся после генерации кода (кнопка «Сгенерировать код»).</div>';
    return;
  }
  const base = window.location.origin.replace(/\/$/, "");
  const links = items
    .map((s) => {
      const sl = String(s.slug || "").trim();
      const name = String(s.name || sl).trim();
      const url = `${base}/t/${encodeURIComponent(c)}/${encodeURIComponent(sl)}`;
      return `<div style="margin: 6px 0"><div style="font-weight:700">${escapeHtml(name)}</div><a href="${escapeHtmlAttr(
        url
      )}" target="_blank" rel="noopener">${escapeHtml(url)}</a></div>`;
    })
    .join("");
  wrap.innerHTML = links || '<div class="hint">Нет активных экранов.</div>';
}

async function refreshTvAccessUi() {
  const head = elements.tvAccessHead;
  const wrap = elements.tvAccessWrap;
  const nonSaas = elements.tvNonSaasInfo;
  const saasControls = elements.tvSaasControls;
  if (!head || !wrap) return;
  const saas = state.meta?.deployment_mode === "saas";
  if (!saas) {
    if (nonSaas) nonSaas.hidden = false;
    if (saasControls) saasControls.hidden = true;
    head.hidden = true;
    wrap.hidden = true;
    return;
  }
  if (nonSaas) nonSaas.hidden = true;
  if (saasControls) saasControls.hidden = false;
  head.hidden = false;
  wrap.hidden = false;
  if (elements.tvCodeOut) elements.tvCodeOut.textContent = "";
  try {
    const st = await api("/api/admin/tv-access");
    const configured = Boolean(st.configured);
    const code = String(st.code || "").trim();
    const tslug = String(st.tenant_slug || "").trim();
    state.tvPinBypassEnv = Boolean(st.pin_bypass_from_env);
    if (code) _tvLastCode = code;
    if (elements.tvPinBypassChk) {
      elements.tvPinBypassChk.setAttribute("data-loading", "1");
      elements.tvPinBypassChk.checked = Boolean(
        st.pin_bypass_from_db || st.pin_bypass_from_config
      );
      elements.tvPinBypassChk.disabled = Boolean(st.pin_bypass_from_env);
      elements.tvPinBypassChk.removeAttribute("data-loading");
    }
    if (elements.tvCodeOut) {
      const head = tslug ? `Школа (тенант): ${tslug}\n\n` : "";
      const envHint = state.tvPinBypassEnv
        ? "\n\nНа сервере задан GUARDSCHOOL_TV_PAIR_BYPASS_PIN — обход PIN включён в окружении; чекбокс ниже заблокирован.\n"
        : "";
      elements.tvCodeOut.textContent =
        head +
        envHint +
        (code
          ? `КОД ШКОЛЫ:\n${code}\n\nСсылки ниже готовы. «Сгенерировать код» отменяет старые ссылки и QR.`
          : configured
            ? "Код школы уже сгенерирован, но не может быть показан. Нажмите «Сгенерировать код», чтобы установить новый код."
            : "Код школы ещё не создан. Нажмите «Сгенерировать код», затем задайте PIN.");
    }
  } catch (e) {
    if (elements.tvCodeOut) elements.tvCodeOut.textContent = `Ошибка: ${e.message || String(e)}`;
  }
  renderTvLinks(_tvLastCode);
}

function getStoredProgramSettingsTab() {
  try {
    const t = sessionStorage.getItem(GS_ADMIN_PROGRAM_SETTINGS_TAB);
    if (
      t === "general" ||
      t === "school_news" ||
      t === "tv" ||
      t === "feedback" ||
      t === "changelog" ||
      t === "emergency"
    )
      return t;
  } catch (_) {}
  return "general";
}

async function refreshProgramHistoryFromApi() {
  try {
    const hist = await api("/api/admin/history");
    state.history = hist.history || [];
    state.appVersion = hist.app_version || state.appVersion;
  } catch (_) {}
  renderHistory();
}

function setProgramSettingsTab(tab) {
  const panel = elements.programSettingsPanel;
  if (!panel) return;
  try {
    sessionStorage.setItem(GS_ADMIN_PROGRAM_SETTINGS_TAB, tab);
  } catch (_) {}
  panel.querySelectorAll("[data-ps-pane]").forEach((pane) => {
    pane.hidden = pane.getAttribute("data-ps-pane") !== tab;
  });
  if (tab === "changelog") refreshProgramHistoryFromApi();
  if (tab === "emergency") renderEmergencyTemplatesAdmin();
  if (tab === "feedback") {
    bindFeedbackAdminPanelOnce();
    refreshFeedbackAdminPanel();
  }
  if (tab === "school_news") renderSchoolNewsList();
  if (tab === "tv") refreshTvAccessUi().catch(() => {});
}

function closeAdminSettingsSubmenu() {
  /* Подразделы настроек всегда видны в сайдбаре — закрывать нечего. */
}

/** Синхронизация DOM панели настроек (после restore сессии или при открытии). */
function hydrateProgramSettingsPanelIfOpen() {
  if (!state.programSettingsPanelActive || !elements.programSettingsPanel) return;
  setProgramSettingsTab(getStoredProgramSettingsTab());
  syncProgramSettingsFieldsFromState();
  renderProgramPaletteCheckboxes();
  refreshSyncStatusLine().catch(() => {});
  refreshTvAccessUi().catch(() => {});
  try {
    GuardSchoolI18n.applyDom(elements.programSettingsPanel);
  } catch (_) {}
}

/** @param {string} [initialTab] — вкладка панели настроек: general | tv | emergency | feedback | changelog */
function openProgramSettingsModal(initialTab) {
  if (!elements.programSettingsPanel) return;
  closeWidgetModal();
  closeAdminSettingsSubmenu();
  state.programSettingsPanelActive = true;
  state.audioStreamPanelActive = false;
  state.statsPanelActive = false;
  leaveStatsPanel();
  if (initialTab && typeof initialTab === "string") {
    try {
      sessionStorage.setItem(GS_ADMIN_PROGRAM_SETTINGS_TAB, initialTab);
    } catch (_) {}
  }
  hydrateProgramSettingsPanelIfOpen();
  render();
}

function closeProgramSettingsModal() {
  state.programSettingsPanelActive = false;
  closeAdminSettingsSubmenu();
  render();
}

function bindProgramSettingsModalOnce() {
  if (bindProgramSettingsModalOnce._done) return;
  bindProgramSettingsModalOnce._done = true;
  elements.programSettingsOpenBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    openProgramSettingsModal("general");
  });
  document.getElementById("admin-settings-submenu")?.addEventListener("click", (e) => {
    const btn = e.target && e.target.closest ? e.target.closest("[data-admin-submenu]") : null;
    if (!btn) return;
    e.preventDefault();
    const kind = btn.getAttribute("data-admin-submenu");
    closeAdminSettingsSubmenu();
    if (kind === "program") {
      const tab = btn.getAttribute("data-ps-tab") || "general";
      openProgramSettingsModal(tab);
      return;
    }
    if (kind === "audio") {
      closeWidgetModal();
      state.programSettingsPanelActive = false;
      state.statsPanelActive = false;
      state.audioStreamPanelActive = true;
      render();
      return;
    }
    if (kind === "stats") {
      if (state.meta?.demo_session) return;
      closeWidgetModal();
      state.programSettingsPanelActive = false;
      state.audioStreamPanelActive = false;
      state.statsPanelActive = true;
      render();
    }
  });
  elements.tvRotateCodeBtn?.addEventListener("click", async () => {
    try {
      const r = await api("/api/admin/tv-access/rotate-code", { method: "POST" });
      const code = String(r.code || "").trim();
      const ip = String(r.initial_pin || "").trim();
      _tvLastCode = code;
      if (elements.tvCodeOut) {
        const pinLine = ip ? `\n\nPIN ТВ (показан один раз):\n${ip}\n` : "";
        const hint = r.pin_hint ? `\n${String(r.pin_hint)}` : "";
        const ts = String(r.tenant_slug || "").trim();
        const head = ts ? `Школа (тенант): ${ts}\n\n` : "";
        elements.tvCodeOut.textContent =
          `${head}КОД ШКОЛЫ:\n${code}\n\nСохраните код и обновите QR/ссылки. Старый код перестаёт работать.${pinLine}${hint}`;
      }
      renderTvLinks(code);
    } catch (e) {
      alert(e.message || String(e));
    }
  });

  elements.tvSetPinBtn?.addEventListener("click", async () => {
    const pin = String(elements.tvPinInput?.value || "").trim();
    if (!/^[0-9]{4,12}$/.test(pin)) {
      alert("PIN должен быть 4–12 цифр.");
      return;
    }
    try {
      await api("/api/admin/tv-access/set-pin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin }),
      });
      alert("PIN сохранён.");
    } catch (e) {
      alert(e.message || String(e));
    }
  });

  elements.tvPinBypassChk?.addEventListener("change", async () => {
    const el = elements.tvPinBypassChk;
    if (!el || el.getAttribute("data-loading")) return;
    if (state.tvPinBypassEnv) {
      el.checked = !el.checked;
      alert("Отключите GUARDSCHOOL_TV_PAIR_BYPASS_PIN на сервере — сейчас обход задаётся только переменной окружения.");
      return;
    }
    const want = Boolean(el.checked);
    try {
      await api("/api/admin/tv-access/pin-bypass", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: want }),
      });
    } catch (e) {
      el.checked = !want;
      alert(e.message || String(e));
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
    mobile_mode: false,
    enable_feedback: false,
    /** Устарело: порядок ленты = порядок виджетов на экране; поле сохраняется для совместимости. */
    mobile_widget_ids: [],
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
        id: "school_news",
        type: "school_news",
        title: "Новости школы",
        enabled: false,
        x: 0, y: 13, w: 16, h: 11,
        settings: {
          fontSize: 18,
          titleFontSize: 22,
          color: "#ffffff",
          background: "rgba(15,23,42,0.55)",
          rotateSec: 12,
          bold: false,
        },
      },
      {
        id: "rss_news",
        type: "rss_news",
        title: "RSS-лента",
        enabled: false,
        x: 24, y: 14, w: 8, h: 10,
        settings: {
          fontSize: 16,
          titleFontSize: 18,
          color: "#ffffff",
          background: "rgba(15,23,42,0.55)",
          rotateSec: 12,
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

function widgetStubFromDefaultTemplate(typ) {
  const t = String(typ || "");
  const tmpl = createDefaultScreen(1);
  const found = tmpl.widgets.find((w) => w && w.type === t);
  return found ? JSON.parse(JSON.stringify(found)) : null;
}

function screenHasSingletonId(sc, singletonId) {
  return (sc.widgets || []).some((w) => w && String(w.id) === String(singletonId));
}

/** Для каждого типа из палитры программы создаёт экземпляр на текущем экране, если его ещё нет (в т.ч. новые типы после обновления). */
function ensurePaletteWidgetInstancesOnSelectedScreen() {
  const sc = selectedScreen();
  if (!sc || !state.config) return;
  if (!Array.isArray(sc.widgets)) sc.widgets = [];
  for (const typ of PALETTE_TYPES_ORDER) {
    if (!WIDGET_TYPE_KEYS.has(typ)) continue;
    if (isWidgetTypeHiddenInAdminPalette(typ)) continue;
    const has = (sc.widgets || []).some((w) => w && String(w.type) === typ);
    if (has) continue;
    const w = createWidgetStubForPaletteType(typ);
    if (!w) continue;
    clampWidget(w);
    sc.widgets.push(w);
  }
}

function createWidgetStubForPaletteType(typ) {
  const sc = selectedScreen();
  if (!sc || !typ) return null;
  const typeKey = String(typ);
  if (WIDGET_SINGLETON_IDS[typeKey]) {
    const expectId = WIDGET_SINGLETON_IDS[typeKey];
    if (screenHasSingletonId(sc, expectId)) {
      return null;
    }
    const w = widgetStubFromDefaultTemplate(typeKey);
    if (w) {
      w.id = expectId;
      w.type = typeKey;
      w.enabled = true;
      return w;
    }
    if (typeKey === "bell_countdown") {
      return {
        id: "bell_countdown",
        type: "bell_countdown",
        title: t("widget.type.bell_countdown"),
        enabled: true,
        x: 24,
        y: 13,
        w: 8,
        h: 3,
        settings: {
          fontSize: 18,
          titleFontSize: 18,
          color: "#ffffff",
          background: "rgba(15,23,42,0.55)",
          bold: false,
          backdrop: true,
        },
      };
    }
    return null;
  }
  if (typeKey === "carousel") {
    const n = (sc.widgets || []).filter((x) => x && x.type === "carousel").length + 1;
    return {
      id: createWidgetId("carousel"),
      type: "carousel",
      title: tf("carousel.nameN", { n }),
      enabled: true,
      x: 0,
      y: 2,
      w: 24,
      h: 11,
      settings: {
        startDelaySec: 0,
        animation: "slide",
        childWidgetIds: [],
        childSlideSec: {},
        backdrop: true,
      },
    };
  }
  if (typeKey === "checkin_submit") {
    return {
      id: createWidgetId("widget"),
      type: "checkin_submit",
      title: t("widget.type.checkin_submit"),
      enabled: true,
      x: 0,
      y: 18,
      w: 12,
      h: 8,
      settings: {
        places: [],
        monitor_widget_id: "",
        labels: {},
        backdrop: true,
        fontSize: 0,
        bold: false,
      },
    };
  }
  if (typeKey === "checkin_monitor") {
    return {
      id: createWidgetId("widget"),
      type: "checkin_monitor",
      title: t("widget.type.checkin_monitor"),
      enabled: true,
      x: 12,
      y: 18,
      w: 14,
      h: 8,
      settings: {
        places: [{ id: "place_a", title: "Место A" }],
        panel_title: "Сводка мест",
        events_screen_slug: "",
        labels: {},
        backdrop: true,
        fontSize: 0,
        bold: false,
      },
    };
  }
  return null;
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
  const apiNames = state.scheduleClassOptions;
  const fromDatedOnly = [...new Set((state.schedule || []).map((item) => item.class_name).filter(Boolean))];
  const rawNames =
    Array.isArray(apiNames) && apiNames.length > 0 ? [...apiNames] : fromDatedOnly;
  const classNames = [...new Set(rawNames)].sort(compareClassNames);
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
const GS_ADMIN_PROGRAM_SETTINGS_TAB = "gs_admin_program_settings_tab";

function restoreAdminUiFromSession() {
  if (!state.config?.screens?.length) return;
  try {
    if (state.meta?.demo_session) {
      state.statsPanelActive = false;
      if (sessionStorage.getItem(GS_ADMIN_SESSION_TOP) === "stats") {
        sessionStorage.setItem(GS_ADMIN_SESSION_TOP, "screen");
      }
    }
    const sec = sessionStorage.getItem(GS_ADMIN_SESSION_SECTION);
    if (sec === "history") state.activeSection = "screen";
    else if (sec && ["screen", "widgets", "lessons", "bells", "preview"].includes(sec)) state.activeSection = sec;
    else if (sec === "main") state.activeSection = "screen";
    else if (sec === "schedule") state.activeSection = "lessons";
    const top = sessionStorage.getItem(GS_ADMIN_SESSION_TOP);
    const sid = sessionStorage.getItem(GS_ADMIN_SESSION_SCREEN);
    if (top === "audio") {
      state.audioStreamPanelActive = true;
      state.statsPanelActive = false;
      state.programSettingsPanelActive = false;
    } else if (top === "stats" && !state.meta?.demo_session) {
      state.statsPanelActive = true;
      state.audioStreamPanelActive = false;
      state.programSettingsPanelActive = false;
    } else if (top === "program") {
      state.audioStreamPanelActive = false;
      state.statsPanelActive = false;
      state.programSettingsPanelActive = true;
      if (sid && state.config.screens.some((s) => s.id === sid)) {
        state.selectedScreenId = sid;
      }
    } else {
      state.audioStreamPanelActive = false;
      state.statsPanelActive = false;
      state.programSettingsPanelActive = false;
      if (sid && state.config.screens.some((s) => s.id === sid)) {
        state.selectedScreenId = sid;
      }
    }
  } catch (_) {}
}

function finishTopBarSessionWidgets() {
  syncEmergencyModeCheckbox();
  bindEmergencyModeToggleOnce();
  renderEmergencyTemplateBar();
  persistAdminUiToSession();
}

function persistAdminUiToSession() {
  try {
    let top = "screen";
    if (state.audioStreamPanelActive) top = "audio";
    else if (state.programSettingsPanelActive) top = "program";
    else if (state.statsPanelActive) top = "stats";
    sessionStorage.setItem(GS_ADMIN_SESSION_TOP, top);
    sessionStorage.setItem(GS_ADMIN_SESSION_SCREEN, state.selectedScreenId || "");
    sessionStorage.setItem(GS_ADMIN_SESSION_SECTION, state.activeSection || "screen");
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
      imageUrl: "",
      imageCaption: "",
    },
  };
}

/** Совпадает с _default_emergency_templates() на сервере (для «вернуть стандарт» в UI). */
const CLIENT_EMERGENCY_DEFAULTS = [
  {
    id: "preset_fire",
    title: "Пожар",
    settings: {
      text: "ПОЖАР!\nЭвакуация по сигналу. Следуйте указаниям персонала.",
      fontSize: 44,
      color: "#ffffff",
      background: "#b91c1c",
      bold: true,
      backdrop: true,
      soundEnabled: true,
      soundUrl: "",
      timer_seconds: 0,
      byScreenName: {},
    },
  },
  {
    id: "preset_terror",
    title: "Антитеррор",
    settings: {
      text: "ВНИМАНИЕ!\nРежим повышенной готовности.\nСохраняйте спокойствие, действуйте по указаниям.",
      fontSize: 40,
      color: "#f8fafc",
      background: "#1e3a8a",
      bold: true,
      backdrop: true,
      soundEnabled: false,
      soundUrl: "",
      timer_seconds: 0,
      byScreenName: {},
    },
  },
  {
    id: "preset_bomb",
    title: "Заминирование",
    settings: {
      text: "СООБЩЕНИЕ ОБ УГРОЗЕ\nОставайтесь на местах. Ожидайте указаний администрации.\nНе паникуйте.",
      fontSize: 38,
      color: "#fef3c7",
      background: "#78350f",
      bold: true,
      backdrop: true,
      soundEnabled: false,
      soundUrl: "",
      timer_seconds: 0,
      byScreenName: {},
    },
  },
  {
    id: "preset_crisis",
    title: "Чрезвычайная ситуация",
    settings: {
      text: "ЧРЕЗВЫЧАЙНАЯ СИТУАЦИЯ\nСледуйте плану действий персонала школы.",
      fontSize: 40,
      color: "#ffffff",
      background: "#7f1d1d",
      bold: true,
      backdrop: true,
      soundEnabled: true,
      soundUrl: "",
      timer_seconds: 0,
      byScreenName: {},
    },
  },
];

function ensureEmergencyConfig() {
  if (!state.config) return;
  if (!Array.isArray(state.config.emergency_templates)) {
    state.config.emergency_templates = JSON.parse(JSON.stringify(CLIENT_EMERGENCY_DEFAULTS));
  }
  if (typeof state.config.emergency_active_template_id !== "string") {
    state.config.emergency_active_template_id = "";
  }
}

async function persistConfigQuick() {
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
  fetchPreviewPayloadOnce().catch(() => {});
}

function renderEmergencyTemplateBar() {
  const wrap = document.getElementById("emergency-template-bar");
  if (!wrap || !state.config) return;
  const list = state.config.emergency_templates || [];
  const cur = String(state.config.emergency_active_template_id || "").trim();
  wrap.innerHTML = "";
  // Важно: можно "снять" глобальный шаблон, вернувшись к индивидуальным настройкам emergency-виджета на экранах.
  const clearBtn = document.createElement("button");
  clearBtn.type = "button";
  clearBtn.className = `emergency-template-btn${!cur ? " active" : ""}`;
  clearBtn.textContent = t("emergencyTemplates.defaultBtn");
  clearBtn.title = t("emergencyTemplates.defaultHint");
  clearBtn.onclick = async () => {
    state.config.emergency_active_template_id = "";
    await persistConfigQuick();
  };
  wrap.appendChild(clearBtn);
  list.forEach((tpl) => {
    const id = String(tpl.id || "").trim();
    if (!id) return;
    const b = document.createElement("button");
    b.type = "button";
    b.className = `emergency-template-btn${id === cur ? " active" : ""}`;
    b.textContent = String(tpl.title || id);
    b.title = String(tpl.title || id);
    b.onclick = async () => {
      // Повторный клик по активному — снимает шаблон.
      state.config.emergency_active_template_id = id === cur ? "" : id;
      await persistConfigQuick();
    };
    wrap.appendChild(b);
  });
}

function tplByScreen(tpl) {
  if (!tpl.settings) tpl.settings = {};
  if (!tpl.settings.byScreenName || typeof tpl.settings.byScreenName !== "object") {
    tpl.settings.byScreenName = {};
  }
  return tpl.settings.byScreenName;
}

function renderEmergencyTemplatesAdmin() {
  const root = document.getElementById("emergency-templates-admin-root");
  if (!root || !state.config) return;
  const list = state.config.emergency_templates || [];
  if (!list.length) {
    root.innerHTML = `<p class="hint">${escapeHtml(t("emergencyTemplates.emptyHint"))}</p>
      <button type="button" class="secondary-btn compact-btn" id="emergency-restore-empty">${escapeHtml(t("emergencyTemplates.restore"))}</button>`;
    const rb = document.getElementById("emergency-restore-empty");
    if (rb) rb.onclick = () => restoreEmergencyTemplatesDefaults();
    return;
  }
  if (!state.emergencyTemplateEditorId || !list.some((x) => x.id === state.emergencyTemplateEditorId)) {
    state.emergencyTemplateEditorId = list[0].id;
  }
  const sel = state.emergencyTemplateEditorId;
  const tpl = list.find((x) => x.id === sel);
  if (!tpl) return;
  const s = tpl.settings || (tpl.settings = {});
  const opts = list
    .map((x) => `<option value="${escapeHtmlAttr(x.id)}" ${x.id === sel ? "selected" : ""}>${escapeHtml(x.title || x.id)}</option>`)
    .join("");
  const screens = state.config.screens || [];
  const by = tplByScreen(tpl);
  const rows = screens
    .map((sc) => {
      const nm = String(sc.name || sc.slug || "").trim() || "—";
      const row = by[nm] || { imageUrl: "", caption: "" };
      const iu = escapeHtmlAttr(String(row.imageUrl || ""));
      const cap = escapeHtmlAttr(String(row.caption || ""));
      return `<div class="emergency-screen-row" style="margin:10px 0;padding:10px;border:1px solid rgba(148,163,184,.25);border-radius:8px">
        <div style="font-weight:600;margin-bottom:6px">${escapeHtml(nm)}</div>
        <label class="settings-row"><span>${escapeHtml(t("emergencyTemplates.screenImage"))}</span>
          <input type="text" class="standard-input wide-input" data-em-screen="${escapeHtmlAttr(nm)}" data-em-part="imageUrl" value="${iu}" placeholder="/uploads/…"></label>
        <label class="settings-row"><span>${escapeHtml(t("emergencyTemplates.screenCaption"))}</span>
          <input type="text" class="standard-input wide-input" data-em-screen="${escapeHtmlAttr(nm)}" data-em-part="caption" value="${cap}"></label>
        <div class="compact-form-row"><label class="bell-file-upload"><span class="bell-file-upload-main">${escapeHtml(t("w.browse"))}</span>
          <input type="file" accept="image/*" data-em-screen-upload="${escapeHtmlAttr(nm)}" hidden></label></div>
      </div>`;
    })
    .join("");
  const soundRo = state.meta?.saas_mode ? "readonly" : "";
  root.innerHTML = `
    <div class="emergency-editor-shell">
      <div class="emergency-editor-toolbar">
        <label class="settings-row emergency-editor-picker"><span>${escapeHtml(t("emergencyTemplates.pick"))}</span>
          <select id="emergency-admin-pick" class="standard-input emergency-admin-pick-select">${opts}</select></label>
        <div class="settings-row settings-btn-row emergency-editor-actions">
          <button type="button" class="secondary-btn compact-btn" id="emergency-add-tpl">${escapeHtml(t("emergencyTemplates.add"))}</button>
          <button type="button" class="secondary-btn compact-btn" id="emergency-del-tpl">${escapeHtml(t("emergencyTemplates.delete"))}</button>
          <button type="button" class="secondary-btn compact-btn" id="emergency-restore-tpl">${escapeHtml(t("emergencyTemplates.restore"))}</button>
        </div>
      </div>
      <label class="settings-row"><span>${escapeHtml(t("emergencyTemplates.templateTitle"))}</span>
        <input type="text" id="emergency-f-title" class="standard-input wide-input" value="${escapeHtmlAttr(String(tpl.title || ""))}"></label>
      <label class="settings-row"><span>${escapeHtml(t("w.textLines"))}</span>
        <textarea id="emergency-f-text" class="wide-input" rows="5">${escapeHtml(String(s.text || ""))}</textarea></label>
      <div class="settings-row emergency-editor-grid">
        <label><span>${escapeHtml(t("w.fontSize"))}</span><input type="number" id="emergency-f-fs" class="standard-input" min="10" max="200" value="${Number(s.fontSize) || 42}"></label>
        <label><span>${escapeHtml(t("w.color"))}</span><input type="color" id="emergency-f-color" value="${escapeHtmlAttr(/^#[0-9a-fA-F]{6}$/.test(String(s.color || "").trim()) ? String(s.color).trim() : "#ffffff")}"></label>
        <label><span>${escapeHtml(t("w.blockBg"))}</span><input type="text" id="emergency-f-bg" class="standard-input" value="${escapeHtmlAttr(String(s.background || "#b91c1c"))}"></label>
        <label><span>${escapeHtml(t("emergencyTemplates.timerSeconds"))}</span><input type="number" id="emergency-f-timer" class="standard-input" min="0" max="86400" step="1" value="${Math.max(0, Math.round(Number(s.timer_seconds) || 0))}" placeholder="${escapeHtmlAttr(t("emergencyTemplates.timerHint"))}"></label>
        <label class="toggle-label"><input type="checkbox" id="emergency-f-bold" ${s.bold !== false ? "checked" : ""}> ${escapeHtml(t("w.bold"))}</label>
        <label class="toggle-label"><input type="checkbox" id="emergency-f-backdrop" ${s.backdrop !== false ? "checked" : ""}> ${escapeHtml(t("w.backdrop"))}</label>
        <label class="toggle-label"><input type="checkbox" id="emergency-f-sound" ${s.soundEnabled === true ? "checked" : ""}> ${escapeHtml(t("emergencyTemplates.globalSound"))}</label>
      </div>
      <p class="hint">${escapeHtml(t("emergencyTemplates.timerHintValues"))}</p>
      <label class="settings-row"><span>${escapeHtml(t("w.emergencySoundFile"))}</span>
        <input type="text" id="emergency-f-surl" class="standard-input wide-input" value="${escapeHtmlAttr(String(s.soundUrl || ""))}" ${soundRo}></label>
      <div class="compact-form-row">${state.meta?.saas_mode ? "" : `<label class="bell-file-upload"><span class="bell-file-upload-main">${escapeHtml(t("w.browse"))}</span>
        <input type="file" accept="audio/*" id="emergency-f-sound-file" hidden></label>`}</div>
      <h4 class="settings-popover-subhead emergency-editor-subhead">${escapeHtml(t("emergencyTemplates.perScreenBlock"))}</h4>
      ${rows || `<p class="hint">${escapeHtml(t("emergencyTemplates.noScreens"))}</p>`}
      <div class="settings-row settings-btn-row emergency-editor-save-wrap">
        <button type="button" class="primary-btn compact-btn" id="emergency-save-editor">${escapeHtml(t("emergencyTemplates.saveTemplate"))}</button>
      </div>
    </div>`;

  document.getElementById("emergency-admin-pick").onchange = (e) => {
    flushEmergencyEditorToState();
    state.emergencyTemplateEditorId = String(e.target.value || "");
    renderEmergencyTemplatesAdmin();
  };
  document.getElementById("emergency-add-tpl").onclick = () => {
    flushEmergencyEditorToState();
    const nid = `tpl_${Math.random().toString(16).slice(2, 10)}`;
    list.push({
      id: nid,
      title: t("emergencyTemplates.newTitle"),
      settings: {
        text: t("emergencyTemplates.newText"),
        fontSize: 40,
        color: "#ffffff",
        background: "#991b1b",
        bold: true,
        backdrop: true,
        soundEnabled: false,
        soundUrl: "",
        timer_seconds: 0,
        byScreenName: {},
      },
    });
    state.emergencyTemplateEditorId = nid;
    renderEmergencyTemplatesAdmin();
  };
  document.getElementById("emergency-del-tpl").onclick = () => {
    if (!confirm(t("emergencyTemplates.confirmDelete"))) return;
    flushEmergencyEditorToState();
    const i = list.findIndex((x) => x.id === sel);
    if (i >= 0) list.splice(i, 1);
    if (state.config.emergency_active_template_id === sel) state.config.emergency_active_template_id = "";
    state.emergencyTemplateEditorId = list[0]?.id || null;
    renderEmergencyTemplatesAdmin();
    renderEmergencyTemplateBar();
  };
  document.getElementById("emergency-restore-tpl").onclick = () => restoreEmergencyTemplatesDefaults();
  document.getElementById("emergency-save-editor").onclick = async () => {
    flushEmergencyEditorToState();
    await persistConfigQuick();
  };
  root.querySelectorAll("[data-em-screen]").forEach((inp) => {
    inp.addEventListener("change", () => {
      const nm = inp.getAttribute("data-em-screen");
      const part = inp.getAttribute("data-em-part");
      if (!nm || !part) return;
      const b = tplByScreen(tpl);
      if (!b[nm]) b[nm] = { imageUrl: "", caption: "" };
      b[nm][part] = String(inp.value || "").trim();
    });
  });
  root.querySelectorAll("[data-em-screen-upload]").forEach((inp) => {
    inp.addEventListener("change", async (ev) => {
      const nm = inp.getAttribute("data-em-screen-upload");
      const f = ev.target.files && ev.target.files[0];
      if (!nm || !f || state.meta?.saas_mode) return;
      if (f.size > MAX_WIDGET_IMAGE_UPLOAD_BYTES) {
        alert(t("w.widgetImageTooLarge"));
        ev.target.value = "";
        return;
      }
      const formData = new FormData();
      formData.append("file", f);
      try {
        const payload = await api("/api/admin/upload-widget-image", { method: "POST", body: formData });
        const b = tplByScreen(tpl);
        if (!b[nm]) b[nm] = { imageUrl: "", caption: "" };
        b[nm].imageUrl = payload.path || "";
        ev.target.value = "";
        renderEmergencyTemplatesAdmin();
      } catch (err) {
        alert(String(err.message || err));
      }
    });
  });
  const sf = document.getElementById("emergency-f-sound-file");
  if (sf) {
    sf.addEventListener("change", async (ev) => {
      const f = ev.target.files && ev.target.files[0];
      if (!f) return;
      const formData = new FormData();
      formData.append("file", f);
      try {
        const payload = await api("/api/admin/upload-emergency-sound", { method: "POST", body: formData });
        s.soundUrl = payload.url || "";
        ev.target.value = "";
        renderEmergencyTemplatesAdmin();
      } catch (err) {
        alert(String(err.message || err));
      }
    });
  }
}

function flushEmergencyEditorToState() {
  const list = state.config?.emergency_templates;
  if (!Array.isArray(list)) return;
  const sel = state.emergencyTemplateEditorId;
  const tpl = list.find((x) => x.id === sel);
  if (!tpl) return;
  const titleEl = document.getElementById("emergency-f-title");
  const textEl = document.getElementById("emergency-f-text");
  if (titleEl) tpl.title = String(titleEl.value || "").trim() || tpl.id;
  if (textEl) {
    if (!tpl.settings) tpl.settings = {};
    tpl.settings.text = String(textEl.value || "");
  }
  const fs = document.getElementById("emergency-f-fs");
  const col = document.getElementById("emergency-f-color");
  const bg = document.getElementById("emergency-f-bg");
  const bd = document.getElementById("emergency-f-bold");
  const bk = document.getElementById("emergency-f-backdrop");
  const snd = document.getElementById("emergency-f-sound");
  const surl = document.getElementById("emergency-f-surl");
  const timer = document.getElementById("emergency-f-timer");
  if (!tpl.settings) tpl.settings = {};
  if (fs) {
    const n = Number(fs.value);
    tpl.settings.fontSize = Number.isFinite(n) ? Math.max(10, Math.min(200, Math.round(n))) : 42;
  }
  if (col) {
    const cv = String(col.value || "#ffffff").trim();
    tpl.settings.color = /^#[0-9a-fA-F]{6}$/.test(cv) ? cv : "#ffffff";
  }
  if (bg) tpl.settings.background = String(bg.value || "").trim();
  if (bd) tpl.settings.bold = Boolean(bd.checked);
  if (bk) tpl.settings.backdrop = Boolean(bk.checked);
  if (snd) tpl.settings.soundEnabled = Boolean(snd.checked);
  if (surl) tpl.settings.soundUrl = String(surl.value || "").trim();
  if (timer) {
    const n = Number(timer.value);
    tpl.settings.timer_seconds = Number.isFinite(n) ? Math.max(0, Math.min(86400, Math.round(n))) : 0;
  }
  const root = document.getElementById("emergency-templates-admin-root");
  if (root) {
    root.querySelectorAll("[data-em-screen]").forEach((inp) => {
      const nm = inp.getAttribute("data-em-screen");
      const part = inp.getAttribute("data-em-part");
      if (!nm || !part) return;
      const b = tplByScreen(tpl);
      if (!b[nm]) b[nm] = { imageUrl: "", caption: "" };
      b[nm][part] = String(inp.value || "").trim();
    });
  }
}

function restoreEmergencyTemplatesDefaults() {
  if (!confirm(t("emergencyTemplates.confirmRestore"))) return;
  state.config.emergency_templates = JSON.parse(JSON.stringify(CLIENT_EMERGENCY_DEFAULTS));
  state.config.emergency_active_template_id = "";
  state.emergencyTemplateEditorId = CLIENT_EMERGENCY_DEFAULTS[0].id;
  renderEmergencyTemplatesAdmin();
  renderEmergencyTemplateBar();
  persistConfigQuick().catch(() => {});
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
    await persistConfigQuick();
  });
}

function renderTabs() {
  if (!elements.tabs || !state.config?.screens) return;
  elements.tabs.innerHTML = "";

  state.config.screens.forEach((screen) => {
    const row = document.createElement("div");
    row.className = "admin-sidebar-screen-row";

    const nameBtn = document.createElement("button");
    nameBtn.type = "button";
    nameBtn.className = `admin-sidebar-screen-btn${!state.audioStreamPanelActive && !state.statsPanelActive && !state.programSettingsPanelActive && screen.id === state.selectedScreenId ? " active" : ""}`;
    nameBtn.textContent = screen.name || "";
    nameBtn.onclick = () => {
      state.audioStreamPanelActive = false;
      state.statsPanelActive = false;
      state.programSettingsPanelActive = false;
      closeWidgetModal();
      closeAdminSettingsSubmenu();
      state.selectedScreenId = screen.id;
      render();
    };

    const slug = String(screen.slug || "").trim();
    const openA = document.createElement("a");
    openA.className = "admin-sidebar-screen-open";
    openA.textContent = "\u2192";
    openA.target = "_blank";
    openA.rel = "noopener noreferrer";
    openA.title = t("admin.openScreenNewTab");
    if (slug) {
      openA.href = new URL(`/screen/${encodeURIComponent(slug)}`, window.location.origin).href;
    } else {
      openA.href = "#";
      openA.setAttribute("aria-disabled", "true");
      openA.addEventListener("click", (ev) => {
        ev.preventDefault();
      });
    }

    row.appendChild(nameBtn);
    row.appendChild(openA);
    elements.tabs.appendChild(row);
  });

  const plus = document.createElement("button");
  plus.type = "button";
  plus.className = "top-nav-btn admin-sidebar-add-btn";
  plus.textContent = t("tabs.addScreen");
  plus.onclick = addScreen;
  elements.tabs.appendChild(plus);

  const wrapSettings = document.getElementById("admin-sidebar-settings");
  const panelish = Boolean(
    state.programSettingsPanelActive || state.audioStreamPanelActive || state.statsPanelActive,
  );
  if (wrapSettings) {
    wrapSettings.classList.toggle("admin-sidebar-settings--active", panelish);
  }
  if (elements.programSettingsOpenBtn) {
    elements.programSettingsOpenBtn.classList.toggle("active", panelish);
  }

  const statsItem = document.querySelector("#admin-settings-submenu [data-admin-submenu=\"stats\"]");
  if (statsItem) statsItem.hidden = Boolean(state.meta?.demo_session);
}

function renderSectionTabs() {
  elements.sectionTabs.innerHTML = "";
  getSectionTabs().forEach((section) => {
    const button = document.createElement("button");
    button.className = `section-tab-btn ${state.activeSection === section.id ? "active" : ""}`;
    button.textContent = section.label;
    button.onclick = () => {
      state.activeSection = section.id;
      if (section.id !== "widgets") closeWidgetModal();
      renderSectionVisibility();
      renderSectionTabs();
      if (section.id === "preview") {
        renderPreview();
        clearTimeout(window.__previewCfgDebounce);
        window.__previewCfgDebounce = setTimeout(() => fetchPreviewPayloadOnce(), 80);
      } else if (section.id === "bells") {
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
  // Сетка зависит от ориентации (для предпросмотра/drag/resize).
  if (screen.orientation === "portrait") { GRID.cols = 26; GRID.rows = 32; } else { GRID.cols = 32; GRID.rows = 26; }
  elements.screenName.value = screen.name;
  elements.screenSlug.value = screen.slug;
  if (elements.screenOrientation) elements.screenOrientation.value = screen.orientation === "portrait" ? "portrait" : "landscape";
  if (elements.screenMobileMode) elements.screenMobileMode.checked = Boolean(screen.mobile_mode);
  if (elements.screenEnableFeedback) elements.screenEnableFeedback.checked = Boolean(screen.enable_feedback);
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
    if (w.type === "checkin_submit" && w.settings && w.settings.monitor_widget_id) {
      const mid = String(w.settings.monitor_widget_id || "").trim();
      if (mid && idMap.has(mid)) w.settings.monitor_widget_id = idMap.get(mid);
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
  state.programSettingsPanelActive = false;
  render();
}

function ymdTodayInSchoolTz() {
  const tz = (state.config && state.config.timezone) || "Europe/Moscow";
  try {
    return new Intl.DateTimeFormat("en-CA", {
      timeZone: String(tz).trim() || "Europe/Moscow",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(new Date());
  } catch {
    const d = new Date();
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  }
}

/** Удаляет ручные замены с датой раньше «сегодня» по часовому поясу школы. */
function prunePastOverrides() {
  const today = ymdTodayInSchoolTz();
  const before = (state.overrides || []).length;
  state.overrides = (state.overrides || []).filter((o) => o && String(o.date || "") >= today);
  return state.overrides.length !== before;
}

let persistOverridesPruneTimer = null;
function schedulePersistOverridesPruned() {
  clearTimeout(persistOverridesPruneTimer);
  persistOverridesPruneTimer = setTimeout(() => {
    api("/api/admin/overrides", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.overrides),
    }).catch(() => {});
  }, 500);
}

function renderOverrides() {
  if (prunePastOverrides()) schedulePersistOverridesPruned();
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

function resetSchoolNewsForm() {
  if (elements.schoolNewsId) elements.schoolNewsId.value = "";
  if (elements.schoolNewsTitle) elements.schoolNewsTitle.value = "";
  if (elements.schoolNewsDate) elements.schoolNewsDate.value = new Date().toISOString().slice(0, 10);
  if (elements.schoolNewsCover) elements.schoolNewsCover.value = "";
  if (elements.schoolNewsActive) elements.schoolNewsActive.checked = true;
  setSchoolNewsEditorContent("");
  state.editingSchoolNewsId = "";
}

function getSchoolNewsEditorContent() {
  try {
    const ed = window.tinymce && typeof window.tinymce.get === "function" ? window.tinymce.get("school-news-content") : null;
    if (ed && typeof ed.getContent === "function") return String(ed.getContent() || "").trim();
  } catch (_) {}
  return String(elements.schoolNewsContent?.value || "").trim();
}

function schoolNewsSanitizePreviewHtml(html) {
  // Минимальная защита предпросмотра в админке (сервер тоже чистит при сохранении).
  let s = String(html || "");
  s = s.replace(/<script[^>]*>[\s\S]*?<\/script>/gi, "");
  s = s.replace(/\son[a-z]+\s*=\s*"[^"]*"/gi, "");
  s = s.replace(/\son[a-z]+\s*=\s*'[^']*'/gi, "");
  return s;
}

function schoolNewsNormalizeEditorHtml(html) {
  // Предпочитаем <p> блоки, чтобы текст не был "монолитом" после вставки.
  const s = String(html || "").trim();
  if (!s) return "";
  // Если это уже похоже на HTML с блоками — оставляем.
  if (/<p[\s>]/i.test(s) || /<ul[\s>]/i.test(s) || /<ol[\s>]/i.test(s) || /<br[\s/>]/i.test(s)) return s;
  // Plain text -> paragraphs.
  const src = s.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const blocks = src.split(/\n{2,}/g).map((b) => b.trim()).filter(Boolean);
  const esc = (t) => escapeHtml(String(t || ""));
  return blocks.map((b) => `<p>${esc(b).replace(/\n/g, "<br>")}</p>`).join("");
}

function setSchoolNewsEditorContent(html) {
  const text = String(html || "");
  try {
    const ed = window.tinymce && typeof window.tinymce.get === "function" ? window.tinymce.get("school-news-content") : null;
    if (ed && typeof ed.setContent === "function") {
      ed.setContent(text);
      return;
    }
  } catch (_) {}
  const normalized = schoolNewsNormalizeEditorHtml(text);
  if (elements.schoolNewsEditor) elements.schoolNewsEditor.innerHTML = schoolNewsSanitizePreviewHtml(normalized);
  if (elements.schoolNewsContent) elements.schoolNewsContent.value = normalized;
}

function getSchoolNewsRichEditorHtml() {
  try {
    const el = elements.schoolNewsEditor;
    if (!el) return "";
    const raw = el.innerHTML || "";
    return schoolNewsSanitizePreviewHtml(raw).trim();
  } catch (_) {
    return "";
  }
}

function syncSchoolNewsRichEditorToTextarea() {
  if (!elements.schoolNewsContent) return;
  const html = getSchoolNewsRichEditorHtml();
  elements.schoolNewsContent.value = html;
}

function gsRichExec(cmd) {
  try {
    document.execCommand(cmd, false, null);
  } catch (_) {}
}

function ensureSchoolNewsRichEditor() {
  if (!elements.schoolNewsEditorWrap || !elements.schoolNewsEditor) return;
  if (window.__gsSchoolNewsRichInitDone) return;
  window.__gsSchoolNewsRichInitDone = true;

  const wrap = elements.schoolNewsEditorWrap;
  const surface = elements.schoolNewsEditor;

  wrap.addEventListener("click", (ev) => {
    const btn = ev.target && ev.target.closest ? ev.target.closest("[data-gs-cmd],[data-gs-action]") : null;
    if (!btn) return;
    ev.preventDefault();
    surface.focus();
    const cmd = btn.getAttribute("data-gs-cmd");
    const action = btn.getAttribute("data-gs-action");
    if (cmd) {
      gsRichExec(cmd);
      syncSchoolNewsRichEditorToTextarea();
      return;
    }
    if (action === "link") {
      const url = window.prompt("Ссылка (https://...)", "https://");
      if (!url) return;
      try {
        document.execCommand("createLink", false, String(url).trim());
      } catch (_) {}
      syncSchoolNewsRichEditorToTextarea();
      return;
    }
    if (action === "unlink") {
      gsRichExec("unlink");
      syncSchoolNewsRichEditorToTextarea();
      return;
    }
    if (action === "clear") {
      gsRichExec("removeFormat");
      gsRichExec("unlink");
      syncSchoolNewsRichEditorToTextarea();
    }
  });

  surface.addEventListener("input", () => {
    syncSchoolNewsRichEditorToTextarea();
  });

  surface.addEventListener("paste", (ev) => {
    try {
      const dt = ev.clipboardData;
      const html = dt ? dt.getData("text/html") : "";
      const text = dt ? dt.getData("text/plain") : "";
      // Если вставляют из Word/браузера — оставляем HTML; иначе plain text -> абзацы.
      if (!html && text) {
        ev.preventDefault();
        const converted = schoolNewsNormalizeEditorHtml(text);
        document.execCommand("insertHTML", false, converted);
        syncSchoolNewsRichEditorToTextarea();
      }
    } catch (_) {}
  });

  // Инициализируем пустым абзацем, чтобы курсор/ввод на ТВ/старых браузерах был стабильнее.
  if (!surface.innerHTML.trim()) surface.innerHTML = "<p><br></p>";
  syncSchoolNewsRichEditorToTextarea();
}

async function ensureSchoolNewsTinyMce() {
  if (!elements.schoolNewsContent) return;
  if (window.__gsSchoolNewsEditorInitDone) return;
  // Без ключа Tiny Cloud показывает баннер "A valid API key..." — не грузим редактор вообще.
  const apiKey = String(state.config?.tinymce_api_key || "").trim();
  if (!apiKey) {
    window.__gsSchoolNewsEditorInitDone = true;
    // Визуальный редактор без внешних зависимостей.
    ensureSchoolNewsRichEditor();
    return;
  }
  const setupEditor = async () => {
    if (!window.tinymce || typeof window.tinymce.init !== "function") return;
    if (window.tinymce.get("school-news-content")) {
      window.__gsSchoolNewsEditorInitDone = true;
      return;
    }
    await window.tinymce.init({
      selector: "#school-news-content",
      menubar: false,
      height: 520,
      plugins: "lists link image table code autoresize",
      toolbar: "undo redo | styles | bold italic underline | alignleft aligncenter alignright | bullist numlist | link image table | code",
      branding: false,
      promotion: false,
      convert_urls: false,
      content_style: "body { font-family: Inter, Arial, sans-serif; font-size: 14px; }",
    });
    window.__gsSchoolNewsEditorInitDone = true;
  };
  try {
    await setupEditor();
    if (window.__gsSchoolNewsEditorInitDone) return;
    if (!window.__gsTinyScriptLoading) {
      window.__gsTinyScriptLoading = new Promise((resolve, reject) => {
        const s = document.createElement("script");
        s.src = `https://cdn.tiny.cloud/1/${encodeURIComponent(apiKey)}/tinymce/6/tinymce.min.js`;
        s.referrerPolicy = "origin";
        s.onload = resolve;
        s.onerror = reject;
        document.head.appendChild(s);
      });
    }
    await window.__gsTinyScriptLoading;
    await setupEditor();
  } catch (_) {
    // fallback: оставляем обычный textarea без блокировки работы формы
  }
}

function ensureSchoolNewsId() {
  let id = String(elements.schoolNewsId?.value || "").trim();
  if (id) return id;
  id = `news_${crypto.randomUUID().slice(0, 8)}`;
  if (elements.schoolNewsId) elements.schoolNewsId.value = id;
  state.editingSchoolNewsId = id;
  return id;
}

async function uploadSchoolNewsCoverFromPc(file) {
  if (!file) return;
  if (file.size > 1024 * 1024) {
    alert("Файл обложки слишком большой (максимум 1 МБ).");
    return;
  }
  const nid = ensureSchoolNewsId();
  const fd = new FormData();
  fd.append("file", file);
  fd.append("news_id", nid);
  const r = await api("/api/admin/school-news/cover-upload", { method: "POST", body: fd });
  if (elements.schoolNewsCover) elements.schoolNewsCover.value = String(r.url || "");
}

async function fetchSchoolNewsCoverFromUrl(url) {
  const u = String(url || "").trim();
  if (!/^https?:\/\//i.test(u)) {
    alert("Нужна ссылка вида http(s)://...");
    return;
  }
  const nid = ensureSchoolNewsId();
  const r = await api("/api/admin/school-news/cover-fetch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: u, news_id: nid }),
  });
  if (elements.schoolNewsCover) elements.schoolNewsCover.value = String(r.url || "");
}

function renderSchoolNewsList() {
  const root = elements.schoolNewsList;
  if (!root) return;
  const items = Array.isArray(state.schoolNews) ? state.schoolNews : [];
  if (!items.length) {
    root.innerHTML = '<div class="hint">Новостей пока нет.</div>';
    return;
  }
  root.innerHTML = items
    .map((row) => {
      const id = escapeHtmlAttr(String(row.id || ""));
      const title = escapeHtml(String(row.title || ""));
      const dt = escapeHtml(String(row.created_at || ""));
      const active = row.is_active !== false ? "✅" : "⛔";
      return `<div class="override-item"><span class="override-row-text">${active} ${dt} — ${title}</span>
        <div class="table-actions">
          <button type="button" class="secondary-btn compact-btn" data-news-edit="${id}">Ред.</button>
          <button type="button" class="danger-btn compact-btn" data-news-del="${id}">Удалить</button>
        </div>
      </div>`;
    })
    .join("");
}

function render() {
  if (state.meta?.demo_session && state.statsPanelActive) {
    state.statsPanelActive = false;
    leaveStatsPanel();
  }
  const tabPanel = document.getElementById("section-tabs-panel");
  const screenWrap = document.getElementById("screen-editor-wrap");
  const audioPanel = document.getElementById("audio-stream-panel");
  const statsPanel = document.getElementById("stats-panel");
  const programPanel = elements.programSettingsPanel;

  renderTabs();

  if (state.programSettingsPanelActive) {
    leaveStatsPanel();
    clearInterval(window.__streamStatusInterval);
    if (elements.deleteScreenBtn) {
      elements.deleteScreenBtn.hidden = true;
      elements.deleteScreenBtn.disabled = true;
    }
    if (elements.duplicateScreenBtn) elements.duplicateScreenBtn.hidden = true;
    if (tabPanel) tabPanel.style.display = "none";
    if (screenWrap) screenWrap.hidden = true;
    if (statsPanel) statsPanel.hidden = true;
    if (audioPanel) audioPanel.hidden = true;
    if (programPanel) {
      programPanel.hidden = false;
      programPanel.setAttribute("aria-hidden", "false");
    }
    window.GuardSchoolScreen?.clearAllTimers();
    const psTab = getStoredProgramSettingsTab();
    if (psTab === "emergency") renderEmergencyTemplatesAdmin();
    if (psTab === "school_news") renderSchoolNewsList();
    finishTopBarSessionWidgets();
    return;
  }
  if (programPanel) {
    programPanel.hidden = true;
    programPanel.setAttribute("aria-hidden", "true");
  }

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
  ensurePaletteWidgetInstancesOnSelectedScreen();
  renderForm();
  renderWidgets();
  if (state.widgetModalWidgetId) syncWidgetModal();
  renderPreview();
  renderOverrides();
  renderSchoolNewsList();
  renderLessonImportStats();
  if (state.activeSection === "bells") {
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
  if (elements.screenOrientation) {
    elements.screenOrientation.onchange = (event) => {
      selectedScreen().orientation = (event.target.value === "portrait" ? "portrait" : "landscape");
      if (selectedScreen().orientation === "portrait") { GRID.cols = 26; GRID.rows = 32; } else { GRID.cols = 32; GRID.rows = 26; }
      renderPreview();
    };
  }
  if (elements.screenMobileMode) {
    elements.screenMobileMode.onchange = () => {
      selectedScreen().mobile_mode = Boolean(elements.screenMobileMode.checked);
      renderPreview();
    };
  }
  if (elements.screenEnableFeedback) {
    elements.screenEnableFeedback.onchange = () => {
      selectedScreen().enable_feedback = Boolean(elements.screenEnableFeedback.checked);
    };
  }
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
  if (elements.screenBellTemplate) {
    elements.screenBellTemplate.onchange = (event) => {
      selectedScreen().bell_schedule_template = event.target.value;
      renderBellEditor();
      renderPreview();
    };
  }
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
  if (elements.rssRefreshMinutes) {
    elements.rssRefreshMinutes.oninput = (e) => {
      const n = Number(e.target.value);
      state.config.rss_refresh_minutes = Number.isFinite(n) ? Math.max(30, Math.min(60, Math.round(n))) : 45;
    };
  }
  if (elements.rssSourceAddBtn) {
    elements.rssSourceAddBtn.onclick = () => {
      if (!Array.isArray(state.config.rss_sources)) state.config.rss_sources = [];
      state.config.rss_sources.push({ name: "", rss_url: "", enabled: true });
      renderRssSourcesEditor();
    };
  }
  if (elements.rssRefreshNowBtn) {
    elements.rssRefreshNowBtn.onclick = async () => {
      try {
        const result = await api("/api/admin/rss-news/refresh", { method: "POST" });
        const count = Number(result?.count || 0);
        alert(`RSS обновлены. Новостей в кэше: ${count}.`);
      } catch (e) {
        alert(e.message || String(e));
      }
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
  if (elements.schoolNewsResetBtn) {
    elements.schoolNewsResetBtn.onclick = () => {
      resetSchoolNewsForm();
      renderSchoolNewsList();
    };
  }
  if (elements.schoolNewsSaveBtn) {
    elements.schoolNewsSaveBtn.onclick = async () => {
      const payload = {
        id: String(elements.schoolNewsId?.value || "").trim(),
        title: String(elements.schoolNewsTitle?.value || "").trim(),
        created_at: String(elements.schoolNewsDate?.value || "").trim(),
        cover_image: String(elements.schoolNewsCover?.value || "").trim(),
        is_active: Boolean(elements.schoolNewsActive?.checked),
        content: getSchoolNewsEditorContent(),
      };
      if (!payload.title || !payload.content) {
        alert("Укажите заголовок и текст новости.");
        return;
      }
      try {
        const r = await api("/api/admin/school-news", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        state.schoolNews = r.items || [];
        resetSchoolNewsForm();
        renderSchoolNewsList();
      } catch (e) {
        alert(e.message || String(e));
      }
    };
  }
  if (elements.schoolNewsList) {
    elements.schoolNewsList.addEventListener("click", async (event) => {
      const editBtn = event.target.closest("[data-news-edit]");
      const delBtn = event.target.closest("[data-news-del]");
      if (editBtn) {
        const id = String(editBtn.getAttribute("data-news-edit") || "");
        const row = (state.schoolNews || []).find((item) => String(item.id || "") === id);
        if (!row) return;
        elements.schoolNewsId.value = String(row.id || "");
        elements.schoolNewsTitle.value = String(row.title || "");
        elements.schoolNewsDate.value = String(row.created_at || "");
        elements.schoolNewsCover.value = String(row.cover_image || "");
        elements.schoolNewsActive.checked = row.is_active !== false;
        setSchoolNewsEditorContent(String(row.content || ""));
        return;
      }
      if (delBtn) {
        const id = String(delBtn.getAttribute("data-news-del") || "");
        if (!id || !confirm("Удалить новость?")) return;
        try {
          const r = await api(`/api/admin/school-news/${encodeURIComponent(id)}`, { method: "DELETE" });
          state.schoolNews = r.items || [];
          resetSchoolNewsForm();
          renderSchoolNewsList();
        } catch (e) {
          alert(e.message || String(e));
        }
      }
    });
  }
}

function addScreen() {
  const index = state.config.screens.length + 1;
  const screen = createDefaultScreen(index);
  state.config.screens.push(screen);
  state.audioStreamPanelActive = false;
  state.statsPanelActive = false;
  state.programSettingsPanelActive = false;
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
  if (state.programSettingsPanelActive && getStoredProgramSettingsTab() === "emergency") {
    flushEmergencyEditorToState();
  }
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
  state.programSettingsPanelActive = false;
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
  state.meta = config?._meta || state.meta;
  if (config && typeof config === "object") delete config._meta;
  state.config = config;
  ensureEmergencyConfig();
  const demoBanner = document.getElementById("demo-session-banner");
  if (demoBanner) {
    if (state.meta?.demo_session) {
      demoBanner.hidden = false;
    } else {
      demoBanner.hidden = true;
    }
  }
  if (state.meta?.deployment_mode === "saas") {
    // SaaS: синхронизация "с SaaS" не имеет смысла (облако и есть источник).
    const hide = (el) => { if (el) el.closest?.(".settings-row")?.classList?.add("hidden") || (el.hidden = true); };
    hide(elements.cloudBaseUrl);
    hide(elements.cloudSyncInterval);
    hide(elements.cloudSyncEnabled);
    hide(elements.cloudSyncToken);
    if (elements.syncStatusLine) elements.syncStatusLine.hidden = true;
    if (elements.syncNowBtn) elements.syncNowBtn.hidden = true;
  }
  ensureAdminPaletteHidden();
  ensureAudioStreamConfig();
  /* Иначе скрытые поля «Стрим» остаются пустыми до первого открытия вкладки — сохранение с ТВ затирало бы audio_stream */
  syncAudioStreamFormFromState();
  state.schedule = schedule.schedule || [];
  state.scheduleClassOptions = schedule.schedule_class_options || [];
  state.fullScheduleRows = schedule.full_schedule_rows ?? 0;
  state.scheduleSampleRows = schedule.schedule_sample_rows ?? 0;
  state.overrides = schedule.overrides || [];
  if (prunePastOverrides()) schedulePersistOverridesPruned();
  state.announcements = schedule.announcements || [];
  state.schoolNews = schedule.school_news || [];
  state.marquee = schedule.marquee || [];
  state.bells = schedule.bells || { templates: [], weekday_overrides: {}, date_overrides: [], sound_defaults: { start: null, end: null } };
  state.bells.sound_defaults = state.bells.sound_defaults || { start: null, end: null };
  state.bellSoundFiles = sounds.files || [];
  state.history = schedule.history || [];
  state.appVersion = schedule.app_version || "";
  state.schoolNews = schedule.school_news || [];
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
  await ensureSchoolNewsTinyMce();
  resetSchoolNewsForm();
  render();
  if (state.programSettingsPanelActive) hydrateProgramSettingsPanelIfOpen();
  refreshAdminFooterStats().catch(() => {});
  window.setInterval(() => {
    refreshAdminFooterStats().catch(() => {});
  }, 60000);
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

if (elements.saveConfigTopBtn) elements.saveConfigTopBtn.onclick = saveAll;
if (elements.exportDataBtn) {
  elements.exportDataBtn.onclick = async () => {
    await downloadFile("/api/admin/export", "gorniitv_export");
  };
}
if (elements.importDataBtn && elements.importDataInput) {
  elements.importDataBtn.onclick = () => elements.importDataInput.click();
  elements.importDataInput.onchange = (event) => event.target.files[0] && importBundle(event.target.files[0]);
}
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
if (elements.backgroundInput) {
  elements.backgroundInput.onchange = (event) => event.target.files[0] && uploadBackground(event.target.files[0]);
}
if (elements.pickBackgroundBtn && elements.backgroundInput) {
  elements.pickBackgroundBtn.onclick = () => elements.backgroundInput.click();
}
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

document.body.addEventListener("click", (ev) => {
  const btn = ev.target && ev.target.closest && ev.target.closest("[data-import-excel-sample]");
  if (!btn) return;
  const kind = btn.getAttribute("data-import-excel-sample");
  if (!kind) return;
  ev.preventDefault();
  downloadImportExcelSample(kind).catch((e) => alert(e.message || String(e)));
});

async function adminLogoutThenNavigate(href) {
  await api("/api/logout", { method: "POST" });
  try {
    sessionStorage.removeItem(GS_ADMIN_SESSION_TOP);
    sessionStorage.removeItem(GS_ADMIN_SESSION_SCREEN);
    sessionStorage.removeItem(GS_ADMIN_SESSION_SECTION);
  } catch (_) {}
  if (state.meta) state.meta.demo_session = false;
  state.statsPanelActive = false;
  state.audioStreamPanelActive = false;
  state.programSettingsPanelActive = false;
  window.location.href = href;
}

if (elements.logoutBtn) elements.logoutBtn.onclick = () => adminLogoutThenNavigate("/login");

if (elements.schoolNewsCoverPickBtn && elements.schoolNewsCoverFile) {
  elements.schoolNewsCoverPickBtn.onclick = () => elements.schoolNewsCoverFile.click();
  elements.schoolNewsCoverFile.onchange = async (ev) => {
    const f = ev.target.files?.[0];
    try {
      if (f) await uploadSchoolNewsCoverFromPc(f);
    } catch (e) {
      alert(String(e.message || e));
    }
    ev.target.value = "";
  };
}

if (elements.schoolNewsCoverFetchBtn) {
  elements.schoolNewsCoverFetchBtn.onclick = async () => {
    try {
      await fetchSchoolNewsCoverFromUrl(elements.schoolNewsCover?.value || "");
    } catch (e) {
      alert(String(e.message || e));
    }
  };
}

const demoLogoutBtn = document.getElementById("demo-session-logout-btn");
if (demoLogoutBtn) {
  demoLogoutBtn.onclick = () => {
    const exitUrl = state.meta?.demo_exit_url;
    const href =
      typeof exitUrl === "string" && /^https?:\/\//i.test(exitUrl) ? exitUrl : "/login";
    adminLogoutThenNavigate(href);
  };
}

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
