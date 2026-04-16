/**
 * Редактор шаблонов звонков: сетка по дням недели, загрузка mp3, строки уроков, список шаблонов.
 * Зависимости из app.js — через setBellDeps (без циклического импорта).
 */
import { state, elements } from "./state.js";
import { t, tf } from "./i18n-helpers.js";
import { api, mergeFetchOptions } from "./api-client.js";
import { escapeHtml, escapeHtmlAttr } from "./escape-html.js";

let deps = {
  /** @returns {any} */
  selectedScreen: () => null,
  render: () => {},
  getWeekdayOptions: () => [],
  createTemplateId: () => "",
};

/** Вызвать из app.js после объявления selectedScreen, render, getWeekdayOptions, createTemplateId. */
export function setBellDeps(d) {
  deps = { ...deps, ...d };
}

function currentScreen() {
  return deps.selectedScreen();
}

function selectedBellTemplate() {
  const screen = currentScreen();
  if (!screen || !state.bells?.templates?.length) return state.bells.templates[0];
  return state.bells.templates.find((item) => item.id === screen.bell_schedule_template) || state.bells.templates[0];
}

export function renderBellTemplateOptions() {
  const screen = currentScreen();
  if (!screen) return;
  const current = screen.bell_schedule_template;
  elements.screenBellTemplate.innerHTML = state.bells.templates
    .map(
      (item) =>
        `<option value="${escapeHtmlAttr(String(item.id))}" ${item.id === current ? "selected" : ""}>${escapeHtml(String(item.name || ""))}</option>`,
    )
    .join("");
}

function renderWeekdayBellGrid() {
  const screen = currentScreen();
  if (!screen) return;
  const mapping = screen.weekday_bell_templates || {};
  const templateOptions = state.bells.templates
    .map((item) => `<option value="${escapeHtmlAttr(String(item.id))}">${escapeHtml(String(item.name || ""))}</option>`)
    .join("");
  elements.bellWeekdayGrid.innerHTML = deps.getWeekdayOptions().map((day) => `
    <label title="${escapeHtmlAttr(day.title || day.label)}">
      ${escapeHtml(day.label)}
      <select class="standard-input" data-weekday="${escapeHtmlAttr(day.id)}">
        <option value="">${escapeHtml(t("weekday.defaultTemplate"))}</option>
        ${templateOptions}
      </select>
    </label>
  `).join("");
  elements.bellWeekdayGrid.querySelectorAll("[data-weekday]").forEach((select) => {
    select.value = mapping[select.dataset.weekday] || "";
    select.onchange = (event) => {
      const weekday = event.target.dataset.weekday;
      const value = event.target.value;
      if (!screen.weekday_bell_templates) screen.weekday_bell_templates = {};
      if (value) screen.weekday_bell_templates[weekday] = value;
      else delete screen.weekday_bell_templates[weekday];
    };
  });
}

function bellSoundSelectOptions(selectedVal) {
  const sel = selectedVal || "";
  let html = `<option value="">${escapeHtmlAttr(t("weekday.defaultTemplate"))}</option><option value="-">${escapeHtmlAttr(t("bells.soundNone"))}</option>`;
  (state.bellSoundFiles || []).forEach((f) => {
    html += `<option value="${escapeHtmlAttr(f.filename)}"${f.filename === sel ? " selected" : ""}>${escapeHtmlAttr(f.filename)}</option>`;
  });
  return html;
}

function ensureBellSoundPanel() {
  let panel = document.getElementById("bell-sound-panel");
  if (panel) return panel;
  const bellsCard = document.getElementById("bell-rows")?.closest(".card");
  panel = document.createElement("div");
  panel.id = "bell-sound-panel";
  panel.className = "card-subsection";
  const hint = bellsCard?.querySelector(".hint");
  const rows = document.getElementById("bell-rows");
  if (hint) {
    hint.after(panel);
  } else if (rows && bellsCard) {
    bellsCard.insertBefore(panel, rows);
  } else if (bellsCard) {
    bellsCard.appendChild(panel);
  }
  return panel;
}

