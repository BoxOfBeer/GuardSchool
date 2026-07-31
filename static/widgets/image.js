(function (global) {
  const W = global.GuardSchoolWidgets;
  if (!W) return;
  const tag = "di" + "v";
  W.register("image", function (ctx) {
    const H = W.helpers;
    const widget = ctx.widget;
    const L = ctx.L || (H.tvUiStrings ? H.tvUiStrings() : {});
    const s = widget.settings || {};
    const escA = H.escapeHtmlAttr;
    const rawList = Array.isArray(s.images) ? s.images : [];
    const legacy = String(s.imageUrl || "").trim();
    const slides = (rawList.length ? rawList : legacy ? [{ name: "", url: legacy }] : [])
      .map(function (it) {
        return {
          name: String(it && it.name != null ? it.name : "").trim(),
          url: String(it && it.url != null ? it.url : "").trim(),
        };
      })
      .filter(function (it) {
        return it.url;
      });
    const opacityPct = Math.max(0, Math.min(100, Number(s.opacity != null ? s.opacity : 85)));
    const op = opacityPct / 100;
    const fit = s.objectFit === "cover" ? "cover" : "contain";
    if (!slides.length) {
      return "<" + tag + ' class="image-widget-empty widget-meta">' + (L.imageEmpty || "") + "</" + tag + ">";
    }
    const rotateSec = Math.max(0, Number(s.imagesRotateSec) || 0);
    var idx = 0;
    if (slides.length > 1 && rotateSec >= 1) {
      const slot = Math.floor(Date.now() / 1000 / rotateSec);
      idx = slot % slides.length;
    }
    const pick = slides[idx];
    const url = pick.url;
    const label = escA(pick.name || L.imageAlt || "");
    return (
      "<" +
      tag +
      ' class="image-widget-root" style="opacity:' +
      op +
      ';width:100%;height:100%;display:flex;align-items:center;justify-content:center;overflow:hidden;">' +
      '<img class="image-widget-img" src="' +
      escA(url) +
      '" alt="' +
      label +
      '" style="object-fit:' +
      fit +
      ';max-width:100%;max-height:100%;width:100%;height:100%;pointer-events:none;" />' +
      "</" +
      tag +
      ">"
    );
  });
})(typeof window !== "undefined" ? window : globalThis);
