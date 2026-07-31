(function (global) {
  const W = global.GuardSchoolWidgets;
  if (!W) return;
  const tag = "di" + "v";
  W.register("time", function (ctx) {
    const widget = ctx.widget;
    const weight = ctx.weight || "";
    const fs = widget.settings.fontSize;
    const col = widget.settings.color;
    return (
      "<" +
      tag +
      ' class="gs-screen-clock widget-center-text" style="font-size:' +
      fs +
      "px;color:" +
      col +
      ";" +
      weight +
      '"></' +
      tag +
      ">"
    );
  });
})(typeof window !== "undefined" ? window : globalThis);
