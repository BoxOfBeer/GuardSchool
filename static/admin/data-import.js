/**
 * Загрузка фона, Excel (расписание, праздники, объявления, бегущая строка),
 * экспорт/импорт ZIP недельного расписания, полный импорт ZIP GuardSchool.
 */
import { state } from "./state.js";
import { t, tf } from "./i18n-helpers.js";
import { api, downloadBinaryFile } from "./api-client.js";

let deps = {
  /** @returns {any} */
  selectedScreen: () => null,
  render: () => {},
};

/** Вызвать из app.js после объявления selectedScreen и render. */
export function setDataImportDeps(d) {
  deps = { ...deps, ...d };
}

export async function uploadBackground(file) {
  const formData = new FormData();
  formData.append("file", file);
  const payload = await api("/api/admin/upload-background", { method: "POST", body: formData });
  const sc = deps.selectedScreen();
  if (sc) sc.background_image = payload.path;
  deps.render();
}

export async function uploadScheduleDated(file) {
  const formData = new FormData();
  formData.append("file", file);
  const payload = await api("/api/admin/upload-schedule", { method: "POST", body: formData });
  const snapshot = await api("/api/admin/schedule");
  state.schedule = snapshot.schedule || [];
  state.fullScheduleRows = snapshot.full_schedule_rows;
  state.scheduleSampleRows = snapshot.schedule_sample_rows;
  state.history = snapshot.history || [];
  state.appVersion = snapshot.app_version || state.appVersion;
  alert(tf("alert.uploadDated", { n: payload.rows }));
  deps.render();
}

export async function uploadFullSchedule(file) {
  const formData = new FormData();
  formData.append("file", file);
  const payload = await api("/api/admin/upload-full-schedule", { method: "POST", body: formData });
  const snapshot = await api("/api/admin/schedule");
  state.schedule = snapshot.schedule || [];
  state.fullScheduleRows = snapshot.full_schedule_rows;
  state.scheduleSampleRows = snapshot.schedule_sample_rows;
  state.history = snapshot.history || [];
  state.appVersion = snapshot.app_version || state.appVersion;
  alert(tf("alert.uploadFull", { n: payload.rows }));
  deps.render();
}

export async function uploadScheduleSample(file) {
  const formData = new FormData();
  formData.append("file", file);
  const payload = await api("/api/admin/upload-schedule-sample", { method: "POST", body: formData });
  const snapshot = await api("/api/admin/schedule");
  state.schedule = snapshot.schedule || [];
  state.fullScheduleRows = snapshot.full_schedule_rows;
  state.scheduleSampleRows = snapshot.schedule_sample_rows;
  state.history = snapshot.history || [];
  state.appVersion = snapshot.app_version || state.appVersion;
  alert(tf("alert.uploadSample", { n: payload.rows }));
  deps.render();
}

export async function uploadHolidays(file) {
  const formData = new FormData();
  formData.append("file", file);
  const payload = await api("/api/admin/upload-holidays", { method: "POST", body: formData });
  const snapshot = await api("/api/admin/schedule");
  state.schedule = snapshot.schedule || [];
  state.overrides = snapshot.overrides || [];
  state.announcements = snapshot.announcements || [];
  alert(tf("alert.uploadHolidays", { n: payload.rows }));
  deps.render();
}

export async function uploadAnnouncements(file) {
  const formData = new FormData();
  formData.append("file", file);
  const payload = await api("/api/admin/upload-announcements", { method: "POST", body: formData });
  const snapshot = await api("/api/admin/schedule");
  state.announcements = snapshot.announcements || [];
  alert(tf("alert.uploadAnnounce", { n: payload.rows }));
  deps.render();
}

export async function uploadMarquee(file) {
  const formData = new FormData();
  formData.append("file", file);
  const payload = await api("/api/admin/upload-marquee", { method: "POST", body: formData });
  const snapshot = await api("/api/admin/schedule");
  state.marquee = snapshot.marquee || [];
  alert(tf("alert.uploadMarquee", { n: payload.rows }));
  deps.render();
}

export async function exportWeeklyScheduleZip() {
  const stamp = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, "");
  await downloadBinaryFile("/api/admin/export-weekly-schedule", `guardschool_weekly_schedule_${stamp}.zip`);
}

export async function importWeeklyScheduleZip(file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await api("/api/admin/import-weekly-schedule", { method: "POST", body: formData });
  const snapshot = await api("/api/admin/schedule");
  state.schedule = snapshot.schedule || [];
  state.fullScheduleRows = snapshot.full_schedule_rows;
  state.scheduleSampleRows = snapshot.schedule_sample_rows;
  state.history = snapshot.history || [];
  state.appVersion = snapshot.app_version || state.appVersion;
  alert(tf("alert.importWeek", { full: res.full_schedule_rows ?? "—", sample: res.schedule_sample_rows ?? "—" }));
  deps.render();
}

export async function downloadWeeklyScheduleTemplateXlsx() {
  await downloadBinaryFile("/api/admin/weekly-schedule-template.xlsx", "full_schedule_sample.xlsx");
}

export async function importBundle(file) {
  const formData = new FormData();
  formData.append("file", file);
  await api("/api/admin/import", { method: "POST", body: formData });
  alert(t("alert.importDone"));
  window.location.reload();
}
