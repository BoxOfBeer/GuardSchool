(function (global) {
  const W = global.GuardSchoolWidgets;
  if (!W) return;
  W.register("marquee", function (ctx) {
    const H = W.helpers;
    if (!H.buildMarquee) return undefined;
    return H.buildMarquee(ctx.widget, ctx.marquee || []);
  });
})(typeof window !== "undefined" ? window : globalThis);
