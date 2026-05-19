(function (global) {
  const W = global.GuardSchoolWidgets;
  if (!W) return;
  const tag = "di" + "v";
  W.register("emergency", function (ctx) {
    const H = W.helpers;
    const widget = ctx.widget;
    const weight = ctx.weight || "";
    const L = ctx.L || (H.tvUiStrings ? H.tvUiStrings() : {});
    const s = widget.settings || {};
    const esc = H.escapeHtml;
    const escA = H.escapeHtmlAttr;
    const bg = String(s.background || "#b91c1c").trim();
    const raw = String(s.text || "");
    const htmlBody =
      raw
        .split("\n")
        .map(function (line) {
          return esc(line);
        })
        .join("<br>") || "&nbsp;";
    const fs = Math.max(10, Math.min(200, Number(s.fontSize) || 42));
    const color = String(s.color || "#ffffff").trim();
    const imgUrl = String(s.imageUrl || "").trim();
    const cap = String(s.imageCaption || "").trim();
    const capHtml = cap
      ? "<" +
        tag +
        ' class="emergency-overlay-caption" style="font-size:' +
        Math.max(10, Math.round(fs * 0.35)) +
        'px;opacity:0.95;margin-top:12px;">' +
        esc(cap) +
        "</" +
        tag +
        ">"
      : "";
    const imgBlock =
      imgUrl && /^\/uploads\//.test(imgUrl)
        ? "<" +
          tag +
          ' class="emergency-overlay-image-wrap"><img class="emergency-overlay-image" src="' +
          escA(imgUrl) +
          '" alt="" /></' +
          tag +
          ">"
        : "";
    const timerRaw = Number(
      s.timerRemainingSec != null ? s.timerRemainingSec : s.timer_seconds != null ? s.timer_seconds : s.timerSeconds,
    );
    const timerSec = Number.isFinite(timerRaw) ? Math.max(0, Math.round(timerRaw)) : 0;
    const fmt = H.formatEmergencyCountdown || function () {
      return "00:00";
    };
    const timerLabel =
      timerSec > 0 || s.timerShowZero === true
        ? "<" +
          tag +
          ' class="emergency-overlay-timer-wrap"><' +
          tag +
          ' class="emergency-overlay-timer-title">' +
          esc(L.emergencyTimeLeft || "Осталось времени:") +
          "</" +
          tag +
          "><" +
          tag +
          ' class="emergency-overlay-timer" data-emergency-countdown="1" data-seconds-left="' +
          timerSec +
          '">' +
          esc(fmt(timerSec)) +
          "</" +
          tag +
          "></" +
          tag +
          ">"
        : "";
    return (
      "<" +
      tag +
      ' class="emergency-overlay-inner" style="background:' +
      bg +
      ";color:" +
      color +
      ";font-size:" +
      fs +
      "px;" +
      weight +
      '"><' +
      tag +
      ' class="emergency-overlay-stack"><' +
      tag +
      ' class="emergency-overlay-text">' +
      htmlBody +
      "</" +
      tag +
      ">" +
      timerLabel +
      imgBlock +
      capHtml +
      "</" +
      tag +
      "></" +
      tag +
      ">"
    );
  });
})(typeof window !== "undefined" ? window : globalThis);
