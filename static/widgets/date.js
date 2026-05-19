(function (global) {
  const W = global.GuardSchoolWidgets;
  if (!W) return;
  W.register("date", function (ctx) {
    const H = W.helpers;
    const widget = ctx.widget;
    const weight = ctx.weight || "";
    const line = H && H.formatWidgetDateLine ? H.formatWidgetDateLine() : "";
    const fs = widget.settings.fontSize;
    const col = widget.settings.color;
    return (
      '<div class="widget-center-text" style="font-size:' +
      fs +
      "px;color:" +
      col +
      ";" +
      weight +
      '">' +
      line +
      "</div>"
    );
  });
})(typeof window !== "undefined" ? window : globalThis);
