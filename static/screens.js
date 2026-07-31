(function () {
  const list = document.getElementById("screens-pick-list");
  const msg = document.getElementById("screens-pick-msg");

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/"/g, "&quot;");
  }

  async function load() {
    if (!list) return;
    list.innerHTML = "<p class=\"hint\">Загрузка…</p>";
    try {
      const r = await fetch("/api/screens-index", { credentials: "same-origin", cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const data = await r.json();
      const screens = Array.isArray(data.screens) ? data.screens : [];
      if (!screens.length) {
        list.innerHTML = "<p class=\"hint\">Нет активных экранов в конфигурации.</p>";
        return;
      }
      list.innerHTML = "";
      screens.forEach((row) => {
        const slug = row.slug || "";
        const name = row.name || slug;
        const path = row.path || `/screen/${encodeURIComponent(slug)}`;
        const a = document.createElement("a");
        a.className = "screens-pick-link";
        a.href = path;
        a.textContent = `${name} (${slug})`;
        list.appendChild(a);
      });
    } catch (e) {
      list.innerHTML = "";
      if (msg) msg.textContent = "Не удалось загрузить список: " + (e && e.message ? e.message : e);
    }
  }

  load();
})();
