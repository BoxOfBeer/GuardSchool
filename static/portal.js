/**
 * Портал экосистемы GuardDoc: контент с /api/portal/cms (редактируется в /ADM → «Контент портала»).
 */
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

function renderActions(actions, primary) {
  const parts = [];
  if (primary && primary.label && primary.href) {
    const ext = primary.external ? '<span class="ext" aria-hidden="true">↗</span>' : "";
    parts.push(
      `<a class="portal-eco-btn primary" href="${escAttr(primary.href)}" ${
        primary.external ? 'target="_blank" rel="noopener noreferrer"' : ""
      }>${esc(primary.label)}${ext}</a>`,
    );
  }
  if (Array.isArray(actions)) {
    for (const a of actions) {
      if (!a || !a.label || !a.href) continue;
      const ext = a.external ? '<span class="ext" aria-hidden="true">↗</span>' : "";
      parts.push(
        `<a class="portal-eco-btn" href="${escAttr(a.href)}" ${
          a.external ? 'target="_blank" rel="noopener noreferrer"' : ""
        }>${esc(a.label)}${ext}</a>`,
      );
    }
  }
  return `<div class="portal-eco-actions">${parts.join("")}</div>`;
}

function renderAppCard(app) {
  const tagClass = ["live", "soon", "planned", "platform"].includes(app.tag_style)
    ? app.tag_style
    : "soon";
  const tagText = app.tag ? `<span class="portal-app-tag ${tagClass}">${esc(app.tag)}</span>` : "";
  const url = (app.url || "").trim();
  const urlLabel = (app.url_label || "Открыть").trim();
  const link =
    url &&
    `<a class="portal-eco-btn" href="${escAttr(url)}" target="_blank" rel="noopener noreferrer">${esc(
      urlLabel,
    )}<span class="ext" aria-hidden="true"> ↗</span></a>`;
  return `<article class="portal-app-card">
    <h3>${esc(app.name)} ${tagText}</h3>
    <p class="summary">${esc(app.summary)}</p>
    <p class="detail">${esc(app.detail)}</p>
    ${link || ""}
  </article>`;
}

function render(cms) {
  const meta = cms.meta || {};
  const hero = cms.hero || {};
  const eco = cms.ecosystem || {};
  const demo = cms.demo || {};
  const aside = cms.links_column || {};
  const foot = cms.footer || {};

  const paras = Array.isArray(eco.paragraphs)
    ? eco.paragraphs.map((p) => `<p class="portal-eco-prose">${esc(p)}</p>`).join("")
    : "";

  const apps = Array.isArray(cms.applications)
    ? cms.applications.map(renderAppCard).join("")
    : "";

  const bullets = Array.isArray(demo.bullets)
    ? `<ul>${demo.bullets.map((b) => `<li>${esc(b)}</li>`).join("")}</ul>`
    : "";

  const demoAction =
    demo.action && demo.action.label && demo.action.href
      ? `<p style="margin:0"><a class="portal-eco-btn primary" href="${escAttr(demo.action.href)}">${esc(
          demo.action.label,
        )}</a></p>`
      : "";

  const asideItems = Array.isArray(aside.items)
    ? aside.items
        .map(
          (it) =>
            `<li><a href="${escAttr(it.href)}">${esc(it.label)}</a></li>`,
        )
        .join("")
    : "";

  return `
  <div class="portal-eco-wrap">
    <header class="portal-eco-hero">
      ${hero.brand ? `<p class="portal-eco-brand">${esc(hero.brand)}</p>` : ""}
      <h1>${esc(hero.title || "")}</h1>
      <p class="portal-eco-lead">${esc(hero.lead || "")}</p>
      ${renderActions(hero.secondary_actions, hero.primary_action)}
    </header>

    <section class="portal-eco-section" aria-labelledby="eco-heading">
      <h2 id="eco-heading">${esc(eco.heading || "")}</h2>
      ${paras}
    </section>

    <div class="portal-eco-split">
      <div>
        <section class="portal-eco-section" aria-labelledby="apps-heading">
          <h2 id="apps-heading">Приложения экосистемы</h2>
          <div class="portal-eco-apps">${apps}</div>
        </section>

        <section class="portal-eco-section portal-eco-demo" aria-labelledby="demo-heading">
          <h2 id="demo-heading">${esc(demo.heading || "")}</h2>
          <p class="portal-eco-prose">${esc(demo.intro || "")}</p>
          ${bullets}
          ${demoAction}
        </section>
      </div>
      <aside class="portal-eco-aside" aria-label="${esc(aside.heading || "Ссылки")}">
        <h3>${esc(aside.heading || "")}</h3>
        <ul>${asideItems}</ul>
      </aside>
    </div>

    <footer class="portal-eco-foot">${esc(foot.note || "")}</footer>
  </div>`;
}

async function main() {
  const root = document.getElementById("portal-root");
  if (!root) return;

  try {
    const r = await fetch("/api/portal/cms", { credentials: "same-origin" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const cms = await r.json();

    if (cms.meta) {
      if (cms.meta.page_title) document.title = cms.meta.page_title;
      const md = document.querySelector('meta[name="description"]');
      if (md && cms.meta.description) md.setAttribute("content", cms.meta.description);
    }

    root.className = "";
    root.innerHTML = render(cms);
  } catch (e) {
    root.className = "portal-eco-error";
    root.innerHTML = `<p>Не удалось загрузить контент портала.</p><p style="font-size:13px;opacity:.85">${esc(
      String(e.message || e),
    )}</p>`;
  }
}

main();
