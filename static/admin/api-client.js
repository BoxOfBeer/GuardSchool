import { state } from "./state.js";
import { t } from "./i18n-helpers.js";

export function apiDetailMessage(payload) {
  const d = payload && payload.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    return d
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .join("; ");
  }
  if (d != null) return String(d);
  return null;
}

export function currentUiLocale() {
  try {
    const v = state.config && state.config.ui_locale;
    if (v === "en") return "en";
    if (v === "ru") return "ru";
  } catch (_) {}
  try {
    if (document.documentElement.lang === "en") return "en";
  } catch (_) {}
  return "ru";
}

export function mergeFetchOptions(options = {}) {
  const merged = { credentials: "same-origin", ...options };
  const h = new Headers(merged.headers || {});
  if (!h.has("X-UI-Locale")) h.set("X-UI-Locale", currentUiLocale());
  merged.headers = h;
  return merged;
}

export async function api(url, options = {}) {
  const response = await fetch(url, mergeFetchOptions(options));
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    if (response.status === 401) {
      window.location.href = "/login";
      throw new Error(t("alert.session"));
    }
    throw new Error(apiDetailMessage(payload) || t("api.error"));
  }
  return response.json();
}

export async function downloadFile(url, filenamePrefix) {
  await downloadBinaryFile(url, `${filenamePrefix}.zip`);
}

export async function downloadBinaryFile(url, downloadName) {
  const response = await fetch(url, mergeFetchOptions());
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || t("api.downloadError"));
  }
  const blob = await response.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = downloadName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}
