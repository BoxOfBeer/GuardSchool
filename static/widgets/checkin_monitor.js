(function (global) {
  const W = global.GuardSchoolWidgets;
  if (!W) return;
  W.register("checkin_monitor", function (ctx) {
    const H = W.helpers;
    if (!H.renderCheckinMonitorWidget) return undefined;
    return H.renderCheckinMonitorWidget(ctx.widget);
  });
})(typeof window !== "undefined" ? window : globalThis);
