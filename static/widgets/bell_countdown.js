(function (global) {
  const W = global.GuardSchoolWidgets;
  if (!W) return;
  W.register("bell_countdown", function (ctx) {
    const H = W.helpers;
    if (!H.buildBellCountdown) return undefined;
    const status = ctx.schedule && ctx.schedule.bell_status;
    if (!status) return undefined;
    return H.buildBellCountdown(status, ctx.widget.settings || {});
  });
})(typeof window !== "undefined" ? window : globalThis);
