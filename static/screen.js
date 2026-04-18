function getSlug() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  return parts.length ? parts[parts.length - 1] : "";
}

/** Часть ТВ-браузеров без CSS.escape (нужен для мягкого обновления по data-widget-id). */
function gsCssEscape(ident) {
  try {
    if (typeof CSS !== "undefined" && typeof CSS.escape === "function") return CSS.escape(String(ident));
  } catch (_) {}
  return String(ident).replace(/[^a-zA-Z0-9_-]/g, "\\$&");
}

/** Стабильный id клиента для статистики (localStorage). */
function getGsClientId() {
  try {
    let id = localStorage.getItem("gs_client_id");
    if (!id || id.length < 8) {
      id =
        (typeof crypto !== "undefined" && crypto.randomUUID && crypto.randomUUID()) ||
        `g${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
      localStorage.setItem("gs_client_id", id);
    }
    return id;
  } catch (_) {
    return `t${Date.now().toString(36)}`;
  }
}

/** Подпись места (из URL ?gs_label=…), передаётся на сервер при каждом опросе. */
function getGsLabelForPoll() {
  try {
    if (window.__gsScreenLabelCached !== undefined) return window.__gsScreenLabelCached;
    const q = new URLSearchParams(window.location.search).get("gs_label");
    window.__gsScreenLabelCached = q ? q.trim().slice(0, 120) : "";
    return window.__gsScreenLabelCached;
  } catch (_) {
    return "";
  }
}

/** Параметры гибрида: primary/fallback API и токен ТВ (из URL один раз → localStorage). */
function initGsHybridFromUrl() {
  try {
    const q = new URLSearchParams(window.location.search);
    const p = q.get("gs_primary_base");
    const f = q.get("gs_fallback_base");
    const to = q.get("gs_poll_timeout_sec");
    const tok = q.get("gs_tv_token");
    if (p && p.trim()) {
      window.__GS_PRIMARY_BASE = p.trim().replace(/\/$/, "");
      try {
        localStorage.setItem("gs_primary_base", window.__GS_PRIMARY_BASE);
      } catch (_) {}
    }
    if (f && f.trim()) {
      window.__GS_FALLBACK_BASE = f.trim().replace(/\/$/, "");
      try {
        localStorage.setItem("gs_fallback_base", window.__GS_FALLBACK_BASE);
      } catch (_) {}
    }
    if (to != null && String(to).trim() !== "") {
      const sec = Number(to);
      if (Number.isFinite(sec)) window.__GS_POLL_TIMEOUT_MS = Math.max(2000, Math.min(120000, sec * 1000));
    }
    if (tok && tok.trim()) {
      try {
        localStorage.setItem("gs_tv_bearer", tok.trim());
      } catch (_) {}
      q.delete("gs_tv_token");
      const ns = q.toString();
      const url = window.location.pathname + (ns ? `?${ns}` : "") + window.location.hash;
      window.history.replaceState({}, "", url);
    }
  } catch (_) {}
  try {
    if (!window.__GS_PRIMARY_BASE) window.__GS_PRIMARY_BASE = localStorage.getItem("gs_primary_base") || "";
    if (!window.__GS_FALLBACK_BASE) window.__GS_FALLBACK_BASE = localStorage.getItem("gs_fallback_base") || "";
  } catch (_) {}
}

initGsHybridFromUrl();

// Быстрый «удалённый» сброс кэша/настроек для конкретного экрана:
// удобно, когда устройство (телефон) застряло на старых localStorage значениях (gs_mw/gs_mobile/gs_classes или base URL).
// Использование: добавить в адрес `?gs_reset=1` (параметр удалится сам).
(function maybeResetDevicePrefsOnce() {
  try {
    const slug = getSlug();
    if (!slug) return;
    const q = new URLSearchParams(window.location.search || "");
    if (q.get("gs_reset") !== "1") return;
    try {
      clearDevicePrefs(slug);
    } catch (_) {}
    try {
      localStorage.removeItem("gs_primary_base");
      localStorage.removeItem("gs_fallback_base");
      // bearer тоже может мешать (например, если устарел) — сбрасываем при явном reset
      localStorage.removeItem("gs_tv_bearer");
    } catch (_) {}
    q.delete("gs_reset");
    const ns = q.toString();
    const url = window.location.pathname + (ns ? `?${ns}` : "") + window.location.hash;
    window.history.replaceState({}, "", url);
    window.location.reload();
  } catch (_) {}
})();

function getGsTvBearer() {
  try {
    return (localStorage.getItem("gs_tv_bearer") || "").trim();
  } catch (_) {
    return "";
  }
}

function ensureDeviceSettingsUi() {
  try {
    if (document.getElementById("gs-device-settings-btn")) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.id = "gs-device-settings-btn";
    btn.className = "gs-device-settings-btn";
    btn.setAttribute("aria-label", "Настройки устройства");
    btn.textContent = "⚙";

    const panel = document.createElement("div");
    panel.id = "gs-device-settings-panel";
    panel.className = "gs-device-settings-panel";
    panel.hidden = true;
    panel.innerHTML = `
      <div class="gs-device-settings-head">
        <div class="gs-device-settings-title">Настройки для этого устройства</div>
        <button type="button" class="gs-device-settings-close" id="gs-device-settings-close">Закрыть</button>
      </div>
      <div class="gs-device-settings-row">
        <label for="gs-device-classes">Классы (через запятую)</label>
        <input id="gs-device-classes" class="gs-device-settings-input" placeholder="например: 6, 9, 11" />
      </div>
      <div class="gs-device-settings-row">
        <label>Режим</label>
        <div class="gs-device-settings-checks">
          <label class="opt"><input type="checkbox" id="gs-device-mobile" /> <span>Мобильный режим (лента со скроллом)</span></label>
          <label class="opt"><input type="checkbox" id="gs-device-persist" /> <span>Сохранять настройки на этом устройстве</span></label>
        </div>
      </div>
      <div class="gs-device-settings-row">
        <label>Виджеты (по типам)</label>
        <div id="gs-device-widgets" class="gs-device-settings-checks"></div>
      </div>
      <div class="gs-device-settings-actions">
        <button type="button" class="gs-device-btn-primary" id="gs-device-apply">Применить</button>
        <button type="button" class="gs-device-btn-secondary" id="gs-device-reset">Сбросить</button>
      </div>
    `;

    document.body.appendChild(btn);
    document.body.appendChild(panel);

    const toggle = (show) => {
      panel.hidden = !show;
    };
    btn.addEventListener("click", () => toggle(panel.hidden));
    const closeBtn = panel.querySelector("#gs-device-settings-close");
    if (closeBtn) closeBtn.addEventListener("click", () => toggle(false));
    document.addEventListener(
      "pointerdown",
      (ev) => {
        try {
          if (panel.hidden) return;
          if (panel.contains(ev.target) || btn.contains(ev.target)) return;
          toggle(false);
        } catch (_) {}
      },
      { capture: true }
    );
  } catch (_) {}
}

function devicePrefsKey(slug) {
  return `gs_device_prefs_${slug}`;
}

function loadDevicePrefs(slug) {
  try {
    const raw = localStorage.getItem(devicePrefsKey(slug));
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (_) {
    return null;
  }
}

function saveDevicePrefs(slug, prefs) {
  try {
    localStorage.setItem(devicePrefsKey(slug), JSON.stringify(prefs || {}));
  } catch (_) {}
}

function clearDevicePrefs(slug) {
  try {
    localStorage.removeItem(devicePrefsKey(slug));
  } catch (_) {}
  try {
    localStorage.removeItem(`gs_classes_${slug}`);
    localStorage.removeItem(`gs_mobile_${slug}`);
    localStorage.removeItem(`gs_mw_${slug}`);
  } catch (_) {}
}

function getGsMobileWidgetsForPoll(slug) {
  try {
    const q = new URLSearchParams(window.location.search || "");
    const v = (q.get("gs_mw") || "").trim();
    if (v) {
      localStorage.setItem(`gs_mw_${slug}`, v);
      return v;
    }
    return (localStorage.getItem(`gs_mw_${slug}`) || "").trim();
  } catch (_) {
    return "";
  }
}

function screenPollUrl(base, slug, cid, lab, dev) {
  const classes = getGsClassesForPoll(slug);
  const mobile = getGsMobileForPoll(slug);
  const mw = getGsMobileWidgetsForPoll(slug);
  const qs = `ts=${Date.now()}&gs_client=${cid}&gs_label=${lab}&gs_device=${dev}`
    + (classes ? `&gs_classes=${encodeURIComponent(classes)}` : "")
    + (mobile ? `&gs_mobile=1` : "")
    + (mw ? `&gs_mw=${encodeURIComponent(mw)}` : "");
  const path = `/api/screen/${encodeURIComponent(slug)}?${qs}`;
  if (!base) return path;
  return `${String(base).replace(/\/$/, "")}${path}`;
}

function getGsMobileForPoll(slug) {
  try {
    const q = new URLSearchParams(window.location.search || "");
    if (q.get("gs_mobile") === "1") {
      localStorage.setItem(`gs_mobile_${slug}`, "1");
      return true;
    }
    const raw = localStorage.getItem(`gs_mobile_${slug}`) || "";
    return raw === "1";
  } catch (_) {
    return false;
  }
}

function getGsClassesForPoll(slug) {
  try {
    const q = new URLSearchParams(window.location.search || "");
    const v = (q.get("gs_classes") || "").trim();
    if (v) {
      localStorage.setItem(`gs_classes_${slug}`, v);
      return v;
    }
    return (localStorage.getItem(`gs_classes_${slug}`) || "").trim();
  } catch (_) {
    return "";
  }
}

async function fetchScreenPayload(url, headers, timeoutMs) {
  const ac = new AbortController();
  const to = window.setTimeout(() => ac.abort(), timeoutMs);
  try {
    return await fetch(url, {
      cache: "no-store",
      signal: ac.signal,
      headers,
    });
  } finally {
    window.clearTimeout(to);
  }
}

/**
 * Краткая подпись устройства для статистики (не hostname ОС — браузер его не отдаёт).
 * Chromium: Client Hints (модель телефона и т.п.). Иначе — platform / грубая эвристика по UA.
 */
async function resolveGsDeviceHintOnce() {
  if (window.__gsDeviceHintPromise) return window.__gsDeviceHintPromise;
  window.__gsDeviceHintPromise = (async () => {
    try {
      const parts = [];
      try {
        const uad = navigator.userAgentData;
        if (uad && typeof uad.getHighEntropyValues === "function") {
          const h = await uad.getHighEntropyValues([
            "platform",
            "platformVersion",
            "model",
            "mobile",
          ]);
          if (h.platform) parts.push(String(h.platform));
          const model = h.model && String(h.model).trim();
          if (model && model.toLowerCase() !== "unknown") parts.push(model);
          else if (h.platformVersion) parts.push(String(h.platformVersion));
          if (h.mobile === true) parts.push("mobile");
        } else if (navigator.platform) {
          parts.push(navigator.platform);
        }
      } catch (_) {}
      if (!parts.length) {
        try {
          const ua = navigator.userAgent || "";
          parts.push(/Mobile|Android|iPhone|iPad/i.test(ua) ? "mobile" : "desktop");
        } catch (_) {
          parts.push("unknown");
        }
      }
      return parts.filter(Boolean).join(" / ").slice(0, 160);
    } catch (_) {
      return "unknown";
    }
  })();
  return window.__gsDeviceHintPromise;
}

/** Календарная дата в часовом поясе браузера (не UTC — иначе звонки «молчат» вечером по России). */
function localCalendarISO(d = new Date()) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

const playedBellKeys = new Set();
let bellAudioDay = null;

let screenAudioUnlocked = false;
let emergencyAudioEl = null;
let emergencyAudioUrl = "";

let lastRenderOkAt = Date.now();

function showCrashBanner(msg) {
  try {
    const el = document.getElementById("gs-crash-banner");
    if (!el) return;
    el.textContent = String(msg || "Ошибка на экране").slice(0, 600);
    el.hidden = false;
  } catch (_) {}
}

function hideCrashBanner() {
  try {
    const el = document.getElementById("gs-crash-banner");
    if (el) el.hidden = true;
  } catch (_) {}
}

window.addEventListener("error", (ev) => {
  try {
    const m = ev && (ev.message || (ev.error && ev.error.message)) ? (ev.message || ev.error.message) : "JS error";
    showCrashBanner(`Ошибка JS: ${m}`);
  } catch (_) {}
});

window.addEventListener("unhandledrejection", (ev) => {
  try {
    const r = ev && ev.reason ? ev.reason : null;
    const m = r && r.message ? r.message : String(r || "promise rejected");
    showCrashBanner(`Ошибка Promise: ${m}`);
  } catch (_) {}
});

function unlockScreenAudio() {
  if (screenAudioUnlocked) return;
  screenAudioUnlocked = true;
  const hint = document.getElementById("gs-audio-hint");
  if (hint) hint.hidden = true;
  try {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (AC) {
      const ctx = new AC();
      ctx.resume().catch(() => {});
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      gain.gain.value = 0.0001;
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.06);
    }
  } catch (_) {}
  try {
    const a = new Audio(
      "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAIlYAAESsAAACABAAZGF0YQAAAAA="
    );
    a.volume = 0.001;
    a.play().catch(() => {});
  } catch (_) {}
  try {
    if (window.__lastScreenPayload) tickEmergencyAudio(window.__lastScreenPayload);
  } catch (_) {}
}

["click", "touchstart", "keydown"].forEach((ev) => {
  document.addEventListener(ev, unlockScreenAudio, { capture: true, passive: true });
});

function parseTimeToMinutes(t) {
  const s = String(t).trim();
  const parts = s.split(":");
  if (parts.length < 2) return NaN;
  const h = Number(parts[0]);
  const m = Number(parts[1]);
  if (!Number.isFinite(h) || !Number.isFinite(m)) return NaN;
  return h * 60 + m;
}

/**
 * «Сейчас» на школьных часах: как `wall_clock_minutes_for_config` на сервере (timezone + clock_offset).
 * Раньше tickBellAudio брал getHours()/getMinutes() устройства — при другом поясе/смещении звонок совпадал с одним
 * набором интервалов, а подпись «до звонка» / заголовок расписания (с сервера) — с другим.
 */
function schoolWallClockPartsFromDisplay(display) {
  const disp = display || {};
  const tz = String(disp.timezone || "Europe/Moscow").trim() || "Europe/Moscow";
  let off = Number(disp.clock_offset_minutes || 0);
  if (!Number.isFinite(off)) off = 0;
  off = Math.max(-720, Math.min(720, Math.round(off)));
  const inst = new Date(Date.now() + off * 60 * 1000);
  try {
    const parts = new Intl.DateTimeFormat("en-GB", {
      timeZone: tz,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).formatToParts(inst);
    const take = (type) => {
      const p = parts.find((x) => x.type === type);
      const n = p ? Number(p.value) : NaN;
      return Number.isFinite(n) ? n : 0;
    };
    const hour = take("hour");
    const minute = take("minute");
    const second = take("second");
    return { mins: hour * 60 + minute, secs: second };
  } catch (_) {
    return { mins: inst.getHours() * 60 + inst.getMinutes(), secs: inst.getSeconds() };
  }
}

function bellMediaUrl(u) {
  if (!u) return u;
  const s = String(u).trim();
  if (s.startsWith("data:") || s.startsWith("blob:")) return s;
  if (/^https?:\/\//i.test(s)) return s;
  try {
    return new URL(s, window.location.origin).href;
  } catch (_) {
    return s;
  }
}

let bellAudioQueue = Promise.resolve();

function playOneBellClip(url, key) {
  return new Promise((resolve) => {
    if (!url) {
      resolve();
      return;
    }
    let settled = false;
    const a = new Audio(bellMediaUrl(url));
    a.volume = 1;
    const finish = () => {
      if (settled) return;
      settled = true;
      try {
        a.removeAttribute("src");
        a.load();
      } catch (_) {}
      resolve();
    };
    const safety = window.setTimeout(finish, 120000);
    a.addEventListener("ended", () => {
      window.clearTimeout(safety);
      finish();
    });
    a.addEventListener("error", () => {
      window.clearTimeout(safety);
      finish();
    });
    a.play()
      .then(() => {
        if (key) playedBellKeys.add(key);
      })
      .catch(() => {
        window.clearTimeout(safety);
        finish();
      });
  });
}

/** Несколько звонков в одну минуту (конец интервала + начало следующего) — иначе второй play() часто не слышен. */
function enqueueBellClips(items) {
  if (!items.length) return;
  const gapMs = 350;
  bellAudioQueue = bellAudioQueue.then(async () => {
    for (const item of items) {
      const url = typeof item === "string" ? item : item.url;
      const key = typeof item === "string" ? null : item.key;
      await playOneBellClip(url, key);
      await new Promise((r) => setTimeout(r, gapMs));
    }
  });
}

function tickBellAudio(payload) {
  const ba = payload.bell_audio;
  if (!ba || !ba.entries || !ba.entries.length) return;
  const scheduleDay = ba.day;
  if (!scheduleDay) return;
  if (bellAudioDay !== scheduleDay) {
    playedBellKeys.clear();
    bellAudioDay = scheduleDay;
  }
  const { mins, secs } = schoolWallClockPartsFromDisplay(payload.display);
  let secWin = Number(ba.trigger_sec_window);
  if (!Number.isFinite(secWin)) secWin = 25;
  secWin = Math.max(5, Math.min(55, secWin));

  const clips = [];
  ba.entries.forEach((row) => {
    const st = parseTimeToMinutes(row.start);
    const en = parseTimeToMinutes(row.end);
    if (!Number.isFinite(st) || !Number.isFinite(en)) return;
    const base = `${scheduleDay}_${row.index}`;
    if (mins === st && secs < secWin && row.sound_start) {
      const k = `${base}_s`;
      if (!playedBellKeys.has(k)) {
        clips.push({ url: row.sound_start, key: k });
      }
    }
    if (mins === en && secs < secWin && row.sound_end) {
      const k = `${base}_e`;
      if (!playedBellKeys.has(k)) {
        clips.push({ url: row.sound_end, key: k });
      }
    }
  });
  if (clips.length) enqueueBellClips(clips);
}

function resolveEmergencySoundState(payload) {
  try {
    const screen = payload && payload.screen;
    const widgets = (screen && screen.widgets) || [];
    const w = widgets.find((x) => x && x.type === "emergency" && x.enabled !== false);
    if (!w) return { shouldPlay: false, url: "" };
    const s = w.settings || {};
    const enabled = s.soundEnabled === true;
    const url = String(s.soundUrl || "").trim();
    if (!enabled || !url) return { shouldPlay: false, url: "" };
    return { shouldPlay: true, url };
  } catch (_) {
    return { shouldPlay: false, url: "" };
  }
}

function stopEmergencyAudio() {
  try {
    if (!emergencyAudioEl) return;
    emergencyAudioEl.pause();
    emergencyAudioEl.loop = false;
    emergencyAudioEl.removeAttribute("src");
    emergencyAudioEl.load();
  } catch (_) {}
  emergencyAudioEl = null;
  emergencyAudioUrl = "";
}

function tickEmergencyAudio(payload) {
  const st = resolveEmergencySoundState(payload);
  if (!st.shouldPlay) {
    if (emergencyAudioEl) stopEmergencyAudio();
    return;
  }
  if (!screenAudioUnlocked) return;
  if (emergencyAudioEl && emergencyAudioUrl === st.url) return;
  stopEmergencyAudio();
  try {
    const a = new Audio(bellMediaUrl(st.url));
    a.loop = true;
    a.volume = 1;
    emergencyAudioEl = a;
    emergencyAudioUrl = st.url;
    a.play().catch(() => {
      // если браузер снова заблокировал — попробуем после следующего unlockScreenAudio
    });
  } catch (_) {}
}

function screenPayloadScheduleSig(p) {
  if (!p || typeof p !== "object") return "";
  try {
    return JSON.stringify(p.schedule);
  } catch (_) {
    return String(Date.now());
  }
}

/** Всё, кроме динамического расписания (расписание/звонки/строки таблицы). */
function screenPayloadStaticSig(p) {
  if (!p || typeof p !== "object") return "";
  try {
    return JSON.stringify({
      revision: p.revision,
      screen: p.screen,
      holidays: p.holidays,
      announcements: p.announcements,
      marquee: p.marquee,
      background_gallery: p.background_gallery,
      bell_audio: p.bell_audio,
      display: p.display,
    });
  } catch (_) {
    return String(Date.now());
  }
}

/**
 * Мягкое обновление: что перерисовывать innerHTML.
 * Расписание на сервере (время до звонка, «прошлые» уроки) — только при смене schedule.
 * Объявления, бегущая строка, праздники — при смене статики. Часы — отдельным таймером, без innerHTML.
 */
function shouldSoftRefreshWidget(widget, scheduleChanged, staticChanged) {
  const t = widget.type;
  if (t === "carousel" || t === "time") return false;
  if (t === "schedule" || t === "bell_status" || t === "bell_countdown") {
    return scheduleChanged;
  }
  if (t === "announcements" || t === "marquee" || t === "holidays") {
    return staticChanged;
  }
  if (t === "image") {
    const s = widget.settings || {};
    const rotateSec = Math.max(0, Number(s.imagesRotateSec) || 0);
    const list = Array.isArray(s.images) ? s.images : [];
    const legacy = String(s.imageUrl || "").trim();
    const n = list.length || (legacy ? 1 : 0);
    if (n > 1 && rotateSec >= 1) return true;
    return scheduleChanged || staticChanged;
  }
  if (t === "date") {
    return scheduleChanged || staticChanged;
  }
  if (t === "text" || t === "emergency" || t === "blank") {
    return staticChanged;
  }
  return scheduleChanged || staticChanged;
}

function render(screenPayload) {
  window.__lastScreenPayload = screenPayload;
  // Device-настройки (шестерёнка) показываем только для экранов, где включён mobile_mode.
  // Иначе на обычных ТВ/ПК (tv-1) она путает и даёт ощущение "конфиг не подтянулся".
  const screenForUi = (screenPayload && screenPayload.screen) || {};
  const deviceUiAllowed = Boolean(screenForUi && screenForUi.mobile_mode);
  if (deviceUiAllowed) {
    ensureDeviceSettingsUi();
    syncDeviceSettingsFromPayload(screenPayload);
  } else {
    try {
      const panel = document.getElementById("gs-device-settings-panel");
      if (panel && panel.remove) panel.remove();
      const btn = document.getElementById("gs-device-settings-btn");
      if (btn && btn.remove) btn.remove();
    } catch (_) {}
  }
  tickBellAudio(screenPayload);
  tickEmergencyAudio(screenPayload);

  const scheduleSig = screenPayloadScheduleSig(screenPayload);
  const staticSig = screenPayloadStaticSig(screenPayload);
  const scheduleChanged =
    window.__lastScheduleSig === undefined || scheduleSig !== window.__lastScheduleSig;
  const staticChanged = window.__lastStaticSig === undefined || staticSig !== window.__lastStaticSig;

  const GRef = window.GuardSchoolScreen;
  if (!GRef) return;
  const { screen, schedule, holidays, announcements, marquee } = screenPayload;
  const root = document.getElementById("screen-root");
  if (!root) return;
  const menuMode = new URLSearchParams(window.location.search || "").get("gs_menu") === "1";
  const slug = getSlug();
  const mobileForced = getGsMobileForPoll(slug);
  const mwRaw = getGsMobileWidgetsForPoll(slug);
  const mwTypes = mwRaw ? new Set(mwRaw.split(",").map((x) => x.trim()).filter(Boolean)) : null;
  const mobileViewport = (() => {
    try {
      return window.matchMedia && window.matchMedia("(max-width: 720px)").matches;
    } catch (_) {
      return false;
    }
  })();
  const mobileMode = (screen && screen.mobile_mode) && (mobileForced || mobileViewport);

  const layoutSig = JSON.stringify((screen.widgets || []).map((w) => {
    const ws = w.settings || {};
    return {
      id: w.id,
      type: w.type,
      enabled: w.enabled !== false,
      x: w.x, y: w.y, w: w.w, h: w.h,
      // Важные настройки, влияющие на структуру/карусель
      settings: w.type === "carousel"
        ? {
            childWidgetIds: ws.childWidgetIds || [],
            childSlideSec: ws.childSlideSec || {},
            startDelaySec: ws.startDelaySec || 0,
            animation: ws.animation || "slide",
          }
        : null,
    };
  }));
  const canSoftUpdate = root.dataset && root.dataset.layoutSig === layoutSig && root.querySelector(".screen-grid");
  if (!canSoftUpdate) {
    (GRef.pruneStaleWidgetState || GRef.pruneStaleCarouselState)(screen);
    GRef.clearAllTimers();
    root.innerHTML = "";
    if (root.dataset) root.dataset.layoutSig = layoutSig;
  }

  const gallery = screenPayload.background_gallery || [];

  if (menuMode) {
    // Режим меню: показываем виджеты, помеченные menu_only=true, списком.
    (GRef.pruneStaleWidgetState || GRef.pruneStaleCarouselState)(screen);
    GRef.clearAllTimers();
    root.innerHTML = "";
    const isPortrait = String(screen.orientation || "").toLowerCase() === "portrait";
    if (root && root.style) root.style.aspectRatio = isPortrait ? "9 / 16" : "16 / 9";
    const list = document.createElement("div");
    list.className = "gs-menu-list";
    list.style.display = "grid";
    list.style.gap = "10px";
    list.style.padding = "14px";
    list.style.boxSizing = "border-box";
    (screen.widgets || []).forEach((widget) => {
      if (widget.enabled === false) return;
      if (widget.menu_only !== true) return;
      const item = document.createElement("div");
      item.className = "screen-widget";
      item.dataset.widgetId = String(widget.id);
      item.dataset.widgetType = String(widget.type);
      item.innerHTML = GRef.renderWidgetHtml(widget, schedule, screen, holidays, announcements || [], marquee || []);
      if (GRef.applyWidgetBackdropClass) GRef.applyWidgetBackdropClass(item, widget);
      list.appendChild(item);
    });
    root.appendChild(list);
  } else if (mobileMode) {
    // Мобильный режим: вертикальная лента, без сетки, со скроллом.
    (GRef.pruneStaleWidgetState || GRef.pruneStaleCarouselState)(screen);
    GRef.clearAllTimers();
    root.innerHTML = "";
    root.classList.add("gs-mobile-screen");
    if (root && root.style) root.style.aspectRatio = "";
    const list = document.createElement("div");
    list.className = "gs-mobile-list";
    const hiddenWidgetIds = GRef.widgetIdsHiddenByCarousel(screen);
    const configured = Array.isArray(screen.mobile_widget_ids) ? screen.mobile_widget_ids.map(String) : [];
    const configuredSet = new Set(configured);
    const orderedAll = (GRef.sortWidgetsForDom ? GRef.sortWidgetsForDom(screen) : (screen.widgets || []))
      .filter((w) => w && w.menu_only !== true && w.type !== "emergency" && !(hiddenWidgetIds.has(w.id) && w.type !== "carousel"));
    const orderedDefault = orderedAll.filter((w) => w.enabled !== false);
    // Если список mobile_widget_ids задан — это явный выбор пользователя, показываем выбранные,
    // даже если виджет был выключен в сетке (иначе выбор "не работает").
    const ordered = configured.length
      ? orderedAll.filter((w) => configuredSet.has(String(w.id)))
      : orderedDefault;
    const filtered = mwTypes ? ordered.filter((w) => mwTypes.has(String(w.type))) : ordered;
    filtered.forEach((widget) => {
      const item = document.createElement("div");
      item.className = "screen-widget gs-mobile-widget";
      item.dataset.widgetId = String(widget.id);
      item.dataset.widgetType = String(widget.type);
      if (widget.type === "carousel") {
        item.classList.add("carousel-widget");
        const childWidgets = GRef.orderedCarouselChildWidgets
          ? GRef.orderedCarouselChildWidgets(screen, widget)
          : (screen.widgets || []).filter((it) => (widget.settings.childWidgetIds || []).includes(it.id));
        GRef.startCarousel(item, widget, childWidgets, schedule, screen, holidays, announcements || [], marquee || []);
      } else {
        item.innerHTML = GRef.renderWidgetHtml(widget, schedule, screen, holidays, announcements || [], marquee || []);
      }
      if (GRef.applyWidgetBackdropClass) GRef.applyWidgetBackdropClass(item, widget);
      list.appendChild(item);
    });
    root.appendChild(list);
  } else if (!canSoftUpdate) {
    const grid = document.createElement("div");
    grid.className = "screen-grid";
    const isPortrait = String(screen.orientation || "").toLowerCase() === "portrait";
    const cols = isPortrait ? 26 : 32;
    const rows = isPortrait ? 32 : 26;
    grid.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
    grid.style.gridTemplateRows = `repeat(${rows}, 1fr)`;
    // Портрет: правим aspect-ratio контейнера.
    if (root && root.style) root.style.aspectRatio = isPortrait ? "9 / 16" : "16 / 9";
    const hiddenWidgetIds = GRef.widgetIdsHiddenByCarousel(screen);
    const ordered = GRef.sortWidgetsForDom ? GRef.sortWidgetsForDom(screen) : (screen.widgets || []).filter((w) => {
      if (w.enabled === false) return false;
      if (hiddenWidgetIds.has(w.id) && w.type !== "carousel") return false;
      if (w.menu_only === true) return false;
      return true;
    });

    ordered.forEach((widget) => {
      if (widget.enabled === false) return;
      if (hiddenWidgetIds.has(widget.id) && widget.type !== "carousel") return;
      const block = document.createElement("div");
      block.className = "screen-widget";
      block.dataset.widgetId = String(widget.id);
      block.dataset.widgetType = String(widget.type);
      if (widget.type === "emergency") {
        block.classList.add("screen-widget--emergency");
        block.style.gridColumn = "1 / -1";
        block.style.gridRow = "1 / -1";
      } else if (widget.type === "image") {
        block.classList.add("screen-widget--image");
        block.style.gridColumn = `${widget.x + 1} / span ${widget.w}`;
        block.style.gridRow = `${widget.y + 1} / span ${widget.h}`;
        block.style.zIndex = "0";
      } else {
        block.style.gridColumn = `${widget.x + 1} / span ${widget.w}`;
        block.style.gridRow = `${widget.y + 1} / span ${widget.h}`;
      }

      if (widget.type === "text") {
        block.style.background = widget.settings.background;
        block.innerHTML = GRef.renderWidgetHtml(widget, schedule, screen, holidays, announcements || [], marquee || []);
      } else if (widget.type === "carousel") {
        block.classList.add("carousel-widget");
        const childWidgets = GRef.orderedCarouselChildWidgets
          ? GRef.orderedCarouselChildWidgets(screen, widget)
          : (screen.widgets || []).filter((item) => (widget.settings.childWidgetIds || []).includes(item.id));
        GRef.startCarousel(block, widget, childWidgets, schedule, screen, holidays, announcements || [], marquee || []);
      } else {
        block.innerHTML = GRef.renderWidgetHtml(widget, schedule, screen, holidays, announcements || [], marquee || []);
      }

      if (GRef.applyWidgetBackdropClass) GRef.applyWidgetBackdropClass(block, widget);
      else if (widget.settings && widget.settings.backdrop === false) block.classList.add("no-backdrop");

      grid.appendChild(block);
    });

    root.appendChild(grid);
  } else {
    // Мягкое обновление: карусель/таймеры не трогаем; innerHTML — выборочно (расписание vs остальной контент).
    const hiddenWidgetIds = GRef.widgetIdsHiddenByCarousel(screen);
    (screen.widgets || []).forEach((widget) => {
      if (widget.enabled === false) return;
      if (hiddenWidgetIds.has(widget.id) && widget.type !== "carousel") return;
      if (widget.type === "carousel") return;
      if (!shouldSoftRefreshWidget(widget, scheduleChanged, staticChanged)) return;
      const el = root.querySelector(`.screen-widget[data-widget-id="${gsCssEscape(String(widget.id))}"]`);
      if (!el) return;
      if (widget.type === "text") {
        el.style.background = widget.settings.background;
      }
      el.innerHTML = GRef.renderWidgetHtml(widget, schedule, screen, holidays, announcements || [], marquee || []);
      if (GRef.applyWidgetBackdropClass) GRef.applyWidgetBackdropClass(el, widget);
      else if (widget.settings && widget.settings.backdrop === false) el.classList.add("no-backdrop");
      else el.classList.remove("no-backdrop");
    });
  }

  if (GRef.applyTvScreenBackground) {
    GRef.applyTvScreenBackground(root, screen, gallery);
  }
  if (GRef.applyTvTextOutline) {
    GRef.applyTvTextOutline(root, screen);
  }

  GRef.updateAllClocks(root);
  window.__lastScheduleSig = scheduleSig;
  window.__lastStaticSig = staticSig;
}

function syncDeviceSettingsFromPayload(screenPayload) {
  try {
    const slug = getSlug();
    const panel = document.getElementById("gs-device-settings-panel");
    if (!panel) return;
    const inpClasses = panel.querySelector("#gs-device-classes");
    const chkMobile = panel.querySelector("#gs-device-mobile");
    const chkPersist = panel.querySelector("#gs-device-persist");
    const wrapWidgets = panel.querySelector("#gs-device-widgets");
    const btnApply = panel.querySelector("#gs-device-apply");
    const btnReset = panel.querySelector("#gs-device-reset");
    if (!inpClasses || !chkMobile || !chkPersist || !wrapWidgets || !btnApply || !btnReset) return;

    const existing = loadDevicePrefs(slug) || {};
    const persisted = Boolean(existing.persist);
    chkPersist.checked = persisted;
    inpClasses.value = String(existing.classes || localStorage.getItem(`gs_classes_${slug}`) || "").trim();
    chkMobile.checked = (existing.mobile === true) || (localStorage.getItem(`gs_mobile_${slug}`) === "1");

    const screen = (screenPayload && screenPayload.screen) || {};
    const types = [...new Set(((screen.widgets || [])).map((w) => w && w.type).filter(Boolean))].filter((t) => t !== "emergency");
    const selectedTypes = new Set(
      String(existing.widgetTypes || localStorage.getItem(`gs_mw_${slug}`) || "")
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean)
    );
    wrapWidgets.innerHTML = types
      .map(
        (t) =>
          `<label class="opt"><input type="checkbox" value="${String(t)}" ${selectedTypes.has(String(t)) ? "checked" : ""} /> <span>${String(t)}</span></label>`
      )
      .join("");

    btnApply.onclick = () => {
      const classes = String(inpClasses.value || "").trim();
      const mobile = chkMobile.checked ? "1" : "";
      const mw = [...wrapWidgets.querySelectorAll('input[type="checkbox"]:checked')].map((x) => String(x.value)).join(",");
      const persist = chkPersist.checked;
      try {
        if (classes) localStorage.setItem(`gs_classes_${slug}`, classes);
        else localStorage.removeItem(`gs_classes_${slug}`);
        if (mobile) localStorage.setItem(`gs_mobile_${slug}`, "1");
        else localStorage.removeItem(`gs_mobile_${slug}`);
        if (mw) localStorage.setItem(`gs_mw_${slug}`, mw);
        else localStorage.removeItem(`gs_mw_${slug}`);
      } catch (_) {}
      if (persist) saveDevicePrefs(slug, { persist: true, classes, mobile: !!mobile, widgetTypes: mw });
      else saveDevicePrefs(slug, { persist: false });
      window.location.reload();
    };

    btnReset.onclick = () => {
      const ok = window.confirm(
        "Сбросить настройки устройства для этого экрана?\n\nБудут очищены: выбранные классы, принудительный мобильный режим и фильтр виджетов. Серверный конфиг экранов не изменится."
      );
      if (!ok) return;
      clearDevicePrefs(slug);
      window.location.reload();
    };
  } catch (_) {}
}

function bumpTvStylesheetHref(hrefBase) {
  try {
    const ts = Date.now();
    const link = document.getElementById("tv-styles");
    if (link) link.href = `${hrefBase}?tvts=${ts}`;
  } catch (_) {}
}

function ensureTvStylesheet() {
  // ТВ: error — явная ошибка сети. Одноразовая проверка через несколько секунд — пустой
  // лист без события error (BrowseHere). Без циклов по poll/«пробам» grid/th/radius.
  try {
    const hrefBase =
      typeof window !== "undefined" && window.__GS_TV_CSS_BASE
        ? String(window.__GS_TV_CSS_BASE)
        : "/static/styles-screen.css";
    let link = document.getElementById("tv-styles");
    if (!link) {
      link = document.createElement("link");
      link.id = "tv-styles";
      link.rel = "stylesheet";
      link.media = "all";
      document.head.appendChild(link);
    }
    if (!link.dataset.gsTvCssErrorBound) {
      link.dataset.gsTvCssErrorBound = "1";
      link.addEventListener("error", () => bumpTvStylesheetHref(hrefBase));
    }
    if (!window.__gsTvCssRecoveryScheduled) {
      window.__gsTvCssRecoveryScheduled = 1;
      window.setTimeout(() => {
        try {
          const L = document.getElementById("tv-styles");
          if (!L || !L.href) return;
          let sheetLooksEmpty = false;
          try {
            if (!L.sheet) sheetLooksEmpty = true;
            else {
              const rules = L.sheet.cssRules;
              if (!rules || rules.length < 8) sheetLooksEmpty = true;
            }
          } catch (_) {
            sheetLooksEmpty = true;
          }
          if (sheetLooksEmpty) bumpTvStylesheetHref(hrefBase);
        } catch (_) {}
      }, 5000);
    }
  } catch (_) {}
}

function scheduleNextRefresh(delayMs) {
  window.clearTimeout(window.__screenRefreshTimer);
  window.__screenRefreshTimer = window.setTimeout(refresh, delayMs);
}

async function refresh() {
  const fallbackDelay = Math.max(5000, window.__lastScreenPollMs || 10000);
  let nextDelay = fallbackDelay;
  try {
    const slug = getSlug();
    if (!slug) throw new Error("empty slug");
    const cid = encodeURIComponent(getGsClientId());
    const lab = encodeURIComponent(getGsLabelForPoll());
    const dev = encodeURIComponent(await resolveGsDeviceHintOnce());
    const timeoutMs = Math.max(
      2000,
      Number(window.__GS_POLL_TIMEOUT_MS) || 5000,
    );
    const primary = (window.__GS_PRIMARY_BASE || "").trim().replace(/\/$/, "");
    const fallbackBase = (window.__GS_FALLBACK_BASE || "").trim().replace(/\/$/, "");
    const bearer = getGsTvBearer();
    const hdr = {
      "Cache-Control": "no-cache",
      Pragma: "no-cache",
    };
    if (bearer) hdr.Authorization = `Bearer ${bearer}`;

    /** Порядок: primary (LAN) → этот же origin → fallback (облако). */
    const bases = [];
    if (primary) bases.push(primary);
    bases.push("");
    if (fallbackBase && !bases.includes(fallbackBase)) bases.push(fallbackBase);

    let response = null;
    let lastErr = null;
    for (const b of bases) {
      const url = screenPollUrl(b, slug, cid, lab, dev);
      try {
        const r = await fetchScreenPayload(url, hdr, Math.min(45000, timeoutMs + 5000));
        if (r.ok) {
          response = r;
          break;
        }
        lastErr = new Error(`HTTP ${r.status}`);
      } catch (e) {
        lastErr = e;
      }
    }
    if (!response || !response.ok) {
      throw lastErr || new Error("poll failed");
    }
    const payload = await response.json();
    nextDelay = Math.max(5000, (payload.screen.poll_interval_sec || 10) * 1000);
    window.__lastScreenPollMs = nextDelay;
    try {
      render(payload);
      lastRenderOkAt = Date.now();
      hideCrashBanner();
    } catch (e) {
      showCrashBanner(`Ошибка отрисовки: ${(e && e.message) ? e.message : String(e)}`);
    }
  } catch (_) {
    /* сеть / таймаут / пустой slug: не копим запросы, один цикл */
  }
  scheduleNextRefresh(nextDelay);
}

const rootForClock = () => document.getElementById("screen-root");

window.setInterval(() => {
  const g = window.GuardSchoolScreen;
  if (g) g.updateAllClocks(rootForClock());
}, 1000);
window.setInterval(() => {
  if (window.__lastScreenPayload) tickBellAudio(window.__lastScreenPayload);
}, 1000);
/** Смена фона по интервалу без полного poll (картинки уже известны с сервера). */
window.setInterval(() => {
  const root = document.getElementById("screen-root");
  const p = window.__lastScreenPayload;
  const GRef = window.GuardSchoolScreen;
  if (!root || !p || !GRef || !GRef.applyTvScreenBackground) return;
  GRef.applyTvScreenBackground(root, p.screen, p.background_gallery || []);
  if (GRef.applyTvTextOutline) GRef.applyTvTextOutline(root, p.screen);
}, 15000);
ensureTvStylesheet();
/* Полную перезагрузку страницы не делаем: браузер снова блокирует звук до жеста.
   Данные ТВ и так подтягиваются по таймеру через refresh() без reload. */
refresh();

// Если браузер «подвис» или перестал рендерить, пробуем мягко восстановиться.
window.setInterval(() => {
  try {
    const poll = Math.max(5000, window.__lastScreenPollMs || 10000);
    if (Date.now() - lastRenderOkAt > poll * 4) {
      showCrashBanner("Экран давно не обновлялся. Пробуем восстановить…");
      ensureTvStylesheet();
      refresh();
    }
  } catch (_) {}
}, 10000);

// На мобильных браузерах таймеры в фоне/при блокировке экрана могут «замерзать».
// Когда вкладка снова становится активной — сразу делаем refresh (вместо ожидания setTimeout).
document.addEventListener("visibilitychange", () => {
  try {
    if (document.visibilityState === "visible") refresh();
  } catch (_) {}
});
window.addEventListener("online", () => {
  try {
    refresh();
  } catch (_) {}
});
