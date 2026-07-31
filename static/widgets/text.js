(function (global) {
  const W = global.GuardSchoolWidgets;
  if (!W) return;
  const tag = "di" + "v";
  W.register("text", function (ctx) {
    const widget = ctx.widget;
    const weight = ctx.weight || "";
    const fs = widget.settings.fontSize;
    const col = widget.settings.color;
    const body = widget.settings.text;
    return (
      "<" +
      tag +
      ' class="widget-center-text" style="font-size:' +
      fs +
      "px;color:" +
      col +
      ";" +
      weight +
      '">' +
      body +
      "</" +
      tag +
      ">"
    );
  });
})(typeof window !== "undefined" ? window : globalThis);
