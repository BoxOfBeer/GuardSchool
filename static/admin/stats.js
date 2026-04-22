/**
 * Вкладка «Статистика»: опросы ТВ и подключённые клиенты (GET /api/admin/screen-watch).
 */
import { api, currentUiLocale } from "./api-client.js";
import { t, tf } from "./i18n-helpers.js";
import { escapeHtml, escapeHtmlAttr } from "./escape-html.js";

let statsInterval = null;

/** Примерная длительность «на связи» с начала сессии опросов. */
function formatApproxConnected(sec) {
  const raw = Math.max(0, Number(sec) || 0);
  const en = currentUiLocale() === "en";
  if (raw >= 3600) {
    const h = Math.floor(raw / 3600);
    const m = Math.floor((raw % 3600) / 60);
    return en ? `~${h} h ${m} min` : `~${h} ч ${m} мин`;
  }
  if (raw >= 60) {
    const m = Math.floor(raw / 60);
    return en ? `~${m} min` : `~${m} мин`;
  }
  if (raw <= 0) return en ? "~0 s" : "~0 с";
  if (raw < 1) return en ? "<1 s" : "<1 с";
  if (raw < 60) {
    const dec = raw < 10 ? raw.toFixed(1) : String(Math.round(raw));
    return en ? `~${dec} s` : `~${dec} с`;
  }
  return en ? "~0 s" : "~0 с";
}


/** Иконка (знак) + цветная точка; подсказка для экрана «на связи / давно молчит / ещё не открывали». */
function statusIndicator(status) {
  const st = status === "ok" ? "ok" : status === "stale" ? "stale" : "never";
  const glyph = st === "ok" ? "\u2713" : st === "stale" ? "\u26a0" : "\u25cb";
  const title =
    st === "ok" ? t("stats.statusOk") : st === "stale" ? t("stats.statusStale") : t("stats.statusNever");
  return (
    `<span class="stats-status-wrap stats-status--${st}" title="${escapeHtmlAttr(title)}">` +
    `<span class="stats-status-glyph" aria-hidden="true">${glyph}</span>` +
    `<span class="stats-led stats-led--${st}" role="presentation"></span>` +
    `</span>`
  );
}

/** Подсветка «последний опрос»: зелёный &lt;30 с, жёлтый 30 с–2 мин, красный &gt;2 мин. */
function lastPollCell(secAgo) {
  if (secAgo == null || !Number.isFinite(Number(secAgo))) {
    return `<span class="stats-ago-pill stats-ago--na" title="${escapeHtmlAttr(t("stats.agoNaTitle"))}">—</span>`;
  }
  const n = Number(secAgo);
  let level = "fresh";
  if (n > 120) level = "bad";
  else if (n >= 30) level = "warn";
  const label = `${String(secAgo)} ${t("stats.secShort")}`;
  const title =
    level === "fresh"
      ? t("stats.agoFreshTitle")
      : level === "warn"
        ? t("stats.agoWarnTitle")
        : t("stats.agoBadTitle");
  return `<span class="stats-ago-pill stats-ago--${level}" title="${escapeHtmlAttr(title)}">${escapeHtml(label)}</span>`;
}

function renderWatch(data, root) {
  const screens = Array.isArray(data.screens) ? data.screens : [];
  const online = screens.filter((s) => s.status === "ok").length;
  const total = screens.length;
  const devicesTotal = screens.reduce((acc, s) => acc + (Array.isArray(s.clients) ? s.clients.length : 0), 0);
  const summaryHtml =
    `<div class="stats-summary-bar" role="status">` +
    `<p class="stats-summary-main">${tf("stats.onlineScreens", { online, total })}</p>` +
    `<p class="stats-summary-sub hint">${tf("stats.devicesOnline", { n: devicesTotal })}</p>` +
    `<p class="hint stats-ago-legend">${escapeHtml(t("stats.agoLegendShort"))}</p>` +
    `</div>`;

  const rows = screens
    .map((sc) => {
      const ago = lastPollCell(sc.last_seen_sec_ago);
      const pollVal = sc.poll_interval_sec ?? "";
      const pollCell =
        pollVal === "" || pollVal == null
          ? "—"
          : `${escapeHtml(String(pollVal))}\u00a0${escapeHtml(t("stats.secShort"))}`;
      const clients = Array.isArray(sc.clients) ? sc.clients : [];
      const sub =
        clients.length === 0
          ? `<p class="hint stats-clients-empty">${escapeHtml(t("stats.noClients"))}</p>`
          : `<ul class="stats-client-list">${clients
              .map((c) => {
                const dev = (c.device || "").trim();
                const devHtml = dev
                  ? `<span class="stats-client-device">${escapeHtml(dev)}</span>`
                  : `<span class="stats-client-device stats-client-device--na">${escapeHtml(t("stats.deviceUnknown"))}</span>`;
                const shortId = escapeHtml(String(c.client_id_short || c.client_id || ""));
                const dur = formatApproxConnected(c.connected_sec);
                return (
                  `<li><span class="stats-client-line">` +
                  `${devHtml}` +
                  ` · ${escapeHtml(c.ip || "—")}` +
                  ` · <span class="stats-connected-dur">${escapeHtml(dur)}</span>` +
                  `</span>` +
                  (c.label ? ` <span class="stats-client-label">(${escapeHtml(c.label)})</span>` : "") +
                  ` <span class="stats-client-id" title="${escapeHtml(String(c.client_id || ""))}">${shortId}</span></li>`
                );
              })
              .join("")}</ul>`;
      return (
        `<tr><td class="stats-status-cell">${statusIndicator(sc.status)}</td>` +
        `<td><strong>${escapeHtml(String(sc.name || ""))}</strong><div class="stats-slug">${escapeHtml(String(sc.slug || ""))}</div></td>` +
        `<td>${escapeHtml(String(sc.ip_note || "—"))}</td>` +
        `<td>${pollCell}</td>` +
        `<td>${ago}</td></tr>` +
        `<tr class="stats-subrow"><td colspan="5">${sub}</td></tr>`
      );
    })
    .join("");

  const log = Array.isArray(data.connection_log) ? data.connection_log : [];
  const logHtml =
    log.length === 0
      ? `<p class="hint stats-history-empty">${escapeHtml(t("stats.historyEmpty"))}</p>`
      : `<ol class="stats-history-list">${log
          .map((e) => {
            const dev = (e.device || "").trim();
            const devPart = dev
              ? escapeHtml(dev)
              : escapeHtml(t("stats.deviceUnknown"));
            const lab = e.label ? ` · (${escapeHtml(e.label)})` : "";
            const dur = formatApproxConnected(e.connected_sec);
            return (
              `<li><span class="stats-connected-dur">${escapeHtml(dur)}</span>` +
              ` — <strong>${escapeHtml(String(e.screen_name || e.slug || ""))}</strong>` +
              ` <span class="stats-history-slug">(${escapeHtml(String(e.slug || ""))})</span>` +
              ` · ${devPart}` +
              ` · ${escapeHtml(e.ip || "—")}${lab}` +
              ` · <span class="stats-history-cid" title="${escapeHtml(String(e.client_id || ""))}">${escapeHtml(String(e.client_id_short || ""))}</span></li>`
            );
          })
          .join("")}</ol>`;

  root.innerHTML =
    `${summaryHtml}` +
    `<table class="stats-table"><thead><tr>` +
    `<th></th><th>${escapeHtml(t("stats.colScreen"))}</th>` +
    `<th>${escapeHtml(t("stats.colNote"))}</th>` +
    `<th>${escapeHtml(t("stats.colPoll"))}</th>` +
    `<th>${escapeHtml(t("stats.colAgo"))}</th>` +
    `</tr></thead><tbody>${rows}</tbody></table>` +
    `<div class="stats-history-wrap">` +
    `<h3 class="stats-history-title">${escapeHtml(t("stats.historyTitle"))}</h3>` +
    `<p class="hint stats-history-lead">${escapeHtml(t("stats.historyLead"))}</p>` +
    `${logHtml}</div>`;
}

