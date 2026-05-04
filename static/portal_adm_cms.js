/**
 * Редактор контента портала экосистемы (провайдер ADM).
 */
const $ = (id) => document.getElementById(id);

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, credentials: "include" });
  const data = await r.json().catch(() => ({}));
  if (r.status === 401) {
    window.location.replace("/ADM");
    throw new Error("401");
  }
  if (!r.ok) throw new Error(`${r.status}: ${data.detail || JSON.stringify(data)}`);
  return data;
}

function splitParas(text) {
  return String(text || "")
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean);
}

function joinParas(arr) {
  return Array.isArray(arr) ? arr.join("\n\n") : "";
}

function parsePipeLines(text) {
  const out = [];
  for (const line of String(text || "").split("\n")) {
    const t = line.trim();
    if (!t || t.startsWith("//")) continue;
    const parts = t.split("|").map((s) => s.trim());
    if (parts.length < 2) continue;
    const label = parts[0];
    const href = parts[1];
    const flag = (parts[2] || "").toLowerCase();
    if (!label || !href) continue;
    const row = { label, href };
    if (flag === "demo") row.role = "demo";
    else if (flag === "register" || flag === "reg") row.role = "register";
    else if (flag === "1" || flag === "true" || flag === "ext" || flag === "yes") row.external = true;
    else if (/^https?:\/\//i.test(href)) row.external = true;
    out.push(row);
  }
  return out;
}

function formatPipeLines(items) {
  if (!Array.isArray(items)) return "";
  return items
    .filter((x) => x && x.label && x.href)
    .map((x) => {
      let line = `${x.label}|${x.href}`;
      if (x.role === "demo") line += "|demo";
      else if (x.role === "register") line += "|register";
      else if (x.external) line += "|1";
      return line;
    })
    .join("\n");
}

function collectAppsFromDom() {
  const rows = document.querySelectorAll("[data-cms-app-row]");
  const apps = [];
  rows.forEach((row) => {
    const id = (row.querySelector('[data-f="id"]')?.value || "").trim();
    const name = (row.querySelector('[data-f="name"]')?.value || "").trim();
    if (!name) return;
    apps.push({
      id,
      name,
      tag: (row.querySelector('[data-f="tag"]')?.value || "").trim(),
      tag_style: (row.querySelector('[data-f="tag_style"]')?.value || "soon").trim(),
      summary: (row.querySelector('[data-f="summary"]')?.value || "").trim(),
      detail: (row.querySelector('[data-f="detail"]')?.value || "").trim(),
      url: (row.querySelector('[data-f="url"]')?.value || "").trim(),
      url_label: (row.querySelector('[data-f="url_label"]')?.value || "").trim(),
    });
  });
  return apps;
}

function appRowHtml(app, idx) {
  const a = app || {};
  return `<div class="cms-app-block portal-card" data-cms-app-row="${idx}" style="margin-top:12px;padding:12px">
    <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap">
      <strong style="color:#fff">Приложение ${idx + 1}</strong>
      <button type="button" class="portal-btn danger cms-app-remove" data-idx="${idx}">Удалить</button>
    </div>
    <div class="toolbar inputs-row" style="margin-top:8px">
      <div class="grow compact">
        <label class="portal-label">id (латиница)</label>
        <input class="portal-field" data-f="id" value="${esc(a.id || "")}" />
      </div>
      <div class="grow">
        <label class="portal-label">Название</label>
        <input class="portal-field" data-f="name" value="${esc(a.name || "")}" />
      </div>
      <div class="grow compact">
        <label class="portal-label">Бейдж</label>
        <input class="portal-field" data-f="tag" value="${esc(a.tag || "")}" placeholder="Доступно / В разработке" />
      </div>
      <div class="grow compact">
        <label class="portal-label">Стиль бейджа</label>
        <select class="portal-field" data-f="tag_style">
          ${["live", "soon", "planned", "platform"]
            .map(
              (v) =>
                `<option value="${v}" ${a.tag_style === v ? "selected" : ""}>${v}</option>`,
            )
            .join("")}
        </select>
      </div>
    </div>
    <label class="portal-label" style="display:block;margin-top:8px">Кратко</label>
    <textarea class="portal-field" data-f="summary" rows="2" style="width:100%;min-height:52px">${esc(a.summary || "")}</textarea>
    <label class="portal-label" style="display:block;margin-top:8px">Подробно</label>
    <textarea class="portal-field" data-f="detail" rows="4" style="width:100%">${esc(a.detail || "")}</textarea>
    <div class="toolbar inputs-row" style="margin-top:8px">
      <div class="grow">
        <label class="portal-label">URL (https… или пусто)</label>
        <input class="portal-field" data-f="url" value="${esc(a.url || "")}" />
      </div>
      <div class="grow compact">
        <label class="portal-label">Подпись кнопки</label>
        <input class="portal-field" data-f="url_label" value="${esc(a.url_label || "")}" placeholder="Перейти" />
      </div>
    </div>
  </div>`;
}

function wireAppRemove() {
  const host = $("cms-apps-host");
  if (!host) return;
  host.querySelectorAll(".cms-app-remove").forEach((btn) => {
    btn.addEventListener("click", () => {
      const row = btn.closest("[data-cms-app-row]");
      row?.remove();
      if (!host.querySelector("[data-cms-app-row]")) {
        host.innerHTML = appRowHtml({}, 0);
        wireAppRemove();
      }
    });
  });
}

function renderAppRows(apps) {
  const host = $("cms-apps-host");
  if (!host) return;
  const list = Array.isArray(apps) && apps.length ? apps : [{}];
  host.innerHTML = list.map((a, i) => appRowHtml(a, i)).join("");
  wireAppRemove();
}

function blockTypeFields(t, b) {
  const x = b || {};
  if (t === "h2" || t === "p") {
    return `<label class="portal-label">Текст</label><textarea class="portal-field" data-bf="text" rows="${
      t === "h2" ? 2 : 5
    }" style="width:100%">${esc(x.text || "")}</textarea>`;
  }
  if (t === "badge") {
    const v = ["success", "neutral", "warning"].includes(x.variant) ? x.variant : "neutral";
    return `<div class="toolbar inputs-row" style="margin-top:8px">
      <div class="grow compact">
        <label class="portal-label">Вариант</label>
        <select class="portal-field" data-bf="badge-variant">
          ${["success", "neutral", "warning"]
            .map((opt) => `<option value="${opt}" ${opt === v ? "selected" : ""}>${opt}</option>`)
            .join("")}
        </select>
      </div>
    </div>
    <label class="portal-label">Текст метки</label>
    <input class="portal-field" data-bf="badge-text" value="${esc(x.text || "")}" style="width:100%" />`;
  }
  if (t === "figure") {
    return `<label class="portal-label">URL изображения (https…, /static/…, /uploads/…)</label>
    <input class="portal-field" data-bf="fig-src" value="${esc(x.src || "")}" style="width:100%" />
    <label class="portal-label">Подпись над картинкой (необяз.)</label>
    <input class="portal-field" data-bf="fig-title" value="${esc(x.title || "")}" style="width:100%" />
    <label class="portal-label">Подпись под картинкой</label>
    <textarea class="portal-field" data-bf="fig-caption" rows="2" style="width:100%">${esc(x.caption || "")}</textarea>
    <label class="portal-label">alt для доступности</label>
    <input class="portal-field" data-bf="fig-alt" value="${esc(x.alt || "")}" style="width:100%" />`;
  }
  if (t === "ul") {
    const lines = Array.isArray(x.items) ? x.items.join("\n") : "";
    return `<label class="portal-label">Строки списка (одна строка — один пункт)</label>
    <textarea class="portal-field" data-bf="ul-items" rows="6" style="width:100%">${esc(lines)}</textarea>`;
  }
  return `<label class="portal-label">Текст</label><textarea class="portal-field" data-bf="text" rows="4" style="width:100%">${esc(
    x.text || "",
  )}</textarea>`;
}

function blockRowHtml(b, idx, pg) {
  const raw = (b && b.type) || "p";
  const t = ["h2", "p", "badge", "figure", "ul"].includes(raw) ? raw : "p";
  return `<div class="portal-card" data-cms-block-row data-pg="${pg}" style="margin-top:12px;padding:12px">
    <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap">
      <strong style="color:#fff">Блок ${idx + 1}</strong>
      <button type="button" class="portal-btn danger cms-block-remove">Удалить</button>
    </div>
    <label class="portal-label">Тип</label>
    <select class="portal-field" data-bf="type">
      ${["h2", "p", "badge", "figure", "ul"]
        .map((v) => `<option value="${v}" ${t === v ? "selected" : ""}>${v}</option>`)
        .join("")}
    </select>
    <div data-bf-host>${blockTypeFields(t, b)}</div>
  </div>`;
}

function wirePageBlockHandlers(pg) {
  const host = $(`cms-blocks-${pg}-host`);
  if (!host) return;
  if (host.dataset.delegation === "1") return;
  host.dataset.delegation = "1";
  host.addEventListener("change", (ev) => {
    const sel = ev.target.closest('[data-bf="type"]');
    if (!sel || !host.contains(sel)) return;
    const row = sel.closest("[data-cms-block-row]");
    if (!row) return;
    const t = sel.value;
    const hostFields = row.querySelector("[data-bf-host]");
    if (hostFields) hostFields.innerHTML = blockTypeFields(t, {});
  });
  host.addEventListener("click", (ev) => {
    const btn = ev.target.closest(".cms-block-remove");
    if (!btn || !host.contains(btn)) return;
    const row = btn.closest("[data-cms-block-row]");
    row?.remove();
    if (!host.querySelector("[data-cms-block-row]")) {
      host.innerHTML = blockRowHtml({ type: "p", text: "" }, 0, pg);
    }
  });
}

function collectBlocksFromDom(pg) {
  const host = $(`cms-blocks-${pg}-host`);
  if (!host) return [];
  const out = [];
  host.querySelectorAll("[data-cms-block-row]").forEach((row) => {
    const t = (row.querySelector('[data-bf="type"]')?.value || "p").toLowerCase();
    if (t === "h2" || t === "p") {
      const text = (row.querySelector('[data-bf="text"]')?.value || "").trim();
      if (text) out.push({ type: t, text });
      return;
    }
    if (t === "badge") {
      const text = (row.querySelector('[data-bf="badge-text"]')?.value || "").trim();
      let variant = (row.querySelector('[data-bf="badge-variant"]')?.value || "neutral").toLowerCase();
      if (!["success", "neutral", "warning"].includes(variant)) variant = "neutral";
      if (text) out.push({ type: "badge", text, variant });
      return;
    }
    if (t === "figure") {
      const src = (row.querySelector('[data-bf="fig-src"]')?.value || "").trim();
      const title = (row.querySelector('[data-bf="fig-title"]')?.value || "").trim();
      const caption = (row.querySelector('[data-bf="fig-caption"]')?.value || "").trim();
      const alt = (row.querySelector('[data-bf="fig-alt"]')?.value || "").trim();
      if (src || title || caption || alt) {
        out.push({ type: "figure", src, title, caption, alt });
      }
      return;
    }
    if (t === "ul") {
      const raw = row.querySelector('[data-bf="ul-items"]')?.value || "";
      const items = raw
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);
      if (items.length) out.push({ type: "ul", items });
    }
  });
  return out;
}

