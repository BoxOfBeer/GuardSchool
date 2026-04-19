import { state, elements, GRID } from "./admin/state.js";
import { t, tf, getSectionTabs } from "./admin/i18n-helpers.js";
import {
  api,
  apiDetailMessage,
  mergeFetchOptions,
  downloadFile,
  downloadBinaryFile,
} from "./admin/api-client.js";
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
}

function emergencyWidget() {
  const screen = selectedScreen();
  const w = screen?.widgets?.find((x) => x.type === "emergency");
  return w || null;
}

function syncEmergencyModeCheckbox() {
  const el = document.getElementById("admin-emergency-mode");
  if (!el) return;
  const w = emergencyWidget();
  if (!w) {
    el.disabled = true;
    el.checked = false;
    return;
  }
  el.disabled = false;
  el.checked = !!w.enabled;
}

function bindEmergencyModeOnce() {
  if (bindEmergencyModeOnce._done) return;
  bindEmergencyModeOnce._done = true;
  const el = document.getElementById("admin-emergency-mode");
  if (!el) return;
  el.addEventListener("change", () => {
    const w = emergencyWidget();
    if (!w) return;
    w.enabled = !!el.checked;
    render();
  });
}

function setProgramSettingsTab(tab) {
  const root = elements.programSettingsPanel;
  if (!root) return;
  const allowed = new Set(["general", "tv", "changelog"]);
  const t = allowed.has(tab) ? tab : "general";
  root.querySelectorAll("[data-ps-tab]").forEach((btn) => {
    const on = btn.getAttribute("data-ps-tab") === t;
    btn.classList.toggle("active", on);
    btn.setAttribute("aria-selected", on ? "true" : "false");
  });
  root.querySelectorAll("[data-ps-pane]").forEach((pane) => {
    pane.hidden = pane.getAttribute("data-ps-pane") !== t;
  });
  if (t === "changelog") renderHistory();
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

function openProgramSettingsModal() {
  if (!elements.programSettingsPanel) return;
  closeWidgetModal();
  state.programSettingsPanelActive = true;
  state.audioStreamPanelActive = false;
  syncProgramSettingsFieldsFromState();
  renderProgramPaletteCheckboxes();
  setProgramSettingsTab("general");
  try {
    GuardSchoolI18n.applyDom(elements.programSettingsPanel);
  } catch (_) {}
  render();
}

function closeProgramSettingsModal() {
  state.programSettingsPanelActive = false;
  render();
}

function bindProgramSettingsModalOnce() {
  if (bindProgramSettingsModalOnce._done) return;
  bindProgramSettingsModalOnce._done = true;
  elements.programSettingsOpenBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    if (state.programSettingsPanelActive) closeProgramSettingsModal();
    else openProgramSettingsModal();
  });
  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-close-program-settings]")) {
      e.preventDefault();
      closeProgramSettingsModal();
    }
  });
  elements.programSettingsPanel?.addEventListener("click", (e) => {
    const b = e.target.closest("[data-ps-tab]");
    if (!b || !elements.programSettingsPanel?.contains(b)) return;
    e.preventDefault();
    const t = b.getAttribute("data-ps-tab");
    if (t) setProgramSettingsTab(t);
  });
}

