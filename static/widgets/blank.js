(function (global) {
  const W = global.GuardSchoolWidgets;
  if (!W) return;
  const tag = "di" + "v";
  W.register("blank", function () {
    return "<" + tag + ' class="widget-center-text"></' + tag + ">";
  });
})(typeof window !== "undefined" ? window : globalThis);
