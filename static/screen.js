function getSlug() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  return parts.length ? parts[parts.length - 1] : "";
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

function getGsTvBearer() {
  try {
    return (localStorage.getItem("gs_tv_bearer") || "").trim();
  } catch (_) {
    return "";
  }
}

function screenPollUrl(base, slug, cid, lab, dev) {
  const qs = `ts=${Date.now()}&gs_client=${cid}&gs_label=${lab}&gs_device=${dev}`;
  const path = `/api/screen/${encodeURIComponent(slug)}?${qs}`;
  if (!base) return path;
  return `${String(base).replace(/\/$/, "")}${path}`;
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
  const now = new Date();
  const mins = now.getHours() * 60 + now.getMinutes();
  const secs = now.getSeconds();
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

  const layoutSig = JSON.stringify((screen.widgets || []).map((w) => ({
    id: w.id,
    type: w.type,
    enabled: w.enabled !== false,
    x: w.x, y: w.y, w: w.w, h: w.h,
    // Важные настройки, влияющие на структуру/карусель
    settings: w.type === "carousel"
      ? { childWidgetIds: w.settings?.childWidgetIds || [], childSlideSec: w.settings?.childSlideSec || {}, startDelaySec: w.settings?.startDelaySec || 0, animation: w.settings?.animation || "slide" }
      : null,
  })));
  const canSoftUpdate = root.dataset && root.dataset.layoutSig === layoutSig && root.querySelector(".screen-grid");
  if (!canSoftUpdate) {
    (GRef.pruneStaleWidgetState || GRef.pruneStaleCarouselState)(screen);
    GRef.clearAllTimers();
    root.innerHTML = "";
    if (root.dataset) root.dataset.layoutSig = layoutSig;
  }

  const gallery = screenPayload.background_gallery || [];

  if (!canSoftUpdate) {
    const grid = document.createElement("div");
    grid.className = "screen-grid";
    const hiddenWidgetIds = GRef.widgetIdsHiddenByCarousel(screen);
    const ordered = GRef.sortWidgetsForDom ? GRef.sortWidgetsForDom(screen) : (screen.widgets || []).filter((w) => {
      if (w.enabled === false) return false;
      if (hiddenWidgetIds.has(w.id) && w.type !== "carousel") return false;
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
      const el = root.querySelector(`.screen-widget[data-widget-id="${CSS.escape(String(widget.id))}"]`);
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
