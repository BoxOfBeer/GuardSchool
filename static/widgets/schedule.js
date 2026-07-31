(function (global) {
  const W = global.GuardSchoolWidgets;
  if (!W) return;
  const tag = "di" + "v";
  W.register("schedule", function (ctx) {
    const H = W.helpers;
    const widget = ctx.widget;
    const schedule = ctx.schedule || {};
    const L = ctx.L || {};
    const ws = widget.settings || {};
    const fmt = H.formatDateLabel;
    const tbl = H.buildScheduleTable;
    if (!fmt || !tbl) return undefined;
    const title = (schedule.bell_status && schedule.bell_status.schedule_title) || L.scheduleDefault;
    const nextDayTitle = (L.nextSchoolDay || "") + " " + fmt(schedule.next_school_day);
    const bellEntries =
      schedule.bell_status && Array.isArray(schedule.bell_status.entries) ? schedule.bell_status.entries : [];
    const hideTodayAsSchoolDayOver = schedule.bell_status && schedule.bell_status.state === "done" && bellEntries.length > 0;
    const hasTodayRows = Array.isArray(schedule.today_rows) && schedule.today_rows.length > 0;
    const hasTomorrowRows = Array.isArray(schedule.tomorrow_rows) && schedule.tomorrow_rows.length > 0;
    const todayBlock = hideTodayAsSchoolDayOver || !hasTodayRows ? "" : tbl(schedule.today_rows, title, ws);
    const showTomorrowBlock = ws.showTomorrow !== false && schedule.tomorrow_schedule_visible !== false;
    const tomorrowBlock = showTomorrowBlock && hasTomorrowRows ? tbl(schedule.tomorrow_rows, nextDayTitle, ws) : "";
    return "<" + tag + ' class="schedule-widget-content">' + todayBlock + tomorrowBlock + "</" + tag + ">";
  });
})(typeof window !== "undefined" ? window : globalThis);
