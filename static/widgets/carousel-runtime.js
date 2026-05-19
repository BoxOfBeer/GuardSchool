/**
 * Состояние и таймеры карусели на ТВ (до screen_widgets.js, после runtime.js).
 * start() получает renderWidgetHtml / widgetEffectiveType из screen_widgets.
 */
(function (global) {
  const carouselState = new Map();

  const RANDOM_ANIMATIONS = [
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

  function clearTimeouts() {
    for (const st of carouselState.values()) {
      if (st.timerId) clearTimeout(st.timerId);
      if (st.animTimeout) clearTimeout(st.animTimeout);
      st.timerId = null;
      st.animTimeout = null;
    }
  }

  function prune(screen) {
    const widgets = (screen && screen.widgets) || [];
    const allowed = new Set(widgets.filter((w) => w && w.type === "carousel").map((w) => w.id));
    for (const id of [...carouselState.keys()]) {
      if (!allowed.has(id)) carouselState.delete(id);
    }
  }

  function slideDurationMs(widget, childWidget) {
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

  /**
   * @param {HTMLElement} block
   * @param {object} widget
   * @param {object[]} childWidgets
   * @param {object} deps — renderWidgetHtml, widgetEffectiveType, tvUiStrings, getDisplayFromPayload
   */
  function start(block, widget, childWidgets, schedule, screen, holidays, announcements, marquee, schoolNews, rssNews, deps) {
    const renderWidgetHtml = deps.renderWidgetHtml;
    const widgetEffectiveType = deps.widgetEffectiveType;
    const tvUiStrings = deps.tvUiStrings;
    const getDisplayFromPayload = deps.getDisplayFromPayload;

    if (!childWidgets.length) {
      block.innerHTML = `<div class="widget-meta">${tvUiStrings().carouselNoSlides}</div>`;
      return;
    }

    const startDelayMs = Math.max(0, Number(widget.settings.startDelaySec || 0) * 1000);
    const now = Date.now();
    const firstDur = slideDurationMs(widget, childWidgets[0]);
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
      st.nextSwitchAt = slideEnd + slideDurationMs(widget, childWidgets[st.index]);
    }

    const slides = childWidgets.map((childWidget, index) => {
      const slide = document.createElement("div");
      slide.className = `carousel-slide ${index === st.index ? "active" : ""}`;
      if (widgetEffectiveType(childWidget) === "text") slide.style.background = childWidget.settings.background;
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
      const waitMs = slideDurationMs(widget, nextWidget);
      st.nextSwitchAt = Date.now() + waitMs;
      const next = slides[st.index];
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
      const animation =
        widget.settings.animation === "random"
          ? RANDOM_ANIMATIONS[Math.floor(Math.random() * RANDOM_ANIMATIONS.length)]
          : widget.settings.animation || "slide";
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

  const api = {
    state: carouselState,
    clearTimeouts,
    prune,
    slideDurationMs,
    RANDOM_ANIMATIONS,
    start,
  };

  if (!global.GuardSchoolWidgets) {
    global.GuardSchoolWidgets = { register() {}, render() {}, has() {}, helpers: {}, carousel: api };
  } else {
    global.GuardSchoolWidgets.carousel = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
