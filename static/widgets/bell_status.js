(function (global) {
  const W = global.GuardSchoolWidgets;
  if (!W) return;
  W.register("bell_status", function (ctx) {
    const H = W.helpers;
    if (!H.buildBellStatus) return undefined;
    const status = ctx.schedule && ctx.schedule.bell_status;
    if (!status) return undefined;
    return H.buildBellStatus(status, ctx.widget.settings || {});
  });
})(typeof window !== "undefined" ? window : globalThis);