function collectPage(pg) {
  const title = ($(`cms-pg-${pg}-title`)?.value || "").trim();
  if (!title) return null;
  const meta_description = ($(`cms-pg-${pg}-meta`)?.value || "").trim();
  const vbOn = $(`cms-pg-${pg}-vb-on`)?.checked;
  const vbText = ($(`cms-pg-${pg}-vb-text`)?.value || "").trim();
  let vbVar = ($(`cms-pg-${pg}-vb-var`)?.value || "neutral").toLowerCase();
  if (!["success", "neutral", "warning"].includes(vbVar)) vbVar = "neutral";
  let version_badge = null;
  if (vbOn && vbText) {
    version_badge = { text: vbText, variant: vbVar };
  }
  const blocks = collectBlocksFromDom(pg);
  return { title, meta_description, version_badge, blocks };
}

function fillPageSection(pg, page) {
  const p = page || {};
  const tEl = $(`cms-pg-${pg}-title`);
  const mEl = $(`cms-pg-${pg}-meta`);
  if (tEl) tEl.value = p.title || "";
  if (mEl) mEl.value = p.meta_description || "";
  const vb = p.version_badge;
  const vbOn = $(`cms-pg-${pg}-vb-on`);
  if (vbOn) {
    vbOn.checked = !!(vb && vb.text);
    const vbt = $(`cms-pg-${pg}-vb-text`);
    const vbv = $(`cms-pg-${pg}-vb-var`);
    if (vbt) vbt.value = vb?.text || "";
    if (vbv) vbv.value = ["success", "neutral", "warning"].includes(vb?.variant) ? vb.variant : "neutral";
  }
  const host = $(`cms-blocks-${pg}-host`);
  if (!host) return;
  host.dataset.delegation = "";
  const blocks = Array.isArray(p.blocks) && p.blocks.length ? p.blocks : [{ type: "p", text: "" }];
  host.innerHTML = blocks.map((b, i) => blockRowHtml(b, i, pg)).join("");
  wirePageBlockHandlers(pg);
}

