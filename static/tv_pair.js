function show(el, msg) {
  el.style.display = "block";
  el.textContent = msg;
}

function parseCodeAndScreen() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  // ожидаем /t/<code>/<screen_slug>
  const tIdx = parts.indexOf("t");
  if (tIdx < 0) return { code: "", screen_slug: "" };
  return { code: parts[tIdx + 1] || "", screen_slug: parts[tIdx + 2] || "" };
}

function getDeviceLabel() {
  try {
    const q = new URLSearchParams(window.location.search);
    return (q.get("gs_label") || "").trim().slice(0, 120);
  } catch (_) {
    return "";
  }
}

const pin = document.getElementById("pin");
const go = document.getElementById("go");
const out = document.getElementById("out");
const meta = document.getElementById("meta");

const { code, screen_slug } = parseCodeAndScreen();
meta.textContent = code && screen_slug ? `Код: ${code} · Экран: ${screen_slug}` : "Неверная ссылка подключения.";

go.addEventListener("click", async () => {
  const p = String(pin.value || "").trim();
  if (!p) return show(out, "Введите PIN.");
  if (!code || !screen_slug) return show(out, "Неверная ссылка подключения.");
  go.disabled = true;
  try {
    const r = await fetch("/api/tv/pair", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, pin: p, screen_slug, label: getDeviceLabel() }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) return show(out, `Ошибка ${r.status}: ${data.detail || JSON.stringify(data)}`);

    // Используем тот же ключ, что и текущая логика экрана (screen.js).
    try {
      localStorage.setItem("gs_tv_bearer", String(data.token || ""));
    } catch (_) {}
    window.location.href = data.screen_path || `/screen/${encodeURIComponent(screen_slug)}`;
  } catch (e) {
    show(out, String(e));
  } finally {
    go.disabled = false;
  }
});