function renderFeedback(items, root) {
  const rows = Array.isArray(items) ? items : [];
  if (!rows.length) {
    root.innerHTML = `<p class="hint">Пока нет сообщений.</p>`;
    return;
  }
  root.innerHTML = `<div class="stats-feedback-list">${
    rows
      .map(
        (it) => `<div class="stats-feedback-item" data-feedback-id="${Number(it.id)}" data-feedback-hash="${escapeHtmlAttr(String(it.device_hash || ""))}">
          <div><strong>${escapeHtml(String(it.created_at || ""))}</strong> · <code>${escapeHtml(String(it.device_hash || ""))}</code></div>
          <div style="white-space:pre-wrap">${escapeHtml(String(it.message || ""))}</div>
          <div class="stats-feedback-actions">
            <button type="button" class="secondary-btn compact-btn" data-fb-act="read">Отметить прочитанным</button>
            <button type="button" class="secondary-btn compact-btn" data-fb-act="hide">Скрыть</button>
            <button type="button" class="danger-btn compact-btn" data-fb-act="block">Заблокировать hash</button>
          </div>
        </div>`,
      )
      .join("")
  }</div>`;
}

async function fetchAndRender() {
  const root = document.getElementById("stats-panel-body");
  if (!root) return;
  try {
    const data = await api("/api/admin/screen-watch");
    renderWatch(data, root);
  } catch (e) {
    root.innerHTML = `<p class="hint">${escapeHtml(String(e.message || e))}</p>`;
  }
}

export async function refreshFeedbackAdminPanel() {
  const feedbackRoot = document.getElementById("feedback-admin-body");
  if (!feedbackRoot) return;
  try {
    const feedback = await api("/api/admin/feedback");
    renderFeedback(feedback.items || [], feedbackRoot);
  } catch (e) {
    feedbackRoot.innerHTML = `<p class="hint">${escapeHtml(String(e.message || e))}</p>`;
  }
}

export function bindFeedbackAdminPanelOnce() {
  const feedbackRoot = document.getElementById("feedback-admin-body");
  if (!feedbackRoot || feedbackRoot.dataset.feedbackBound) return;
  feedbackRoot.dataset.feedbackBound = "1";
  feedbackRoot.addEventListener("click", async (ev) => {
    const btn = ev.target && ev.target.closest ? ev.target.closest("[data-fb-act]") : null;
    if (!btn) return;
    const item = btn.closest("[data-feedback-id]");
    if (!item) return;
    const id = Number(item.getAttribute("data-feedback-id"));
    const hash = String(item.getAttribute("data-feedback-hash") || "");
    const act = String(btn.getAttribute("data-fb-act") || "");
    try {
      if (act === "read") await api(`/api/admin/feedback/${id}/read`, { method: "POST" });
      else if (act === "hide") await api(`/api/admin/feedback/${id}/hide`, { method: "POST" });
      else if (act === "block") await api("/api/admin/feedback/block-hash", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ device_hash: hash }) });
      await refreshFeedbackAdminPanel();
    } catch (e) {
      window.alert(String(e.message || e));
    }
  });
}

export function enterStatsPanel() {
  if (statsInterval) window.clearInterval(statsInterval);
  fetchAndRender();
  statsInterval = window.setInterval(fetchAndRender, 3000);
}

export function leaveStatsPanel() {
  if (statsInterval) {
    window.clearInterval(statsInterval);
    statsInterval = null;
  }
}
