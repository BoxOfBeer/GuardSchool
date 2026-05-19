(function (global) {
  const W = global.GuardSchoolWidgets;
  if (!W) return;
  W.register("rss_news", function (ctx) {
    const H = W.helpers;
    if (!H.buildRssNews) return undefined;
    return H.buildRssNews(ctx.widget, ctx.rssNews || []);
  });
})(typeof window !== "undefined" ? window : globalThis);