function renderBellSoundPanel() {
  const panel = ensureBellSoundPanel();
  if (!panel || !state.bells) return;
  state.bells.sound_defaults = state.bells.sound_defaults || { start: null, end: null };
  const sd = state.bells.sound_defaults;
  const s0 = sd.start || "";
  const s1 = sd.end || "";
  panel.innerHTML = `
    <h3>${escapeHtml(t("bells.soundsTitle"))}</h3>
    <p class="hint bell-sound-intro">${escapeHtml(t("bells.soundsIntro"))}</p>
    <div class="bell-upload-row">
      <label class="bell-file-upload">
        <span class="bell-file-upload-main">${escapeHtml(t("bells.uploadBell"))}</span>
        <span class="bell-file-upload-sub">${escapeHtml(t("bells.uploadFormats"))}</span>
        <input type="file" id="bell-sound-upload" accept=".mp3,.wav,.ogg,.m4a,.aac,audio/*" hidden>
      </label>
    </div>
    <div class="compact-form-row bell-sound-defaults">
      <label>${escapeHtml(t("bells.defIntervalStart"))}<select id="bell-def-start" class="standard-input">${bellSoundSelectOptions(s0)}</select></label>
      <label>${escapeHtml(t("bells.defIntervalEnd"))}<select id="bell-def-end" class="standard-input">${bellSoundSelectOptions(s1)}</select></label>
      <button type="button" class="secondary-btn" id="bell-apply-starts">${escapeHtml(t("bells.applyAllStarts"))}</button>
      <button type="button" class="secondary-btn" id="bell-apply-ends">${escapeHtml(t("bells.applyAllEnds"))}</button>
    </div>`;
  panel.querySelector("#bell-def-start").value = s0;
  panel.querySelector("#bell-def-end").value = s1;
  panel.querySelector("#bell-def-start").onchange = (e) => {
    state.bells.sound_defaults.start = e.target.value || null;
  };
  panel.querySelector("#bell-def-end").onchange = (e) => {
    state.bells.sound_defaults.end = e.target.value || null;
  };
  panel.querySelector("#bell-apply-starts").onclick = () => {
    const v = panel.querySelector("#bell-def-start").value;
    selectedBellTemplate().entries.forEach((e) => {
      if (v === "") delete e.sound_start;
      else e.sound_start = v;
    });
    renderBellEditor();
  };
  panel.querySelector("#bell-apply-ends").onclick = () => {
    const v = panel.querySelector("#bell-def-end").value;
    selectedBellTemplate().entries.forEach((e) => {
      if (v === "") delete e.sound_end;
      else e.sound_end = v;
    });
    renderBellEditor();
  };
  panel.querySelector("#bell-sound-upload").onchange = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    const response = await fetch("/api/admin/upload-bell-sound", mergeFetchOptions({ method: "POST", body: fd }));
    if (!response.ok) {
      alert((await response.json().catch(() => ({}))).detail || t("bells.uploadError"));
      return;
    }
    state.bellSoundFiles = (await api("/api/admin/bell-sounds")).files || [];
    renderBellEditor();
    event.target.value = "";
  };
}

function buildBellRows(entries = []) {
  elements.bellRows.innerHTML = "";
  entries.forEach((entry, index) => {
    const row = document.createElement("div");
    row.className = "bell-row";
    const lessonVal = escapeHtmlAttr(String(entry.lesson ?? ""));
    const ss = entry.sound_start || "";
    const se = entry.sound_end || "";
    const startVal = escapeHtmlAttr(String(entry.start ?? ""));
    const endVal = escapeHtmlAttr(String(entry.end ?? ""));
    row.innerHTML = `
      <label class="bell-field-lesson">${escapeHtml(t("bells.lessonField"))}<input class="standard-input bell-lesson-input" data-bell-index="${index}" data-key="lesson" type="text" autocomplete="off" value="${lessonVal}" placeholder="${escapeHtmlAttr(t("bells.lessonPlaceholder"))}"></label>
      <label>${escapeHtml(t("bells.soundStart"))}<select data-bell-index="${index}" data-key="sound_start" class="standard-input bell-sound-select">${bellSoundSelectOptions(ss)}</select></label>
      <label>${escapeHtml(t("bells.soundEnd"))}<select data-bell-index="${index}" data-key="sound_end" class="standard-input bell-sound-select">${bellSoundSelectOptions(se)}</select></label>
      <label>${escapeHtml(t("bells.timeStart"))}<input class="standard-input" data-bell-index="${index}" data-key="start" type="time" value="${startVal}"></label>
      <label>${escapeHtml(t("bells.timeEnd"))}<input class="standard-input" data-bell-index="${index}" data-key="end" type="time" value="${endVal}"></label>
      <button type="button" class="secondary-btn" data-remove-bell="${index}">${escapeHtml(t("bells.removeRow"))}</button>
    `;
    elements.bellRows.appendChild(row);
    row.querySelector('[data-key="sound_start"]').value = ss;
    row.querySelector('[data-key="sound_end"]').value = se;
  });
  const syncBellField = (event) => {
    const template = selectedBellTemplate();
    const idx = Number(event.target.dataset.bellIndex);
    const key = event.target.dataset.key;
    template.entries[idx][key] = event.target.value;
  };
  elements.bellRows.querySelectorAll("input").forEach((input) => {
    input.addEventListener("input", syncBellField);
    input.addEventListener("change", syncBellField);
  });
  elements.bellRows.querySelectorAll("select").forEach((sel) => {
    sel.onchange = (event) => {
      const template = selectedBellTemplate();
      const idx = Number(event.target.dataset.bellIndex);
      const key = event.target.dataset.key;
      const v = event.target.value;
      if (v === "") delete template.entries[idx][key];
      else template.entries[idx][key] = v;
    };
  });
  elements.bellRows.querySelectorAll("[data-remove-bell]").forEach((button) => {
    button.onclick = () => {
      selectedBellTemplate().entries.splice(Number(button.dataset.removeBell), 1);
      renderBellEditor();
    };
  });
}