function widgetDisplayTitle(widget) {
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
    { id: "fade", label: t("carousel.fade") },
    { id: "zoom", label: t("carousel.zoom") },
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

function selectedBellTemplate() {
  return state.bells.templates.find((item) => item.id === selectedScreen().bell_schedule_template) || state.bells.templates[0];
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
          backdrop: false,
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

function widgetInput(label, value, onChange, type = "text", sizeClass = "standard-input") {
  return `<label>${label}<input class="${sizeClass}" data-key="${onChange}" type="${type}" value="${value ?? ""}"></label>`;
}

function widgetTextarea(label, value, onChange, sizeClass = "wide-input") {
  return `<label>${label}<textarea class="${sizeClass}" data-key="${onChange}" rows="4">${value ?? ""}</textarea></label>`;
}

function widgetToggle(label, checked, onChange) {
  return `<label class="toggle-label"><input data-key="${onChange}" type="checkbox" ${checked ? "checked" : ""}> ${label}</label>`;
}

function availableCarouselChildren(currentWidget) {
  const list = selectedScreen().widgets
    .filter(
      (widget) =>
        widget.id !== currentWidget.id &&
        widget.type !== "carousel" &&
        widget.type !== "emergency" &&
        widget.type !== "image"
    )
    .map((widget) => ({ id: widget.id, title: widget.title, type: widget.type }));
  // Пустой слот: показать только фон, без виджета.
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

function addWidgetImageSlot(widgetIndex) {
  const w = selectedScreen().widgets[widgetIndex];
  if (!w || w.type !== "image") return;
  coerceWidgetImageSlots(w);
  const n = w.settings.images.length + 1;
  w.settings.images.push({ name: tf("w.imageDefaultName", { n }), url: "" });
  render();
  if (state.widgetModalWidgetId === w.id) syncWidgetModal();
  renderPreview();
}

function removeWidgetImageSlot(widgetIndex, slotIndex) {
  const w = selectedScreen().widgets[widgetIndex];
  if (!w || w.type !== "image") return;
  coerceWidgetImageSlots(w);
  const i = Number(slotIndex);
  if (!Number.isFinite(i) || i < 0 || i >= w.settings.images.length) return;
  if (w.settings.images.length <= 1) {
    w.settings.images[0] = { name: w.settings.images[0].name || tf("w.imageDefaultName", { n: 1 }), url: "" };
  } else {
    w.settings.images.splice(i, 1);
  }
  render();
  if (state.widgetModalWidgetId === w.id) syncWidgetModal();
  renderPreview();
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

function ensureAudioStreamConfig() {
  const d = {
    enabled: false,
    receiver_ip: "",
    stream_port: 11990,
    ping_host: "",
    multicast_ip: "224.0.224.1",
    multicast_ttl: 10,
    base_port: 11990,
    ffmpeg_path: "",
    interface_note: "",
    use_bell_schedule: true,
    use_bell_sound_files: true,
    volume_percent: 80,
    source_screen_id: "",
    send_via_multicast: false,
    udp_bind_localaddr: false,
    stream_profile: "mpegts_aac",
    break_music_on_breaks: false,
    break_music_volume_percent: 40,
    bell_trigger_sec_window: 25,
  };
  state.config.audio_stream = { ...d, ...(state.config.audio_stream || {}) };
  const s = state.config.audio_stream;
  if (!s.receiver_ip && s.ping_host) s.receiver_ip = s.ping_host;
  if (!s.ping_host && s.receiver_ip) s.ping_host = s.receiver_ip;
  if (s.stream_port == null && s.base_port != null) s.stream_port = s.base_port;
}

function refreshBellSoundsForStream() {
  api("/api/admin/bell-sounds")
    .then((r) => {
      state.bellSoundFiles = r.files || [];
    })
    .catch(() => {});
}

async function refreshPcPlayerFiles() {
  let breaks = [];
  try {
    const r = await api("/api/admin/break-music-files");
    breaks = (r.files || []).map((x) => x && x.filename).filter(Boolean);
  } catch (_) {
    breaks = [];
  }
  const out = [];
  breaks.forEach((fn) => {
    const name = String(fn != null ? fn : "").trim();
    if (!name) return;
    out.push({ filename: name, label: name });
  });
  state.pcPlayerFiles = out;
  if (state.pcPlayerSelectedIndex >= out.length) state.pcPlayerSelectedIndex = 0;
  renderPcPlayerFileList();
}

function selectedPcPlayerItem() {
  return state.pcPlayerFiles && state.pcPlayerFiles.length
    ? state.pcPlayerFiles[Math.max(0, Math.min(state.pcPlayerFiles.length - 1, state.pcPlayerSelectedIndex))]
    : null;
}

function renderPcPlayerFileList() {
  const el = elements.pcPlayerFileList;
  if (!el) return;
  const items = state.pcPlayerFiles || [];
  if (!items.length) {
    el.innerHTML = `<div class="hint">${t("audio.noBreakFiles")}</div>`;
    return;
  }
  el.innerHTML = "";
  items.forEach((item, idx) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = `pc-player-file-item ${idx === state.pcPlayerSelectedIndex ? "active" : ""}`;
    b.innerHTML = `<span class="pc-player-file-badge break">${escapeHtmlAttr(t("audio.badgeBreak"))}</span><span class="pc-player-file-name">${escapeHtmlAttr(item.label)}</span>`;
    b.onclick = () => {
      state.pcPlayerSelectedIndex = idx;
      renderPcPlayerFileList();
    };
    el.appendChild(b);
  });
}

async function pcPlayerPlaySelected() {
  const item = selectedPcPlayerItem();
  if (!item) return;
  readAudioStreamFormIntoState();
  const breakVol = Number(elements.audioStreamBreakMusicVol && elements.audioStreamBreakMusicVol.value);
  const volBreak = Number.isFinite(breakVol) ? Math.max(0, Math.min(100, breakVol)) : 40;
  if (elements.audioStreamStatusBar) elements.audioStreamStatusBar.textContent = t("audio.statusStarting");

  try {
    const fn = String(item.filename != null ? item.filename : "").trim();
    if (!fn) {
      if (elements.audioStreamStatusBar) elements.audioStreamStatusBar.textContent = t("audio.noFileName");
      return;
    }
    await api("/api/admin/break-music-preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: fn, volume_percent: volBreak }),
    });
    updateStreamStatusBar();
  } catch (e) {
    if (elements.audioStreamStatusBar) elements.audioStreamStatusBar.textContent = String(e.message || e);
  }
}

function pcPlayerStep(delta) {
  const n = state.pcPlayerFiles ? state.pcPlayerFiles.length : 0;
  if (!n) return;
  state.pcPlayerSelectedIndex = (state.pcPlayerSelectedIndex + delta + n) % n;
  renderPcPlayerFileList();
}

function breakMusicVolumesFromForm() {
  const rawB = elements.audioStreamVolume && elements.audioStreamVolume.value;
  const rawBr = elements.audioStreamBreakMusicVol && elements.audioStreamBreakMusicVol.value;
  const bell =
    rawB !== undefined && rawB !== "" && Number.isFinite(Number(rawB))
      ? Math.max(0, Math.min(100, Number(rawB)))
      : null;
  const br =
    rawBr !== undefined && rawBr !== "" && Number.isFinite(Number(rawBr))
      ? Math.max(0, Math.min(100, Number(rawBr)))
      : null;
  return { bell, br };
}

/** Порядок очереди с сервера + громкость из полей формы (или с сервера). */
async function renderBreakMusicPlayback() {
  const el = elements.breakMusicPlayerList;
  if (!el) return;
  try {
    const r = await api("/api/admin/break-music-files");
    const pb = r.playback;
    if (!pb) {
      el.innerHTML = `<p class="hint">${t("audio.queueEmpty")}</p>`;
      return;
    }
    const vf = breakMusicVolumesFromForm();
    const bellPct = vf.bell ?? pb.volume_bell_percent;
    const breakPct = vf.br ?? pb.volume_break_percent;
    const volLine = `<div class="break-music-vol-line"><strong>Громкость:</strong> звонки <strong>${bellPct}%</strong> · перемена <strong>${breakPct}%</strong> (ffmpeg <code>volume=${(breakPct / 100).toFixed(3)}</code> для фона)</div><p class="hint break-music-save-hint">Чтобы на ПК применились новые %, нажмите «Сохранить» вверху.</p>`;

    const kindLine =
      pb.play_kind && pb.play_kind !== "idle"
        ? `<p class="hint break-music-kind">Сейчас в плеере ПК: <code>${escapeHtmlAttr(String(pb.play_kind))}</code></p>`
        : "";

    const modeBlock = `<p class="break-music-mode"><strong>${escapeHtmlAttr(pb.mode_label || "")}</strong></p><p class="hint break-music-note">${escapeHtmlAttr(pb.order_note || "")}</p>`;

    const orows = pb.ordered_rows || [];
    const rows =
      orows.length > 0
        ? orows
            .map(
              (row) =>
                `<div class="break-music-row ${row.is_next ? "break-music-row-next" : ""}"><span class="break-music-idx">${row.i}.</span><span class="break-music-name">${escapeHtmlAttr(row.filename)}</span>${row.is_next ? '<span class="break-music-badge">следующий</span>' : ""}</div>`,
            )
            .join("")
        : '<p class="hint">Нет строк очереди.</p>';

    el.innerHTML = `${volLine}${kindLine}${modeBlock}<div class="break-music-order">${rows}</div>`;
  } catch (_) {
    el.innerHTML = `<p class="hint">${t("audio.queueLoadFail")}</p>`;
  }
}

function updateStreamStatusBar() {
  const el = elements.audioStreamStatusBar;
  if (!el) return;
  api("/api/admin/audio-stream-status")
    .then((st) => {
      const last = st.last;
      const be = last && last.backend ? String(last.backend) : "";
      const run = st.ffmpeg_process_running
        ? `воспроизведение: да${be ? ` (${be})` : ""}`
        : "воспроизведение: нет";
      const pid = st.pid != null ? ` (PID ${st.pid})` : "";
      const kind = st.play_kind && st.play_kind !== "idle" ? `\nРежим: ${st.play_kind}` : "";
      const busy = st.stream_slot_busy ? "Занято" : "Свободно";
      let tail = "";
      if (last) {
        if (last.finished === false) tail += "\nВоспроизведение…";
        if (last.returncode != null) tail += `\nКод выхода: ${last.returncode}`;
        if (last.ok === false && last.stderr) tail += `\n${String(last.stderr).slice(0, 400)}`;
      }
      let diag = "";
      if (st.volume_bell_percent != null && st.volume_break_percent != null) {
        diag += `\nГромкость (настройки): звонки ${st.volume_bell_percent}% | перемена ${st.volume_break_percent}%`;
      }
      if (st.pc_playback_backend_hint) {
        diag += `\nПК: бэкенд ${st.pc_playback_backend_hint}`;
      }
      if (st.resolved_ffmpeg) diag += `\nffmpeg: ${st.resolved_ffmpeg}`;
      if (!st.resolved_ffmpeg && st.resolved_ffplay) diag += `\nffplay: ${st.resolved_ffplay}`;
      if (
        st.pc_audio_enabled &&
        !st.resolved_ffmpeg &&
        !st.resolved_ffplay
      ) {
        diag +=
          "\n⚠ Не найден ffmpeg/ffplay — расписание на Рупор с этого ПК не сыграет. Установите ffmpeg или укажите путь.";
      }
      el.textContent = `${run}${pid} (${busy})${kind}${tail}${diag}`;
      if (state.audioStreamPanelActive) {
        renderBreakMusicPlayback();
      }
    })
    .catch((err) => {
      el.textContent = tf("audio.statusUnavailable", { msg: String(err.message || err) });
    });
}

function populateAudioStreamSourceScreenSelect() {
  const sel = elements.audioStreamSourceScreen;
  if (!sel || !state.config?.screens?.length) return;
  const cur = (state.config.audio_stream && state.config.audio_stream.source_screen_id) || "";
  sel.innerHTML = "";
  const first = document.createElement("option");
  first.value = "";
  first.textContent = t("audio.firstScreenOption");
  sel.appendChild(first);
  state.config.screens.forEach((sc) => {
    const o = document.createElement("option");
    o.value = String(sc.id);
    o.textContent = sc.name || sc.slug || sc.id;
    sel.appendChild(o);
  });
  const exists = [...sel.options].some((opt) => opt.value === cur);
  sel.value = exists ? cur : "";
}

function syncAudioStreamFormFromState() {
  ensureAudioStreamConfig();
  populateAudioStreamSourceScreenSelect();
  const s = state.config.audio_stream;
  if (elements.audioStreamEnabled) elements.audioStreamEnabled.checked = !!s.enabled;
  if (elements.audioStreamFfmpegPath) elements.audioStreamFfmpegPath.value = s.ffmpeg_path || "";
  if (elements.audioStreamUseBellSchedule) elements.audioStreamUseBellSchedule.checked = s.use_bell_schedule !== false;
  if (elements.audioStreamUseBellFiles) elements.audioStreamUseBellFiles.checked = s.use_bell_sound_files !== false;
  if (elements.audioStreamVolume) elements.audioStreamVolume.value = String(s.volume_percent ?? 80);
  if (elements.audioStreamBreakMusic) elements.audioStreamBreakMusic.checked = !!s.break_music_on_breaks;
  if (elements.audioStreamBreakMusicVol) elements.audioStreamBreakMusicVol.value = String(s.break_music_volume_percent ?? 40);
  if (elements.audioStreamBellWindow) elements.audioStreamBellWindow.value = String(s.bell_trigger_sec_window ?? 25);
}

function readAudioStreamFormIntoState() {
  ensureAudioStreamConfig();
  const s = state.config.audio_stream;
  s.enabled = !!(elements.audioStreamEnabled && elements.audioStreamEnabled.checked);
  s.ffmpeg_path = (elements.audioStreamFfmpegPath && elements.audioStreamFfmpegPath.value.trim()) || "";
  s.use_bell_schedule = !!(elements.audioStreamUseBellSchedule && elements.audioStreamUseBellSchedule.checked);
  s.use_bell_sound_files = !!(elements.audioStreamUseBellFiles && elements.audioStreamUseBellFiles.checked);
  s.volume_percent = Math.max(0, Math.min(100, Number(elements.audioStreamVolume && elements.audioStreamVolume.value) || s.volume_percent));
  s.source_screen_id = (elements.audioStreamSourceScreen && elements.audioStreamSourceScreen.value) || "";
  s.break_music_on_breaks = !!(elements.audioStreamBreakMusic && elements.audioStreamBreakMusic.checked);
  s.break_music_volume_percent = Math.max(0, Math.min(100, Number(elements.audioStreamBreakMusicVol && elements.audioStreamBreakMusicVol.value) || s.break_music_volume_percent));
  s.bell_trigger_sec_window = Math.max(5, Math.min(55, Number(elements.audioStreamBellWindow && elements.audioStreamBellWindow.value) || s.bell_trigger_sec_window));
}

let audioStreamFormWired = false;
function bindAudioStreamFormOnce() {
  if (audioStreamFormWired) return;
  audioStreamFormWired = true;
  const onChange = () => readAudioStreamFormIntoState();
  [
    elements.audioStreamEnabled,
    elements.audioStreamFfmpegPath,
    elements.audioStreamUseBellSchedule,
    elements.audioStreamUseBellFiles,
    elements.audioStreamVolume,
    elements.audioStreamSourceScreen,
    elements.audioStreamBreakMusic,
    elements.audioStreamBreakMusicVol,
    elements.audioStreamBellWindow,
  ].forEach((el) => {
    if (!el) return;
    el.addEventListener(el.type === "checkbox" || el.tagName === "SELECT" ? "change" : "input", onChange);
  });
  [elements.audioStreamVolume, elements.audioStreamBreakMusicVol].forEach((el) => {
    if (!el) return;
    el.addEventListener("input", () => {
      if (state.audioStreamPanelActive) renderBreakMusicPlayback();
    });
  });
  if (elements.audioStreamStopBtn) {
    elements.audioStreamStopBtn.addEventListener("click", async () => {
      if (elements.audioStreamStatusBar) elements.audioStreamStatusBar.textContent = t("audio.statusStopping");
      try {
        await api("/api/admin/audio-stream-stop", { method: "POST" });
        updateStreamStatusBar();
      } catch (err) {
        if (elements.audioStreamStatusBar) elements.audioStreamStatusBar.textContent = String(err.message || err);
      }
    });
  }
}

let pcPlayerWired = false;
function bindPcPlayerOnce() {
  if (pcPlayerWired) return;
  pcPlayerWired = true;
  if (elements.pcPlayerPrev) elements.pcPlayerPrev.addEventListener("click", () => pcPlayerStep(-1));
  if (elements.pcPlayerNext) elements.pcPlayerNext.addEventListener("click", () => pcPlayerStep(1));
  if (elements.pcPlayerPlay) elements.pcPlayerPlay.addEventListener("click", () => pcPlayerPlaySelected());
  if (elements.audioStreamBreakMusicVol) {
    const sync = () => {
      if (elements.pcPlayerVolDisplay) elements.pcPlayerVolDisplay.textContent = String(elements.audioStreamBreakMusicVol.value || "");
    };
    elements.audioStreamBreakMusicVol.addEventListener("input", sync);
    sync();
  }
}

let settingsSoundTestsWired = false;

function pollFfplayIntoPre(base, preEl) {
  const pollFfmpeg = async () => {
    for (let i = 0; i < 40; i += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      try {
        const st = await api("/api/admin/audio-stream-last-send");
        const last = st.last;
        if (!last || !last.finished) continue;
        const rc = last.returncode;
        const err = last.stderr || "";
        const tail = `\n\n--- вывод (код ${rc === null || rc === undefined ? "?" : rc}) ---\n${err || "(пустой stderr)"}`;
        if (preEl) preEl.textContent = base + tail;
        return;
      } catch (_) {
        /* сеть */
      }
    }
    if (preEl) {
      preEl.textContent = `${base}\n\n${t("audio.statusTimeout")}`;
    }
  };
  pollFfmpeg();
}

function bindSettingsSoundTestsOnce() {
  if (settingsSoundTestsWired) return;
  settingsSoundTestsWired = true;
  const out = () => elements.settingsSoundTestResult;

  if (elements.settingsTestRuporBtn) {
    elements.settingsTestRuporBtn.addEventListener("click", async () => {
      readAudioStreamFormIntoState();
      if (out()) out().textContent = t("audio.playbackStarting");
      const testUrl = "/api/admin/pc-audio-test-play?use_first=1";
      try {
        const response = await fetch(
          testUrl,
          mergeFetchOptions({
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ volume_percent: Number(elements.audioStreamVolume && elements.audioStreamVolume.value) || 80 }),
          }),
        );
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          if (response.status === 401) {
            window.location.href = "/login";
            return;
          }
          if (response.status === 404) {
            if (out()) {
              out().textContent =
                "Сервер не знает этот API (404) — запущен старый процесс GuardSchool.\n\n"
                + "Закройте все окна/службы, остановите python/uvicorn, запустите снова из папки с текущим проектом (где есть маршрут pc-audio-test-play в app.py).";
            }
            return;
          }
          throw new Error(apiDetailMessage(payload) || `Ошибка ${response.status}`);
        }
        const r = payload;
        const base = r.detail || "Готово.";
        if (out()) out().textContent = `${base}\n\n${t("audio.waitingFinish")}`;
        pollFfplayIntoPre(base, elements.settingsSoundTestResult);
      } catch (err) {
        if (out()) out().textContent = String(err.message || err);
      }
    });
  }

  if (elements.settingsTestTvBtn) {
    elements.settingsTestTvBtn.addEventListener("click", async () => {
      try {
        const r = await api("/api/admin/bell-sounds");
        const files = r.files || [];
        if (!files.length) {
          if (out()) {
            out().textContent =
              "В uploads/bells нет файлов. Загрузите звук в разделе «Звонки».";
          }
          return;
        }
        const slug = selectedScreenSlug();
        const screenUrl = `${window.location.origin}/screen/${encodeURIComponent(slug)}`;
        const w = window.open(screenUrl, "_blank", "noopener,noreferrer");
        let msg =
          `Тест ТВ: откройте экран «${slug}» — звук по расписанию идёт там. В админке файл не играет (Рупор только «Тест Рупор»).\n${screenUrl}`;
        if (!w) msg += "\n\nВкладка не открылась — разрешите всплывающие окна или скопируйте URL выше.";
        if (out()) out().textContent = msg;
      } catch (err) {
        if (out()) out().textContent = String(err.message || err);
      }
    });
  }
}