function fillForm(cms) {
  $("cms-meta-title").value = cms.meta?.page_title || "";
  $("cms-meta-desc").value = cms.meta?.description || "";
  $("cms-meta-portal-url").value = cms.meta?.portal_public_url || "";
  $("cms-hero-brand").value = cms.hero?.brand || "";
  $("cms-hero-title").value = cms.hero?.title || "";
  $("cms-hero-lead").value = cms.hero?.lead || "";
  $("cms-hero-p-label").value = cms.hero?.primary_action?.label || "";
  $("cms-hero-p-href").value = cms.hero?.primary_action?.href || "";
  $("cms-hero-p-ext").checked = !!cms.hero?.primary_action?.external;
  $("cms-hero-secondary").value = formatPipeLines(cms.hero?.secondary_actions);
  $("cms-eco-h").value = cms.ecosystem?.heading || "";
  $("cms-eco-paras").value = joinParas(cms.ecosystem?.paragraphs);
  $("cms-demo-h").value = cms.demo?.heading || "";
  $("cms-demo-intro").value = cms.demo?.intro || "";
  $("cms-demo-bullets").value = Array.isArray(cms.demo?.bullets) ? cms.demo.bullets.join("\n") : "";
  $("cms-demo-act-label").value = cms.demo?.action?.label || "";
  $("cms-demo-act-href").value = cms.demo?.action?.href || "";
  $("cms-aside-h").value = cms.links_column?.heading || "";
  $("cms-aside-items").value = formatPipeLines(cms.links_column?.items);
  $("cms-foot").value = cms.footer?.note || "";
  if ($("cms-shell-title")) $("cms-shell-title").value = cms.shell?.nav_title || "";
  if ($("cms-shell-sub")) $("cms-shell-sub").value = cms.shell?.nav_subtitle || "";
  if ($("cms-shell-nav")) $("cms-shell-nav").value = formatPipeLines(cms.shell?.nav);

  const fl = cms.footer_legal || {};
  if ($("cms-fl-copyright")) $("cms-fl-copyright").value = fl.copyright || "";
  if ($("cms-fl-privacy")) $("cms-fl-privacy").value = fl.privacy_text || "";
  if ($("cms-fl-cookies")) $("cms-fl-cookies").value = fl.cookies_text || "";
  if ($("cms-fl-contacts")) $("cms-fl-contacts").value = fl.contacts_text || "";
  if ($("cms-fl-links")) $("cms-fl-links").value = formatPipeLines(fl.extra_links);

  fillPageSection("gs", cms.pages?.guardschool);
  fillPageSection("demo", cms.pages?.["guardschool-demo"]);

  renderAppRows(cms.applications);
}

