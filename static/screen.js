

/**
 * URLSearchParams fallback для старых браузеров ТВ.
 * Поддерживает get/set/delete/toString, достаточно для текущей страницы.
 */
function gsQueryParams(search) {
  const raw = String(search || "");
  const src = raw && raw.charAt(0) === "?" ? raw.slice(1) : raw;
  if (typeof URLSearchParams !== "undefined") {
    try {
      return new URLSearchParams(src);
    } catch (_) {}
  }
  const pairs = [];
  const chunks = src ? src.split("&") : [];
  for (let i = 0; i < chunks.length; i++) {
    const part = chunks[i];
    if (!part) continue;
    const pos = part.indexOf("=");
    const k0 = pos >= 0 ? part.slice(0, pos) : part;
    const v0 = pos >= 0 ? part.slice(pos + 1) : "";
    let k = "";
    let v = "";
    try {
      k = decodeURIComponent(String(k0 || "").replace(/\+/g, "%20"));
    } catch (_) {
      k = String(k0 || "");
    }
    try {
      v = decodeURIComponent(String(v0 || "").replace(/\+/g, "%20"));
    } catch (_) {
      v = String(v0 || "");
    }
    pairs.push([k, v]);
  }
  return {
    get(key) {
      const k = String(key);
      for (let i = 0; i < pairs.length; i++) {
        if (pairs[i][0] === k) return pairs[i][1];
      }
      return null;
    },
    set(key, value) {
      const k = String(key);
      const v = String(value);
      let done = false;
      for (let i = pairs.length - 1; i >= 0; i--) {
        if (pairs[i][0] !== k) continue;
        if (!done) {
          pairs[i][1] = v;
          done = true;
        } else {
          pairs.splice(i, 1);
        }
      }
      if (!done) pairs.push([k, v]);
    },
    delete(key) {
      const k = String(key);
      for (let i = pairs.length - 1; i >= 0; i--) {
        if (pairs[i][0] === k) pairs.splice(i, 1);
      }
    },
    toString() {
      const out = [];
      for (let i = 0; i < pairs.length; i++) {
        const kv = pairs[i];
        out.push(`${encodeURIComponent(kv[0])}=${encodeURIComponent(kv[1])}`);
      }
      return out.join("&");
    },
  };
}

function getSlug() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  const raw = parts.length ? parts[parts.length - 1] : "";
  try {
    return decodeURIComponent(String(raw || "")).trim().toLowerCase();
  } catch (_) {
    return String(raw || "").trim().toLowerCase();
  }
}

/** Удалить все ключи localStorage, начинающиеся с gs_ (токен ТВ, гибрид, gs_client_id, все экраны). */
function purgeAllGsLocalStorage() {
  try {
    const kill = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.indexOf("gs_") === 0) kill.push(k);
    }
    for (let j = 0; j < kill.length; j++) {
      try {
        localStorage.removeItem(kill[j]);
      } catch (_) {}
    }
  } catch (_) {}
}

/** Кэши Fetch API (если есть). На части ТВ WebView `caches`/Promise ведут себя нестабильно — не бросаем наружу. */
function purgeGsCachesBestEffort() {
  function resolved() {
    if (typeof Promise !== "undefined" && Promise.resolve) return Promise.resolve();
    return { then: function (cb) { try { if (typeof cb === "function") cb(); } catch (_) {} } };
  }
  try {
    if (!window.caches || typeof window.caches.keys !== "function") return resolved();
    const ck = window.caches.keys();
    if (!ck || typeof ck.then !== "function") return resolved();
    return ck
      .then(function (keys) {
        if (!keys || !keys.length) return;
        if (typeof Promise !== "undefined" && Promise.all) {
          const ps = [];
          for (let i = 0; i < keys.length; i++) ps.push(window.caches.delete(keys[i]));
          return Promise.all(ps);
        }
        for (let i = 0; i < keys.length; i++) {
          try {
            window.caches.delete(keys[i]);
          } catch (_) {}
        }
      })
      .catch(function () {});
  } catch (_) {
    return resolved();
  }
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
    const q = gsQueryParams(window.location.search).get("gs_label");
    window.__gsScreenLabelCached = q ? q.trim().slice(0, 120) : "";
    return window.__gsScreenLabelCached;
  } catch (_) {
    return "";
  }
}

