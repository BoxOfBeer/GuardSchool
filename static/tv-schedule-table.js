(function (global) {
  "use strict";
  const SCHEDULE_THEME = Object.freeze({
    fg: "#0f172a",
    surface: "rgba(255, 255, 255, 0.92)",
    sectionTitle: "#cbd5e1",
  });

  const {
    escapeHtml,
    escapeHtmlAttr,
    tvUiStrings,
    formatDateLabel,
    capitalizeSubjectDisplay,
  } = global.GuardSchoolTvCore || {};
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

  global.GuardSchoolTvSchedule = {
    SCHEDULE_THEME,
    buildScheduleTable,
    buildBellStatus,
    buildBellCountdown,
    buildUpcomingHolidays,
    holidayTargetDate,
    capitalizeSubjectDisplay,
  };
})(typeof window !== "undefined" ? window : globalThis);