function collectCms() {
  const primary = {
    label: $("cms-hero-p-label").value.trim(),
    href: $("cms-hero-p-href").value.trim(),
    external: $("cms-hero-p-ext").checked,
  };
  const pages = {};
  const pgGs = collectPage("gs");
  const pgDemo = collectPage("demo");
  if (pgGs) pages.guardschool = pgGs;
  if (pgDemo) pages["guardschool-demo"] = pgDemo;

  const cms = {
    shell: {
      nav_title: $("cms-shell-title").value.trim(),
      nav_subtitle: $("cms-shell-sub").value.trim(),
      nav: parsePipeLines($("cms-shell-nav").value),
    },
    meta: {
      page_title: $("cms-meta-title").value.trim(),
      description: $("cms-meta-desc").value.trim(),
      portal_public_url: $("cms-meta-portal-url").value.trim(),
    },
    hero: {
      brand: $("cms-hero-brand").value.trim(),
      title: $("cms-hero-title").value.trim(),
      lead: $("cms-hero-lead").value.trim(),
      primary_action: primary.label && primary.href ? primary : { label: "", href: "", external: false },
      secondary_actions: parsePipeLines($("cms-hero-secondary").value),
    },
    ecosystem: {
      heading: $("cms-eco-h").value.trim(),
      paragraphs: splitParas($("cms-eco-paras").value),
    },
    applications: collectAppsFromDom(),
    demo: {
      heading: $("cms-demo-h").value.trim(),
      intro: $("cms-demo-intro").value.trim(),
      bullets: $("cms-demo-bullets")
        .value.split("\n")
        .map((s) => s.trim())
        .filter(Boolean),
      action: {
        label: $("cms-demo-act-label").value.trim(),
        href: $("cms-demo-act-href").value.trim(),
      },
    },
    links_column: {
      heading: $("cms-aside-h").value.trim(),
      items: parsePipeLines($("cms-aside-items").value),
    },
    footer: { note: $("cms-foot").value.trim() },
    footer_legal: {
      copyright: ($("cms-fl-copyright")?.value || "").trim(),
      privacy_text: ($("cms-fl-privacy")?.value || "").trim(),
      cookies_text: ($("cms-fl-cookies")?.value || "").trim(),
      contacts_text: ($("cms-fl-contacts")?.value || "").trim(),
      extra_links: parsePipeLines($("cms-fl-links")?.value || ""),
    },
    pages,
  };
  return cms;
}

