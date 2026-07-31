(function (global) {
  const W = global.GuardSchoolWidgets;
  if (!W) return;
  W.register("holidays", function (ctx) {
    const H = W.helpers;
    if (!H.buildUpcomingHolidays) return undefined;
    return H.buildUpcomingHolidays(ctx.widget.settings || {}, ctx.holidays || []);
  });
})(typeof window !== "undefined" ? window : globalThis);
