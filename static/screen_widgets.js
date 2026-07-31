(function (global) {
  "use strict";
  const core = global.GuardSchoolTvCore || {};
  const sched = global.GuardSchoolTvSchedule || {};
  const shell = global.GuardSchoolTvShell || {};
  const {
    formatWidgetDateLine,
    formatClockTimeString,
    getDisplayFromPayload,
    adjustedDateFromDisplay,
    localeTagFromUi,
    capitalizeFirst,
    escapeHtml,
    escapeHtmlAttr,
    tvUiStrings,
    resolveSchoolNewsMediaSrc,
    schoolNewsImageSrcWithV,
    sanitizeSchoolNewsDisplayHtml,
    schoolNewsBodyFontPx,
    checkinWidgetRootStyle,
    checkinWidgetRootFluidClass,
    capitalizeSubjectDisplay,
    formatDateLabel,
  } = core;
  const {
    buildScheduleTable,
    buildBellStatus,
    buildBellCountdown,
    buildUpcomingHolidays,
  } = sched;

  const marqueeState = new Map();
  // announcementsState: widgetId -> { contentKey, order, pos, lastIdx }
  const announcementsState = new Map();
  // schoolNewsState: widgetId -> { contentKey, order, pos, lastIdx, currentIdx }
  const schoolNewsState = new Map();

  function carouselApi() {
    return global.GuardSchoolWidgets && global.GuardSchoolWidgets.carousel;
  }

  function clearCarouselTimeouts() {
    const c = carouselApi();
    if (c && c.clearTimeouts) c.clearTimeouts();
  }

  /** Удалить состояние каруселей, которых уже нет в конфиге экрана. */
  function pruneStaleCarouselState(screen) {
    const c = carouselApi();
    if (c && c.prune) c.prune(screen);
  }

  function pruneStaleMarqueeState(screen) {
    const widgets = (screen && screen.widgets) || [];
    const allowed = new Set(widgets.filter((w) => w.type === "marquee").map((w) => w.id));
    for (const id of [...marqueeState.keys()]) {
      if (!allowed.has(id)) marqueeState.delete(id);
    }
  }

  function pruneStaleWidgetState(screen) {
    pruneStaleCarouselState(screen);
    pruneStaleMarqueeState(screen);
  }

  function clearAllTimers() {
    clearCarouselTimeouts();
    try {
      const prev = global.__gsCheckinMonitorTimers || [];
      for (let i = 0; i < prev.length; i++) {
        try {
          global.clearInterval(prev[i]);
        } catch (_) {}
      }
      global.__gsCheckinMonitorTimers = [];
    } catch (_) {}
  }

  function renderCheckinSubmitWidget(widget) {
    const ws = widget.settings || {};
    const title = escapeHtml(String(ws.labels && ws.labels.module_title ? ws.labels.module_title : "Оперативная отметка"));
    const saveLbl = escapeHtml(String(ws.labels && ws.labels.save ? ws.labels.save : "Сохранить"));
    const fluid = checkinWidgetRootFluidClass(ws);
    const rootStyle = checkinWidgetRootStyle(ws);
    return `<div class="gs-checkin-submit${fluid}" data-gs-checkin-role="submit" style="${rootStyle}">
        <div class="gs-checkin-submit-title">${title}</div>
        <label style="display:flex;flex-direction:column;gap:4px;"><span data-lbl="device">${escapeHtml(String(ws.labels && ws.labels.device_name ? ws.labels.device_name : "Имя"))}</span>
          <input type="text" class="gs-checkin-device standard-input" maxlength="200" style="width:100%;box-sizing:border-box;" /></label>
        <label style="display:flex;flex-direction:column;gap:4px;"><span data-lbl="place">${escapeHtml(String(ws.labels && ws.labels.place ? ws.labels.place : "Место"))}</span>
          <select class="gs-checkin-place standard-input" style="width:100%;"></select></label>
        <div class="gs-checkin-levels-wrap"><span data-lbl="state">${escapeHtml(String(ws.labels && ws.labels.state ? ws.labels.state : "Состояние"))}</span>
          <div class="gs-checkin-levels"></div></div>
        <label style="display:flex;flex-direction:column;gap:4px;"><span data-lbl="comment">${escapeHtml(String(ws.labels && ws.labels.comment ? ws.labels.comment : "Комментарий"))}</span>
          <textarea class="gs-checkin-comment standard-input" rows="2" maxlength="4000" style="width:100%;resize:vertical;box-sizing:border-box;"></textarea></label>
        <div class="gs-checkin-actions" style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:4px;">
          <button type="button" class="gs-checkin-send primary-btn">${escapeHtml(String(ws.labels && ws.labels.submit ? ws.labels.submit : "Отправить"))}</button>
          <button type="button" class="gs-checkin-save secondary-btn compact-btn">${saveLbl}</button>
        </div>
        <div class="gs-checkin-recent"></div>
        <div class="gs-checkin-status hint" style="min-height:1.2em;"></div>
      </div>`;
  }

  function renderCheckinMonitorWidget(widget) {
    const ws = widget.settings || {};
    const pt = escapeHtml(String(ws.panel_title || "Сводка мест"));
    const fluid = checkinWidgetRootFluidClass(ws);
    const rootStyle = checkinWidgetRootStyle(ws);
    return `<div class="gs-checkin-monitor${fluid}" data-gs-checkin-role="monitor" style="${rootStyle}">
        <div class="gs-checkin-toolbar">
          <strong class="gs-checkin-panel-heading">${pt}</strong>
          <div class="gs-checkin-toolbar-actions">
            <label class="gs-checkin-period-label"><span>Период</span>
              <select class="gs-checkin-period standard-input">
                <option value="day">День</option>
                <option value="week">Неделя</option>
                <option value="month">Месяц</option>
              </select>
            </label>
            <button type="button" class="gs-checkin-confirm-all secondary-btn compact-btn">Подтвердить всех</button>
            <button type="button" class="gs-checkin-export secondary-btn compact-btn">CSV</button>
          </div>
        </div>
        <div class="gs-checkin-monitor-summary"></div>
        <div class="gs-checkin-monitor-journal"></div>
      </div>`;
  }

  /** Как на сервере: первая буква предмета — заглавная (в т.ч. после BOM/пробелов); дублируем здесь, чтобы ТВ не зависел от перезапуска сервера и кэша. */
  function shuffleInPlace(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      const tmp = arr[i];
      arr[i] = arr[j];
      arr[j] = tmp;
    }
    return arr;
  }

  function announcementsContentKey(blocks) {
    // Достаточно стабильный ключ: если блоки поменялись — перегенерим порядок.
    return `${blocks.length}|${blocks.join("\u0000")}`;
  }

  function ensureAnnouncementsOrder(widgetId, blocks) {
    if (!widgetId) return null;
    const key = announcementsContentKey(blocks);
    let st = announcementsState.get(widgetId);
    if (!st || st.contentKey !== key || !Array.isArray(st.order) || st.order.length !== blocks.length) {
      const order = shuffleInPlace(Array.from({ length: blocks.length }, (_, i) => i));
      st = { contentKey: key, order, pos: 0, lastIdx: null };
      announcementsState.set(widgetId, st);
    }
    return st;
  }

  function nextAnnouncementIndex(widgetId, blocks) {
    const st = ensureAnnouncementsOrder(widgetId, blocks);
    if (!st) return 0;
    if (!blocks.length) return 0;
    if (st.pos >= st.order.length) {
      // Цикл закончился: перемешиваем заново. Постараемся не повторить сразу предыдущий.
      const order = shuffleInPlace(Array.from({ length: blocks.length }, (_, i) => i));
      if (blocks.length >= 2 && st.lastIdx != null && order[0] === st.lastIdx) {
        // swap first with another
        const swapAt = 1;
        const tmp = order[0];
        order[0] = order[swapAt];
        order[swapAt] = tmp;
      }
      st.order = order;
      st.pos = 0;
    }
    const idx = st.order[st.pos] != null ? st.order[st.pos] : 0;
    st.pos += 1;
    st.lastIdx = idx;
    announcementsState.set(widgetId, st);
    return idx;
  }

  function timeSlotAnnouncementIndex(widgetId, blocks, slot) {
    // Для режима ротации по времени: хотим детерминированно менять блок при смене slot,
    // но без повторов и с перемешиванием по циклам.
    const st = ensureAnnouncementsOrder(widgetId, blocks);
    if (!st) return 0;
    const lastSlot = st.lastSlot;
    if (lastSlot === slot && Number.isFinite(st.currentIdx)) return st.currentIdx;
    const idx = nextAnnouncementIndex(widgetId, blocks);
    st.lastSlot = slot;
    st.currentIdx = idx;
    announcementsState.set(widgetId, st);
    return idx;
  }

  function schoolNewsContentKey(rows) {
    // Достаточно стабильный ключ: если поменялся набор/порядок новостей — перегенерим order.
    // id+created_at достаточно, summary может быть длинным.
    try {
      return (rows || [])
        .map(
          (x) =>
            `${String(x && x.id || "")}|${String(x && x.created_at || "")}|${(x && Array.isArray(x.gallery_images) ? x.gallery_images.map(String).join(",") : "").slice(0, 240)}`,
        )
        .join("\u0000");
    } catch (_) {
      return String((rows || []).length || 0);
    }
  }

  function ensureSchoolNewsOrder(widgetId, rows) {
    if (!widgetId) return null;
    const key = schoolNewsContentKey(rows);
    let st = schoolNewsState.get(widgetId);
    if (!st || st.contentKey !== key || !Array.isArray(st.order) || st.order.length !== rows.length) {
      const order = shuffleInPlace(Array.from({ length: rows.length }, (_, i) => i));
      st = { contentKey: key, order, pos: 0, lastIdx: null, currentIdx: rows.length ? order[0] : 0 };
      schoolNewsState.set(widgetId, st);
    }
    return st;
  }

  function nextSchoolNewsIndex(widgetId, rows) {
    const st = ensureSchoolNewsOrder(widgetId, rows);
    if (!st) return 0;
    if (!rows.length) return 0;
    if (st.pos >= st.order.length) {
      const order = shuffleInPlace(Array.from({ length: rows.length }, (_, i) => i));
      if (rows.length >= 2 && st.lastIdx != null && order[0] === st.lastIdx) {
        const tmp = order[0];
        order[0] = order[1];
        order[1] = tmp;
      }
      st.order = order;
      st.pos = 0;
    }
    const idx = st.order[st.pos] != null ? st.order[st.pos] : 0;
    st.pos += 1;
    st.lastIdx = idx;
    st.currentIdx = idx;
    schoolNewsState.set(widgetId, st);
    return idx;
  }

  function buildAnnouncements(settings, announcementsData = [], widgetId = "", ctx = null) {
    const useManual = Boolean(settings && settings.useManual);
    const raw = String(settings.items || "");
    const manual = useManual ? raw.split("\n").map((item) => item.trim()).filter(Boolean) : [];
    const blocks = Array.isArray(announcementsData) ? announcementsData.map((x) => String(x.text || "").trim()).filter(Boolean) : [];
    const rotateSec = Math.max(5, Number(settings.rotateSec || 30));
    const advanceOnShow = Boolean(settings && settings.advanceOnShow);
    const randomize = settings && settings.randomize === false ? false : true;
    let text = "";
    if (manual.length) {
      text = manual.join("\n");
    } else if (blocks.length) {
      const isCarouselShow = Boolean(ctx && ctx.mode === "carousel_show");
      if (randomize && widgetId) {
        if (advanceOnShow && isCarouselShow) {
          const idx = nextAnnouncementIndex(widgetId, blocks);
          text = blocks[idx] || "";
        } else {
          const slot = Math.floor(Date.now() / 1000 / rotateSec);
          const idx = timeSlotAnnouncementIndex(widgetId, blocks, slot);
          text = blocks[idx] || "";
        }
      } else if (advanceOnShow && isCarouselShow && widgetId) {
        // Старое поведение по кругу (без рандома), если рандом выключен.
        const st = announcementsState.get(widgetId);
        const prev = st && Number.isFinite(st.lastIdx) ? st.lastIdx : -1;
        const idx = ((prev + 1) % blocks.length + blocks.length) % blocks.length;
        announcementsState.set(widgetId, { contentKey: announcementsContentKey(blocks), order: [], pos: 0, lastIdx: idx });
        text = blocks[idx] || "";
      } else {
        const slot = Math.floor(Date.now() / 1000 / rotateSec);
        text = blocks[slot % blocks.length] || "";
      }
    }
    const items = text.split("\n").map((item) => item.trimEnd());
    const L = tvUiStrings();
    const rows = items.length && (items.some((x) => x.trim() !== "")) ? items.map((item) => `<div>${item || "&nbsp;"}</div>`).join("") : `<div>${L.noAnnouncements}</div>`;
    return `
    <div class="info-widget-box" style="background:${settings.background};color:${settings.color};">
      <div style="font-size:${settings.titleFontSize || 18}px;${settings.bold ? "font-weight:700;" : ""}">${L.announcements}</div>
      <div style="font-size:${settings.fontSize || 18}px;${settings.bold ? "font-weight:700;" : ""}">${rows}</div>
    </div>
  `;
  }

  function buildMarquee(widget, marqueeData = []) {
    const settings = widget.settings || {};
    const manual = Boolean(settings.useManual)
      ? String(settings.items || "").split("\n").map((item) => item.trim()).filter(Boolean)
      : [];
    const items = manual.length ? manual : (Array.isArray(marqueeData) ? marqueeData.map((x) => String(x).trim()).filter(Boolean) : []);
    const L = tvUiStrings();
    const text = items.length ? items.join("   •   ") : L.noAnnouncements;
    const charCount = Math.max(1, text.length);
    const cpmRaw = settings.charsPerMin;
    let duration;
    if (cpmRaw != null && cpmRaw !== "" && Number.isFinite(Number(cpmRaw)) && Number(cpmRaw) > 0) {
      const cpm = Math.max(20, Math.min(900, Number(cpmRaw)));
      /** Один цикл −50%…0 ≈ проход одной копии текста; T = 60·N/CPM даёт близкий к заданному поток знаков/мин при длине N. */
      duration = Math.max(6, (60 * charCount) / cpm);
    } else {
      duration = Math.max(6, Number(settings.speedSec || 18));
    }
    const durationMs = duration * 1000;
    const contentKey = `${duration}|${text}`;
    let st = marqueeState.get(widget.id);
    if (!st || st.contentKey !== contentKey) {
      st = { startedAt: Date.now(), contentKey };
      marqueeState.set(widget.id, st);
    }
    const offsetSec = ((Date.now() - st.startedAt) % durationMs) / 1000;
    const weight = settings.bold ? "font-weight:700;" : "";
    return `
    <div class="marquee-box" style="background:${settings.background};color:${settings.color};">
      <div class="marquee-track" style="animation-duration:${duration}s;animation-delay:-${offsetSec}s;font-size:${settings.fontSize || 22}px;${weight}">
        <span>${text}</span>
        <span aria-hidden="true">${text}</span>
      </div>
    </div>
  `;
  }

  function schoolNewsImageLayoutSettings(source) {
    const s = source || {};
    let widthPct = Number(s.image_width_percent != null ? s.image_width_percent : s.imageWidthPercent);
    if (!Number.isFinite(widthPct)) widthPct = 32;
    widthPct = Math.max(15, Math.min(55, Math.round(widthPct)));
    let maxHeightPx = Number(s.image_max_height_px != null ? s.image_max_height_px : s.imageMaxHeightPx);
    if (!Number.isFinite(maxHeightPx)) maxHeightPx = 200;
    maxHeightPx = Math.max(80, Math.min(400, Math.round(maxHeightPx)));
    const wrapRaw = s.single_image_text_wrap != null ? s.single_image_text_wrap : s.singleImageTextWrap;
    const wrapSingle = wrapRaw !== false;
    return { widthPct, maxHeightPx, wrapSingle };
  }

  function buildSchoolNews(widget, schoolNews = [], screen = null, ctx = null) {
    const L = tvUiStrings();
    const settings = widget.settings || {};
    const bodyFs = schoolNewsBodyFontPx(settings);
    const emojiFont =
      'system-ui,"Segoe UI",Roboto,sans-serif,"Apple Color Emoji","Segoe UI Emoji","Segoe UI Symbol","Noto Color Emoji"';
    // Берём 3 последних активных — и ротируем их (а не весь список целиком).
    const rowsAll = Array.isArray(schoolNews) ? schoolNews.filter((x) => x && x.is_active !== false) : [];
    const rows = rowsAll.slice(0, 3);
    if (!rows.length) {
      return `<div class="info-widget-box" style="background:${settings.background};color:${settings.color};font-family:${emojiFont};"><div style="font-size:${settings.titleFontSize || 18}px;">${L.schoolNews}</div><div>${L.noSchoolNews}</div></div>`;
    }
    // Как «Объявления»: без таймера. Переключаем только при показе (карусель) в уникальном порядке.
    const st = ensureSchoolNewsOrder(widget.id, rows);
    const isCarouselShow = Boolean(ctx && ctx.mode === "carousel_show");
    const pickIdx = isCarouselShow ? nextSchoolNewsIndex(widget.id, rows) : (st && Number.isFinite(st.currentIdx) ? st.currentIdx : 0);
    const item = rows[pickIdx] || rows[0];
    const title = escapeHtml(String(item.title || ""));
    const rawBody = String(item.display_html != null && item.display_html !== "" ? item.display_html : item.content || "");
    const bodyHtml = sanitizeSchoolNewsDisplayHtml(rawBody);
    const summaryText = String(item.summary || "");
    const summaryFallback = escapeHtml(summaryText).replace(/\n/g, "<br>");
    const cover = String(item.cover_image || "").trim();
    const galleryList = Array.isArray(item.gallery_images)
      ? item.gallery_images.map((u) => String(u || "").trim()).filter(Boolean).slice(0, 4)
      : [];
    const mediaUrls = [];
    if (cover) mediaUrls.push(cover);
    for (let gi = 0; gi < galleryList.length; gi++) mediaUrls.push(galleryList[gi]);
    const imgLayout = schoolNewsImageLayoutSettings(item);
    const useWrap = imgLayout.wrapSingle && mediaUrls.length === 1;
    const sideImgStyle = `max-height:${imgLayout.maxHeightPx}px;`;
    let mediaBlock = "";
    if (mediaUrls.length) {
      if (useWrap) {
        const src = schoolNewsImageSrcWithV(mediaUrls[0], item);
        if (src) {
          mediaBlock = `<img class="gs-school-news-float-img" style="width:${imgLayout.widthPct}%;max-height:${imgLayout.maxHeightPx}px;" src="${escapeHtmlAttr(src)}" alt="">`;
        }
      } else {
        mediaBlock = `<div class="gs-school-news-media" style="width:${imgLayout.widthPct}%;max-width:none;">${mediaUrls
          .map((raw) => {
            const src = schoolNewsImageSrcWithV(raw, item);
            return src
              ? `<img class="gs-school-news-side-img" style="${sideImgStyle}" src="${escapeHtmlAttr(src)}" alt="">`
              : "";
          })
          .join("")}</div>`;
      }
    }
    const created = String(item.created_at || "").trim();
    const createdLabel = created ? formatDateLabel(created) : "";
    let rowClass = "gs-school-news-row";
    if (!mediaBlock) rowClass += " gs-school-news-row--nomedia";
    else if (useWrap) rowClass += " gs-school-news-row--wrap";
    const bodyWeight = settings.bold ? "font-weight:600;" : "";
    return `<article class="gs-school-news-card" style="background:${settings.background};color:${settings.color};font-family:${emojiFont};">
      <div class="gs-school-news-head">
        <div class="gs-school-news-title" style="font-size:${settings.titleFontSize || 20}px;${settings.bold ? "font-weight:700;" : ""}">${title || L.schoolNews}</div>
        <div class="gs-school-news-date">${createdLabel}</div>
      </div>
      <div class="${rowClass}">
        ${mediaBlock}
        <div class="gs-school-news-body" style="font-size:${bodyFs}px;${bodyWeight}">${bodyHtml || summaryFallback || escapeHtml(L.noSchoolNews)}</div>
      </div>
      <div class="gs-school-news-foot">${rows.length > 1 ? `${Math.min(rows.length, (st && st.pos ? st.pos : 1))}/${rows.length}` : ""}</div>
    </article>`;
  }

  function buildRssNews(widget, rssNews = []) {
    const L = tvUiStrings();
    const settings = widget.settings || {};
    const bodyFs = schoolNewsBodyFontPx(settings);
    const rows = Array.isArray(rssNews) ? rssNews : [];
    if (!rows.length) {
      return `<div class="info-widget-box" style="background:${settings.background};color:${settings.color};"><div style="font-size:${settings.titleFontSize || 18}px;">${L.rssNews}</div><div>${L.noRssNews}</div></div>`;
    }
    const sec = Math.max(10, Math.min(15, Number(settings.rotateSec || 12)));
    const idx = Math.floor(Date.now() / (sec * 1000)) % rows.length;
    const item = rows[idx] || {};
    const title = escapeHtml(String(item.title || ""));
    const summary = escapeHtml(String(item.summary || item.description || ""));
    const url = String(item.url || "").trim();
    return `<article style="background:${settings.background};color:${settings.color};padding:10px;border-radius:10px;height:100%;overflow:hidden;">
      <div style="font-size:${settings.titleFontSize || 18}px;${settings.bold ? "font-weight:700;" : ""};margin-bottom:8px;">${title || L.rssNews}</div>
      <div style="font-size:${bodyFs}px;line-height:1.3;">${summary || L.noRssNews}</div>
      ${url ? `<div style="margin-top:8px;font-size:12px;opacity:.9;"><a href="${escapeHtmlAttr(url)}" style="color:${settings.color}" target="_blank" rel="noopener">Источник</a></div>` : ""}
    </article>`;
  }

  function widgetIdsHiddenByCarousel(screen) {
    const sw = (screen && screen.widgets) || [];
    return new Set(sw
      .filter((widget) => widget.type === "carousel" && widget.enabled !== false)
      .flatMap((widget) => (widget.settings.childWidgetIds || []).filter((id) => id !== "__blank__")));
  }

  /** Порядок в DOM: изображения снизу, остальные, аварийный поверх всех. */
  function sortWidgetsForDom(screen) {
    const widgets = (screen && screen.widgets) || [];
    const hiddenIds = widgetIdsHiddenByCarousel(screen);
    const list = widgets
      .map((w, i) => ({ w, i }))
      .filter(({ w }) => w.enabled !== false && !(hiddenIds.has(w.id) && w.type !== "carousel"));
    list.sort((a, b) => {
      const rank = (t) => (t === "image" ? 0 : t === "emergency" ? 2 : 1);
      const d = rank(a.w.type) - rank(b.w.type);
      if (d !== 0) return d;
      return a.i - b.i;
    });
    return list.map((x) => x.w);
  }

  /**
   * Мобильная лента: порядок как в конфиге экрана (индекс в массиве widgets), без перестановки по типу/сетке.
   * x,y,w,h не учитываются — только столбец «сверху вниз».
   */
  function sortWidgetsForMobileStack(screen) {
    const widgets = (screen && screen.widgets) || [];
    const hiddenIds = widgetIdsHiddenByCarousel(screen);
    const out = [];
    for (let i = 0; i < widgets.length; i++) {
      const w = widgets[i];
      if (!w || w.menu_only === true || w.type === "emergency") continue;
      if (hiddenIds.has(w.id) && w.type !== "carousel") continue;
      out.push(w);
    }
    return out;
  }

  /** Дочерние виджеты карусели в порядке из `childWidgetIds`. */
  function orderedCarouselChildWidgets(screen, widget) {
    const ids = widget.settings.childWidgetIds || [];
    const byId = new Map((screen.widgets || []).map((w) => [w.id, w]));
    return ids
      .map((id) => {
        if (id === "__blank__") {
          const L = tvUiStrings();
          return { id: "__blank__", type: "blank", title: L.carouselBlank, enabled: true, settings: {} };
        }
        const child = byId.get(id);
        if (!child) return null;
        if (registryKnownTypes && !registryKnown(child.type)) return null;
        return child;
      })
      .filter(Boolean);
  }

  /** null = все типы из JS-рендера допустимы (до первого poll). */
  let registryKnownTypes = null;

  function setWidgetTypesAvailable(types) {
    if (Array.isArray(types)) {
      registryKnownTypes = new Set(types.map((t) => String(t)));
    } else {
      registryKnownTypes = null;
    }
  }

  function registryKnown(widgetType) {
    const t = String(widgetType || "");
    if (!registryKnownTypes) return true;
    return registryKnownTypes.has(t);
  }

  function tvSubst(template, vars) {
    let s = String(template || "");
    const v = vars || {};
    for (const key of Object.keys(v)) {
      s = s.split(`{{${key}}}`).join(String(v[key]));
    }
    return s;
  }

  function renderWidgetMissingPlaceholder(widget) {
    const typ = escapeHtml(String((widget && widget.type) || "?"));
    const L = tvUiStrings();
    const msg = tvSubst(L.widgetMissing || "Виджет {{type}} отсутствует.", { type: typ });
    return `<div class="widget-missing widget-meta">${msg}</div>`;
  }

  function renderWidgetErrorPlaceholder(widget, err) {
    const typ = escapeHtml(String((widget && widget.type) || "?"));
    const detail = err && err.message ? escapeHtml(String(err.message)) : "";
    const L = tvUiStrings();
    const msg = tvSubst(L.widgetError || "Ошибка виджета {{type}}.", { type: typ });
    return `<div class="widget-error widget-meta">${msg}${detail ? `<div class="widget-error-detail">${detail}</div>` : ""}</div>`;
  }

  function widgetEffectiveType(widget) {
    const rk = widget && widget.render_key != null ? String(widget.render_key).trim() : "";
    if (rk) return rk;
    return String((widget && widget.type) || "");
  }

  function renderWidgetHtmlImpl(widget, schedule, screen, holidays = [], announcements = [], marquee = [], schoolNews = [], rssNews = [], ctx = null) {
    const L = tvUiStrings();
    const weight = widget.settings.bold ? "font-weight:700;" : "";
    const wtype = widgetEffectiveType(widget);
    const W = global.GuardSchoolWidgets;
    if (W && typeof W.render === "function") {
      const pluginHtml = W.render(wtype, {
        widget,
        schedule,
        screen,
        holidays,
        announcements,
        marquee,
        schoolNews,
        rssNews,
        ctx,
        weight,
        L,
        wtype,
      });
      if (pluginHtml !== undefined) return pluginHtml;
    }
    return "";
  }

  function startCarousel(block, widget, childWidgets, schedule, screen, holidays, announcements, marquee, schoolNews, rssNews) {
    const c = carouselApi();
    if (!c || !c.start) {
      if (!childWidgets.length) {
        block.innerHTML = `<div class="widget-meta">${tvUiStrings().carouselNoSlides}</div>`;
      }
      return;
    }
    c.start(block, widget, childWidgets, schedule, screen, holidays, announcements, marquee, schoolNews, rssNews, {
      renderWidgetHtml,
      widgetEffectiveType,
      tvUiStrings,
      getDisplayFromPayload,
    });
  }

  function renderWidgetHtml(widget, schedule, screen, holidays, announcements, marquee, schoolNews, rssNews, ctx) {
    try {
      if (!registryKnown(widget && widget.type)) {
        return renderWidgetMissingPlaceholder(widget);
      }
      const html = renderWidgetHtmlImpl(
        widget,
        schedule,
        screen,
        holidays,
        announcements,
        marquee,
        schoolNews,
        rssNews,
        ctx
      );
      if (!html || !String(html).trim()) {
        return renderWidgetMissingPlaceholder(widget);
      }
      return html;
    } catch (e) {
      try {
        console.error("[widget]", widget && widget.type, widget && widget.id, e);
      } catch (_) {}
      return renderWidgetErrorPlaceholder(widget, e);
    }
  }

  if (global.GuardSchoolWidgets) {
    global.GuardSchoolWidgets.helpers = {
      formatWidgetDateLine,
      formatClockTimeString,
      formatEmergencyCountdown: shell.formatEmergencyCountdown,
      escapeHtml,
      escapeHtmlAttr,
      tvUiStrings,
      getDisplayFromPayload,
      adjustedDateFromDisplay,
      localeTagFromUi,
      capitalizeFirst,
      buildBellStatus,
      buildBellCountdown,
      buildUpcomingHolidays,
      formatDateLabel,
      buildScheduleTable,
      buildAnnouncements,
      buildMarquee,
      schoolNewsImageLayoutSettings,
      buildSchoolNews,
      buildRssNews,
      renderCheckinSubmitWidget,
      renderCheckinMonitorWidget,
    };
  }

  global.GuardSchoolScreen = {
    clearAllTimers,
    pruneStaleCarouselState,
    pruneStaleWidgetState,
    setWidgetTypesAvailable,
    renderWidgetHtml,
    updateAllEmergencyCountdowns: shell.updateAllEmergencyCountdowns,
    widgetIdsHiddenByCarousel,
    sortWidgetsForDom,
    sortWidgetsForMobileStack,
    orderedCarouselChildWidgets,
    applyWidgetBackdropClass: shell.applyWidgetBackdropClass,
    startCarousel,
    updateAllClocks: shell.updateAllClocks,
    resolveBackgroundImageUrl: shell.resolveBackgroundImageUrl,
    applyTvScreenBackground: shell.applyTvScreenBackground,
    buildTextOutlineShadow: shell.buildTextOutlineShadow,
    applyTvTextOutline: shell.applyTvTextOutline,
    bindCheckinWidgets: shell.bindCheckinWidgets,
  };
})(typeof window !== "undefined" ? window : globalThis);
