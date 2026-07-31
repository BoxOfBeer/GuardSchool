(function (global) {
  "use strict";
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

  /** Подписи на ТВ: static/tv-locales.js (GuardSchoolTvLocales), иначе встроенный fallback. */
  const TV_UI_FALLBACK = {
    ru: {
      noData: "Нет данных",
      lessonColumn: "Слот",
      bells: "Сигналы",
      countdown: "До сигнала",
      events: "События",
      announcements: "Объявления",
      schoolNews: "Новости",
      rssNews: "RSS-лента",
      noAnnouncements: "Нет объявлений",
      noSchoolNews: "Нет новостей",
      qr: "QR на материал",
      noRssNews: "Нет новостей",
      scheduleDefault: "Расписание",
      nextSchoolDay: "Следующий рабочий день:",
      carouselBlank: "Пауза (фон)",
      imageEmpty: "Нет изображения (добавьте файл или URL)",
      imageAlt: "изображение",
      carouselNoSlides: "Слайды не выбраны",
      emergencyTimeLeft: "Осталось времени:",
      widgetMissing: "Виджет {{type}} отсутствует.",
      widgetError: "Ошибка виджета {{type}}.",
    },
    en: {
      noData: "No data",
      lessonColumn: "Slot",
      bells: "Signals",
      countdown: "Until signal",
      events: "Events",
      announcements: "Announcements",
      schoolNews: "News",
      rssNews: "RSS feed",
      noAnnouncements: "No announcements",
      noSchoolNews: "No news",
      qr: "QR to article",
      noRssNews: "No news",
      scheduleDefault: "Schedule",
      nextSchoolDay: "Next schedule day:",
      carouselBlank: "Pause (background)",
      imageEmpty: "No image (add a file or URL)",
      imageAlt: "image",
      carouselNoSlides: "No slides selected",
      emergencyTimeLeft: "Time left:",
      widgetMissing: "Widget {{type}} is missing.",
      widgetError: "Widget {{type}} error.",
    },
  };

  function tvUiStrings() {
    const ui = String(getDisplayFromPayload().ui_locale || "ru").toLowerCase();
    const lang = ui === "en" ? "en" : "ru";
    const ext = typeof globalThis !== "undefined" && globalThis.GuardSchoolTvLocales;
    if (ext && ext[lang]) return ext[lang];
    return TV_UI_FALLBACK[lang];
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

  /** Абсолютный URL для <img>: часть ТВ/WebView криво резолвит относительные /uploads/… */
  function resolveSchoolNewsMediaSrc(u) {
    const s = String(u || "").trim();
    if (!s) return "";
    if (s.startsWith("data:") || s.startsWith("blob:")) return s;
    if (/^https?:\/\//i.test(s)) return s;
    try {
      const origin = global.location && global.location.origin ? String(global.location.origin) : "";
      if (origin && s.startsWith("/")) return new URL(s, origin).href;
    } catch (_) {}
    return s;
  }

  function schoolNewsImageSrcWithV(raw, item) {
    const base = resolveSchoolNewsMediaSrc(raw);
    if (!base) return "";
    const v = encodeURIComponent(String(item.id || item.created_at || "")).slice(0, 80);
    const sep = base.indexOf("?") >= 0 ? "&" : "?";
    return v ? `${base}${sep}v=${v}` : base;
  }

  /** Совпадает с guardschool.app._sanitize_school_news_display_html (fallback для старых payload). */
  function sanitizeSchoolNewsDisplayHtml(raw) {
    let s = String(raw || "").trim();
    if (s.length > 120000) s = s.slice(0, 120000);
    s = s.replace(/<script[^>]*>[\s\S]*?<\/script>/gi, "");
    s = s.replace(/<\/?script[^>]*>/gi, "");
    s = s.replace(/<\s*iframe[^>]*>[\s\S]*?<\/iframe>/gi, "");
    s = s.replace(/<\s*(?:object|embed)[^>]*>[\s\S]*?<\/(?:object|embed)>/gi, "");
    s = s.replace(/\son[a-z]+\s*=\s*"[^"]*"/gi, "");
    s = s.replace(/\son[a-z]+\s*=\s*'[^']*'/gi, "");
    s = s.replace(/\sstyle\s*=\s*"[^"]*"/gi, "");
    s = s.replace(/\sstyle\s*=\s*'[^']*'/gi, "");
    s = s.replace(/href\s*=\s*"javascript:[^"]*"/gi, 'href="#"');
    s = s.replace(/href\s*=\s*'javascript:[^']*'/gi, "href='#'");
    return s.trim();
  }

  function schoolNewsBodyFontPx(settings) {
    const raw = settings && settings.bodyFontSize != null && settings.bodyFontSize !== "" ? settings.bodyFontSize : settings && settings.fontSize;
    const n = Number(raw);
    const v = Number.isFinite(n) ? Math.round(n) : 18;
    return Math.max(8, Math.min(96, v));
  }

  function checkinWidgetRootStyle(ws) {
    const s = ws || {};
    const n = Number(s.fontSize);
    const hasFs = Number.isFinite(n) && n >= 10 && n <= 48;
    const bold = s.bold === true || s.bold === 1;
    const fw = bold ? 700 : 400;
    const parts = [
      "height:100%",
      "display:flex",
      "flex-direction:column",
      "gap:8px",
      "padding:10px",
      "overflow:auto",
      "box-sizing:border-box",
      `font-weight:${fw}`,
    ];
    if (hasFs) parts.push(`font-size:${Math.round(n)}px`);
    return parts.join(";");
  }

  function checkinWidgetRootFluidClass(ws) {
    const s = ws || {};
    const n = Number(s.fontSize);
    const hasFs = Number.isFinite(n) && n >= 10 && n <= 48;
    return hasFs ? "" : " gs-checkin--font-fluid";
  }
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

  global.GuardSchoolTvCore = {
    getDisplayFromPayload,
    localeTagFromUi,
    tvUiStrings,
    adjustedDateFromDisplay,
    formatDateLabel,
    formatWidgetDateLine,
    formatClockTimeString,
    capitalizeFirst,
    escapeHtml,
    escapeHtmlAttr,
    resolveSchoolNewsMediaSrc,
    schoolNewsImageSrcWithV,
    sanitizeSchoolNewsDisplayHtml,
    schoolNewsBodyFontPx,
    checkinWidgetRootStyle,
    checkinWidgetRootFluidClass,
    capitalizeSubjectDisplay,
  };
})(typeof window !== "undefined" ? window : globalThis);
