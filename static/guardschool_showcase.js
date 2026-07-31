function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escAttr(s) {
  return esc(s).replace(/'/g, "&#39;");
}

function renderShot(sh, idx) {
  const src = String(sh.src || "").trim();
  const img = src
    ? `<img src="${escAttr(src)}" alt="${escAttr(sh.title || "Скриншот")}" loading="lazy" />`
    : `<div class="showcase-shot-placeholder">Укажите URL изображения в админке портала (раздел «Страница GuardSchool»).</div>`;
  return `<figure class="showcase-shot">
    ${img}
    <figcaption>
      <h3>${esc(sh.title || `Фрагмент ${idx + 1}`)}</h3>
      ${sh.caption ? `<p>${esc(sh.caption)}</p>` : ""}
    </figcaption>
  </figure>`;
}

async function main() {
  const root = document.getElementById("showcase-root");
  if (!root) return;

  try {
    const r = await fetch("/api/portal/cms", { credentials: "same-origin" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const cms = await r.json();
    const gs = cms.showcase?.guardschool;
    if (!gs) {
      root.className = "showcase-page";
      root.innerHTML = "<p>Раздел не настроен в CMS портала.</p>";
      return;
    }

    const title = gs.page_title || "GuardSchool";
    document.title = title;
    const md = document.querySelector('meta[name="description"]');
    if (md && gs.meta_description) md.setAttribute("content", gs.meta_description);

    const paras = Array.isArray(gs.paragraphs)
      ? gs.paragraphs.map((p) => `<p class="showcase-prose">${esc(p)}</p>`).join("")
      : "";
    const shots = Array.isArray(gs.screenshots) ? gs.screenshots.map(renderShot).join("") : "";

    root.className = "showcase-page";
    root.innerHTML = `
      <a class="showcase-back portal-side-link" href="/" style="border-radius:10px;padding:8px 12px">← На главную портала</a>
      <h1>${esc(title)}</h1>
      ${gs.intro ? `<p class="showcase-intro">${esc(gs.intro)}</p>` : ""}
      ${paras}
      <div class="showcase-grid">${shots}</div>
    `;
  } catch (e) {
    root.className = "portal-eco-error";
    root.innerHTML = `<p>Не удалось загрузить страницу.</p><p style="font-size:13px">${esc(String(e.message || e))}</p>`;
  }
}

main();
