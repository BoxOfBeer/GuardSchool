/**
 * Блок «История изменений» в админке.
 */
import { state, elements } from "./state.js";
import { t } from "./i18n-helpers.js";
import { escapeHtmlAttr } from "./escape-html.js";

export function renderHistory() {
  const loc = window.GuardSchoolI18n?.getLang?.() === "en" ? "en-US" : "ru-RU";
  const verHint = state.appVersion
    ? `<p class="hint history-app-ver">${t("history.currentVersion")} <strong>${escapeHtmlAttr(state.appVersion)}</strong></p>`
    : "";
  if (!state.history.length) {
    elements.historyList.innerHTML = `${verHint}<div class="hint">${t("history.empty")}</div>`;
    return;
  }
  elements.historyList.innerHTML =
    verHint +
    state.history
      .map((item) => {
        const rawTs = item.timestamp;
        let ts = "—";
        if (rawTs) {
          const d = new Date(rawTs);
          ts = Number.isNaN(d.getTime()) ? String(rawTs) : d.toLocaleString(loc);
        }
        const ver = item.version ? String(item.version).trim() : "";
        const verBlock = ver
          ? `<span class="history-ver" title="${escapeHtmlAttr(t("history.versionLabel"))}">${escapeHtmlAttr(ver)}</span>`
          : `<span class="history-ver history-ver-na">${escapeHtmlAttr(t("history.noVersion"))}</span>`;
        return `
    <div class="history-item">
      <div class="history-meta">${verBlock}<span class="history-time">${escapeHtmlAttr(ts)}</span></div>
      <div class="history-msg">${escapeHtmlAttr(String(item.message || ""))}</div>
    </div>`;
      })
      .join("");
}
