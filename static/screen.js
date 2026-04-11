function getSlug() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  return parts.length ? parts[parts.length - 1] : "";
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

function render(screenPayload) {
  window.__lastScreenPayload = screenPayload;
  tickBellAudio(screenPayload);
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
  if (GRef.applyTvScreenBackground) {
    GRef.applyTvScreenBackground(root, screen, gallery);
  } else if (screen.background_image) {
    root.style.background = `url(${screen.background_image}) center/cover no-repeat`;
  }
  if (GRef.applyTvTextOutline) {
    GRef.applyTvTextOutline(root, screen);
  }

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
    // Мягкое обновление: не трогаем карусель/таймеры, обновляем только контент остальных виджетов.
    const hiddenWidgetIds = GRef.widgetIdsHiddenByCarousel(screen);
    (screen.widgets || []).forEach((widget) => {
      if (widget.enabled === false) return;
      if (hiddenWidgetIds.has(widget.id) && widget.type !== "carousel") return;
      if (widget.type === "carousel") return;
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

  GRef.updateAllClocks(root);
}

function ensureTvStylesheet() {
  // На некоторых ТВ-браузерах styles.css иногда «слетает» (кэш/304/гонка). Подстрахуемся: пере-добавим link.
  try {
    const hrefBase = "/static/styles.css";
    let link = document.getElementById("tv-styles");
    if (!link) {
      link = document.createElement("link");
      link.id = "tv-styles";
      link.rel = "stylesheet";
      document.head.appendChild(link);
    }
    // Признак, что стили реально применились: есть grid у .screen-grid.
    const probe = document.querySelector(".screen-grid");
    const gridOk = probe && window.getComputedStyle(probe).display === "grid";

    // Доп. признак: у таблицы расписания должна быть «синяя шапка» и белый текст.
    const th = document.querySelector(".schedule-table th");
    const thBg = th ? window.getComputedStyle(th).backgroundColor : "";
    const thColor = th ? window.getComputedStyle(th).color : "";
    const looksGray = (s) => typeof s === "string" && (s.includes("rgb(128") || s.includes("128, 128, 128") || s.toLowerCase().includes("gray"));
    const tableOk = th ? (!looksGray(thBg) && !looksGray(thColor)) : true;

    if (gridOk && tableOk) return;
    link.href = `${hrefBase}?tvts=${Date.now()}`;
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
    const ac = new AbortController();
    const to = window.setTimeout(() => ac.abort(), 45000);
    try {
      const response = await fetch(`/api/screen/${slug}?ts=${Date.now()}`, {
        cache: "no-store",
        signal: ac.signal,
        headers: {
          "Cache-Control": "no-cache",
          Pragma: "no-cache",
        },
      });
      if (!response.ok) {
        throw new Error("poll failed");
      }
      const payload = await response.json();
      nextDelay = Math.max(5000, (payload.screen.poll_interval_sec || 10) * 1000);
      window.__lastScreenPollMs = nextDelay;
      render(payload);
    } finally {
      window.clearTimeout(to);
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
// Подстраховка: если CSS «слетел», вернём его без reload страницы.
window.setInterval(() => ensureTvStylesheet(), 20000);
/* Полную перезагрузку страницы не делаем: браузер снова блокирует звук до жеста.
   Данные ТВ и так подтягиваются по таймеру через refresh() без reload. */
refresh();