function renderBellTemplateList() {
  elements.bellTemplateList.innerHTML = "";
  state.bells.templates.forEach((item) => {
    const div = document.createElement("div");
    div.className = "override-item";
    div.innerHTML = `<span>${tf("bells.templateEntries", { name: escapeHtmlAttr(item.name), n: item.entries.length })}</span>`;
    const button = document.createElement("button");
    button.textContent = t("bells.pickTemplate");
    button.className = "secondary-btn";
    button.onclick = () => {
      currentScreen().bell_schedule_template = item.id;
      deps.render();
    };
    div.appendChild(button);
    elements.bellTemplateList.appendChild(div);
  });
}

export function renderBellEditor() {
  const template = selectedBellTemplate();
  elements.bellTemplateName.value = template?.name || "";
  if (elements.bellLastLesson) {
    const ll = template?.last_lesson;
    elements.bellLastLesson.value = ll != null && ll !== "" ? String(ll) : "";
  }
  elements.bellDateOverride.value = "";
  renderWeekdayBellGrid();
  renderBellSoundPanel();
  buildBellRows(template.entries || []);
  renderBellTemplateList();
}

export function addBellTemplate() {
  const template = {
    id: deps.createTemplateId(),
    name: tf("bell.templateN", { n: state.bells.templates.length + 1 }),
    entries: [
      { lesson: "1", start: "08:30", end: "09:15" },
      { lesson: "2", start: "09:25", end: "10:10" },
    ],
  };
  state.bells.templates.push(template);
  currentScreen().bell_schedule_template = template.id;
  deps.render();
}

export function deleteBellTemplate() {
  if (state.bells.templates.length <= 1) {
    alert(t("alert.oneBellTemplate"));
    return;
  }
  const currentId = selectedBellTemplate().id;
  state.bells.templates = state.bells.templates.filter((item) => item.id !== currentId);
  Object.keys(state.bells.weekday_overrides).forEach((key) => {
    if (state.bells.weekday_overrides[key] === currentId) delete state.bells.weekday_overrides[key];
  });
  state.bells.date_overrides = state.bells.date_overrides.filter((item) => item.template_id !== currentId);
  const nextId = state.bells.templates[0].id;
  state.config.screens.forEach((screen) => {
    if (screen.bell_schedule_template === currentId) {
      screen.bell_schedule_template = nextId;
    }
    Object.keys(screen.weekday_bell_templates || {}).forEach((key) => {
      if (screen.weekday_bell_templates[key] === currentId) delete screen.weekday_bell_templates[key];
    });
  });
  deps.render();
}

export function addBellRow() {
  selectedBellTemplate().entries.push({
    lesson: String(selectedBellTemplate().entries.length + 1),
    start: "08:30",
    end: "09:15",
  });
  renderBellEditor();
}

export function flushBellEditorFromDom() {
  if (!elements.bellRows || !state.bells) return;
  const template = selectedBellTemplate();
  if (!template?.entries?.length) return;
  elements.bellRows.querySelectorAll("[data-bell-index][data-key]").forEach((el) => {
    const idx = Number(el.dataset.bellIndex);
    const key = el.dataset.key;
    if (!Number.isFinite(idx) || idx < 0 || idx >= template.entries.length) return;
    const v = el.value;
    if (key === "sound_start" || key === "sound_end") {
      if (v === "") delete template.entries[idx][key];
      else template.entries[idx][key] = v;
    } else {
      template.entries[idx][key] = v;
    }
  });
}

export function saveBellEditorToState() {
  flushBellEditorFromDom();
  const template = selectedBellTemplate();
  template.name = elements.bellTemplateName.value.trim() || template.name;
  if (elements.bellLastLesson) {
    const raw = elements.bellLastLesson.value.trim();
    if (raw === "") template.last_lesson = null;
    else {
      const n = Number(raw);
      template.last_lesson = Number.isFinite(n) ? Math.max(1, Math.min(24, Math.round(n))) : null;
    }
  }
  const dateOverride = elements.bellDateOverride.value;
  if (dateOverride) {
    state.bells.date_overrides = state.bells.date_overrides.filter((item) => item.date !== dateOverride);
    state.bells.date_overrides.push({ date: dateOverride, template_id: template.id, name: `${template.name} (${dateOverride})`, entries: template.entries.map((item) => ({ ...item })) });
  }
}
