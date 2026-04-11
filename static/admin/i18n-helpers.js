export function t(key) {
  return window.GuardSchoolI18n ? window.GuardSchoolI18n.t(key) : key;
}

export function tf(key, vars) {
  return window.GuardSchoolI18n ? window.GuardSchoolI18n.tf(key, vars) : key;
}

export function getSectionTabs() {
  return [
    { id: "main", label: t("section.main") },
    { id: "schedule", label: t("section.schedule") },
    { id: "preview", label: t("section.preview") },
    { id: "history", label: t("section.changelog") },
  ];
}
