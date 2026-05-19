(function (global) {
  const W = global.GuardSchoolWidgets;
  if (!W) return;
  W.register("checkin_submit", function (ctx) {
    const H = W.helpers;
    if (!H.renderCheckinSubmitWidget) return undefined;
    return H.renderCheckinSubmitWidget(ctx.widget);
  });
})(typeof window !== "undefined" ? window : globalThis);
