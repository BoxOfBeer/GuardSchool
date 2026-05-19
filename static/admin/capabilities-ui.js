/**

 * Отключение UI по capabilities из state.meta.capabilities или /api/capabilities.

 */

import { t, tf } from "./i18n-helpers.js";



/** Порядок для обзора в настройках. */

const CAPABILITY_OVERVIEW_ORDER = [

  "local_widgets",

  "custom_widgets",

  "cloud_sync",

  "cloud_status",

  "mobile_external",

  "push_notifications",

  "tenant_feedback",

  "remote_tv_pairing",

  "license_check",

  "registration",

  "payment",

  "tenant_provisioning",

  "tariff_limits",

  "production_portal",

];



function capabilityLabel(id) {

  const key = `cap.${id}`;

  const tr = t(key);

  return tr !== key ? tr : id;

}



function capabilityStatusLabel(st) {

  const key = `capStatus.${st}`;

  const tr = t(key);

  return tr !== key ? tr : st;

}



/**

 * @param {string} capId

 * @param {Record<string, { status?: string, message?: string }>} capabilities

 */

export function capabilityStatus(capId, capabilities) {

  const c = capabilities && capabilities[capId];

  return String((c && c.status) || "missing");

}



export function isCapabilityAvailable(capId, capabilities) {

  return capabilityStatus(capId, capabilities) === "available";

}



export function capabilityMessage(capId, capabilities) {

  const c = capabilities && capabilities[capId];

  return String((c && c.message) || "");

}



function gateElement(el, status, message) {

  if (!el) return;

  const row = el.closest(".settings-row") || el.closest("label") || el;

  const blocked = status !== "available";

  el.disabled = blocked;

  if (blocked && el.type === "checkbox") {

    el.checked = false;

  }

  const tip = message || (blocked ? tf("cap.gateUnavailable", { status }) : "");

  if (row && row !== el) {

    row.title = tip;

    row.classList.toggle("capability-gated", blocked);

  } else {

    el.title = tip;

    el.classList.toggle("capability-gated", blocked);

  }

}



function gateSection(section, status, message) {

  if (!section) return;

  const blocked = status !== "available";

  section.querySelectorAll("input, select, textarea, button").forEach((el) => {

    if (el.id === "program-settings-open-btn") return;

    gateElement(el, status, message);

  });

  if (blocked) {

    section.classList.add("capability-section-gated");

    let banner = section.querySelector(".capability-section-banner");

    if (!banner) {

      banner = document.createElement("p");

      banner.className = "hint capability-section-banner";

      section.insertBefore(banner, section.firstChild?.nextSibling || null);

    }

    banner.textContent = message || t("cap.sectionUnavailable");

  } else {

    section.classList.remove("capability-section-gated");

    section.querySelector(".capability-section-banner")?.remove();

  }

}



/**

 * @param {Record<string, { status?: string, message?: string }>} capabilities

 * @param {{ cloudBaseUrl?: HTMLElement, cloudSyncInterval?: HTMLElement, cloudSyncEnabled?: HTMLElement, cloudSyncToken?: HTMLElement, syncNowBtn?: HTMLElement, screenFallbackBase?: HTMLElement, screenFallbackEnabled?: HTMLElement }} elements

 */

export function applyCapabilityGates(capabilities, elements = {}) {

  if (!capabilities || typeof capabilities !== "object") return;



  const cloudStatus = capabilityStatus("cloud_sync", capabilities);

  const cloudMsg = capabilityMessage("cloud_sync", capabilities);

  gateElement(elements.cloudBaseUrl, cloudStatus, cloudMsg);

  gateElement(elements.cloudSyncInterval, cloudStatus, cloudMsg);

  gateElement(elements.cloudSyncEnabled, cloudStatus, cloudMsg);

  gateElement(elements.cloudSyncToken, cloudStatus, cloudMsg);

  gateElement(elements.syncNowBtn, cloudStatus, cloudMsg);



  const cloudSection = document.getElementById("ps-cloud-head")?.closest(".program-settings-block");

  if (cloudStatus !== "available") {

    gateSection(cloudSection, cloudStatus, cloudMsg);

  } else if (cloudSection) {

    gateSection(cloudSection, "available", "");

  }



  const fbStatus = capabilityStatus("mobile_external", capabilities);

  const fbMsg = capabilityMessage("mobile_external", capabilities) || capabilityMessage("cloud_sync", capabilities);

  gateElement(elements.screenFallbackBase, fbStatus, fbMsg);

  gateElement(elements.screenFallbackEnabled, fbStatus, fbMsg);

}



