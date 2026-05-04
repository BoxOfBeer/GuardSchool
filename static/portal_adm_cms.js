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
    const flag = parts[2];
    if (!label || !href) continue;
    const row = { label, href };
    const extFlag = flag === "1" || flag === "true" || flag === "ext" || flag === "yes";
    if (extFlag || /^https?:\/\//i.test(href)) row.external = true;
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
      if (x.external) line += "|1";
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
  renderAppRows(cms.applications);
}

function collectCms() {
  const primary = {
    label: $("cms-hero-p-label").value.trim(),
    href: $("cms-hero-p-href").value.trim(),
    external: $("cms-hero-p-ext").checked,
  };
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
      <a href="#cms-section-hero">Герой</a>
      <a href="#cms-section-eco">О платформе</a>
      <a href="#cms-section-apps">Приложения</a>
      <a href="#cms-section-demo">Песочница</a>
      <a href="#cms-section-extras">Доп. ссылки</a>
      <a href="#cms-section-foot">Подвал</a>
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
    <label class="portal-label">Доп. кнопки — по одной строке: <code>подпись|/путь</code> или <code>подпись|https://…</code></label>
    <textarea class="portal-field cms-monospace" id="cms-hero-secondary" rows="3" style="width:100%"></textarea>

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

    <h3 id="cms-section-foot" class="cms-section-title">Подвал</h3>
    <textarea class="portal-field" id="cms-foot" rows="3" style="width:100%"></textarea>
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