let cmsLoaded = false;

async function loadCms() {
  const data = await api("/api/provider/portal-cms");
  const cms = data.cms || data;
  fillForm(cms);
  $("cms-status").textContent = "Загружено.";
  cmsLoaded = true;
}

async function saveCms() {
  const body = collectCms();
  $("cms-status").textContent = "Сохранение…";
  await api("/api/provider/portal-cms", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cms: body }),
  });
  $("cms-status").textContent = "Сохранено.";
}

function mountForm() {
  const root = $("cms-mount");
  if (!root || root.dataset.mounted) return;
  root.dataset.mounted = "1";
  root.innerHTML = `
    <div class="cms-editor-layout">
    <nav class="cms-editor-rail" aria-label="К разделам формы">
      <a href="#cms-section-meta">Мета / SEO</a>
      <a href="#cms-section-shell">Левое меню</a>
      <a href="#cms-section-page-gs">/about/guardschool</a>
      <a href="#cms-section-page-demo">/about/guardschool-demo</a>
      <a href="#cms-section-hero">Герой</a>
      <a href="#cms-section-eco">О платформе</a>
      <a href="#cms-section-apps">Приложения</a>
      <a href="#cms-section-demo">Песочница</a>
      <a href="#cms-section-extras">Доп. ссылки</a>
      <a href="#cms-section-foot">Подвал главной</a>
      <a href="#cms-section-legal">Юридический блок</a>
    </nav>
    <div class="cms-editor-main">
    <div class="toolbar actions-row" style="margin-top:0">
      <button type="button" class="portal-btn primary" id="cms-save">Сохранить</button>
      <button type="button" class="portal-btn" id="cms-reload">Сбросить (перечитать с сервера)</button>
      <div style="flex:1"></div>
      <span class="portal-hint" id="cms-status"></span>
    </div>

    <h3 id="cms-section-meta" class="cms-section-title">Мета / SEO</h3>
    <div class="toolbar inputs-row">
      <div class="grow"><label class="portal-label">Заголовок вкладки</label><input class="portal-field" id="cms-meta-title" /></div>
      <div class="grow"><label class="portal-label">Публичный URL портала (для ссылок «назад»)</label><input class="portal-field" id="cms-meta-portal-url" placeholder="https://…" /></div>
    </div>
    <label class="portal-label">Описание (meta description)</label>
    <textarea class="portal-field" id="cms-meta-desc" rows="2" style="width:100%"></textarea>

    <h3 id="cms-section-shell" class="cms-section-title">Левое меню портала</h3>
    <p class="portal-hint">Строки навигации: <code>подпись|/путь</code> или <code>подпись|https://…</code> (https открывается в новой вкладке). Якорь: <code>Обзор|#portal-main-top</code>. Опционально третье поле <code>|1</code> — принудительно «внешняя вкладка».</p>
    <div class="toolbar inputs-row">
      <div class="grow"><label class="portal-label">Заголовок в сайдбаре</label><input class="portal-field" id="cms-shell-title" placeholder="GuardDoc" /></div>
      <div class="grow"><label class="portal-label">Подзаголовок</label><input class="portal-field" id="cms-shell-sub" /></div>
    </div>
    <label class="portal-label">Пункты меню (по одной строке)</label>
    <textarea class="portal-field cms-monospace" id="cms-shell-nav" rows="8" style="width:100%"></textarea>

    <h3 id="cms-section-page-gs" class="cms-section-title">Страница <code>/about/guardschool</code></h3>
    <p class="portal-hint">Полный текст, метка версии, изображения и списки — блоками ниже. Публичный URL задаётся заголовком страницы.</p>
    <div class="toolbar inputs-row">
      <div class="grow"><label class="portal-label">Заголовок (h1 / вкладка)</label><input class="portal-field" id="cms-pg-gs-title" /></div>
    </div>
    <label class="portal-label">Meta description этой страницы</label>
    <textarea class="portal-field" id="cms-pg-gs-meta" rows="2" style="width:100%"></textarea>
    <div class="toolbar inputs-row" style="margin-top:8px;align-items:flex-end">
      <div class="grow compact"><label class="portal-label"><input type="checkbox" id="cms-pg-gs-vb-on" /> Показать метку (версия / статус)</label></div>
      <div class="grow"><label class="portal-label">Текст метки</label><input class="portal-field" id="cms-pg-gs-vb-text" placeholder="Версия актуальна" /></div>
      <div class="grow compact">
        <label class="portal-label">Стиль</label>
        <select class="portal-field" id="cms-pg-gs-vb-var"><option value="success">success</option><option value="neutral">neutral</option><option value="warning">warning</option></select>
      </div>
    </div>
    <label class="portal-label">Блоки контента</label>
    <div id="cms-blocks-gs-host"></div>
    <button type="button" class="portal-btn" id="cms-add-block-gs">+ Блок</button>

    <h3 id="cms-section-page-demo" class="cms-section-title">Страница <code>/about/guardschool-demo</code></h3>
    <p class="portal-hint">Описание демо-песочницы — отдельная страница в том же разделе <code>/about/</code>.</p>
    <div class="toolbar inputs-row">
      <div class="grow"><label class="portal-label">Заголовок</label><input class="portal-field" id="cms-pg-demo-title" /></div>
    </div>
    <label class="portal-label">Meta description</label>
    <textarea class="portal-field" id="cms-pg-demo-meta" rows="2" style="width:100%"></textarea>
    <div class="toolbar inputs-row" style="margin-top:8px;align-items:flex-end">
      <div class="grow compact"><label class="portal-label"><input type="checkbox" id="cms-pg-demo-vb-on" /> Показать метку</label></div>
      <div class="grow"><label class="portal-label">Текст метки</label><input class="portal-field" id="cms-pg-demo-vb-text" /></div>
      <div class="grow compact">
        <label class="portal-label">Стиль</label>
        <select class="portal-field" id="cms-pg-demo-vb-var"><option value="success">success</option><option value="neutral">neutral</option><option value="warning">warning</option></select>
      </div>
    </div>
    <label class="portal-label">Блоки контента</label>
    <div id="cms-blocks-demo-host"></div>
    <button type="button" class="portal-btn" id="cms-add-block-demo">+ Блок</button>

    <h3 id="cms-section-hero" class="cms-section-title">Герой</h3>
    <div class="toolbar inputs-row">
      <div class="grow compact"><label class="portal-label">Бренд (строчка сверху)</label><input class="portal-field" id="cms-hero-brand" /></div>
    </div>
    <label class="portal-label">Заголовок</label>
    <textarea class="portal-field" id="cms-hero-title" rows="2" style="width:100%"></textarea>
    <label class="portal-label">Лид-абзац</label>
    <textarea class="portal-field" id="cms-hero-lead" rows="4" style="width:100%"></textarea>
    <div class="toolbar inputs-row" style="margin-top:8px">
      <div class="grow"><label class="portal-label">Главная кнопка — подпись</label><input class="portal-field" id="cms-hero-p-label" /></div>
      <div class="grow"><label class="portal-label">Главная кнопка — ссылка</label><input class="portal-field" id="cms-hero-p-href" /></div>
      <div class="grow compact" style="align-self:flex-end">
        <label class="portal-label"><input type="checkbox" id="cms-hero-p-ext" /> Внешняя (новая вкладка)</label>
      </div>
    </div>
    <p class="portal-hint">Для кнопки «войти в GuardSchool» укажите <code>https://…/login</code> — иначе корень школьного сайта редиректит на <code>/setup</code> (пока нет учётки).</p>
    <label class="portal-label">Доп. кнопки — строка: <code>подпись|/путь</code>. Для стиля кнопки добавьте третье поле: <code>|demo</code> (акцент демо) или <code>|register</code> (контур). Внешняя вкладка: <code>|1</code>.</label>
    <textarea class="portal-field cms-monospace" id="cms-hero-secondary" rows="4" style="width:100%"></textarea>

    <h3 id="cms-section-eco" class="cms-section-title">Блок «экосистема»</h3>
    <label class="portal-label">Заголовок секции</label>
    <input class="portal-field" id="cms-eco-h" style="width:100%" />
    <label class="portal-label">Абзацы (пустая строка между абзацами)</label>
    <textarea class="portal-field" id="cms-eco-paras" rows="5" style="width:100%"></textarea>

    <h3 id="cms-section-apps" class="cms-section-title">Приложения</h3>
    <p class="portal-hint">Несколько продуктов GuardDoc: карточки на главной. Порядок — как в списке.</p>
    <div id="cms-apps-host"></div>
    <button type="button" class="portal-btn" id="cms-add-app">+ Добавить приложение</button>

    <h3 id="cms-section-demo" class="cms-section-title">Пробная песочница</h3>
    <div class="toolbar inputs-row">
      <div class="grow"><label class="portal-label">Заголовок</label><input class="portal-field" id="cms-demo-h" /></div>
    </div>
    <label class="portal-label">Вводный текст</label>
    <textarea class="portal-field" id="cms-demo-intro" rows="4" style="width:100%"></textarea>
    <label class="portal-label">Маркеры (одна строка — один пункт)</label>
    <textarea class="portal-field" id="cms-demo-bullets" rows="4" style="width:100%"></textarea>
    <div class="toolbar inputs-row">
      <div class="grow"><label class="portal-label">Кнопка песочницы — подпись</label><input class="portal-field" id="cms-demo-act-label" /></div>
      <div class="grow"><label class="portal-label">Кнопка песочницы — href</label><input class="portal-field" id="cms-demo-act-href" placeholder="/try-demo" /></div>
    </div>

    <h3 id="cms-section-extras" class="cms-section-title">Дополнительные ссылки (необязательно)</h3>
    <label class="portal-label">Заголовок колонки</label>
    <input class="portal-field" id="cms-aside-h" style="width:100%" />
    <label class="portal-label">Ссылки — строки <code>подпись|/путь</code></label>
    <textarea class="portal-field cms-monospace" id="cms-aside-items" rows="4" style="width:100%"></textarea>
    <p class="portal-hint">Если список пуст — блок на сайте не показывается.</p>

    <h3 id="cms-section-foot" class="cms-section-title">Подвал главной (короткая строка)</h3>
    <textarea class="portal-field" id="cms-foot" rows="3" style="width:100%"></textarea>

    <h3 id="cms-section-legal" class="cms-section-title">Юридический блок (конфиденциальность, cookie, контакты)</h3>
    <p class="portal-hint">Показывается на главной и на страницах <code>/about/…</code> внизу макета.</p>
    <label class="portal-label">Копирайт</label>
    <input class="portal-field" id="cms-fl-copyright" style="width:100%" />
    <label class="portal-label">Конфиденциальность</label>
    <textarea class="portal-field" id="cms-fl-privacy" rows="4" style="width:100%"></textarea>
    <label class="portal-label">Файлы cookie</label>
    <textarea class="portal-field" id="cms-fl-cookies" rows="4" style="width:100%"></textarea>
    <label class="portal-label">Контакты</label>
    <textarea class="portal-field" id="cms-fl-contacts" rows="3" style="width:100%"></textarea>
    <label class="portal-label">Доп. ссылки — строки <code>подпись|/путь</code></label>
    <textarea class="portal-field cms-monospace" id="cms-fl-links" rows="3" style="width:100%"></textarea>
    </div>
    </div>
  `;

  $("cms-save").addEventListener("click", () => saveCms().catch((e) => ($("cms-status").textContent = String(e.message || e))));
  $("cms-reload").addEventListener("click", () => loadCms().catch((e) => ($("cms-status").textContent = String(e.message || e))));
  $("cms-add-app").addEventListener("click", () => {
    const host = $("cms-apps-host");
    const n = host.querySelectorAll("[data-cms-app-row]").length;
    host.insertAdjacentHTML("beforeend", appRowHtml({}, n));
    wireAppRemove();
  });
  $("cms-add-block-gs").addEventListener("click", () => {
    const host = $("cms-blocks-gs-host");
    const n = host.querySelectorAll("[data-cms-block-row]").length;
    host.insertAdjacentHTML("beforeend", blockRowHtml({ type: "p", text: "" }, n, "gs"));
  });
  $("cms-add-block-demo").addEventListener("click", () => {
    const host = $("cms-blocks-demo-host");
    const n = host.querySelectorAll("[data-cms-block-row]").length;
    host.insertAdjacentHTML("beforeend", blockRowHtml({ type: "p", text: "" }, n, "demo"));
  });
}

function switchTab(which) {
  const lic = $("panel-lic");
  const cms = $("panel-cms");
  const bLic = $("adm-tab-lic");
  const bCms = $("adm-tab-cms");
  if (!lic || !cms) return;
  if (which === "cms") {
    lic.hidden = true;
    cms.hidden = false;
    bLic.classList.remove("primary");
    bCms.classList.add("primary");
    mountForm();
    if (!cmsLoaded) loadCms().catch((e) => console.error(e));
  } else {
    cms.hidden = true;
    lic.hidden = false;
    bCms.classList.remove("primary");
    bLic.classList.add("primary");
  }
}

function initAdmTabs() {
  $("adm-tab-lic")?.addEventListener("click", () => switchTab("lic"));
  $("adm-tab-cms")?.addEventListener("click", () => switchTab("cms"));
}

initAdmTabs();