/**

 * Таблица статусов capabilities (настройки → «Функции сборки»).

 * @param {Record<string, { status?: string, message?: string, module_hint?: string }>} capabilities

 * @param {HTMLElement | null} container

 */

export function renderCapabilitiesOverview(capabilities, container) {

  if (!container) return;

  if (!capabilities || typeof capabilities !== "object") {

    container.innerHTML = `<p class="hint">${escapeHtml(t("cap.noData"))}</p>`;

    return;

  }

  const ids = [

    ...CAPABILITY_OVERVIEW_ORDER.filter((id) => id in capabilities),

    ...Object.keys(capabilities).filter((id) => !CAPABILITY_OVERVIEW_ORDER.includes(id)).sort(),

  ];

  const rows = ids.map((id) => {

    const st = capabilityStatus(id, capabilities);

    const label = capabilityLabel(id);

    const stLabel = capabilityStatusLabel(st);

    const msg = capabilityMessage(id, capabilities);

    const hint = capabilities[id] && capabilities[id].module_hint ? String(capabilities[id].module_hint) : "";

    const title = [msg, hint ? tf("cap.layerHint", { hint }) : ""].filter(Boolean).join(" — ");

    return `<tr class="cap-overview-row cap-overview-row--${st}">

      <td class="cap-overview-name" title="${escapeHtmlAttr(title)}">${escapeHtml(label)}</td>

      <td class="cap-overview-status"><span class="cap-status-badge cap-status-badge--${st}">${escapeHtml(stLabel)}</span></td>

    </tr>`;

  });

  container.innerHTML = `<table class="cap-overview-table"><tbody>${rows.join("")}</tbody></table>`;

}



/**

 * Предупреждения о виджетах с ошибкой загрузки (из meta.widget_registry).

 * @param {{ widgets?: Array<{ type?: string, status?: string, status_message?: string }> }} registry

 * @param {HTMLElement | null} container

 */

export function renderWidgetRegistryIssues(registry, container) {

  if (!container) return;

  const widgets = Array.isArray(registry && registry.widgets) ? registry.widgets : [];

  const bad = widgets.filter((w) => w && (w.status === "error" || w.status === "missing"));

  if (!bad.length) {

    container.hidden = true;

    container.innerHTML = "";

    return;

  }

  container.hidden = false;

  const items = bad

    .map((w) => {

      const typ = String(w.type || "?");

      const st =

        w.status === "error" ? t("cap.widgetStatusError") : t("cap.widgetStatusMissing");

      const msg = String(w.status_message || "").trim();

      return `<li><strong>${escapeHtml(typ)}</strong> — ${escapeHtml(st)}${msg ? `: ${escapeHtml(msg)}` : ""}</li>`;

    })

    .join("");

  container.innerHTML = `<p class="hint widget-registry-issues-title">${escapeHtml(t("cap.widgetIssuesTitle"))}</p><ul class="widget-registry-issues-list">${items}</ul>`;

}



function escapeHtml(s) {

  return String(s)

    .replace(/&/g, "&amp;")

    .replace(/</g, "&lt;")

    .replace(/>/g, "&gt;")

    .replace(/"/g, "&quot;");

}



function escapeHtmlAttr(s) {

  return escapeHtml(s).replace(/'/g, "&#39;");

}


