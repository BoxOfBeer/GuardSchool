(function (global) {
  const carouselState = new Map();
  const marqueeState = new Map();
  // announcementsState: widgetId -> { contentKey, order, pos, lastIdx }
  const announcementsState = new Map();
  const RANDOM_CAROUSEL_ANIMATIONS = [
    "slide",
    "slideUp",
    "slideDown",
    "slideFromLeft",
    "fade",
    "zoom",
    "blurSoft",
    "flipLight",
    "rotateIn",
  ];

  /** Совпадает с :root --schedule-fg / --schedule-surface / --muted в styles-tv.css и styles.css (инлайн без var() для ТВ). */
  const SCHEDULE_THEME = Object.freeze({
    fg: "#0f172a",
    surface: "rgba(255, 255, 255, 0.92)",
    sectionTitle: "#cbd5e1",
  });

  function clearCarouselTimeouts() {
    for (const st of carouselState.values()) {
      if (st.timerId) clearTimeout(st.timerId);
      if (st.animTimeout) clearTimeout(st.animTimeout);
      st.timerId = null;
      st.animTimeout = null;
    }
  }

  /** Удалить состояние каруселей, которых уже нет в конфиге экрана. */
  function pruneStaleCarouselState(screen) {
    const widgets = (screen && screen.widgets) || [];
    const allowed = new Set(widgets.filter((w) => w.type === "carousel").map((w) => w.id));
    for (const id of [...carouselState.keys()]) {
      if (!allowed.has(id)) carouselState.delete(id);
    }
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
  }

  function getDisplayFromPayload() {
    try {
      const p = global.__lastScreenPayload;
      return (p && p.display) || {};
    } catch (_) {
      return {};
    }
  }

  function localeTagFromUi(uiLocale) {
    return String(uiLocale || "ru").toLowerCase() === "en" ? "en-GB" : "ru-RU";
  }

  /** Подписи виджетов и служебные строки на ТВ — по display.ui_locale (без отдельного JSON). */
  const TV_UI = {
    ru: {
      noData: "Нет данных",
      lessonColumn: "Урок",
      bells: "Звонки",
      countdown: "До звонка",
      events: "События",
      announcements: "Объявления",
      schoolNews: "Новости школы",
      rssNews: "RSS-лента",
      noAnnouncements: "Нет объявлений",
      noSchoolNews: "Нет новостей",
      qr: "QR на новость",
      noRssNews: "Нет новостей",
      scheduleDefault: "Расписание",
      nextSchoolDay: "Следующий учебный день:",
      carouselBlank: "Пауза (фон)",
      imageEmpty: "Нет изображения (добавьте файл или URL)",
      imageAlt: "изображение",
      carouselNoSlides: "Слайды не выбраны",
      emergencyTimeLeft: "Осталось времени:",
    },
    en: {
      noData: "No data",
      lessonColumn: "Lesson",
      bells: "Bells",
      countdown: "Countdown",
      events: "Events",
      announcements: "Announcements",
      schoolNews: "School news",
      rssNews: "RSS feed",
      noAnnouncements: "No announcements",
      noSchoolNews: "No news",
      qr: "QR to article",
      noRssNews: "No news",
      scheduleDefault: "Schedule",
      nextSchoolDay: "Next school day:",
      carouselBlank: "Pause (background)",
      imageEmpty: "No image (add a file or URL)",
      imageAlt: "image",
      carouselNoSlides: "No slides selected",
      emergencyTimeLeft: "Time left:",
    },
  };

  function tvUiStrings() {
    const ui = String(getDisplayFromPayload().ui_locale || "ru").toLowerCase();
    return TV_UI[ui === "en" ? "en" : "ru"];
  }

  function adjustedDateFromDisplay() {
    const d = getDisplayFromPayload();
    const off = Number(d.clock_offset_minutes || 0);
    const ms = Number.isFinite(off) ? off * 60 * 1000 : 0;
    return new Date(Date.now() + ms);
  }

  function formatDateLabel(isoDate) {
    const value = new Date(`${isoDate}T00:00:00`);
    const disp = getDisplayFromPayload();
    const loc = localeTagFromUi(disp.ui_locale);
    return value.toLocaleDateString(loc, { day: "2-digit", month: "2-digit", year: "numeric" });
  }

  function formatWidgetDateLine() {
    const disp = getDisplayFromPayload();
    const loc = localeTagFromUi(disp.ui_locale);
    const tz = String(disp.timezone || "Europe/Moscow").trim() || "Europe/Moscow";
    const inst = adjustedDateFromDisplay();
    let line;
    try {
      line = inst.toLocaleDateString(loc, {
        timeZone: tz,
        weekday: "long",
        day: "2-digit",
        month: "long",
        year: "numeric",
      });
    } catch (_) {
      line = inst.toLocaleDateString(loc, { weekday: "long", day: "2-digit", month: "long", year: "numeric" });
    }
    const ui = String(disp.ui_locale || "ru").toLowerCase();
    return ui === "en" ? line : capitalizeFirst(line);
  }

  function formatClockTimeString() {
    const disp = getDisplayFromPayload();
    const loc = localeTagFromUi(disp.ui_locale);
    const tz = String(disp.timezone || "Europe/Moscow").trim() || "Europe/Moscow";
    const inst = adjustedDateFromDisplay();
    try {
      return inst.toLocaleTimeString(loc, { timeZone: tz, hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch (_) {
      return inst.toLocaleTimeString(loc, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    }
  }

  function capitalizeFirst(value) {
    if (!value) return value;
    return value.charAt(0).toUpperCase() + value.slice(1);
  }

  function escapeHtml(s) {
    return String(s != null ? s : "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function escapeHtmlAttr(s) {
    return String(s != null ? s : "")
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;");
  }

  /** Как на сервере: первая буква предмета — заглавная (в т.ч. после BOM/пробелов); дублируем здесь, чтобы ТВ не зависел от перезапуска сервера и кэша. */
  function capitalizeSubjectDisplay(raw) {
    const s = String(raw != null ? raw : "").trim();
    if (!s) return "";
    const chars = [...s];
    for (let i = 0; i < chars.length; i++) {
      const ch = chars[i];
      if (ch.toLowerCase() !== ch.toUpperCase()) {
        chars[i] = ch.toUpperCase();
        break;
      }
    }
    return chars.join("");
  }

  function buildScheduleTable(rows, title, settings) {
    const L = tvUiStrings();
    settings = settings || {};
    if (!rows.length) {
      return `<section class="schedule-section"><h3 class="screen-section-title">${escapeHtml(title)}</h3><div class="schedule-section-msg">${escapeHtml(L.noData)}</div></section>`;
    }

    // Макс. номер урока по всем строкам (даже с пустым subject) — иначе на ТВ «съедались» колонки и таблица казалась пустой.
    let maxByIndex = 0;
    for (let ri = 0; ri < rows.length; ri++) {
      const row = rows[ri];
      const lessons = row.lessons || [];
      for (let li = 0; li < lessons.length; li++) {
        const n = Number(lessons[li].index);
        if (Number.isFinite(n) && n > maxByIndex) maxByIndex = n;
      }
    }
    const maxLessons = Math.max(maxByIndex, 1);

    const colgroup = `<colgroup><col class="schedule-col-num" />${rows.map(() => "<col />").join("")}</colgroup>`;

    // На части ТВ CSS-переменные/табличные стили применяются нестабильно.
    // Поэтому делаем минимальные инлайны (background-color/color) для ячеек.

    // На некоторых ТВ hex-цвета с буквами (a-f) обрабатываются нестабильно. Используем rgb(r,g,b).
    const hexToRgbCss = (v, fallbackCss) => {
      const s = String(v || "").trim();
      const m = /^#([0-9a-fA-F]{6})$/.exec(s);
      if (!m) return fallbackCss;
      const n = parseInt(m[1], 16);
      const r = (n >> 16) & 255;
      const g = (n >> 8) & 255;
      const b = n & 255;
      return `rgb(${r},${g},${b})`;
    };
    const bgBase = hexToRgbCss(settings.tableBgColor, "rgb(248,244,232)");
    const textBase = hexToRgbCss(settings.tableTextColor, "rgb(15,23,42)");
    const bgPast = hexToRgbCss(settings.pastBgColor, "rgb(31,41,55)");
    const textPast = hexToRgbCss(settings.pastTextColor, "rgb(241,245,249)");
    const bgCurrent = hexToRgbCss(settings.currentBgColor, "rgb(191,219,254)");
    const bgOverride = hexToRgbCss(settings.highlightColor, "rgb(187,247,208)");
    const bgSample = hexToRgbCss(settings.sampleDiffColor, "rgb(254,243,199)");

    /** Колонка урока — если в данных есть ячейка (даже без текста предмета), показываем столбец (слабые ТВ / «пустые» ячейки в JSON). */
    function rowHasLessonSlot(row, lessonIndex) {
      const leg = (row.lessons || []).find(function (item) {
        return Number(item.index) === lessonIndex;
      });
      if (!leg) return false;
      const subj = String(leg.subject || "").trim();
      if (subj) return true;
      return Boolean(leg.is_current || leg.is_past || leg.is_override || leg.is_sample_diff);
    }

    const indices = [];
    for (let lessonIndex = 1; lessonIndex <= maxLessons; lessonIndex++) {
      let col = false;
      for (let ri = 0; ri < rows.length; ri++) {
        if (rowHasLessonSlot(rows[ri], lessonIndex)) {
          col = true;
          break;
        }
      }
      if (col) indices.push(lessonIndex);
    }

    // Важно для слабых ТВ: избегаем больших style-атрибутов и CSS-переменных.
    // Раскраска делается на уровне каждой ячейки <td> (inline rgb()).
    const wrapStyle = "";
    let devLogHtml = "";
    try {
      if (settings && settings.devMode) {
        let firstOv = "";
        let ovCount = 0;
        let badOverrideColors = 0;
        for (const r of rows) {
          for (const les of r.lessons || []) {
            if (les && les.is_override) {
              ovCount += 1;
              if (!firstOv) firstOv = String(les.override_color || "");
              const raw = String(les.override_color || "").trim();
              if (raw && !/^#[0-9a-fA-F]{6}$/.test(raw)) badOverrideColors += 1;
            }
          }
        }
        const lines = [
          `DEV schedule ${new Date().toLocaleTimeString()}`,
          `hdr=${String(settings.headerColor || "")} bg=${String(settings.tableBgColor || "")} text=${String(settings.tableTextColor || "")}`,
          `pastBg=${String(settings.pastBgColor || "")} pastText=${String(settings.pastTextColor || "")} currentBg=${String(settings.currentBgColor || "")}`,
          `overrideDefault=${String(settings.highlightColor || "")} sample=${String(settings.sampleDiffColor || "")} border=${String(settings.borderColor || "")}`,
          `ovCount=${ovCount} firstOvColor=${firstOv} badOvColor=${badOverrideColors}`,
          `renderMode=inline_rgb_per_cell`,
        ];
        devLogHtml = `<pre class="gs-dev-log">${escapeHtml(lines.join("\n"))}</pre>`;
      }
    } catch (_) {}

    const bodyFiltered = (indices.length ? indices : [1]).map((lessonIndex) => {
      const cells = rows.map((row) => {
        const lesson = (row.lessons || []).find((item) => Number(item.index) === lessonIndex);
        if (!lesson) return `<td></td>`;
        const classes = [
          lesson.is_override ? "schedule-override" : "",
          lesson.is_sample_diff && !lesson.is_override ? "schedule-sample-diff" : "",
          lesson.is_past ? "schedule-past" : "",
          lesson.is_current ? "schedule-current" : "",
        ].filter(Boolean).join(" ");
        let bg = bgBase;
        let fg = textBase;
        let extra = "";
        if (lesson.is_past) {
          bg = bgPast;
          fg = textPast;
          extra = "text-decoration:line-through;";
        } else if (lesson.is_current) {
          bg = bgCurrent;
          fg = textBase;
          extra = "font-weight:700;";
        }
        if (lesson.is_sample_diff && !lesson.is_override) {
          bg = bgSample;
          fg = textBase;
        }
        if (lesson.is_override) {
          const oclr = lesson && lesson.override_color ? String(lesson.override_color).trim() : "";
          bg = hexToRgbCss(oclr, bgOverride);
          fg = textBase;
          extra = "font-weight:700;";
        }
        const styleAttr = ` style="background-color:${escapeHtmlAttr(bg)};color:${escapeHtmlAttr(fg)};${extra}"`;
        return `<td class="${classes}"${styleAttr}>${escapeHtml(capitalizeSubjectDisplay(lesson.subject))}</td>`;
      }).join("");
      return `<tr><td class="schedule-lesson-num">${lessonIndex}</td>${cells}</tr>`;
    }).join("");

    return `
    <section class="schedule-section">
      <h3 class="screen-section-title">${escapeHtml(title)}</h3>
      ${devLogHtml}
      <div class="schedule-table-wrap"${wrapStyle}>
        <table class="schedule-table">
          ${colgroup}
          <thead><tr><th>${escapeHtml(L.lessonColumn)}</th>${rows.map((item) => `<th>${escapeHtml(item.class_name)}</th>`).join("")}</tr></thead>
          <tbody>${bodyFiltered}</tbody>
        </table>
      </div>
    </section>
  `;
  }

  function buildBellStatus(status, settings) {
    const L = tvUiStrings();
    return `
    <div class="bell-status-box" style="background:${settings.background};color:${settings.color};">
      <div style="font-size:${settings.titleFontSize || 18}px;${settings.bold ? "font-weight:700;" : ""}">${L.bells}</div>
      <div style="font-size:${settings.fontSize || 18}px;${settings.bold ? "font-weight:700;" : ""}">${status.message}</div>
      <div style="${settings.bold ? "font-weight:700;" : ""}">${status.template_name || ""}</div>
    </div>
  `;
  }

  function buildBellCountdown(status, settings) {
    const L = tvUiStrings();
    return `
    <div class="bell-status-box" style="background:${settings.background};color:${settings.color};">
      <div style="font-size:${settings.titleFontSize || 18}px;${settings.bold ? "font-weight:700;" : ""}">${L.countdown}</div>
      <div style="font-size:${settings.fontSize || 22}px;${settings.bold ? "font-weight:700;" : ""}">${status.countdown_text || L.noData}</div>
    </div>
  `;
  }

  function holidayTargetDate(item, today) {
    const kind = item && item.kind ? String(item.kind) : "once";
    if (kind === "annual" && item && item.md) {
      const md = String(item.md);
      const parts = md.split("-");
      if (parts.length === 2) {
        const m = Number(parts[0]);
        const d = Number(parts[1]);
        if (Number.isFinite(m) && Number.isFinite(d)) {
          const y = today.getFullYear();
          const t0 = new Date(y, m - 1, d);
          const startToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
          if (t0 >= startToday) return t0;
          return new Date(y + 1, m - 1, d);
        }
      }
    }
    if (item && item.date) return new Date(`${item.date}T00:00:00`);
    return new Date("9999-12-31T00:00:00");
  }

  function buildUpcomingHolidays(settings, holidaysData = []) {
    const today = new Date();
    const startToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const items = holidaysData
      .map((item) => ({ ...item, target: holidayTargetDate(item, today) }))
      .filter((item) => item.target >= startToday)
      .sort((a, b) => a.target - b.target)
      .slice(0, Math.max(1, Number(settings.count || 5)));
    const loc = localeTagFromUi(getDisplayFromPayload().ui_locale);
    const L = tvUiStrings();
    const rows = items.length
      ? items.map((item) => `<div>${item.target.toLocaleDateString(loc, { day: "2-digit", month: "2-digit" })} - ${item.name}${item.description ? `: ${item.description}` : ""}</div>`).join("")
      : `<div>${L.noData}</div>`;
    return `
    <div class="info-widget-box" style="background:${settings.background};color:${settings.color};">
      <div style="font-size:${settings.titleFontSize || 18}px;${settings.bold ? "font-weight:700;" : ""}">${L.events}</div>
      <div style="font-size:${settings.fontSize || 16}px;${settings.bold ? "font-weight:700;" : ""}">${rows}</div>
    </div>
  `;
  }

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

  function buildSchoolNews(widget, schoolNews = [], screen = null) {
    const L = tvUiStrings();
    const settings = widget.settings || {};
    // Берём 3 последних активных — и ротируем их (а не весь список целиком).
    const rowsAll = Array.isArray(schoolNews) ? schoolNews.filter((x) => x && x.is_active !== false) : [];
    const rows = rowsAll.slice(0, 3);
    if (!rows.length) {
      return `<div class="info-widget-box" style="background:${settings.background};color:${settings.color};"><div style="font-size:${settings.titleFontSize || 18}px;">${L.schoolNews}</div><div>${L.noSchoolNews}</div></div>`;
    }
    const sec = Math.max(10, Math.min(15, Number(settings.rotateSec || 12)));
    const idx = Math.floor(Date.now() / (sec * 1000)) % rows.length;
    const item = rows[idx];
    const title = escapeHtml(String(item.title || ""));
    const summary = escapeHtml(String(item.summary || ""));
    const cover = String(item.cover_image || "").trim();
    const created = String(item.created_at || "").trim();
    const createdLabel = created ? formatDateLabel(created) : "";
    // Для школьных новостей: без QR, без обрезки картинки, без ограничения длины текста.
    // Картинка слева (~20% ширины), текст «обтекает».
    return `<article style="background:${settings.background};color:${settings.color};padding:10px;border-radius:10px;flex:1;min-height:0;overflow:auto;">
      <div style="display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin-bottom:8px;">
        <div style="font-size:${settings.titleFontSize || 20}px;${settings.bold ? "font-weight:700;" : ""};flex:1 1 auto;min-width:0;white-space:normal;overflow:visible;overflow-wrap:anywhere;word-break:break-word;">${title || L.schoolNews}</div>
        <div style="font-size:12px;opacity:.85;white-space:nowrap;flex:0 0 auto;">${createdLabel}</div>
      </div>
      ${cover ? `<img src="${escapeHtmlAttr(cover)}" alt="${title}" style="float:left;width:20%;max-width:180px;margin:0 10px 6px 0;border-radius:8px;object-fit:contain;height:auto;max-height:none;">` : ""}
      <div style="font-size:${settings.fontSize || 18}px;line-height:1.35;white-space:normal;overflow:visible;overflow-wrap:anywhere;word-break:break-word;">${summary || L.noSchoolNews}</div>
      <div style="clear:both;"></div>
      <div style="margin-top:6px;font-size:12px;opacity:.85;">${idx + 1}/${rows.length}</div>
    </article>`;
  }

  function buildRssNews(widget, rssNews = []) {
    const L = tvUiStrings();
    const settings = widget.settings || {};
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
      <div style="font-size:${settings.fontSize || 16}px;line-height:1.3;">${summary || L.noRssNews}</div>
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
        return byId.get(id);
      })
      .filter(Boolean);
  }

  function carouselSlideDurationMs(widget, childWidget) {
    const map = widget.settings && widget.settings.childSlideSec;
    const cid = childWidget ? String(childWidget.id) : "";
    if (map && cid && map[cid] != null) {
      const sec = Number(map[cid]);
      if (Number.isFinite(sec) && sec > 0) return Math.max(3000, sec * 1000);
    }
    const legacy = Number(widget.settings && widget.settings.intervalSec);
    if (Number.isFinite(legacy) && legacy > 0) return Math.max(3000, legacy * 1000);
    return Math.max(3000, 180 * 1000);
  }

  function renderWidgetHtml(widget, schedule, screen, holidays = [], announcements = [], marquee = [], schoolNews = [], rssNews = [], ctx = null) {
    const L = tvUiStrings();
    const weight = widget.settings.bold ? "font-weight:700;" : "";
    if (widget.type === "emergency") {
      const s = widget.settings || {};
      const bg = String(s.background || "#b91c1c").trim();
      const raw = String(s.text || "");
      const htmlBody = raw
        .split("\n")
        .map((line) => escapeHtml(line))
        .join("<br>") || "&nbsp;";
      const fs = Math.max(10, Math.min(200, Number(s.fontSize) || 42));
      const color = String(s.color || "#ffffff").trim();
      const imgUrl = String(s.imageUrl || "").trim();
      const cap = String(s.imageCaption || "").trim();
      const capHtml = cap
        ? `<div class="emergency-overlay-caption" style="font-size:${Math.max(10, Math.round(fs * 0.35))}px;opacity:0.95;margin-top:12px;">${escapeHtml(cap)}</div>`
        : "";
      const imgBlock =
        imgUrl && /^\/uploads\//.test(imgUrl)
          ? `<div class="emergency-overlay-image-wrap"><img class="emergency-overlay-image" src="${escapeHtmlAttr(imgUrl)}" alt="" /></div>`
          : "";
      const timerRaw = Number(s.timerRemainingSec != null ? s.timerRemainingSec : (s.timer_seconds != null ? s.timer_seconds : s.timerSeconds));
      const timerSec = Number.isFinite(timerRaw) ? Math.max(0, Math.round(timerRaw)) : 0;
      const timerLabel = timerSec > 0 || s.timerShowZero === true
        ? `<div class="emergency-overlay-timer-wrap"><div class="emergency-overlay-timer-title">${escapeHtml(L.emergencyTimeLeft || "Осталось времени:")}</div><div class="emergency-overlay-timer" data-emergency-countdown="1" data-seconds-left="${timerSec}">${escapeHtml(formatEmergencyCountdown(timerSec))}</div></div>`
        : "";
      return `<div class="emergency-overlay-inner" style="background:${bg};color:${color};font-size:${fs}px;${weight}"><div class="emergency-overlay-stack"><div class="emergency-overlay-text">${htmlBody}</div>${timerLabel}${imgBlock}${capHtml}</div></div>`;
    }
    if (widget.type === "image") {
      const s = widget.settings || {};
      const rawList = Array.isArray(s.images) ? s.images : [];
      const legacy = String(s.imageUrl || "").trim();
      const slides = (rawList.length
        ? rawList
        : legacy
          ? [{ name: "", url: legacy }]
          : []
      )
        .map((it) => ({
          name: String(it && it.name != null ? it.name : "").trim(),
          url: String(it && it.url != null ? it.url : "").trim(),
        }))
        .filter((it) => it.url);
      const opacityPct = Math.max(0, Math.min(100, Number(s.opacity != null ? s.opacity : 85)));
      const op = opacityPct / 100;
      const fit = s.objectFit === "cover" ? "cover" : "contain";
      if (!slides.length) {
        return `<div class="image-widget-empty widget-meta">${L.imageEmpty}</div>`;
      }
      const rotateSec = Math.max(0, Number(s.imagesRotateSec) || 0);
      let idx = 0;
      if (slides.length > 1 && rotateSec >= 1) {
        const slot = Math.floor(Date.now() / 1000 / rotateSec);
        idx = slot % slides.length;
      }
      const pick = slides[idx];
      const url = pick.url;
      const label = escapeHtmlAttr(pick.name || L.imageAlt);
      return `<div class="image-widget-root" style="opacity:${op};width:100%;height:100%;display:flex;align-items:center;justify-content:center;overflow:hidden;">
    <img class="image-widget-img" src="${escapeHtmlAttr(url)}" alt="${label}" style="object-fit:${fit};max-width:100%;max-height:100%;width:100%;height:100%;pointer-events:none;" />
  </div>`;
    }
    if (widget.type === "date") {
      return `<div class="widget-center-text" style="font-size:${widget.settings.fontSize}px;color:${widget.settings.color};${weight}">${formatWidgetDateLine()}</div>`;
    }
    if (widget.type === "time") {
      return `<div class="gs-screen-clock widget-center-text" style="font-size:${widget.settings.fontSize}px;color:${widget.settings.color};${weight}"></div>`;
    }
    if (widget.type === "text") {
      return `<div class="widget-center-text" style="font-size:${widget.settings.fontSize}px;color:${widget.settings.color};${weight}">${widget.settings.text}</div>`;
    }
    if (widget.type === "blank") {
      return `<div class="widget-center-text"></div>`;
    }
    if (widget.type === "bell_status") {
      return buildBellStatus(schedule.bell_status, widget.settings);
    }
    if (widget.type === "bell_countdown") {
      return buildBellCountdown(schedule.bell_status, widget.settings);
    }
    if (widget.type === "schedule") {
      const ws = widget.settings || {};
      const title = schedule.bell_status?.schedule_title || L.scheduleDefault;
      const nextDayTitle = `${L.nextSchoolDay} ${formatDateLabel(schedule.next_school_day)}`;
      // «done» = день по звонкам закончен — тогда таблицу «сегодня» не показываем (остаётся «завтра»).
      // Если слотов звонков нет, сервер раньше оставлял state «done» по умолчанию — таблица пропадала зря; учитываем entries.
      const bellEntries = schedule.bell_status && Array.isArray(schedule.bell_status.entries)
        ? schedule.bell_status.entries
        : [];
      const hideTodayAsSchoolDayOver =
        schedule.bell_status?.state === "done" && bellEntries.length > 0;
      const todayBlock = hideTodayAsSchoolDayOver
        ? ""
        : buildScheduleTable(schedule.today_rows, title, ws);
      const showTomorrowBlock = ws.showTomorrow !== false
        && schedule.tomorrow_schedule_visible !== false;
      const tomorrowBlock = showTomorrowBlock
        ? buildScheduleTable(schedule.tomorrow_rows, nextDayTitle, ws)
        : "";
      return `<div class="schedule-widget-content">${todayBlock}${tomorrowBlock}</div>`;
    }
    if (widget.type === "holidays") {
      return buildUpcomingHolidays(widget.settings, holidays);
    }
    if (widget.type === "announcements") {
      return buildAnnouncements(widget.settings, announcements, widget.id, ctx);
    }
    if (widget.type === "marquee") {
      return buildMarquee(widget, marquee);
    }
    if (widget.type === "school_news") {
      return buildSchoolNews(widget, schoolNews, screen);
    }
    if (widget.type === "rss_news") {
      return buildRssNews(widget, rssNews);
    }
    return "";
  }

  function startCarousel(block, widget, childWidgets, schedule, screen, holidays, announcements, marquee, schoolNews, rssNews) {
    if (!childWidgets.length) {
      block.innerHTML = `<div class="widget-meta">${tvUiStrings().carouselNoSlides}</div>`;
      return;
    }
    const startDelayMs = Math.max(0, Number(widget.settings.startDelaySec || 0) * 1000);
    const now = Date.now();
    const firstDur = carouselSlideDurationMs(widget, childWidgets[0]);
    const st = carouselState.get(widget.id) || {
      initializedAt: now,
      index: 0,
      nextSwitchAt: now + startDelayMs + firstDur,
      timerId: null,
      animTimeout: null,
    };
    st.index = st.index % childWidgets.length;
    if (!st.initializedAt) st.initializedAt = now;
    if (st.timerId) window.clearTimeout(st.timerId);
    if (st.animTimeout) window.clearTimeout(st.animTimeout);
    st.animTimeout = null;
    while (now >= st.nextSwitchAt && childWidgets.length) {
      const slideEnd = st.nextSwitchAt;
      st.index = (st.index + 1) % childWidgets.length;
      st.nextSwitchAt = slideEnd + carouselSlideDurationMs(widget, childWidgets[st.index]);
    }
    const slides = childWidgets.map((childWidget, index) => {
      const slide = document.createElement("div");
      slide.className = `carousel-slide ${index === st.index ? "active" : ""}`;
      if (childWidget.type === "text") slide.style.background = childWidget.settings.background;
      slide.innerHTML = renderWidgetHtml(
        childWidget,
        schedule,
        screen,
        holidays,
        announcements,
        marquee,
        schoolNews,
        rssNews,
        { mode: index === st.index ? "carousel_show" : "carousel_init" }
      );
      block.appendChild(slide);
      return slide;
    });
    const latestData = () => {
      try {
        const p = global && global.__lastScreenPayload;
        if (p && p.screen) {
          return {
            screen: p.screen,
            schedule: p.schedule,
            holidays: p.holidays || [],
            announcements: p.announcements || [],
            marquee: p.marquee || [],
            schoolNews: p.school_news || [],
            rssNews: p.rss_news || [],
            rss_news: p.rss_news || [],
            display: p.display || {},
          };
        }
      } catch (_) {}
      return { screen, schedule, holidays, announcements, marquee, schoolNews, rssNews, display: getDisplayFromPayload() };
    };
    const advance = () => {
      const current = slides[st.index];
      st.index = (st.index + 1) % slides.length;
      const nextWidget = childWidgets[st.index];
      const waitMs = carouselSlideDurationMs(widget, nextWidget);
      st.nextSwitchAt = Date.now() + waitMs;
      const next = slides[st.index];
      // Обновляем HTML именно при показе: так «Объявления» могут менять блок на каждый показ в карусели.
      try {
        const d = latestData();
        next.innerHTML = renderWidgetHtml(
          nextWidget,
          d.schedule,
          d.screen,
          d.holidays,
          d.announcements,
          d.marquee,
          d.schoolNews,
          d.rssNews,
          { mode: "carousel_show" }
        );
      } catch (_) {}
      const animation = widget.settings.animation === "random"
        ? RANDOM_CAROUSEL_ANIMATIONS[Math.floor(Math.random() * RANDOM_CAROUSEL_ANIMATIONS.length)]
        : (widget.settings.animation || "slide");
      current.classList.remove("active");
      current.classList.add(`exit-${animation}`);
      next.classList.add(`enter-${animation}`);
      next.offsetWidth;
      next.classList.add("active");
      next.classList.remove(`enter-${animation}`);
      if (st.animTimeout) window.clearTimeout(st.animTimeout);
      st.animTimeout = window.setTimeout(() => {
        try {
          current.classList.remove(`exit-${animation}`);
        } catch (_) {}
        st.animTimeout = null;
      }, 700);
      st.timerId = window.setTimeout(advance, waitMs);
    };
    st.timerId = window.setTimeout(advance, Math.max(0, st.nextSwitchAt - now));
    carouselState.set(widget.id, st);
  }

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

  function applyTvScreenBackground(el, screen, gallery) {
    if (!el) return;
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

  global.GuardSchoolScreen = {
    clearAllTimers,
    pruneStaleCarouselState,
    pruneStaleWidgetState,
    renderWidgetHtml,
    updateAllEmergencyCountdowns,
    widgetIdsHiddenByCarousel,
    sortWidgetsForDom,
    sortWidgetsForMobileStack,
    orderedCarouselChildWidgets,
    applyWidgetBackdropClass,
    startCarousel,
    updateAllClocks,
    resolveBackgroundImageUrl,
    applyTvScreenBackground,
    buildTextOutlineShadow,
    applyTvTextOutline,
  };
})(window);
