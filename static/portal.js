/**
 * Портал GuardDoc: левый бар + контент из /api/portal/cms.
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

const fallbackCms = {
  meta: {
    page_title: "GuardDoc — информационные экраны без лишнего оборудования",
    description: "Локальная и облачная система для школьных экранов, телефонов и рабочих компьютеров.",
  },
  shell: {
    nav_title: "GuardDoc",
    nav_subtitle: "Информация там, где она нужна",
    nav: [
      { label: "Обзор", href: "#portal-main-top" },
      { label: "Возможности", href: "#section-ecosystem" },
      { label: "Продукты", href: "#section-apps" },
      { label: "Попробовать", href: "#section-demo" },
    ],
  },
  hero: {
    brand: "Локально · SaaS · Гибрид",
    title: "Живая информация на уже существующих экранах",
    lead: "Телевизоры, телефоны и компьютеры получают актуальные данные из одной системы. Без флешек, закрытых аппаратных комплексов и лишнего оборудования.",
    primary_action: { label: "Открыть GuardSchool", href: "https://school.guarddoc.ru/login", external: true },
    secondary_actions: [
      { label: "Попробовать демо", href: "/try-demo", role: "demo" },
      { label: "Активировать лицензию", href: "/register", role: "register" },
    ],
  },
  ecosystem: {
    heading: "Одна платформа — разные сценарии",
    paragraphs: [
      "Система работает как конструктор информационных экранов: расписание занятий, приём посетителей, движение транспорта, дежурства или внутренние объявления.",
      "Основной контур может полностью оставаться внутри организации. Облако используется отдельно или как резерв для срочных изменений.",
    ],
  },
  applications: [
    { id: "guardschool", name: "GuardSchool", tag: "Работает", tag_style: "live", summary: "Информационные экраны и расписание.", detail: "Телевизоры, мобильная версия, рабочие компьютеры и локальный сервер.", url: "https://school.guarddoc.ru/login", url_label: "Войти" },
    { id: "guardnotes", name: "GuardNotes", tag: "Экосистема", tag_style: "platform", summary: "Связанные инструменты GuardDoc.", detail: "Небольшие прикладные системы с общей идеей: простота, автономность и контроль данных.", url: "", url_label: "" },
  ],
  demo: {
    heading: "Посмотрите без установки",
    intro: "Демо показывает рабочий интерфейс и основные сценарии системы.",
    bullets: ["Настройка нескольких экранов", "Отдельная мобильная выдача", "Работа на обычном офисном компьютере"],
    action: { label: "Открыть демо", href: "/try-demo" },
  },
  links_column: { heading: "", items: [] },
  footer: { note: "GuardDoc — практичные информационные системы без лишней инфраструктуры." },
  footer_legal: {},
};

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
      <span class="portal-brand-mark" aria-hidden="true">G</span>
      <span class="portal-brand-copy">
        <span class="portal-sidebar-title">${esc(title)}</span>
        ${sub ? `<span class="portal-sidebar-sub">${esc(sub)}</span>` : ""}
      </span>
    </div>
    <nav class="portal-sidebar-nav" aria-label="Разделы">${links}</nav>
    <div class="portal-sidebar-note">
      <span class="portal-live-dot" aria-hidden="true"></span>
      Локально или в облаке
    </div>
  </aside>`;
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

function secondaryBtnClass(a) {
  if (a.role === "demo") return "portal-eco-btn portal-eco-btn--demo";
  if (a.role === "register") return "portal-eco-btn portal-eco-btn--outline";
  return "portal-eco-btn";
}

function renderActions(actions, primary) {
  const parts = [];
  if (primary && primary.label && primary.href) {
    const ext = primary.external ? '<span class="ext" aria-hidden="true">↗</span>' : "";
    parts.push(
      `<a class="portal-eco-btn primary" href="${escAttr(primary.href)}" ${navLinkAttrs(
        primary.href,
        primary.external,
      )}>${esc(primary.label)}${ext}</a>`,
    );
  }
  if (Array.isArray(actions)) {
    for (const a of actions) {
      if (!a || !a.label || !a.href) continue;
      const ext = a.external ? '<span class="ext" aria-hidden="true">↗</span>' : "";
      const cls = secondaryBtnClass(a);
      parts.push(
        `<a class="${cls}" href="${escAttr(a.href)}" ${navLinkAttrs(a.href, a.external)}>${esc(
          a.label,
        )}${ext}</a>`,
      );
    }
  }
  return `<div class="portal-eco-actions portal-eco-actions--triple">${parts.join("")}</div>`;
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
    `<a class="portal-eco-btn" href="${escAttr(url)}"${navLinkAttrs(url, true)}>${esc(
      urlLabel,
    )}<span class="ext" aria-hidden="true"> ↗</span></a>`;
  const detailMore =
    app.id === "guardschool"
      ? ` <a class="portal-inline-more" href="/about/guardschool">Подробнее →</a>`
      : "";
  return `<article class="portal-app-card">
    <h3>${esc(app.name)} ${tagText}</h3>
    <p class="summary">${esc(app.summary)}</p>
    <p class="detail">${esc(app.detail)}${detailMore}</p>
    ${link || ""}
  </article>`;
}

function renderLinksColumn(aside) {
  const items = Array.isArray(aside && aside.items) ? aside.items : [];
  const clean = items.filter((it) => it && it.label && it.href);
  if (!clean.length) return "";
  const list = clean
    .map(
      (it) =>
        `<li><a href="${escAttr(it.href)}"${navLinkAttrs(it.href, /^https?:/i.test(it.href))}>${esc(
          it.label,
        )}</a></li>`,
    )
    .join("");
  return `<div class="portal-eco-extras" role="complementary" aria-label="${esc(aside.heading || "Дополнительно")}">
    <h3 class="portal-eco-extras-title">${esc(aside.heading || "")}</h3>
    <ul class="portal-eco-extras-list">${list}</ul>
  </div>`;
}

function render(cms) {
  const shell = cms.shell || {};
  const meta = cms.meta || {};
  const hero = cms.hero || {};
  const eco = cms.ecosystem || {};
  const demo = cms.demo || {};
  const aside = cms.links_column || {};
  const foot = cms.footer || {};
  const fl = cms.footer_legal || {};

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
      ? `<p class="portal-eco-demo-cta"><a class="portal-eco-btn primary" href="${escAttr(demo.action.href)}">${esc(
          demo.action.label,
        )}</a></p>`
      : "";

  const extras = renderLinksColumn(aside);

  return `
  <div class="portal-shell">
    ${renderShellNav(shell)}
    <div class="portal-main" id="portal-main-top">
      <header class="portal-eco-hero">
        <div class="portal-hero-copy">
          ${hero.brand ? `<p class="portal-eco-brand">${esc(hero.brand)}</p>` : ""}
          <h1>${esc(hero.title || "")}</h1>
          <p class="portal-eco-lead">${esc(hero.lead || "")}</p>
          ${renderActions(hero.secondary_actions, hero.primary_action)}
          <div class="portal-value-row" aria-label="Преимущества">
            <span>Без специального оборудования</span>
            <span>Контроль данных у организации</span>
            <span>Любой современный экран</span>
          </div>
        </div>
        <div class="portal-hero-visual" aria-label="Схема работы GuardDoc">
          <div class="portal-flow-source"><strong>GuardDoc</strong><span>единый источник</span></div>
          <div class="portal-flow-line" aria-hidden="true"></div>
          <div class="portal-flow-devices">
            <span>TV</span><span>Телефон</span><span>ПК</span>
          </div>
          <p>Одно изменение появляется на всех выбранных экранах.</p>
        </div>
      </header>

      ${extras}

      <section class="portal-eco-section" id="section-ecosystem" aria-labelledby="eco-heading">
        <h2 id="eco-heading">${esc(eco.heading || "")}</h2>
        ${paras}
      </section>

      <section class="portal-eco-section" id="section-apps" aria-labelledby="apps-heading">
        <h2 id="apps-heading">Приложения экосистемы</h2>
        <div class="portal-eco-apps">${apps}</div>
      </section>

      <section class="portal-eco-section portal-eco-demo" id="section-demo" aria-labelledby="demo-heading">
        <h2 id="demo-heading">${esc(demo.heading || "")}</h2>
        <p class="portal-eco-prose">${esc(demo.intro || "")}</p>
        ${bullets}
        ${demoAction}
      </section>

      <footer class="portal-eco-foot">${esc(foot.note || "")}</footer>
      ${renderLegalFooter(fl)}
    </div>
  </div>`;
}

async function main() {
  const root = document.getElementById("portal-root");
  if (!root) return;

  try {
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => ctrl.abort(), 6000);
    const r = await fetch("/api/portal/cms", { credentials: "same-origin", signal: ctrl.signal });
    window.clearTimeout(timer);
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
    root.className = "";
    root.innerHTML = `<div class="portal-fallback-note">Показана резервная версия портала.</div>${render(fallbackCms)}`;
  }
}

main();
