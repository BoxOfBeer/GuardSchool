function show(el, msg) {
  el.style.display = "block";
  el.textContent = msg;
}

/** Как на сервере: NFKC + ZWSP/BOM + типичные «длинные» дефисы → ASCII `-`. */
function normalizeTvPairText(raw) {
  let s = String(raw || "")
    .normalize("NFKC")
    .replace(/[\u200B-\u200D\uFEFF]/g, "")
    .trim();
  s = s.replace(/\u2013/g, "-").replace(/\u2014/g, "-").replace(/\u2212/g, "-").replace(/\uff0d/g, "-");
  return s;
}

/** Цифры 0–9 и распространённые арабско-индийские формы (остальное режет сервер через decimal). */
function pinDigitsToAscii(s) {
  let out = "";
  for (const ch of String(s || "")) {
    if (ch >= "0" && ch <= "9") {
      out += ch;
      continue;
    }
    if (/\s/.test(ch)) continue;
    const cp = ch.codePointAt(0);
    if (cp >= 0x0660 && cp <= 0x0669) out += String(cp - 0x0660);
    else if (cp >= 0x06f0 && cp <= 0x06f9) out += String(cp - 0x06f0);
  }
  return out;
}

function decodePathSeg(seg) {
  try {
    return decodeURIComponent(String(seg || ""));
  } catch (_) {
    return String(seg || "");
  }
}

function parseCodeAndScreen() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  // ожидаем /t/<code>/<screen_slug>
  const tIdx = parts.indexOf("t");
  if (tIdx < 0) return { code: "", screen_slug: "" };
  return {
    code: decodePathSeg(parts[tIdx + 1] || ""),
    screen_slug: decodePathSeg(parts[tIdx + 2] || ""),
  };
}

function sanitizeGsTvBearerToken(raw) {
  const s = String(raw || "").trim();
  if (!s || s.length > 220) return "";
  if (!/^[A-Za-z0-9_-]+$/.test(s)) return "";
  return s;
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
  const p = pinDigitsToAscii(normalizeTvPairText(pin.value));
  if (!p) return show(out, "Введите PIN.");
  if (!code || !screen_slug) return show(out, "Неверная ссылка подключения.");
  go.disabled = true;
  try {
    const body = {
      code: normalizeTvPairText(code).toLowerCase(),
      pin: p,
      screen_slug: normalizeTvPairText(screen_slug).toLowerCase(),
      label: getDeviceLabel(),
    };
    const r = await fetch("/api/tv/pair", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json; charset=utf-8", Accept: "application/json" },
      body: JSON.stringify(body),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      let hint = "";
      if (r.status === 403) {
        hint =
          "\n\nЕсли PIN точно верный: обновите страницу (Ctrl+F5), откройте ссылку из админки заново. Кнопка «Сгенерировать код» отключает старые ссылки. PIN задаётся только кнопкой «Сохранить PIN» в блоке ТВ, а не общей «Сохранить» конфигурации.";
      } else if (r.status === 429) {
        hint = "\n\nСлишком много попыток — подождите минуту и повторите.";
      }
      return show(out, `Ошибка ${r.status}: ${data.detail || JSON.stringify(data)}${hint}`);
    }

    // Используем тот же ключ, что и текущая логика экрана (screen.js).
    try {
      const t = sanitizeGsTvBearerToken(String(data.token || ""));
      if (t) localStorage.setItem("gs_tv_bearer", t);
    } catch (_) {}
    const sl = normalizeTvPairText(screen_slug).toLowerCase();
    window.location.href = data.screen_path || `/screen/${encodeURIComponent(sl)}`;
  } catch (e) {
    show(out, String(e));
  } finally {
    go.disabled = false;
  }
});