function renderTabs() {
  elements.tabs.innerHTML = "";
  const audioBtn = document.createElement("button");
  audioBtn.type = "button";
  audioBtn.className = `top-nav-btn ${state.audioStreamPanelActive ? "active" : ""}`;
  audioBtn.textContent = t("tabs.pcAudio");
  audioBtn.onclick = () => {
    closeWidgetModal();
    state.programSettingsPanelActive = false;
    state.audioStreamPanelActive = true;
    render();
  };
  elements.tabs.appendChild(audioBtn);

  state.config.screens.forEach((screen) => {
    const button = document.createElement("button");
    button.className = `top-nav-btn ${!state.audioStreamPanelActive && screen.id === state.selectedScreenId ? "active" : ""}`;
    button.textContent = screen.name;
    button.onclick = () => {
      state.audioStreamPanelActive = false;
      state.programSettingsPanelActive = false;
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

function renderBellTemplateOptions() {
  const current = selectedScreen().bell_schedule_template;
  elements.screenBellTemplate.innerHTML = state.bells.templates
    .map((item) => `<option value="${item.id}" ${item.id === current ? "selected" : ""}>${item.name}</option>`)
    .join("");
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
    };
    elements.sectionTabs.appendChild(button);
  });
}

function renderSectionVisibility() {
  document.querySelectorAll("[data-section]").forEach((block) => {
    block.hidden = block.dataset.section !== state.activeSection;
  });
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
    parts.push(`<p class="hint">${t("w.emergencyHint")}</p>`);
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
    parts.push(widgetToggle(t("w.bold"), widget.settings.bold, `widget:${index}:settings.bold`));
  }
  if (widget.type === "carousel") {
    const selectedIds = new Set(widget.settings.childWidgetIds || []);
    const childOptions = availableCarouselChildren(widget).map((item) => `
      <label class="toggle-label carousel-child-option">
        <input data-key="widget:${index}:settings.childWidgetIds" data-value="${item.id}" type="checkbox" ${selectedIds.has(item.id) ? "checked" : ""}>
        ${item.title}
      </label>
    `).join("");
    const animationOptions = getCarouselAnimations()
      .map((item) => `<option value="${item.id}" ${widget.settings.animation === item.id ? "selected" : ""}>${item.label}</option>`)
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
    parts.push(widgetInput(t("w.speedSec"), widget.settings.speedSec, `widget:${index}:settings.speedSec`, "number", "standard-input"));
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

async function uploadWidgetImage(file, widgetIndex, slotIndex) {
  const formData = new FormData();
  formData.append("file", file);
  const payload = await api("/api/admin/upload-widget-image", { method: "POST", body: formData });
  const w = selectedScreen().widgets[widgetIndex];
  if (!w || w.type !== "image") return;
  coerceWidgetImageSlots(w);
  const slot = Number(slotIndex);
  const i = Number.isFinite(slot) && slot >= 0 ? slot : 0;
  while (w.settings.images.length <= i) {
    w.settings.images.push({ name: tf("w.imageDefaultName", { n: w.settings.images.length + 1 }), url: "" });
  }
  w.settings.images[i].url = payload.path;
  render();
  if (state.widgetModalWidgetId === w.id) syncWidgetModal();
  renderPreview();
}

function bindWidgetEditorEvents(root, index) {
  const screen = selectedScreen();
  const widget = screen.widgets[index];
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
      const w = selectedScreen().widgets[index];
      if (w) w.settings.animation = "random";
      render();
      renderPreview();
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

function closeWidgetModal() {
  state.widgetModalWidgetId = null;
  const modal = elements.widgetEditorModal;
  if (modal) {
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
  }
}

function syncWidgetModal() {
  const id = state.widgetModalWidgetId;
  const modal = elements.widgetEditorModal;
  const body = elements.widgetEditorModalBody;
  const titleEl = elements.widgetEditorModalTitle;
  if (!modal || !body || !titleEl) return;
  if (!id) {
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
    return;
  }
  const screen = selectedScreen();
  const index = screen.widgets.findIndex((w) => w.id === id);
  if (index < 0) {
    closeWidgetModal();
    return;
  }
  const widget = screen.widgets[index];
  titleEl.textContent = `${widgetDisplayTitle(widget)} · ${widget.type}`;
  body.innerHTML = widgetEditorInnerHtml(widget, index);
  bindWidgetEditorEvents(body, index);
  modal.hidden = false;
  modal.setAttribute("aria-hidden", "false");
}

function openWidgetModal(widgetId) {
  state.widgetModalWidgetId = widgetId;
  syncWidgetModal();
}

function bindWidgetModalOnce() {
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
    else if (state.programSettingsPanelActive) closeProgramSettingsModal();
  });
}

function renderWidgets() {
  const screen = selectedScreen();
  elements.widgetList.innerHTML = "";
  screen.widgets
    .filter((widget) => !isWidgetTypeHiddenInAdminPalette(widget.type))
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
    elements.screenBgRotateInterval.value = String(Number.isFinite(iv) ? iv : 3600);
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

function renderWeekdayBellGrid() {
  const screen = selectedScreen();
  const mapping = screen.weekday_bell_templates || {};
  const templateOptions = state.bells.templates
    .map((item) => `<option value="${escapeHtmlAttr(String(item.id))}">${escapeHtml(String(item.name || ""))}</option>`)
    .join("");
  elements.bellWeekdayGrid.innerHTML = getWeekdayOptions().map((day) => `
    <label title="${day.title || day.label}">
      ${day.label}
      <select class="standard-input" data-weekday="${day.id}">
        <option value="">${t("weekday.defaultTemplate")}</option>
        ${templateOptions}
      </select>
    </label>
  `).join("");
  elements.bellWeekdayGrid.querySelectorAll("[data-weekday]").forEach((select) => {
    select.value = mapping[select.dataset.weekday] || "";
    select.onchange = (event) => {
      const weekday = event.target.dataset.weekday;
      const value = event.target.value;
      if (!screen.weekday_bell_templates) screen.weekday_bell_templates = {};
      if (value) screen.weekday_bell_templates[weekday] = value;
      else delete screen.weekday_bell_templates[weekday];
    };
  });
}

function renderHistory() {
  if (!elements.historyList) return;
  const loc = window.GuardSchoolI18n?.getLang?.() === "en" ? "en-US" : "ru-RU";
  const verHint = state.appVersion
    ? `<p class="hint history-app-ver">${t("history.currentVersion")} <strong>${escapeHtmlAttr(state.appVersion)}</strong></p>`
    : "";
  if (!state.history.length) {
    elements.historyList.innerHTML = `${verHint}<div class="hint">${t("history.empty")}</div>`;
    return;
  }
  elements.historyList.innerHTML =
    verHint +
    state.history
      .map((item) => {
        const rawTs = item.timestamp;
        let ts = "—";
        if (rawTs) {
          const d = new Date(rawTs);
          ts = Number.isNaN(d.getTime()) ? String(rawTs) : d.toLocaleString(loc);
        }
        const ver = item.version ? String(item.version).trim() : "";
        const verBlock = ver
          ? `<span class="history-ver" title="${escapeHtmlAttr(t("history.versionLabel"))}">${escapeHtmlAttr(ver)}</span>`
          : `<span class="history-ver history-ver-na">${escapeHtmlAttr(t("history.noVersion"))}</span>`;
        return `
    <div class="history-item">
      <div class="history-meta">${verBlock}<span class="history-time">${escapeHtmlAttr(ts)}</span></div>
      <div class="history-msg">${escapeHtmlAttr(String(item.message || ""))}</div>
    </div>`;
      })
      .join("");
}

function addCarousel(sourceIndex) {
  const screen = selectedScreen();
  const source = screen.widgets[sourceIndex];
  const copy = JSON.parse(JSON.stringify(source));
  copy.id = createWidgetId("carousel");
  copy.title = tf("carousel.nameN", { n: screen.widgets.filter((item) => item.type === "carousel").length + 1 });
  copy.x = Math.min(copy.x + 1, GRID.cols - copy.w);
  copy.y = Math.min(copy.y + 1, GRID.rows - copy.h);
  copy.settings.startDelaySec = Number(copy.settings.startDelaySec || 0) + 15;
  screen.widgets.splice(sourceIndex + 1, 0, copy);
  render();
}

function removeCarousel(sourceIndex) {
  const screen = selectedScreen();
  const carouselCount = screen.widgets.filter((item) => item.type === "carousel").length;
  if (carouselCount <= 1) {
    alert(t("alert.oneCarousel"));
    return;
  }
  screen.widgets.splice(sourceIndex, 1);
  render();
}

function bellSoundSelectOptions(selectedVal) {
  const sel = selectedVal || "";
  let html = `<option value="">${escapeHtmlAttr(t("weekday.defaultTemplate"))}</option><option value="-">${escapeHtmlAttr(t("bells.soundNone"))}</option>`;
  (state.bellSoundFiles || []).forEach((f) => {
    html += `<option value="${f.filename}"${f.filename === sel ? " selected" : ""}>${f.filename}</option>`;
  });
  return html;
}

function ensureBellSoundPanel() {
  let panel = document.getElementById("bell-sound-panel");
  if (panel) return panel;
  const bellsCard = document.getElementById("bell-rows")?.closest(".card");
  panel = document.createElement("div");
  panel.id = "bell-sound-panel";
  panel.className = "card-subsection";
  const hint = bellsCard?.querySelector(".hint");
  const rows = document.getElementById("bell-rows");
  if (hint) {
    hint.after(panel);
  } else if (rows && bellsCard) {
    bellsCard.insertBefore(panel, rows);
  } else if (bellsCard) {
    bellsCard.appendChild(panel);
  }
  return panel;
}

function renderBellSoundPanel() {
  const panel = ensureBellSoundPanel();
  if (!panel || !state.bells) return;
  state.bells.sound_defaults = state.bells.sound_defaults || { start: null, end: null };
  const sd = state.bells.sound_defaults;
  const s0 = sd.start || "";
  const s1 = sd.end || "";
  panel.innerHTML = `
    <h3>${t("bells.soundsTitle")}</h3>
    <p class="hint bell-sound-intro">${t("bells.soundsIntro")}</p>
    <div class="bell-upload-row">
      <label class="bell-file-upload">
        <span class="bell-file-upload-main">${t("bells.uploadBell")}</span>
        <span class="bell-file-upload-sub">${t("bells.uploadFormats")}</span>
        <input type="file" id="bell-sound-upload" accept=".mp3,.wav,.ogg,.m4a,.aac,audio/*" hidden>
      </label>
    </div>
    <div class="compact-form-row bell-sound-defaults">
      <label>${t("bells.defIntervalStart")}<select id="bell-def-start" class="standard-input">${bellSoundSelectOptions(s0)}</select></label>
      <label>${t("bells.defIntervalEnd")}<select id="bell-def-end" class="standard-input">${bellSoundSelectOptions(s1)}</select></label>
      <button type="button" class="secondary-btn" id="bell-apply-starts">${t("bells.applyAllStarts")}</button>
      <button type="button" class="secondary-btn" id="bell-apply-ends">${t("bells.applyAllEnds")}</button>
    </div>`;
  panel.querySelector("#bell-def-start").value = s0;
  panel.querySelector("#bell-def-end").value = s1;
  panel.querySelector("#bell-def-start").onchange = (e) => {
    state.bells.sound_defaults.start = e.target.value || null;
  };
  panel.querySelector("#bell-def-end").onchange = (e) => {
    state.bells.sound_defaults.end = e.target.value || null;
  };
  panel.querySelector("#bell-apply-starts").onclick = () => {
    const v = panel.querySelector("#bell-def-start").value;
    selectedBellTemplate().entries.forEach((e) => {
      if (v === "") delete e.sound_start;
      else e.sound_start = v;
    });
    renderBellEditor();
  };
  panel.querySelector("#bell-apply-ends").onclick = () => {
    const v = panel.querySelector("#bell-def-end").value;
    selectedBellTemplate().entries.forEach((e) => {
      if (v === "") delete e.sound_end;
      else e.sound_end = v;
    });
    renderBellEditor();
  };
  panel.querySelector("#bell-sound-upload").onchange = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    const response = await fetch("/api/admin/upload-bell-sound", mergeFetchOptions({ method: "POST", body: fd }));
    if (!response.ok) {
      alert((await response.json().catch(() => ({}))).detail || t("bells.uploadError"));
      return;
    }
    state.bellSoundFiles = (await api("/api/admin/bell-sounds")).files || [];
    renderBellEditor();
    event.target.value = "";
  };
}

function buildBellRows(entries = []) {
  elements.bellRows.innerHTML = "";
  entries.forEach((entry, index) => {
    const row = document.createElement("div");
    row.className = "bell-row";
    const lessonVal = escapeHtmlAttr(String(entry.lesson ?? ""));
    const ss = entry.sound_start || "";
    const se = entry.sound_end || "";
    const startVal = escapeHtmlAttr(String(entry.start ?? ""));
    const endVal = escapeHtmlAttr(String(entry.end ?? ""));
    row.innerHTML = `
      <label class="bell-field-lesson">${t("bells.lessonField")}<input class="standard-input bell-lesson-input" data-bell-index="${index}" data-key="lesson" type="text" autocomplete="off" value="${lessonVal}" placeholder="${escapeHtmlAttr(t("bells.lessonPlaceholder"))}"></label>
      <label>${t("bells.soundStart")}<select data-bell-index="${index}" data-key="sound_start" class="standard-input bell-sound-select">${bellSoundSelectOptions(ss)}</select></label>
      <label>${t("bells.soundEnd")}<select data-bell-index="${index}" data-key="sound_end" class="standard-input bell-sound-select">${bellSoundSelectOptions(se)}</select></label>
      <label>${t("bells.timeStart")}<input class="standard-input" data-bell-index="${index}" data-key="start" type="time" value="${startVal}"></label>
      <label>${t("bells.timeEnd")}<input class="standard-input" data-bell-index="${index}" data-key="end" type="time" value="${endVal}"></label>
      <button type="button" class="secondary-btn" data-remove-bell="${index}">${t("bells.removeRow")}</button>
    `;
    elements.bellRows.appendChild(row);
    row.querySelector('[data-key="sound_start"]').value = ss;
    row.querySelector('[data-key="sound_end"]').value = se;
  });
  const syncBellField = (event) => {
    const template = selectedBellTemplate();
    const idx = Number(event.target.dataset.bellIndex);
    const key = event.target.dataset.key;
    template.entries[idx][key] = event.target.value;
  };
  elements.bellRows.querySelectorAll("input").forEach((input) => {
    input.addEventListener("input", syncBellField);
    input.addEventListener("change", syncBellField);
  });
  elements.bellRows.querySelectorAll("select").forEach((sel) => {
    sel.onchange = (event) => {
      const template = selectedBellTemplate();
      const idx = Number(event.target.dataset.bellIndex);
      const key = event.target.dataset.key;
      const v = event.target.value;
      if (v === "") delete template.entries[idx][key];
      else template.entries[idx][key] = v;
    };
  });
  elements.bellRows.querySelectorAll("[data-remove-bell]").forEach((button) => {
    button.onclick = () => {
      selectedBellTemplate().entries.splice(Number(button.dataset.removeBell), 1);
      renderBellEditor();
    };
  });
}

function renderBellEditor() {
  const template = selectedBellTemplate();
  elements.bellTemplateName.value = template?.name || "";
  if (elements.bellLastLesson) {
    const ll = template?.last_lesson;
    elements.bellLastLesson.value = ll != null && ll !== "" ? String(ll) : "";
  }
  elements.bellDateOverride.value = "";
  renderWeekdayBellGrid();
  renderBellSoundPanel();
  buildBellRows(template.entries || []);
  renderBellTemplateList();
}

function renderBellTemplateList() {
  elements.bellTemplateList.innerHTML = "";
  state.bells.templates.forEach((item) => {
    const div = document.createElement("div");
    div.className = "override-item";
    div.innerHTML = `<span>${tf("bells.templateEntries", { name: escapeHtmlAttr(item.name), n: item.entries.length })}</span>`;
    const button = document.createElement("button");
    button.textContent = t("bells.pickTemplate");
    button.className = "secondary-btn";
    button.onclick = () => {
      selectedScreen().bell_schedule_template = item.id;
      render();
    };
    div.appendChild(button);
    elements.bellTemplateList.appendChild(div);
  });
}

function addBellTemplate() {
  const template = {
    id: createTemplateId(),
    name: tf("bell.templateN", { n: state.bells.templates.length + 1 }),
    entries: [
      { lesson: "1", start: "08:30", end: "09:15" },
      { lesson: "2", start: "09:25", end: "10:10" },
    ],
  };
  state.bells.templates.push(template);
  selectedScreen().bell_schedule_template = template.id;
  render();
}

function deleteBellTemplate() {
  if (state.bells.templates.length <= 1) {
    alert(t("alert.oneBellTemplate"));
    return;
  }
  const currentId = selectedBellTemplate().id;
  state.bells.templates = state.bells.templates.filter((item) => item.id !== currentId);
  Object.keys(state.bells.weekday_overrides).forEach((key) => {
    if (state.bells.weekday_overrides[key] === currentId) delete state.bells.weekday_overrides[key];
  });
  state.bells.date_overrides = state.bells.date_overrides.filter((item) => item.template_id !== currentId);
  const nextId = state.bells.templates[0].id;
  state.config.screens.forEach((screen) => {
    if (screen.bell_schedule_template === currentId) {
      screen.bell_schedule_template = nextId;
    }
    Object.keys(screen.weekday_bell_templates || {}).forEach((key) => {
      if (screen.weekday_bell_templates[key] === currentId) delete screen.weekday_bell_templates[key];
    });
  });
  render();
}

async function fetchPreviewPayloadOnce() {
  const screen = selectedScreen();
  if (!screen || !window.GuardSchoolScreen) return;
  try {
    const res = await api("/api/admin/preview-payload", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ screen }),
    });
    state.previewCache = {
      schedule: res.schedule,
      holidays: res.holidays,
      background_gallery: res.background_gallery || [],
      announcements: res.announcements || [],
      marquee: res.marquee || [],
      pc_audio_preview: res.pc_audio_preview || null,
      display: res.display || null,
    };
    state.previewCacheScreenId = screen.id;
    if (state.activeSection === "preview") {
      renderPreview();
    }
  } catch (e) {
    state.previewCache = null;
    if (state.activeSection === "preview") {
      elements.preview.innerHTML = `<p class="hint">${tf("preview.errorDetail", { base: t("preview.error"), msg: escapeHtmlAttr(String(e.message || e)) })}</p>`;
    }
  }
}

