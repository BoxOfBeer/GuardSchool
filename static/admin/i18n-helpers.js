export function t(key) {
  return window.GuardSchoolI18n ? window.GuardSchoolI18n.t(key) : key;
}

export function tf(key, vars) {
  return window.GuardSchoolI18n ? window.GuardSchoolI18n.tf(key, vars) : key;
}

export function getSectionTabs() {
  return [
    { id: "screen", label: t("section.screen") },
    { id: "widgets", label: t("section.widgets") },
    { id: "lessons", label: t("section.lessons") },
    { id: "bells", label: t("section.bells") },
    { id: "preview", label: t("section.preview") },
  ];
}
