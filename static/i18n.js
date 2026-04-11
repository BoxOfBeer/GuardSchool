(function (global) {
  const fallbackLang = "ru";
  const bundles = {};
  let lang = fallbackLang;

  function t(key) {
    const b = bundles[lang] || {};
    const fb = bundles[fallbackLang] || {};
    if (Object.prototype.hasOwnProperty.call(b, key)) return b[key];
    if (Object.prototype.hasOwnProperty.call(fb, key)) return fb[key];
    return key;
  }

  async function loadLang(code) {
    const c = code === "en" ? "en" : "ru";
    if (!bundles[c]) {
      const r = await fetch(`/static/locales/${c}.json?v=2`, { cache: "no-store" });
      if (!r.ok) throw new Error(`locales/${c}.json`);
      bundles[c] = await r.json();
    }
    lang = c;
  }

  async function init(locale) {
    await loadLang(locale || fallbackLang);
  }

  function tf(key, vars) {
    let s = t(key);
    if (!vars || typeof vars !== "object") return s;
    Object.keys(vars).forEach((k) => {
      s = s.split(`{{${k}}}`).join(String(vars[k]));
    });
    return s;
  }

  function applyDom(root) {
    const scope = root && root.querySelectorAll ? root : document;
    if (!scope.querySelectorAll) return;
    scope.querySelectorAll("[data-i18n]").forEach((el) => {
      const k = el.getAttribute("data-i18n");
      if (k) el.textContent = t(k);
    });
    scope.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      const k = el.getAttribute("data-i18n-placeholder");
      if (k) el.setAttribute("placeholder", t(k));
    });
    scope.querySelectorAll("[data-i18n-title]").forEach((el) => {
      const k = el.getAttribute("data-i18n-title");
      if (k) el.setAttribute("title", t(k));
    });
    scope.querySelectorAll("[data-i18n-html]").forEach((el) => {
      const k = el.getAttribute("data-i18n-html");
      if (k) el.innerHTML = t(k);
    });
  }

  function getLang() {
    return lang;
  }

  global.GuardSchoolI18n = { t, tf, init, applyDom, getLang, loadLang };
})(window);