function pointerToGrid(event, rect) {
  return {
    col: Math.max(0, Math.min(GRID.cols - 1, Math.floor(((event.clientX - rect.left) / rect.width) * GRID.cols))),
    row: Math.max(0, Math.min(GRID.rows - 1, Math.floor(((event.clientY - rect.top) / rect.height) * GRID.rows))),
  };
}

function startDrag(event, widgetIndex) {
  const widget = selectedScreen().widgets[widgetIndex];
  if (widget && widget.type === "emergency") return;
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

function handlePointerMove(event) {
  if (!state.drag) return;
  const rect = elements.preview.getBoundingClientRect();
  const point = pointerToGrid(event, rect);
  const widget = selectedScreen().widgets[state.drag.widgetIndex];
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

function stopDrag() {
  state.drag = null;
  renderPreview();
}

function renderGridHighlight(preview) {
  if (!state.drag) return;
  const widget = selectedScreen().widgets[state.drag.widgetIndex];
  const highlight = document.createElement("div");
  highlight.className = "grid-highlight";
  highlight.style.gridColumn = `${widget.x + 1} / span ${widget.w}`;
  highlight.style.gridRow = `${widget.y + 1} / span ${widget.h}`;
  preview.appendChild(highlight);
}

/** Сборка строк предпросмотра звука: i18n-события с бэкенда или fallback на legacy lines. */
function formatPreviewPcAudioLines(soundDiag) {
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
  state.programSettingsPanelActive = false;
  render();
}

function renderPreview() {
  const G = window.GuardSchoolScreen;
  const screen = selectedScreen();
  if (!screen || !G) return;
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
    elements.preview.innerHTML = `<p class="hint">${t("preview.loading")}</p>`;
    fetchPreviewPayloadOnce();
    return;
  }

  const { schedule, holidays, announcements, marquee, background_gallery: previewGallery, pc_audio_preview: soundDiag } = state.previewCache;
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
  const bgU = G.resolveBackgroundImageUrl ? G.resolveBackgroundImageUrl(screen, gal) : screen.background_image || "";
  elements.preview.style.background = bgU ? `url(${bgU}) center/cover` : "";
  if (G.applyTvTextOutline) G.applyTvTextOutline(elements.preview, screen);

  const hiddenWidgetIds = G.widgetIdsHiddenByCarousel(screen);
  const preview = document.createElement("div");
  preview.className = "screen-grid";
  if (state.drag) {
    preview.classList.add("show-grid");
  }
  renderGridHighlight(preview);
  const ordered = G.sortWidgetsForDom ? G.sortWidgetsForDom(screen) : screen.widgets;
  ordered.forEach((widget) => {
    if (widget.enabled === false) return;
    if (hiddenWidgetIds.has(widget.id) && widget.type !== "carousel") return;
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
      G.startCarousel(item, widget, childWidgets, schedule, screen, holidays, announcements || [], marquee || []);
    } else {
      item.innerHTML = G.renderWidgetHtml(widget, schedule, screen, holidays, announcements || [], marquee || []);
    }
    if (G.applyWidgetBackdropClass) G.applyWidgetBackdropClass(item, widget);
    if (widget.type !== "emergency") item.onpointerdown = (event) => startDrag(event, index);
    preview.appendChild(item);
  });
  elements.preview.innerHTML = "";
  elements.preview.appendChild(preview);
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

function renderOverrides() {
  elements.overrideList.innerHTML = "";
  state.overrides.forEach((item, index) => {
    const div = document.createElement("div");
    div.className = "override-item";
    div.innerHTML = `<span>${tf("override.row", {
      date: escapeHtmlAttr(String(item.date)),
      class: escapeHtmlAttr(String(item.class_name)),
      lesson: escapeHtmlAttr(String(item.lesson_index)),
      subject: escapeHtmlAttr(String(item.subject)),
    })}</span>`;
    const button = document.createElement("button");
    button.textContent = t("override.delete");
    button.className = "secondary-btn";
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
  const programPanel = elements.programSettingsPanel;

  renderTabs();

  if (state.programSettingsPanelActive) {
    state.audioStreamPanelActive = false;
    if (elements.deleteScreenBtn) {
      elements.deleteScreenBtn.hidden = true;
      elements.deleteScreenBtn.disabled = true;
    }
    if (elements.duplicateScreenBtn) elements.duplicateScreenBtn.hidden = true;
    if (tabPanel) tabPanel.style.display = "none";
    if (screenWrap) screenWrap.hidden = true;
    if (audioPanel) audioPanel.hidden = true;
    if (programPanel) {
      programPanel.hidden = false;
      programPanel.setAttribute("aria-hidden", "false");
    }
    syncEmergencyModeCheckbox();
    renderHistory();
    elements.programSettingsOpenBtn?.classList.add("active");
    window.GuardSchoolScreen?.clearAllTimers();
    return;
  }

  if (programPanel) {
    programPanel.hidden = true;
    programPanel.setAttribute("aria-hidden", "true");
  }
  elements.programSettingsOpenBtn?.classList.remove("active");

  if (state.audioStreamPanelActive) {
    if (elements.deleteScreenBtn) {
      elements.deleteScreenBtn.hidden = true;
      elements.deleteScreenBtn.disabled = true;
    }
    if (elements.duplicateScreenBtn) elements.duplicateScreenBtn.hidden = true;
    if (tabPanel) tabPanel.style.display = "none";
    if (screenWrap) screenWrap.hidden = true;
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
    return;
  }

  clearInterval(window.__streamStatusInterval);
  if (tabPanel) tabPanel.style.display = "";
  if (screenWrap) screenWrap.hidden = false;
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
  syncEmergencyModeCheckbox();
}

function updateWidgetField(path, value) {
  const [, indexRaw, fieldRaw] = path.match(/^widget:(\d+):(.+)$/);
  const widget = selectedScreen().widgets[Number(indexRaw)];
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
      const m = key.match(/^images\.(\d+)\.(name|url)$/);
      const idx = Number(m[1]);
      const sub = m[2];
      if (!Array.isArray(widget.settings.images)) widget.settings.images = [];
      while (widget.settings.images.length <= idx) {
        widget.settings.images.push({ name: "", url: "" });
      }
      if (!widget.settings.images[idx] || typeof widget.settings.images[idx] !== "object") {
        widget.settings.images[idx] = { name: "", url: "" };
      }
      widget.settings.images[idx][sub] = value;
    } else if (["fontSize", "titleFontSize", "startDelaySec", "count", "speedSec", "rotateSec", "opacity", "imagesRotateSec"].includes(key)) {
      const num = Number(value);
      if (key === "opacity") {
        widget.settings[key] = value === "" || !Number.isFinite(num) ? 85 : Math.max(0, Math.min(100, num));
      } else if (key === "imagesRotateSec") {
        widget.settings[key] = value === "" || !Number.isFinite(num) ? 0 : Math.max(0, Math.min(600, Math.round(num)));
      } else {
        widget.settings[key] = num;
      }
    }
    else if (key === "backdrop" || key === "useManual" || key === "advanceOnShow" || key === "randomize") widget.settings[key] = Boolean(value);
    else widget.settings[key] = value;
  } else {
    widget[fieldRaw] = fieldRaw === "enabled" ? Boolean(value) : Number(value);
  }
  clampWidget(widget);
  render();
}

function bindForm() {
  elements.screenName.oninput = (event) => { selectedScreen().name = event.target.value; renderTabs(); };
  elements.screenSlug.oninput = (event) => { selectedScreen().slug = event.target.value; };
  elements.screenIpNote.oninput = (event) => { selectedScreen().ip_note = event.target.value; };
  elements.screenPollInterval.oninput = (event) => { selectedScreen().poll_interval_sec = Number(event.target.value); };
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
}

function addScreen() {
  const index = state.config.screens.length + 1;
  const screen = createDefaultScreen(index);
  state.config.screens.push(screen);
  state.audioStreamPanelActive = false;
  state.programSettingsPanelActive = false;
  closeWidgetModal();
  state.selectedScreenId = screen.id;
  render();
}

async function uploadBackground(file) {
  const formData = new FormData();
  formData.append("file", file);
  const payload = await api("/api/admin/upload-background", { method: "POST", body: formData });
  selectedScreen().background_image = payload.path;
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

async function uploadScheduleDated(file) {
  const formData = new FormData();
  formData.append("file", file);
  const payload = await api("/api/admin/upload-schedule", { method: "POST", body: formData });
  const snapshot = await api("/api/admin/schedule");
  state.schedule = snapshot.schedule || [];
  state.fullScheduleRows = snapshot.full_schedule_rows;
  state.scheduleSampleRows = snapshot.schedule_sample_rows;
  state.history = snapshot.history || [];
  state.appVersion = snapshot.app_version || state.appVersion;
  alert(tf("alert.uploadDated", { n: payload.rows }));
  render();
}

async function uploadFullSchedule(file) {
  const formData = new FormData();
  formData.append("file", file);
  const payload = await api("/api/admin/upload-full-schedule", { method: "POST", body: formData });
  const snapshot = await api("/api/admin/schedule");
  state.schedule = snapshot.schedule || [];
  state.fullScheduleRows = snapshot.full_schedule_rows;
  state.scheduleSampleRows = snapshot.schedule_sample_rows;
  state.history = snapshot.history || [];
  state.appVersion = snapshot.app_version || state.appVersion;
  alert(tf("alert.uploadFull", { n: payload.rows }));
  render();
}

async function uploadScheduleSample(file) {
  const formData = new FormData();
  formData.append("file", file);
  const payload = await api("/api/admin/upload-schedule-sample", { method: "POST", body: formData });
  const snapshot = await api("/api/admin/schedule");
  state.schedule = snapshot.schedule || [];
  state.fullScheduleRows = snapshot.full_schedule_rows;
  state.scheduleSampleRows = snapshot.schedule_sample_rows;
  state.history = snapshot.history || [];
  state.appVersion = snapshot.app_version || state.appVersion;
  alert(tf("alert.uploadSample", { n: payload.rows }));
  render();
}

async function uploadHolidays(file) {
  const formData = new FormData();
  formData.append("file", file);
  const payload = await api("/api/admin/upload-holidays", { method: "POST", body: formData });
  const snapshot = await api("/api/admin/schedule");
  state.schedule = snapshot.schedule || [];
  state.overrides = snapshot.overrides || [];
  state.announcements = snapshot.announcements || [];
  alert(tf("alert.uploadHolidays", { n: payload.rows }));
  render();
}

async function uploadAnnouncements(file) {
  const formData = new FormData();
  formData.append("file", file);
  const payload = await api("/api/admin/upload-announcements", { method: "POST", body: formData });
  const snapshot = await api("/api/admin/schedule");
  state.announcements = snapshot.announcements || [];
  alert(tf("alert.uploadAnnounce", { n: payload.rows }));
  render();
}

async function uploadMarquee(file) {
  const formData = new FormData();
  formData.append("file", file);
  const payload = await api("/api/admin/upload-marquee", { method: "POST", body: formData });
  const snapshot = await api("/api/admin/schedule");
  state.marquee = snapshot.marquee || [];
  alert(tf("alert.uploadMarquee", { n: payload.rows }));
  render();
}

async function exportWeeklyScheduleZip() {
  const stamp = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, "");
  await downloadBinaryFile("/api/admin/export-weekly-schedule", `guardschool_weekly_schedule_${stamp}.zip`);
}

async function importWeeklyScheduleZip(file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await api("/api/admin/import-weekly-schedule", { method: "POST", body: formData });
  const snapshot = await api("/api/admin/schedule");
  state.schedule = snapshot.schedule || [];
  state.fullScheduleRows = snapshot.full_schedule_rows;
  state.scheduleSampleRows = snapshot.schedule_sample_rows;
  state.history = snapshot.history || [];
  state.appVersion = snapshot.app_version || state.appVersion;
  alert(tf("alert.importWeek", { full: res.full_schedule_rows ?? "—", sample: res.schedule_sample_rows ?? "—" }));
  render();
}

async function downloadWeeklyScheduleTemplateXlsx() {
  await downloadBinaryFile("/api/admin/weekly-schedule-template.xlsx", "full_schedule_sample.xlsx");
}

async function importBundle(file) {
  const formData = new FormData();
  formData.append("file", file);
  await api("/api/admin/import", { method: "POST", body: formData });
  alert(t("alert.importDone"));
  window.location.reload();
}

function addBellRow() {
  selectedBellTemplate().entries.push({
    lesson: String(selectedBellTemplate().entries.length + 1),
    start: "08:30",
    end: "09:15",
  });
  renderBellEditor();
}

function flushBellEditorFromDom() {
  if (!elements.bellRows || !state.bells) return;
  const template = selectedBellTemplate();
  if (!template?.entries?.length) return;
  elements.bellRows.querySelectorAll("[data-bell-index][data-key]").forEach((el) => {
    const idx = Number(el.dataset.bellIndex);
    const key = el.dataset.key;
    if (!Number.isFinite(idx) || idx < 0 || idx >= template.entries.length) return;
    const v = el.value;
    if (key === "sound_start" || key === "sound_end") {
      if (v === "") delete template.entries[idx][key];
      else template.entries[idx][key] = v;
    } else {
      template.entries[idx][key] = v;
    }
  });
}

function saveBellEditorToState() {
  flushBellEditorFromDom();
  const template = selectedBellTemplate();
  template.name = elements.bellTemplateName.value.trim() || template.name;
  if (elements.bellLastLesson) {
    const raw = elements.bellLastLesson.value.trim();
    if (raw === "") template.last_lesson = null;
    else {
      const n = Number(raw);
      template.last_lesson = Number.isFinite(n) ? Math.max(1, Math.min(24, Math.round(n))) : null;
    }
  }
  const dateOverride = elements.bellDateOverride.value;
  if (dateOverride) {
    state.bells.date_overrides = state.bells.date_overrides.filter((item) => item.date !== dateOverride);
    state.bells.date_overrides.push({ date: dateOverride, template_id: template.id, name: `${template.name} (${dateOverride})`, entries: template.entries.map((item) => ({ ...item })) });
  }
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
  if (!date || !className || !lessonIndex || !subject) return alert(t("alert.fillOverride"));
  state.overrides.push({ date, class_name: className, class_key: className.toLowerCase(), lesson_index: lessonIndex, subject });
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
  bindEmergencyModeOnce();
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

window.addEventListener("pointermove", handlePointerMove);
window.addEventListener("pointerup", stopDrag);

init().catch((error) => {
  const msg = String(error.message || "");
  alert(msg);
  if (/вход|Sign in|Session/i.test(msg)) window.location.href = "/login";
});