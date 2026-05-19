(function (global) {
  const W = global.GuardSchoolWidgets;
  if (!W) return;
  W.register("school_news", function (ctx) {
    const H = W.helpers;
    if (!H.buildSchoolNews) return undefined;
    return H.buildSchoolNews(ctx.widget, ctx.schoolNews || [], ctx.screen, ctx.ctx);
  });
})(typeof window !== "undefined" ? window : globalThis);
