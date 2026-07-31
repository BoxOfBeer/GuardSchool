(function (global) {
  "use strict";

  const {
    escapeHtml,
    escapeHtmlAttr,
    tvUiStrings,
    formatClockTimeString,
  } = global.GuardSchoolTvCore || {};
  function updateAllClocks(root) {
    const scope = root && root.querySelectorAll ? root : document;
    if (!scope.querySelectorAll) return;
    const text = formatClockTimeString();
    scope.querySelectorAll(".gs-screen-clock").forEach((el) => {
      el.textContent = text;
    });
  }

  function formatEmergencyCountdown(totalSec) {
    const safe = Math.max(0, Math.round(Number(totalSec) || 0));
    const mm = Math.floor(safe / 60);
    const ss = safe % 60;
    return `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
  }

  function updateAllEmergencyCountdowns(root) {
    const scope = root && root.querySelectorAll ? root : document;
    if (!scope.querySelectorAll) return;
    scope.querySelectorAll("[data-emergency-countdown='1']").forEach((el) => {
      const raw = Number(el.getAttribute("data-seconds-left"));
      const sec = Number.isFinite(raw) ? Math.max(0, Math.round(raw)) : 0;
      el.textContent = formatEmergencyCountdown(sec);
    });
  }

  function backdropSettingOff(settings) {
    if (!settings) return false;
    const v = settings.backdrop;
    if (v === false || v === 0) return true;
    if (v === "false" || v === "0") return true;
    return false;
  }

  /**
   * Подложка: полупрозрачный фон + blur (по умолчанию вкл.).
   * Для «Текст» после этого задаётся inline background — поэтому сюда же сбрасываем backdrop-filter в inline,
   * иначе в части браузеров размытие остаётся поверх прозрачного фона.
   */
  function applyWidgetBackdropClass(el, widget) {
    if (!el || !widget) return;
    const settings = widget.settings || {};
    const off = backdropSettingOff(settings);
    el.classList.toggle("no-backdrop", off);
    if (off) {
      el.style.setProperty("backdrop-filter", "none");
      el.style.setProperty("-webkit-backdrop-filter", "none");
    } else {
      el.style.removeProperty("backdrop-filter");
      el.style.removeProperty("-webkit-backdrop-filter");
    }
  }

  /** URL фона: ротация по списку из uploads или одно поле background_image. */
  function resolveBackgroundImageUrl(screen, gallery) {
    const urls = Array.isArray(gallery) ? gallery.filter((u) => u && String(u).trim()) : [];
    const forced = screen && screen.background_force_image ? String(screen.background_force_image).trim() : "";
    if (forced) return forced;
    const rotate = Boolean(screen && screen.background_rotate_enabled);
    let interval = Number(screen && screen.background_rotate_interval_sec);
    if (!Number.isFinite(interval)) interval = 3600;
    interval = Math.max(60, Math.min(86400, Math.round(interval)));
    if (rotate && urls.length >= 2) {
      const cursor = Number(screen && screen.background_rotate_cursor);
      const base = Number.isFinite(cursor) ? Math.max(0, Math.floor(cursor)) : 0;
      const epRaw = Number(screen && screen.background_rotate_epoch);
      const epoch = Number.isFinite(epRaw) ? Math.max(0, Math.floor(epRaw)) : 0;
      const nowSec = Math.floor(Date.now() / 1000);
      const steps = Math.floor(Math.max(0, nowSec - epoch) / interval);
      return urls[(base + steps) % urls.length] || "";
    }
    if (rotate && urls.length === 1) return urls[0];
    const single = screen && screen.background_image ? String(screen.background_image).trim() : "";
    if (single) return single;
    if (urls.length) return urls[0];
    return "";
  }

  const GS_BG_FADE_MS = 520;

  function cssBackgroundImageUrl(raw) {
    const s = String(raw || "").trim();
    if (!s) return "";
    const esc = s.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
    return `url("${esc}")`;
  }

  function ensureTvBgLayers(el) {
    if (!el.querySelector(".gs-tv-bg-under")) {
      const under = document.createElement("div");
      under.className = "gs-tv-bg-under gs-tv-bg-layer";
      const over = document.createElement("div");
      over.className = "gs-tv-bg-over gs-tv-bg-layer";
      el.insertBefore(under, el.firstChild);
      el.insertBefore(over, under.nextSibling);
    }
    return {
      under: el.querySelector(".gs-tv-bg-under"),
      over: el.querySelector(".gs-tv-bg-over"),
    };
  }

  const MOBILE_APPEARANCE_DEFAULTS = {
    background_color: "#172554",
    card_color: "#13234b",
    text_color: "#f8fafc",
    muted_color: "#cbd5e1",
    accent_color: "#38bdf8",
    font_size_px: 16,
    card_radius_px: 12,
    card_gap_px: 10,
  };

  function mobileHex(value, fallback) {
    const color = String(value || "").trim().toLowerCase();
    return /^#[0-9a-f]{6}$/.test(color) ? color : fallback;
  }

  function mobileNumber(value, fallback, minimum, maximum) {
    const number = Number(value);
    return Number.isFinite(number) ? Math.max(minimum, Math.min(maximum, Math.round(number))) : fallback;
  }

  function applyMobileAppearance(el, screen) {
    if (!el) return;
    const active = Boolean(screen && screen.mobile_mode);
    el.classList.toggle("gs-mobile-screen", active);
    const keys = [
      "--gs-mobile-background",
      "--gs-mobile-card",
      "--gs-mobile-text",
      "--gs-mobile-muted",
      "--gs-mobile-accent",
      "--gs-mobile-font-size",
      "--gs-mobile-card-radius",
      "--gs-mobile-card-gap",
    ];
    if (!active) {
      keys.forEach((key) => el.style.removeProperty(key));
      return;
    }
    const appearance = screen.mobile_appearance && typeof screen.mobile_appearance === "object"
      ? screen.mobile_appearance
      : {};
    el.style.setProperty("--gs-mobile-background", mobileHex(appearance.background_color, MOBILE_APPEARANCE_DEFAULTS.background_color));
    el.style.setProperty("--gs-mobile-card", mobileHex(appearance.card_color, MOBILE_APPEARANCE_DEFAULTS.card_color));
    el.style.setProperty("--gs-mobile-text", mobileHex(appearance.text_color, MOBILE_APPEARANCE_DEFAULTS.text_color));
    el.style.setProperty("--gs-mobile-muted", mobileHex(appearance.muted_color, MOBILE_APPEARANCE_DEFAULTS.muted_color));
    el.style.setProperty("--gs-mobile-accent", mobileHex(appearance.accent_color, MOBILE_APPEARANCE_DEFAULTS.accent_color));
    el.style.setProperty("--gs-mobile-font-size", `${mobileNumber(appearance.font_size_px, 16, 12, 30)}px`);
    el.style.setProperty("--gs-mobile-card-radius", `${mobileNumber(appearance.card_radius_px, 12, 0, 40)}px`);
    el.style.setProperty("--gs-mobile-card-gap", `${mobileNumber(appearance.card_gap_px, 10, 0, 40)}px`);
  }

  function applyTvScreenBackground(el, screen, gallery) {
    if (!el) return;
    applyMobileAppearance(el, screen);
    // В мобильном режиме оставляем дефолтный градиент страницы (без подстановки фоновых изображений).
    // Это проще для читаемости и не ломает вертикальную ленту.
    if (screen && screen.mobile_mode) {
      const prev = el.dataset.gsBgApplied || "";
      if (prev) {
        try {
          el.dataset.gsBgApplied = "";
          const under = el.querySelector(".gs-tv-bg-under");
          const over = el.querySelector(".gs-tv-bg-over");
          if (under) under.style.opacity = "0";
          if (over) over.style.opacity = "0";
        } catch (_) {}
      }
      return;
    }
    const u = resolveBackgroundImageUrl(screen, gallery);
    const prev = el.dataset.gsBgApplied || "";
    /** После root.innerHTML = "" слои .gs-tv-bg-under/over уничтожены, а dataset остаётся — иначе u===prev даёт ранний return без фона (тёмная заглушка). */
    const hasBgLayers = Boolean(el.querySelector(".gs-tv-bg-under"));
    if (u === prev && hasBgLayers) return;
    el.style.background = "";
    el._gsBgGen = (el._gsBgGen || 0) + 1;
    const gen = el._gsBgGen;
    const { under, over } = ensureTvBgLayers(el);
    if (!under || !over) return;
    const grid = el.querySelector(".screen-grid");
    if (grid) {
      grid.style.position = "relative";
      grid.style.zIndex = "2";
    }
    const finishNoImage = () => {
      el.dataset.gsBgApplied = "";
      under.style.transition = "opacity 0.38s ease";
      over.style.transition = "opacity 0.38s ease";
      under.style.opacity = "0";
      over.style.opacity = "0";
      if (el._gsBgFadeTimer) window.clearTimeout(el._gsBgFadeTimer);
      el._gsBgFadeTimer = window.setTimeout(() => {
        if (gen !== el._gsBgGen) return;
        under.style.backgroundImage = "";
        over.style.backgroundImage = "";
      }, 420);
    };
    if (!u) {
      finishNoImage();
      return;
    }
    const bi = cssBackgroundImageUrl(u);
    const applyImmediate = () => {
      if (gen !== el._gsBgGen) return;
      under.style.transition = "none";
      over.style.transition = "none";
      under.style.backgroundImage = bi;
      under.style.opacity = "1";
      over.style.opacity = "0";
      over.style.backgroundImage = "";
      el.dataset.gsBgApplied = u;
    };
    if (!prev) {
      applyImmediate();
      return;
    }
    const img = new Image();
    const startFade = () => {
      if (gen !== el._gsBgGen) return;
      over.style.transition = "none";
      over.style.backgroundImage = bi;
      over.style.opacity = "0";
      void over.offsetWidth;
      over.style.transition = `opacity ${GS_BG_FADE_MS}ms ease`;
      over.style.opacity = "1";
      if (el._gsBgFadeTimer) window.clearTimeout(el._gsBgFadeTimer);
      el._gsBgFadeTimer = window.setTimeout(() => {
        if (gen !== el._gsBgGen) return;
        under.style.transition = "none";
        under.style.backgroundImage = bi;
        under.style.opacity = "1";
        over.style.transition = "none";
        over.style.opacity = "0";
        over.style.backgroundImage = "";
        el.dataset.gsBgApplied = u;
      }, GS_BG_FADE_MS + 35);
    };
    img.onload = () => {
      if (gen !== el._gsBgGen) return;
      if (typeof img.decode === "function") {
        img.decode().then(startFade).catch(startFade);
      } else {
        startFade();
      }
    };
    img.onerror = startFade;
    img.src = u;
  }

  function buildTextOutlineShadow(px, color) {
    const n = Number(px);
    const p = Number.isFinite(n) ? Math.max(0, Math.min(8, Math.round(n))) : 0;
    if (p <= 0) return "none";
    const c = String(color || "rgba(0,0,0,0.85)").trim() || "rgba(0,0,0,0.85)";
    const parts = [];
    for (let dx = -p; dx <= p; dx++) {
      for (let dy = -p; dy <= p; dy++) {
        if (dx === 0 && dy === 0) continue;
        // круглый контур, без «квадратного» шума
        if (dx * dx + dy * dy > p * p) continue;
        parts.push(`${dx}px ${dy}px 0 ${c}`);
      }
    }
    return parts.join(",") || "none";
  }

  function applyTvTextOutline(el, screen) {
    if (!el) return;
    const px = screen && screen.tv_text_outline_px != null ? screen.tv_text_outline_px : 0;
    const col = screen && screen.tv_text_outline_color != null ? screen.tv_text_outline_color : "rgba(0,0,0,0.85)";
    el.style.setProperty("--gs-tv-text-shadow", buildTextOutlineShadow(px, col));
  }

  const CHECKIN_PLACE_ID_RE = /^[a-zA-Z0-9_-]{1,64}$/;

  function sanitizePlacesClient(raw) {
    const out = [];
    if (!Array.isArray(raw)) return out;
    const seen = new Set();
    for (let i = 0; i < raw.length; i++) {
      const p = raw[i];
      if (!p || typeof p !== "object") continue;
      const id = String(p.id || "").trim();
      const title = String(p.title || "").trim().slice(0, 200);
      if (!id || !CHECKIN_PLACE_ID_RE.test(id) || seen.has(id)) continue;
      seen.add(id);
      out.push({ id, title: title || id });
      if (out.length >= 500) break;
    }
    return out;
  }

  function resolveSubmitPlaces(screen, submitWidget) {
    const st = submitWidget.settings || {};
    const link = String(st.monitor_widget_id || "").trim();
    if (link) {
      const mw = (screen.widgets || []).find((w) => String(w.id) === link && w.type === "checkin_monitor");
      if (mw) return sanitizePlacesClient((mw.settings || {}).places);
    }
    const mons = (screen.widgets || []).filter((w) => w && w.type === "checkin_monitor");
    if (mons.length === 1) return sanitizePlacesClient((mons[0].settings || {}).places);
    return sanitizePlacesClient(st.places);
  }

  function bindCheckinWidgets(root, screenPayload) {
    if (!root || !screenPayload) return;
    const screen = screenPayload.screen || {};
    const slug = String(screen.slug || "").trim().toLowerCase();
    if (!slug) return;
    try {
      const prev = global.__gsCheckinMonitorTimers || [];
      for (let i = 0; i < prev.length; i++) {
        try {
          global.clearInterval(prev[i]);
        } catch (_) {}
      }
      global.__gsCheckinMonitorTimers = [];
    } catch (_) {}
    const adminPreview = Boolean(screenPayload.checkin_admin_preview);
    const fetchFn =
      typeof window.gsCheckinApiFetch === "function"
        ? window.gsCheckinApiFetch
        : function (url, opts) {
            return fetch(url, Object.assign({ credentials: "include" }, opts || {}));
          };

    function checkinBoardUrl(period, monitorWidgetId) {
      if (adminPreview) {
        return `/api/admin/checkin/board?screen_slug=${encodeURIComponent(slug)}&monitor_widget_id=${encodeURIComponent(
          monitorWidgetId,
        )}&range=${encodeURIComponent(period)}`;
      }
      return `/api/screen/${encodeURIComponent(slug)}/checkin/board?monitor_widget_id=${encodeURIComponent(
        monitorWidgetId,
      )}&range=${encodeURIComponent(period)}`;
    }

    function checkinExportUrl(period, monitorWidgetId) {
      if (adminPreview) {
        return `/api/admin/checkin/export.csv?screen_slug=${encodeURIComponent(slug)}&monitor_widget_id=${encodeURIComponent(
          monitorWidgetId,
        )}&range=${encodeURIComponent(period)}`;
      }
      return `/api/screen/${encodeURIComponent(slug)}/checkin/export.csv?monitor_widget_id=${encodeURIComponent(
        monitorWidgetId,
      )}&range=${encodeURIComponent(period)}`;
    }

    function checkinEventsStatusUrl(submitWidgetId, deviceHash, idList) {
      const ids = (idList || []).join(",");
      const q = `submit_widget_id=${encodeURIComponent(submitWidgetId)}&device_hash=${encodeURIComponent(deviceHash)}&ids=${encodeURIComponent(ids)}`;
      if (adminPreview) {
        return `/api/admin/checkin/events-status?screen_slug=${encodeURIComponent(slug)}&${q}`;
      }
      return `/api/screen/${encodeURIComponent(slug)}/checkin/events-status?${q}`;
    }

    function checkinConfirmApiUrl(isAll) {
      if (adminPreview) {
        return isAll ? "/api/admin/checkin/confirm-all" : "/api/admin/checkin/confirm";
      }
      return isAll
        ? `/api/screen/${encodeURIComponent(slug)}/checkin/confirm-all`
        : `/api/screen/${encodeURIComponent(slug)}/checkin/confirm`;
    }

    root.querySelectorAll('[data-gs-checkin-role="submit"]').forEach((wrap) => {
      const block = wrap.closest(".screen-widget");
      const widgetId = block && block.dataset ? String(block.dataset.widgetId || "") : "";
      const widget = (screen.widgets || []).find((w) => String(w.id) === widgetId);
      if (!widget || widget.type !== "checkin_submit") return;
      const places = resolveSubmitPlaces(screen, widget);
      const ws = widget.settings || {};
      const L = ws.labels || {};
      const sel = wrap.querySelector(".gs-checkin-place");
      const levelsEl = wrap.querySelector(".gs-checkin-levels");
      const devInput = wrap.querySelector(".gs-checkin-device");
      const ta = wrap.querySelector(".gs-checkin-comment");
      const btn = wrap.querySelector(".gs-checkin-send");
      const saveBtn = wrap.querySelector(".gs-checkin-save");
      const recentEl = wrap.querySelector(".gs-checkin-recent");
      const stEl = wrap.querySelector(".gs-checkin-status");
      if (!sel || !levelsEl || !btn) return;
      const radioName = `gs-checkin-lv-${slug}-${widgetId}`;
      sel.innerHTML = places
        .map((p) => `<option value="${escapeHtmlAttr(p.id)}">${escapeHtml(p.title || p.id)}</option>`)
        .join("");
      const okT = escapeHtml(String(L.ok || "В порядке"));
      const wT = escapeHtml(String(L.warn || "Внимание"));
      const aT = escapeHtml(String(L.alert || "Проблема"));
      levelsEl.innerHTML = `<label class="gs-checkin-seg gs-checkin-seg--ok"><input type="radio" name="${escapeHtmlAttr(
        radioName,
      )}" class="gs-checkin-lv" value="ok" checked /><span>${okT}</span></label>
        <label class="gs-checkin-seg gs-checkin-seg--warn"><input type="radio" name="${escapeHtmlAttr(
          radioName,
        )}" class="gs-checkin-lv" value="warn" /><span>${wT}</span></label>
        <label class="gs-checkin-seg gs-checkin-seg--alert"><input type="radio" name="${escapeHtmlAttr(
          radioName,
        )}" class="gs-checkin-lv" value="alert" /><span>${aT}</span></label>`;

      function readDeviceHash() {
        let device_hash = "";
        try {
          const hk = `gs_checkin_hash_${slug}`;
          device_hash = localStorage.getItem(hk) || "";
          if (!device_hash || device_hash.length < 8) {
            device_hash =
              typeof crypto !== "undefined" && crypto.randomUUID
                ? crypto.randomUUID()
                : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
            localStorage.setItem(hk, device_hash);
          }
        } catch (_) {
          device_hash = `x-${Date.now()}`;
        }
        const tail = device_hash.slice(0, 24);
        return {
          device_hash,
          tail,
          formKey: `gs_checkin_form_${slug}_${widgetId}_${tail}`,
          placeKey: `gs_checkin_place_${slug}_${widgetId}_${tail}`,
          recentKey: `gs_checkin_recent_${slug}_${widgetId}_${tail}`,
        };
      }

      function loadRecentStorage() {
        const ctx = readDeviceHash();
        try {
          const raw = localStorage.getItem(ctx.recentKey);
          const arr = raw ? JSON.parse(raw) : [];
          return { ctx, list: Array.isArray(arr) ? arr.slice(0, 3) : [] };
        } catch (_) {
          return { ctx, list: [] };
        }
      }

      function saveRecentStorage(ctx, list) {
        try {
          localStorage.setItem(ctx.recentKey, JSON.stringify(list.slice(0, 3)));
        } catch (_) {}
      }

      function applySavedForm() {
        const ctx = readDeviceHash();
        try {
          const raw = localStorage.getItem(ctx.formKey);
          if (raw && devInput && ta) {
            const o = JSON.parse(raw);
            if (o && typeof o === "object") {
              if (o.device_name != null) devInput.value = String(o.device_name);
              if (o.comment != null) ta.value = String(o.comment);
              const lv = String(o.level || "ok");
              const safeLv = lv === "warn" || lv === "alert" ? lv : "ok";
              const inp = wrap.querySelector(`.gs-checkin-lv[value="${safeLv}"]`);
              if (inp) inp.checked = true;
              if (o.place_id) {
                const opt = Array.prototype.find.call(sel.options, (op) => op.value === String(o.place_id));
                if (opt) sel.value = opt.value;
              }
              return ctx;
            }
          }
        } catch (_) {}
        try {
          if (devInput) {
            const k = `gs_checkin_dn_${slug}_${widgetId}`;
            const saved = localStorage.getItem(k);
            if (saved) devInput.value = saved;
          }
          const sp = localStorage.getItem(ctx.placeKey);
          if (sp) {
            const opt = Array.prototype.find.call(sel.options, (op) => op.value === String(sp));
            if (opt) sel.value = opt.value;
          }
        } catch (_) {}
        return ctx;
      }

      let hashCtx;
      if (!wrap.dataset.gsCheckinHydrated) {
        hashCtx = applySavedForm();
        wrap.dataset.gsCheckinHydrated = "1";
      } else {
        hashCtx = readDeviceHash();
      }

      sel.addEventListener("change", () => {
        hashCtx = readDeviceHash();
        try {
          localStorage.setItem(hashCtx.placeKey, sel.value);
        } catch (_) {}
      });

      function persistForm() {
        hashCtx = readDeviceHash();
        const rad = wrap.querySelector(".gs-checkin-lv:checked");
        const level = rad ? String(rad.value || "ok") : "ok";
        const payload = {
          device_name: devInput ? String(devInput.value || "") : "",
          place_id: sel.value,
          comment: ta ? String(ta.value || "") : "",
          level,
        };
        try {
          localStorage.setItem(hashCtx.formKey, JSON.stringify(payload));
          localStorage.setItem(`gs_checkin_dn_${slug}_${widgetId}`, String(payload.device_name || "").trim());
          localStorage.setItem(hashCtx.placeKey, payload.place_id);
          if (stEl) stEl.textContent = "Сохранено.";
        } catch (_) {
          if (stEl) stEl.textContent = "Не удалось сохранить.";
        }
      }

      if (saveBtn) saveBtn.onclick = () => persistForm();

      async function refreshRecentStatus() {
        if (!recentEl) return;
        const { ctx, list } = loadRecentStorage();
        if (!list.length) {
          recentEl.innerHTML = "";
          return;
        }
        const ids = list.map((x) => x && x.id).filter(Boolean);
        if (!ids.length) {
          recentEl.innerHTML = "";
          return;
        }
        try {
          const url = checkinEventsStatusUrl(widgetId, ctx.device_hash, ids);
          const r = await fetchFn(url);
          const data = await r.json().catch(() => ({}));
          const items = (data && data.items) || [];
          const byId = {};
          items.forEach((it) => {
            byId[it.id] = it;
          });
          const lines = list
            .map((rec) => {
              const id = rec && rec.id;
              if (!id) return "";
              const it = byId[id];
              const conf = it && it.confirmed_at;
              const cd = it && it.confirmed_date;
              const ct = it && it.confirmed_time;
              const lab = escapeHtml(String((rec && rec.label) || `#${id}`));
              const sentAt =
                rec && rec.created_date && rec.created_time
                  ? ` <span class="gs-checkin-sent-at">· ${escapeHtml(String(rec.created_date))} ${escapeHtml(String(rec.created_time))}</span>`
                  : "";
              const done = conf
                ? ` <span class="gs-checkin-confirm-pill" title="Подтверждено"><span class="gs-checkin-confirm-icon" aria-hidden="true">✓</span> ${escapeHtml(
                    String(cd || ""),
                  )} ${escapeHtml(String(ct || ""))}</span>`
                : "";
              return `<div class="gs-checkin-recent-row">${lab}${sentAt}${done}</div>`;
            })
            .filter(Boolean)
            .join("");
          recentEl.innerHTML = lines
            ? `<div class="gs-checkin-recent-heading">Последние отметки</div>${lines}`
            : "";
        } catch (_) {
          recentEl.innerHTML = "";
        }
      }

      if (wrap._gsCheckinRecentPoll) {
        try {
          window.clearInterval(wrap._gsCheckinRecentPoll);
        } catch (_) {}
        wrap._gsCheckinRecentPoll = null;
      }
      wrap._gsCheckinRecentPoll = window.setInterval(refreshRecentStatus, 20000);
      refreshRecentStatus();

      btn.onclick = async () => {
        if (!places.length) {
          if (stEl) stEl.textContent = "Нет мест в настройках виджета.";
          return;
        }
        const device_name = devInput ? String(devInput.value || "").trim() : "";
        if (!device_name) {
          if (stEl) stEl.textContent = "Укажите имя.";
          return;
        }
        let comment = ta ? String(ta.value || "").trim() : "";
        const rad = wrap.querySelector(".gs-checkin-lv:checked");
        const level = rad ? String(rad.value || "ok") : "ok";
        if (level === "alert" && !comment) {
          if (stEl) stEl.textContent = "Нужен комментарий.";
          return;
        }
        hashCtx = readDeviceHash();
        const device_hash = hashCtx.device_hash;
        try {
          localStorage.setItem(`gs_checkin_dn_${slug}_${widgetId}`, device_name);
        } catch (_) {}
        if (stEl) stEl.textContent = "";
        try {
          const r = await fetchFn("/api/checkin/event", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              screen_slug: slug,
              submit_widget_id: widgetId,
              place_id: sel.value,
              level,
              comment,
              device_name,
              device_hash: device_hash.slice(0, 128),
            }),
          });
          const data = await r.json().catch(() => ({}));
          if (!r.ok) {
            const d = data.detail;
            const msg = Array.isArray(d) ? d.map((x) => (x && x.msg) || "").join(" ") : d || r.statusText;
            throw new Error(msg);
          }
          if (stEl) stEl.textContent = "Отправлено.";
          const pt =
            (places.find((p) => p.id === sel.value) || {}).title ||
            sel.options[sel.selectedIndex]?.textContent ||
            sel.value;
          const newId = data && data.id;
          if (newId) {
            const { ctx, list } = loadRecentStorage();
            const label = `${pt} — ${device_name}`;
            const next = [
              {
                id: newId,
                label,
                created_date: data.created_date || "",
                created_time: data.created_time || "",
              },
              ...list.filter((x) => x && x.id !== newId),
            ];
            saveRecentStorage(ctx, next.slice(0, 3));
            refreshRecentStatus();
          }
        } catch (e) {
          if (stEl) stEl.textContent = e.message || String(e);
        }
      };
    });

    root.querySelectorAll('[data-gs-checkin-role="monitor"]').forEach((wrap) => {
      const block = wrap.closest(".screen-widget");
      const widgetId = block && block.dataset ? String(block.dataset.widgetId || "") : "";
      const widget = (screen.widgets || []).find((w) => String(w.id) === widgetId);
      if (!widget || widget.type !== "checkin_monitor") return;
      const periodSel = wrap.querySelector(".gs-checkin-period");
      const sumEl = wrap.querySelector(".gs-checkin-monitor-summary");
      const jouEl = wrap.querySelector(".gs-checkin-monitor-journal");
      const expBtn = wrap.querySelector(".gs-checkin-export");
      const cfAllBtn = wrap.querySelector(".gs-checkin-confirm-all");
      if (!periodSel || !sumEl || !jouEl) return;
      const timerKey = "_gsCheckinMonTimer";
      if (wrap[timerKey]) {
        try {
          window.clearInterval(wrap[timerKey]);
        } catch (_) {}
        wrap[timerKey] = null;
      }
      const pl = (widget.settings && widget.settings.labels) || {};
      const levelTitle = (code) => {
        const c = String(code || "").toLowerCase();
        if (c === "ok") return escapeHtml(String(pl.ok || "В порядке"));
        if (c === "warn") return escapeHtml(String(pl.warn || "Внимание"));
        if (c === "alert") return escapeHtml(String(pl.alert || "Проблема"));
        if (c === "none") return escapeHtml(String(pl.none || "Нет отметки"));
        return escapeHtml(String(code || ""));
      };
      const levelBadgeHtml = (code) => {
        const c = String(code || "").toLowerCase();
        const tag =
          c === "ok"
            ? "ok"
            : c === "warn"
              ? "warn"
              : c === "alert"
                ? "alert"
                : c === "none"
                  ? "none"
                  : "muted";
        return `<span class="gs-checkin-badge gs-checkin-badge--${tag}">${levelTitle(code)}</span>`;
      };
      async function refresh() {
        const period = periodSel.value || "day";
        let data = {};
        try {
          const url = checkinBoardUrl(period, widgetId);
          const r = await fetchFn(url);
          data = await r.json().catch(() => ({}));
          if (!r.ok) {
            sumEl.innerHTML = `<div class="hint">${escapeHtml(String((data && data.detail) || r.statusText))}</div>`;
            jouEl.innerHTML = "";
            return;
          }
          const summ = (data && data.summary) || [];
          const placeById = {};
          (data.places || []).forEach((p) => {
            if (p && p.id) placeById[p.id] = p.title || p.id;
          });
          const sRows = summ
            .map((row) => {
              if (row.status === "none") {
                return `<tr>
                  <td>${escapeHtml(row.place_title || row.place_id)}</td>
                  <td class="gs-checkin-col-comment"></td>
                  <td colspan="4">${levelBadgeHtml(
                  "none",
                )}</td></tr>`;
              }
              const ev = row.last_event || {};
              const hasEv = ev && ev.id;
              const comment = escapeHtml(String(ev.comment || "").slice(0, 200));
              const surname = escapeHtml(String(ev.device_name || ""));
              const confBtn =
                hasEv && !ev.confirmed_at
                  ? `<button type="button" class="gs-checkin-s-confirm secondary-btn compact-btn" data-checkin-confirm-id="${Number(ev.id)}">Подтвердить</button>`
                  : hasEv && ev.confirmed_at
                    ? `<span class="gs-checkin-confirm-pill gs-checkin-confirm-pill--compact" title="Подтверждено"><span class="gs-checkin-confirm-icon" aria-hidden="true">✓</span></span>`
                    : "";
              return `<tr>
              <td>${escapeHtml(row.place_title || row.place_id)}</td>
              <td class="gs-checkin-col-comment">${comment}</td>
              <td>${levelBadgeHtml(row.status)}</td>
              <td class="gs-checkin-col-surname">${surname}</td>
              <td>${escapeHtml(String(ev.created_date || ""))}</td>
              <td>${escapeHtml(String(ev.created_time || ""))}</td>
              <td class="gs-checkin-actions-cell gs-checkin-col-confirm">${confBtn}</td>
            </tr>`;
            })
            .join("");
          sumEl.innerHTML = `<div class="gs-checkin-range-label">${escapeHtml(String(data.range_label || ""))}</div>
            <table class="gs-checkin-table gs-checkin-table--boxed"><thead><tr>
              <th>Место</th><th>Комментарий</th><th>Состояние</th><th>Фамилия</th><th class="gs-checkin-col-date">Дата</th><th class="gs-checkin-col-time">Время</th><th class="gs-checkin-col-confirm"></th>
            </tr></thead><tbody>${sRows}</tbody></table>`;
          const jou = (data && data.journal) || [];
          const jRows = jou
            .map((ev) => {
              const btn =
                ev.confirmed_at
                  ? `<span class="gs-checkin-confirm-pill"><span class="gs-checkin-confirm-icon" aria-hidden="true">✓</span> ${escapeHtml(
                      String(ev.confirmed_date || ""),
                    )} ${escapeHtml(String(ev.confirmed_time || ""))}</span>`
                  : `<button type="button" class="gs-checkin-j-confirm secondary-btn compact-btn" data-checkin-confirm-id="${Number(ev.id)}">Подтвердить</button>`;
              return `<tr>
              <td>${escapeHtml(String(ev.created_date || ""))}</td>
              <td>${escapeHtml(String(ev.created_time || ""))}</td>
              <td>${escapeHtml(String(placeById[ev.place_id] || ev.place_id || ""))}</td>
              <td>${levelBadgeHtml(ev.level)}</td>
              <td>${escapeHtml(String(ev.device_name || ""))}</td>
              <td>${escapeHtml(String(ev.comment || "").slice(0, 200))}</td>
              <td class="gs-checkin-actions-cell">${btn}</td>
            </tr>`;
            })
            .join("");
          jouEl.innerHTML = `<div class="gs-checkin-section-title">Журнал</div>
            <table class="gs-checkin-table gs-checkin-table--boxed"><thead><tr>
              <th>Дата</th><th>Время</th><th>Место</th><th>Уровень</th><th>Имя</th><th>Комментарий</th><th></th>
            </tr></thead><tbody>${jRows}</tbody></table>`;
        } catch (e) {
          sumEl.innerHTML = `<div class="hint">${escapeHtml(e.message || String(e))}</div>`;
          jouEl.innerHTML = "";
        }
      }
      if (!wrap._gsCheckinConfirmDeleg) {
        wrap._gsCheckinConfirmDeleg = true;
        wrap.addEventListener("click", async (e) => {
          const b = e.target && e.target.closest && e.target.closest("[data-checkin-confirm-id]");
          if (!b || !wrap.contains(b)) return;
          const id = Number(b.getAttribute("data-checkin-confirm-id"));
          if (!id) return;
          try {
            const body = adminPreview
              ? { screen_slug: slug, monitor_widget_id: widgetId, event_id: id }
              : { monitor_widget_id: widgetId, event_id: id };
            const r = await fetchFn(checkinConfirmApiUrl(false), {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(body),
            });
            if (!r.ok) {
              let detail = r.statusText;
              try {
                const errBody = await r.json();
                detail = (errBody && errBody.detail) || detail;
              } catch (_) {}
              throw new Error(typeof detail === "string" ? detail : String(detail));
            }
            await refresh();
          } catch (err) {
            if (sumEl) sumEl.innerHTML = `<div class="hint">${escapeHtml(err.message || String(err))}</div>`;
          }
        });
      }
      if (cfAllBtn && !cfAllBtn.dataset.gsBound) {
        cfAllBtn.dataset.gsBound = "1";
        cfAllBtn.onclick = async () => {
          const period = periodSel.value || "day";
          try {
            const body = adminPreview
              ? { screen_slug: slug, monitor_widget_id: widgetId, range: period }
              : { monitor_widget_id: widgetId, range: period };
            const r = await fetchFn(checkinConfirmApiUrl(true), {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(body),
            });
            if (!r.ok) {
              let detail = r.statusText;
              try {
                const errBody = await r.json();
                detail = (errBody && errBody.detail) || detail;
              } catch (_) {}
              throw new Error(typeof detail === "string" ? detail : String(detail));
            }
            await refresh();
          } catch (err) {
            if (sumEl) sumEl.innerHTML = `<div class="hint">${escapeHtml(err.message || String(err))}</div>`;
          }
        };
      }
      periodSel.onchange = () => refresh();
      if (expBtn) {
        expBtn.onclick = async () => {
          const period = periodSel.value || "day";
          const url = checkinExportUrl(period, widgetId);
          try {
            const r = await fetchFn(url);
            if (!r.ok) {
              let detail = r.statusText;
              try {
                const errBody = await r.json();
                detail = (errBody && errBody.detail) || detail;
              } catch (_) {}
              throw new Error(typeof detail === "string" ? detail : String(detail));
            }
            const blob = await r.blob();
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = `checkin_${slug}_${widgetId}.csv`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(a.href);
          } catch (e) {
            if (sumEl) sumEl.innerHTML = `<div class="hint">${escapeHtml(e.message || String(e))}</div>`;
          }
        };
      }
      refresh();
      const iv = window.setInterval(refresh, 45000);
      wrap[timerKey] = iv;
      try {
        if (!global.__gsCheckinMonitorTimers) global.__gsCheckinMonitorTimers = [];
        global.__gsCheckinMonitorTimers.push(iv);
      } catch (_) {}
    });
  }

  global.GuardSchoolTvShell = {
    updateAllClocks,
    formatEmergencyCountdown,
    updateAllEmergencyCountdowns,
    backdropSettingOff,
    applyWidgetBackdropClass,
    resolveBackgroundImageUrl,
    cssBackgroundImageUrl,
    ensureTvBgLayers,
    applyMobileAppearance,
    applyTvScreenBackground,
    buildTextOutlineShadow,
    applyTvTextOutline,
    bindCheckinWidgets,
  };
})(typeof window !== "undefined" ? window : globalThis);