/** Токен из Python secrets.token_urlsafe — только ASCII A–Z a–z 0–9 _ - (иначе fetch ломается на заголовке Authorization). */
function sanitizeGsTvBearerToken(raw) {
  const s = String(raw || "").trim();
  if (!s || s.length > 220) return "";
  if (!/^[A-Za-z0-9_-]+$/.test(s)) return "";
  return s;
}

/** Параметры гибрида: primary/fallback API и токен ТВ (из URL один раз → localStorage). */
function initGsHybridFromUrl() {
  try {
    const q = gsQueryParams(window.location.search);
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
        const clean = sanitizeGsTvBearerToken(tok);
        if (clean) localStorage.setItem("gs_tv_bearer", clean);
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

// Сброс localStorage/caches до чтения URL (?gs_tv_token / гибрид), иначе токен снова запишется.
// Параметр в адресе: gs_reset=1 — настройки устройства для slug + гибрид + bearer;
// gs_reset=all — полностью все ключи gs_* (в т.ч. gs_client_id), кэши caches API, без slug тоже работает.
(function maybeResetDevicePrefsOnce() {
  try {
    const q = gsQueryParams(window.location.search || "");
    const raw = (q.get("gs_reset") || "").trim().toLowerCase();
    if (!raw) return;
    const full = raw === "all" || raw === "full" || raw === "hard";
    const slugReset = raw === "1" || raw === "true" || raw === "yes" || raw === "on" || full;
    if (!slugReset) return;
    const slug = getSlug();
    if (full) {
      purgeAllGsLocalStorage();
    } else {
      if (slug) {
        try {
          clearDevicePrefs(slug);
        } catch (_) {}
      }
      try {
        localStorage.removeItem("gs_primary_base");
        localStorage.removeItem("gs_fallback_base");
        localStorage.removeItem("gs_tv_bearer");
      } catch (_) {}
    }
    try {
      window.__gsScreenLabelCached = undefined;
    } catch (_) {}
    q.delete("gs_reset");
    const ns = q.toString();
    const url = window.location.pathname + (ns ? `?${ns}` : "") + window.location.hash;
    try {
      window.history.replaceState(null, "", url);
    } catch (_) {
      try {
        window.history.replaceState({}, "", url);
      } catch (_) {}
    }
    const go = function () {
      try {
        window.location.reload();
      } catch (_) {}
    };
    // Не блокируем reload цепочкой Promise: на Smart TV caches/ Promise иногда дают «тихий» сбой → reload не вызывается.
    try {
      const p = purgeGsCachesBestEffort();
      if (p && typeof p.then === "function") {
        p.then(function () {}, function () {});
      }
    } catch (_) {}
    setTimeout(go, 0);
  } catch (_) {}
})();

initGsHybridFromUrl();

function getGsTvBearer() {
  try {
    const raw = localStorage.getItem("gs_tv_bearer") || "";
    const clean = sanitizeGsTvBearerToken(raw);
    if (!clean && raw.trim()) {
      try {
        localStorage.removeItem("gs_tv_bearer");
      } catch (_) {}
    }
    return clean;
  } catch (_) {
    return "";
  }
}

/** Плавающая шестерёнка и фильтр классов на устройстве — только при mobile_mode экрана (см. get_screen / screenPollUrl). */
function gsShowScreenDeviceGear(screen) {
  return Boolean(screen && screen.mobile_mode);
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
        <div class="gs-device-settings-field-head">Классы расписания на этом устройстве</div>
        <div class="gs-device-classes-hint">По умолчанию отмечены все — как в веб-настройке экрана. Снимите лишние, чтобы не показывать эти классы здесь.</div>
        <div id="gs-device-classes-wrap" class="gs-device-settings-checks"></div>
      </div>
      <div class="gs-device-settings-row">
        <label>Режим</label>
        <div class="gs-device-settings-checks">
          <label class="opt"><input type="checkbox" id="gs-device-grid" /> <span>Сетка вместо ленты (если в конфиге включён мобильный режим)</span></label>
          <label class="opt"><input type="checkbox" id="gs-device-persist" /> <span>Сохранять настройки на этом устройстве</span></label>
        </div>
      </div>
      <div class="gs-device-settings-row">
        <div class="gs-device-settings-field-head">Виджеты (по типам)</div>
        <div class="gs-device-classes-hint">Фильтр типов виджетов в ленте. Пустой список в хранилище = все типы. Сохранение «на устройстве» не должно сбрасывать отмеченные типы — см. галочку ниже.</div>
        <div id="gs-device-widgets" class="gs-device-settings-checks"></div>
      </div>
      <div class="gs-device-settings-row gs-device-url-hint-wrap">
        <details class="gs-device-url-hint">
          <summary>Сброс и параметры в адресе (редко нужно)</summary>
          <p class="gs-device-url-hint-body">
            Сброс настроек этого экрана в браузере: добавьте в URL <code>?gs_reset=1</code> (классы, виджеты, сетка/лента, гибрид и токен ТВ для slug) или <code>?gs_reset=all</code> — все ключи <code>gs_*</code> в localStorage и кэши Fetch. Параметр из адреса убирается сам; cookie входа в админку страница не трогает.
            Подпись места в статистике: <code>?gs_label=Столовая</code>.
            Принудительно сетка при мобильном режиме экрана: <code>?gs_grid=1</code>, сброс: <code>?gs_grid=0</code>.
            Имя ПК Windows в браузер не передаётся; в статистику уходит краткая строка устройства (платформа/модель), если доступно.
          </p>
        </details>
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
    localStorage.removeItem(`gs_grid_${slug}`);
  } catch (_) {}
}

function getGsMobileWidgetsForPoll(slug) {
  try {
    const q = gsQueryParams(window.location.search || "");
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

function screenPollUrl(base, slug, cid, lab, dev, _mobileMode) {
  const classes = (getGsClassesForPoll(slug) || "").trim();
  // gs_mw обрабатывает только клиент; в URL — чтобы сразу после ?gs_mw= попало в localStorage.
  const mw = (getGsMobileWidgetsForPoll(slug) || "").trim();
  const qs = `ts=${Date.now()}&gs_client=${cid}&gs_label=${lab}&gs_device=${dev}`
    + (classes ? `&gs_classes=${encodeURIComponent(classes)}` : "")
    + (mw ? `&gs_mw=${encodeURIComponent(mw)}` : "");
  const path = `/api/screen/${encodeURIComponent(slug)}?${qs}`;
  if (!base) return path;
  return `${String(base).replace(/\/$/, "")}${path}`;
}

/** Порядок опроса: LAN → этот origin → fallback. HTTP-LAN с HTTPS-страницы не используем (браузер блокирует). */
function buildScreenPollBases(primaryRaw, fallbackRaw) {
  let primary = String(primaryRaw || "").trim().replace(/\/$/, "");
  const fallback = String(fallbackRaw || "").trim().replace(/\/$/, "");
  try {
    if (
      typeof window !== "undefined" &&
      window.location &&
      window.location.protocol === "https:" &&
      primary.toLowerCase().startsWith("http:")
    ) {
      primary = "";
    }
  } catch (_) {}
  const bases = [];
  if (primary) bases.push(primary);
  bases.push("");
  if (fallback && !bases.includes(fallback)) bases.push(fallback);
  return bases;
}

function gsFormatScreenPollFailureMessage(rawMsg, retrySec) {
  const m = String(rawMsg || "");
  const base = m ? `Сервер не отдал экран: ${m}.` : "Сервер не отдал экран.";
  if (/\bHTTP\s+403\b/i.test(m)) {
    return (
      `${base} Это не из‑за «5 запросов»: 403 — доступ к API экрана запрещён. Чаще всего неверный/отключённый токен ТВ (Bearer) для этого slug, или запрос ушёл не на тот хост. Откройте снова ссылку из админки с ?gs_tv_token=… Если в гибриде сохранён LAN по http, с https-страницы он не работает — очистите primary в localStorage или откройте экран только по облаку. Повтор через ${retrySec} с.`
    );
  }
  if (/\bHTTP\s+401\b/i.test(m)) {
    return `${base} Нет или неверный Bearer. Снова откройте ссылку экрана с ?gs_tv_token=… Повтор через ${retrySec} с.`;
  }
  if (/\bHTTP\s+50[234]\b/i.test(m)) {
    return `${base} Часто после перезапуска сервера или при сбое прокси. Повтор через ${retrySec} с.`;
  }
  if (/failed to fetch|networkerror|load failed|mixed content/i.test(m)) {
    return `${base} Сеть или блокировка запроса (в т.ч. http-LAN с https-страницы). Повтор через ${retrySec} с.`;
  }
  return `${base} Повтор через ${retrySec} с.`;
}

/** На этом устройстве показать сетку, даже если в веб-конфиге включён mobile_mode (?gs_grid=1 сохраняется в localStorage). */
/** Подписи типов виджетов в панели «Настройки для этого устройства» (value остаётся англ. ключом для gs_mw). */
const GS_DEVICE_WIDGET_TYPE_LABELS = {
  date: "Дата",
  time: "Время",
  text: "Текст",
  bell_status: "Звонки",
  schedule: "Расписание",
  carousel: "Карусель",
  holidays: "Праздники",
  announcements: "Объявления",
  marquee: "Бегущая строка",
  image: "Фон / картинка",
};

function getGsGridForPoll(slug) {
  if (!slug) return false;
  try {
    const q = gsQueryParams(window.location.search || "");
    const g = (q.get("gs_grid") || "").trim().toLowerCase();
    if (g === "1" || g === "true" || g === "yes") {
      localStorage.setItem(`gs_grid_${slug}`, "1");
      return true;
    }
    if (g === "0" || g === "off" || g === "false") {
      localStorage.removeItem(`gs_grid_${slug}`);
      return false;
    }
    return localStorage.getItem(`gs_grid_${slug}`) === "1";
  } catch (_) {
    return false;
  }
}

/** Первый виджет типа `type` в конфиге экрана (в т.ч. только внутри карусели — его нет в mobile-stack / sortWidgetsForDom). */
function pickWidgetByTypeFromScreen(screen, type) {
  const want = String(type || "").trim();
  if (!want || !screen || !Array.isArray(screen.widgets)) return null;
  for (let i = 0; i < screen.widgets.length; i++) {
    const w = screen.widgets[i];
    if (!w || String(w.type || "") !== want) continue;
    if (w.menu_only === true || w.type === "emergency") continue;
    return w;
  }
  return null;
}

function getGsClassesForPoll(slug) {
  try {
    const q = gsQueryParams(window.location.search || "");
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
  if (typeof fetch === "function") {
    const canAbort = typeof AbortController !== "undefined";
    const ac = canAbort ? new AbortController() : null;
    const to = window.setTimeout(() => {
      if (ac) ac.abort();
    }, timeoutMs);
    try {
      return await fetch(url, {
        cache: "no-store",
        signal: ac ? ac.signal : undefined,
        headers,
      });
    } finally {
      window.clearTimeout(to);
    }
  }
  return await new Promise((resolve, reject) => {
    try {
      const xhr = new XMLHttpRequest();
      xhr.open("GET", url, true);
      xhr.timeout = timeoutMs;
      if (headers) {
        Object.keys(headers).forEach((k) => {
          try {
            xhr.setRequestHeader(k, headers[k]);
          } catch (_) {}
        });
      }
      xhr.onreadystatechange = function onReady() {
        if (xhr.readyState !== 4) return;
        const status = Number(xhr.status) || 0;
        const body = xhr.responseText || "";
        resolve({
          ok: status >= 200 && status < 300,
          status,
          json: async () => JSON.parse(body || "{}"),
          text: async () => String(body || ""),
        });
      };
      xhr.ontimeout = function onTimeout() {
        reject(new Error("timeout"));
      };
      xhr.onerror = function onErr() {
        reject(new Error("network error"));
      };
      xhr.send(null);
    } catch (e) {
      reject(e);
    }
  });
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
      // Короче строка запроса — реже упираемся в лимиты прокси; для статистики достаточно.
      return parts.filter(Boolean).join(" / ").slice(0, 80);
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

/** Не запускать два poll подряд (ТВ/WebView после рестарта сервера иногда «роняют» вкладку при гонке). */
let __gsRefreshInFlight = false;
let __gsRefreshQueued = false;

function showCrashBanner(msg) {
  try {
    const el = document.getElementById("gs-crash-banner");
    if (!el) return;
    el.textContent = String(msg || "Ошибка на экране").slice(0, 1200);
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
    let m =
      ev && (ev.message || (ev.error && ev.error.message)) ? ev.message || (ev.error && ev.error.message) : "";
    if (!m && ev && ev.filename) {
      const tail = String(ev.filename).split("/").pop() || String(ev.filename);
      m = `${tail}:${ev.lineno != null ? ev.lineno : "?"}`;
    }
    if (!m) m = "JS error";
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
      if (key) playedBellKeys.delete(key);
      window.clearTimeout(safety);
      finish();
    });
    a.play()
      .then(() => {})
      .catch(() => {
        if (key) playedBellKeys.delete(key);
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
        playedBellKeys.add(k);
        clips.push({ url: row.sound_start, key: k });
      }
    }
    if (mins === en && secs < secWin && row.sound_end) {
      const k = `${base}_e`;
      if (!playedBellKeys.has(k)) {
        playedBellKeys.add(k);
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
  const screenForUi = (screenPayload && screenPayload.screen) || {};
  const deviceUiAllowed = gsShowScreenDeviceGear(screenForUi);
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
  const menuMode = gsQueryParams(window.location.search || "").get("gs_menu") === "1";
  const slug = getSlug();
  const mwRaw = getGsMobileWidgetsForPoll(slug);
  const mwTypes = mwRaw ? new Set(mwRaw.split(",").map((x) => x.trim()).filter(Boolean)) : null;
  const deviceGridOverride = Boolean(screen && screen.mobile_mode) && getGsGridForPoll(slug);
  const mobileMode = Boolean(screen && screen.mobile_mode) && !getGsGridForPoll(slug);

  const layoutSig = JSON.stringify({
    m: mobileMode,
    dg: deviceGridOverride,
    mw: mwRaw || "",
    w: (screen.widgets || []).map((w) => {
      const ws = w.settings || {};
      return {
        id: w.id,
        type: w.type,
        enabled: w.enabled !== false,
        x: w.x, y: w.y, w: w.w, h: w.h,
        settings: w.type === "carousel"
          ? {
              childWidgetIds: ws.childWidgetIds || [],
              childSlideSec: ws.childSlideSec || {},
              startDelaySec: ws.startDelaySec || 0,
              animation: ws.animation || "slide",
            }
          : null,
      };
    }),
  });
  const softGrid = !mobileMode && root.querySelector(".screen-grid");
  const softMobile = mobileMode && root.querySelector(".gs-mobile-list");
  const canSoftUpdate = root.dataset && root.dataset.layoutSig === layoutSig && Boolean(softGrid || softMobile);
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
    // Мобильный режим: вертикальная лента; порядок = порядок в конфиге, координаты сетки не используются.
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
    const orderedAll = (GRef.sortWidgetsForMobileStack
      ? GRef.sortWidgetsForMobileStack(screen)
      : (screen.widgets || []).filter(
          (w) => w && w.menu_only !== true && w.type !== "emergency" && !(hiddenWidgetIds.has(w.id) && w.type !== "carousel")
        ));
    const orderedDefault = orderedAll.filter((w) => w.enabled !== false);
    // Если список mobile_widget_ids задан — это явный выбор пользователя, показываем выбранные,
    // даже если виджет был выключен в сетке (иначе выбор "не работает").
    const ordered = configured.length
      ? orderedAll.filter((w) => configuredSet.has(String(w.id)))
      : orderedDefault;
    let filtered = mwTypes ? ordered.filter((w) => mwTypes.has(String(w.type))) : ordered;
    // Тип в gs_mw, но виджета нет в ленте (не в mobile_widget_ids / выключен / только внутри карусели) — берём из полного конфига экрана.
    if (mwTypes && mwTypes.size) {
      for (const t of mwTypes) {
        if (filtered.some((w) => w && String(w.type) === t)) continue;
        const cand = pickWidgetByTypeFromScreen(screen, t);
        if (cand && !filtered.some((w) => String(w.id) === String(cand.id))) filtered.push(cand);
      }
      const rank = new Map(orderedAll.map((w, i) => [String(w.id), i]));
      filtered.sort((a, b) => (rank.get(String(a.id)) ?? 1e9) - (rank.get(String(b.id)) ?? 1e9));
    }
    // Раньше при пустом пересечении gs_mw с лентой мы удаляли gs_mw и показывали все виджеты — для
    // пользователя это выглядело как «сломанный шаблон». Не трогаем localStorage.
    if (mwTypes && mwTypes.size && filtered.length === 0) {
      const empty = document.createElement("div");
      empty.className = "gs-mobile-empty-hint";
      empty.style.cssText =
        "padding:16px 18px;font-size:15px;line-height:1.45;color:rgba(255,255,255,0.88);text-align:center;max-width:28rem;margin:12px auto;";
      empty.textContent =
        "Для выбранных типов виджетов сейчас нечего показать (нет такого виджета в ленте экрана или он отключён). Откройте ⚙ и снимите лишние типы либо включите нужный виджет в админке (мобильная лента / сетка).";
      list.appendChild(empty);
    } else {
      // Добавляем расписание из полного списка только без фильтра gs_mw — иначе «только время» превращалось в «время + расписание».
      if (!mwTypes) {
        const schedW = orderedAll.find((w) => w && w.type === "schedule" && w.enabled !== false);
        if (schedW && !filtered.some((w) => w && w.type === "schedule")) {
          filtered = [schedW, ...filtered.filter((w) => w && w.id !== schedW.id)];
        }
      }
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
    }
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
    let ordered = GRef.sortWidgetsForDom ? GRef.sortWidgetsForDom(screen) : (screen.widgets || []).filter((w) => {
      if (w.enabled === false) return false;
      if (hiddenWidgetIds.has(w.id) && w.type !== "carousel") return false;
      if (w.menu_only === true) return false;
      return true;
    });
    // На экране с mobile_mode «сетка на устройстве» — фильтр gs_mw; дочерние карусели подмешиваем из полного конфига.
    if (deviceGridOverride && mwTypes && mwTypes.size) {
      const seen = new Set(ordered.map((w) => String(w.id)));
      for (const t of mwTypes) {
        if (ordered.some((w) => w && String(w.type) === t)) continue;
        const w = pickWidgetByTypeFromScreen(screen, t);
        if (w && !seen.has(String(w.id))) {
          ordered.push(w);
          seen.add(String(w.id));
        }
      }
      const ord = screen.widgets || [];
      const idx = (w) => {
        const i = ord.findIndex((x) => x && String(x.id) === String(w.id));
        return i < 0 ? 1e9 : i;
      };
      ordered.sort((a, b) => idx(a) - idx(b));
      ordered = ordered.filter((w) => {
        if (!w) return false;
        if (w.type === "emergency") return true;
        return mwTypes.has(String(w.type));
      });
    }

    ordered.forEach((widget) => {
      const allowDisabledForMw =
        Boolean(deviceGridOverride && mwTypes && mwTypes.size && mwTypes.has(String(widget.type)));
      if (widget.enabled === false && !allowDisabledForMw) return;
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

function gsDeviceNormClass(s) {
  return String(s || "")
    .trim()
    .toLowerCase();
}

/** Сопоставить сохранённую строку gs_classes с каноническими именами из pickable; пустой/мусор → «все». */
function gsDeviceClassCanonFromSaved(slug, existing, pickable) {
  let raw = "";
  try {
    raw = String(existing.classes || localStorage.getItem(`gs_classes_${slug}`) || "").trim();
  } catch (_) {
    raw = "";
  }
  const parts = raw ? raw.split(",").map((x) => String(x).trim()).filter(Boolean) : [];
  const normToCanon = new Map();
  pickable.forEach((p) => {
    normToCanon.set(gsDeviceNormClass(p), p);
  });
  const canon = new Set();
  for (const part of parts) {
    const c = normToCanon.get(gsDeviceNormClass(part));
    if (c) canon.add(c);
  }
  if (!parts.length || canon.size === 0) {
    pickable.forEach((p) => canon.add(p));
  }
  return canon;
}

/** Сбросить gs_classes вроде «0», если такой параллели/классов нет в pickable (иначе расписание пустое до ручного сброса). */
function gsRepairToxicGsClasses(slug, pickable) {
  if (!slug || !pickable || !pickable.length) return false;
  let raw = "";
  try {
    raw = (localStorage.getItem(`gs_classes_${slug}`) || "").trim();
  } catch (_) {
    return false;
  }
  if (!raw) return false;
  const parts = raw.split(",").map((x) => x.trim()).filter(Boolean);
  if (parts.length !== 1) return false;
  const token = parts[0];
  if (!/^\d+$/.test(token)) return false;
  const n = parseInt(token, 10);
  const norm = (s) => gsDeviceNormClass(s);
  const hasParallel = pickable.some((x) => norm(x) === norm(token));
  const hasGrade = pickable.some((x) => {
    const m = norm(x).match(/^(\d+)/);
    return m && parseInt(m[1], 10) === n;
  });
  if (!hasParallel && !hasGrade) {
    try {
      localStorage.removeItem(`gs_classes_${slug}`);
    } catch (_) {}
    try {
      const dp = loadDevicePrefs(slug);
      if (dp && String(dp.classes || "").trim() === raw) {
        saveDevicePrefs(slug, { ...dp, classes: "" });
      }
    } catch (_) {}
    return true;
  }
  return false;
}

function syncDeviceSettingsFromPayload(screenPayload) {
  try {
    const slug = getSlug();
    const panel = document.getElementById("gs-device-settings-panel");
    if (!panel) return;
    const wrapClasses = panel.querySelector("#gs-device-classes-wrap");
    const chkGrid = panel.querySelector("#gs-device-grid");
    const chkPersist = panel.querySelector("#gs-device-persist");
    const wrapWidgets = panel.querySelector("#gs-device-widgets");
    const btnApply = panel.querySelector("#gs-device-apply");
    const btnReset = panel.querySelector("#gs-device-reset");
    if (!wrapClasses || !chkGrid || !chkPersist || !wrapWidgets || !btnApply || !btnReset) return;

    const existing = loadDevicePrefs(slug) || {};
    const persisted = Boolean(existing.persist);
    chkPersist.checked = persisted;
    chkGrid.checked = getGsGridForPoll(slug);

    const pickable = Array.isArray(screenPayload && screenPayload.pickable_classes)
      ? screenPayload.pickable_classes.map((x) => String(x).trim()).filter(Boolean)
      : [];
    const canon = gsDeviceClassCanonFromSaved(slug, existing, pickable);
    wrapClasses.textContent = "";
    if (!pickable.length) {
      const hint = document.createElement("div");
      hint.className = "hint";
      hint.style.fontSize = "13px";
      hint.textContent = "Список классов пока недоступен — фильтр не применяется, используется настройка экрана.";
      wrapClasses.appendChild(hint);
    } else {
      pickable.forEach((name, idx) => {
        const lab = document.createElement("label");
        lab.className = "opt";
        const inp = document.createElement("input");
        inp.type = "checkbox";
        inp.value = name;
        inp.id = `gs-device-class-${idx}`;
        inp.checked = canon.has(name);
        const span = document.createElement("span");
        span.textContent = name;
        lab.appendChild(inp);
        lab.appendChild(span);
        wrapClasses.appendChild(lab);
      });
    }

    const screen = (screenPayload && screenPayload.screen) || {};
    const types = [...new Set(((screen.widgets || [])).map((w) => w && w.type).filter(Boolean))].filter((t) => t !== "emergency");
    const rawMwSaved = String(localStorage.getItem(`gs_mw_${slug}`) || "").trim();
    const selectedTypes = new Set(
      rawMwSaved ? rawMwSaved.split(",").map((x) => x.trim()).filter(Boolean) : []
    );
    if (!rawMwSaved && types.length) {
      types.forEach((t) => selectedTypes.add(String(t)));
    }
    wrapWidgets.textContent = "";
    types.forEach((t) => {
      const key = String(t);
      const lab = document.createElement("label");
      lab.className = "opt";
      const inp = document.createElement("input");
      inp.type = "checkbox";
      inp.value = key;
      inp.checked = selectedTypes.has(key);
      const span = document.createElement("span");
      span.textContent = GS_DEVICE_WIDGET_TYPE_LABELS[key] || key;
      lab.appendChild(inp);
      lab.appendChild(span);
      wrapWidgets.appendChild(lab);
    });

    btnApply.onclick = () => {
      const boxes = [...wrapClasses.querySelectorAll('input[type="checkbox"]')];
      const checked = [...wrapClasses.querySelectorAll('input[type="checkbox"]:checked')].map((x) => String(x.value));
      let classes = "";
      if (boxes.length) {
        if (!checked.length) {
          window.alert("Отметьте хотя бы один класс или нажмите «Сбросить».");
          return;
        }
        if (checked.length === boxes.length) classes = "";
        else classes = checked.join(",");
      }
      const gridHere = chkGrid.checked;
      const mwBoxes = [...wrapWidgets.querySelectorAll('input[type="checkbox"]')];
      const mwChecked = [...wrapWidgets.querySelectorAll('input[type="checkbox"]:checked')].map((x) => String(x.value));
      let mw = mwChecked.join(",");
      if (mwBoxes.length && mwChecked.length === mwBoxes.length) mw = "";
      if (mwBoxes.length && !mwChecked.length) {
        window.alert("Отметьте хотя бы один тип виджета или нажмите «Сбросить».");
        return;
      }
      const persist = chkPersist.checked;
      try {
        if (classes) localStorage.setItem(`gs_classes_${slug}`, classes);
        else localStorage.removeItem(`gs_classes_${slug}`);
        if (gridHere) localStorage.setItem(`gs_grid_${slug}`, "1");
        else localStorage.removeItem(`gs_grid_${slug}`);
        if (mw) localStorage.setItem(`gs_mw_${slug}`, mw);
        else localStorage.removeItem(`gs_mw_${slug}`);
      } catch (_) {}
      if (persist) {
        try {
          saveDevicePrefs(slug, { persist: true });
        } catch (_) {}
      } else {
        try {
          localStorage.removeItem(devicePrefsKey(slug));
        } catch (_) {}
      }
      window.location.reload();
    };

    btnReset.onclick = () => {
      const ok = window.confirm(
        "Сбросить настройки устройства для этого экрана?\n\nБудут очищены: классы, сетка/лента (gs_grid), фильтр виджетов (gs_mw). Серверный конфиг экранов не изменится."
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

/** Сколько строк в сетке расписания (сегодня+завтра); 0 — «пусто» с точки зрения данных. */
function schedulePayloadRowScore(payload) {
  try {
    const s = payload && payload.schedule;
    if (!s) return 0;
    return (s.today_rows || []).length + (s.tomorrow_rows || []).length;
  } catch (_) {
    return 0;
  }
}

async function refresh() {
  const fallbackDelay = Math.max(5000, window.__lastScreenPollMs || 10000);
  let nextDelay = fallbackDelay;
  if (__gsRefreshInFlight) {
    __gsRefreshQueued = true;
    return;
  }
  __gsRefreshInFlight = true;
  __gsRefreshQueued = false;
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

    const bases = buildScreenPollBases(primary, fallbackBase);

    let lastErr = null;
    const mobilePoll = Boolean(
      window.__lastScreenPayload &&
      window.__lastScreenPayload.screen &&
      window.__lastScreenPayload.screen.mobile_mode,
    );
    /** Не останавливаться на первом 200 с пустым расписанием (LAN без данных, облако полное). */
    let payload = null;
    let lastOkPayload = null;
    for (const b of bases) {
      const url = screenPollUrl(b, slug, cid, lab, dev, mobilePoll);
      try {
        const r = await fetchScreenPayload(url, hdr, Math.min(45000, timeoutMs + 5000));
        if (r.ok) {
          const p = await r.json();
          lastOkPayload = p;
          if (schedulePayloadRowScore(p) > 0) {
            payload = p;
            break;
          }
        } else {
          lastErr = new Error(`HTTP ${r.status}`);
        }
      } catch (e) {
        lastErr = e;
      }
    }
    if (!payload) {
      if (lastOkPayload) payload = lastOkPayload;
      else throw lastErr || new Error("poll failed");
    }
    if (gsRepairToxicGsClasses(slug, payload.pickable_classes || [])) {
      let bestRepair = null;
      let bestScoreR = -1;
      for (const b of bases) {
        const url2 = screenPollUrl(b, slug, cid, lab, dev, mobilePoll);
        try {
          const r2 = await fetchScreenPayload(url2, hdr, Math.min(45000, timeoutMs + 5000));
          if (r2.ok) {
            const p2 = await r2.json();
            const sc = schedulePayloadRowScore(p2);
            if (sc > bestScoreR) {
              bestScoreR = sc;
              bestRepair = p2;
            }
          }
        } catch (_) {}
      }
      if (bestRepair) payload = bestRepair;
    }
    nextDelay = Math.max(5000, (payload.screen.poll_interval_sec || 10) * 1000);
    window.__lastScreenPollMs = nextDelay;
    try {
      render(payload);
      lastRenderOkAt = Date.now();
      hideCrashBanner();
    } catch (e) {
      showCrashBanner(`Ошибка отрисовки: ${(e && e.message) ? e.message : String(e)}`);
    }
  } catch (e) {
    try {
      const msg = (e && e.message) ? String(e.message) : String(e || "poll failed");
      const sec = Math.max(5, Math.round(nextDelay / 1000));
      showCrashBanner(gsFormatScreenPollFailureMessage(msg, sec));
    } catch (_) {}
  } finally {
    __gsRefreshInFlight = false;
    const doAgain = __gsRefreshQueued;
    __gsRefreshQueued = false;
    if (doAgain) {
      scheduleNextRefresh(Math.min(800, Math.max(250, Math.round(nextDelay / 4))));
    } else {
      scheduleNextRefresh(nextDelay);
    }
  }
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
