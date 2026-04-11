import { state, elements } from "./state.js";

const ADMIN_TIMEZONE_GROUPS = [
  { label: "UTC", zones: ["UTC"] },
  {
    label: "Europe",
    zones: [
      "Europe/Moscow",
      "Europe/Kaliningrad",
      "Europe/Samara",
      "Europe/Kyiv",
      "Europe/Minsk",
      "Europe/Warsaw",
      "Europe/Berlin",
      "Europe/London",
    ],
  },
  {
    label: "Asia",
    zones: [
      "Asia/Yekaterinburg",
      "Asia/Omsk",
      "Asia/Novosibirsk",
      "Asia/Krasnoyarsk",
      "Asia/Irkutsk",
      "Asia/Yakutsk",
      "Asia/Vladivostok",
      "Asia/Magadan",
      "Asia/Kamchatka",
      "Asia/Almaty",
      "Asia/Tashkent",
      "Asia/Tbilisi",
      "Asia/Yerevan",
      "Asia/Baku",
      "Asia/Dubai",
    ],
  },
  {
    label: "America",
    zones: ["America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles"],
  },
];

function timezoneOptionLabel(tzId) {
  try {
    const d = new Date();
    const parts = new Intl.DateTimeFormat("en-US", { timeZone: tzId, timeZoneName: "longOffset" }).formatToParts(d);
    let off = parts.find((p) => p.type === "timeZoneName")?.value || "";
    off = off.replace("GMT", "UTC").replace(/\u2212/g, "-");
    return `${tzId} (${off})`;
  } catch (_) {
    return tzId;
  }
}

export function populateAdminTimezoneSelect() {
  const sel = elements.adminTimezone;
  if (!sel || !state.config) return;
  const current = String(state.config.timezone || "Europe/Moscow").trim();
  const flat = ADMIN_TIMEZONE_GROUPS.flatMap((g) => g.zones);
  sel.innerHTML = "";
  ADMIN_TIMEZONE_GROUPS.forEach((g) => {
    const og = document.createElement("optgroup");
    og.label = g.label;
    g.zones.forEach((z) => {
      const opt = document.createElement("option");
      opt.value = z;
      opt.textContent = timezoneOptionLabel(z);
      og.appendChild(opt);
    });
    sel.appendChild(og);
  });
  if (!flat.includes(current)) {
    const opt = document.createElement("option");
    opt.value = current;
    opt.textContent = timezoneOptionLabel(current);
    sel.appendChild(opt);
  }
  sel.value = current;
}
