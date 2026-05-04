/**
 * Публичные страницы /about/{slug} — контент из /api/portal/cms → pages[slug].
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

function navLinkAttrs(href, external) {
  const h = String(href || "");
  const isHash = h.startsWith("#");
  const ext = !!external && !isHash;
  if (ext) {
    return ' target="_blank" rel="noopener noreferrer"';
  }
  return "";
}

function renderShellNav(shell) {
  const title = (shell && shell.nav_title) || "GuardDoc";
  const sub = (shell && shell.nav_subtitle) || "";
  const items = Array.isArray(shell && shell.nav) ? shell.nav : [];
  const links = items
    .filter((n) => n && n.label && n.href)
    .map(
      (n) =>
        `<a class="portal-side-link" href="${escAttr(n.href)}"${navLinkAttrs(n.href, n.external)}>${esc(
          n.label,
        )}</a>`,
    )
    .join("");
  return `<aside class="portal-sidebar" aria-label="Навигация">
    <div class="portal-sidebar-brand">
      <span class="portal-sidebar-title">${esc(title)}</span>
      ${sub ? `<span class="portal-sidebar-sub">${esc(sub)}</span>` : ""}
    </div>
    <nav class="portal-sidebar-nav" aria-label="Разделы">${links}</nav>
  </aside>`;
}

function renderVersionBadge(vb) {
  if (!vb || !vb.text) return "";
  const v = ["success", "neutral", "warning"].includes(vb.variant) ? vb.variant : "neutral";
  return `<p class="portal-about-ver portal-about-ver--${v}" role="status">${esc(vb.text)}</p>`;
}

function renderBlock(b) {
  if (!b || !b.type) return "";
  const t = b.type;
  if (t === "h2") {
    return `<h2 class="portal-about-h2">${esc(b.text || "")}</h2>`;
  }
  if (t === "p") {
    return `<p class="portal-eco-prose portal-about-p">${esc(b.text || "")}</p>`;
  }
  if (t === "badge") {
    const v = ["success", "neutral", "warning"].includes(b.variant) ? b.variant : "neutral";
    return `<p class="portal-about-badge portal-about-badge--${v}" role="note">${esc(b.text || "")}</p>`;
  }
  if (t === "figure") {
    const src = String(b.src || "").trim();
    const alt = String(b.alt || b.title || "").trim();
    const img = src
      ? `<img class="portal-about-img" src="${escAttr(src)}" alt="${escAttr(alt || "Иллюстрация")}" loading="lazy" />`
      : "";
    const cap = b.caption ? `<figcaption class="portal-about-figcap">${esc(b.caption)}</figcaption>` : "";
    const tit = b.title ? `<span class="portal-about-figtitle">${esc(b.title)}</span>` : "";
    return `<figure class="portal-about-figure">${tit}${img}${cap}</figure>`;
  }
  if (t === "ul") {
    const items = Array.isArray(b.items) ? b.items : [];
    if (!items.length) return "";
    return `<ul class="portal-about-ul">${items.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
  }
  return "";
}

function renderLegalFooter(fl) {
  if (!fl) return "";
  const cr = (fl.copyright || "").trim();
  const pr = (fl.privacy_text || "").trim();
  const ck = (fl.cookies_text || "").trim();
  const ct = (fl.contacts_text || "").trim();
  const links = Array.isArray(fl.extra_links) ? fl.extra_links.filter((x) => x && x.label && x.href) : [];
  if (!cr && !pr && !ck && !ct && !links.length) return "";
  const extra = links
    .map((l) => `<a class="portal-legal-link" href="${escAttr(l.href)}">${esc(l.label)}</a>`)
    .join(" · ");
  return `<footer class="portal-legal-foot" role="contentinfo">
    ${cr ? `<p class="portal-legal-copy">${esc(cr)}</p>` : ""}
    <div class="portal-legal-columns">
      ${
        pr
          ? `<section class="portal-legal-block"><h3 class="portal-legal-h">Конфиденциальность</h3><p class="portal-legal-p">${esc(
              pr,
            )}</p></section>`
          : ""
      }
      ${
        ck
          ? `<section class="portal-legal-block"><h3 class="portal-legal-h">Файлы cookie</h3><p class="portal-legal-p">${esc(
              ck,
            )}</p></section>`
          : ""
      }
      ${
        ct
          ? `<section class="portal-legal-block"><h3 class="portal-legal-h">Контакты</h3><p class="portal-legal-p">${esc(
              ct,
            )}</p></section>`
          : ""
      }
    </div>
    ${extra ? `<p class="portal-legal-extra">${extra}</p>` : ""}
  </footer>`;
}

async function main() {
  const root = document.getElementById("about-root");
  if (!root) return;

  const parts = location.pathname.split("/").filter(Boolean);
  const slug = (parts[parts.length - 1] || "").toLowerCase();

  try {
    const r = await fetch("/api/portal/cms", { credentials: "same-origin" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const cms = await r.json();
    const page = cms.pages && cms.pages[slug];
    if (!page) {
      root.className = "portal-eco-error";
      root.innerHTML = `<p>Страница не найдена.</p><p class="portal-eco-prose"><a class="portal-side-link" href="/">← На главную</a></p>`;
      return;
    }

    if (page.title) document.title = page.title;
    const md = document.querySelector('meta[name="description"]');
    if (md && page.meta_description) md.setAttribute("content", page.meta_description);

    const shell = cms.shell || {};
    const fl = cms.footer_legal;
    const blocksArr = Array.isArray(page.blocks) ? page.blocks : [];

    root.className = "";
    root.innerHTML = `
      <div class="portal-shell">
        ${renderShellNav(shell)}
        <div class="portal-main" id="about-main-top">
          <a class="portal-about-back portal-side-link" href="/">← На главную портала</a>
          <article class="portal-about-article" lang="ru">
            <header class="portal-about-header">
              <h1 class="portal-about-title">${esc(page.title || "")}</h1>
              ${renderVersionBadge(page.version_badge)}
            </header>
            <div class="portal-about-body">${blocksArr.map(renderBlock).join("")}</div>
          </article>
          ${renderLegalFooter(fl)}
        </div>
      </div>`;
  } catch (e) {
    root.className = "portal-eco-error";
    root.innerHTML = `<p>Не удалось загрузить страницу.</p><p style="font-size:13px;opacity:.85">${esc(
      String(e.message || e),
    )}</p>`;
  }
}

main();
