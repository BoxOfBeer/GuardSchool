/**
 * Реестр рендереров виджетов для ТВ (classic script, до carousel-runtime.js / screen_widgets.js).
 * helpers заполняются в конце screen_widgets.js.
 */
(function (global) {
  const renderers = Object.create(null);

  function register(type, fn) {
    const key = String(type || "").trim();
    if (!key || typeof fn !== "function") return;
    renderers[key] = fn;
  }

  /** @returns {string|undefined} undefined — нет плагина, делегировать в screen_widgets */
  function render(type, ctx) {
    const key = String(type || "").trim();
    const fn = renderers[key];
    if (!fn) return undefined;
    return fn(ctx);
  }

  function has(type) {
    return Object.prototype.hasOwnProperty.call(renderers, String(type || "").trim());
  }

  global.GuardSchoolWidgets = {
    register,
    render,
    has,
    helpers: {},
  };
})(typeof window !== "undefined" ? window : globalThis);
