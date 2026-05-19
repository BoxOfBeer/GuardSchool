(function (global) {
  const W = global.GuardSchoolWidgets;
  if (!W) return;
  W.register("announcements", function (ctx) {
    const H = W.helpers;
    if (!H.buildAnnouncements) return undefined;
    return H.buildAnnouncements(ctx.widget.settings, ctx.announcements || [], ctx.widget.id, ctx.ctx);
  });
})(typeof window !== "undefined" ? window : globalThis);
