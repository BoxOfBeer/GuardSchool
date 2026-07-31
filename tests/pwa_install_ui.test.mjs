import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const source = fs.readFileSync(new URL("../static/screen.js", import.meta.url), "utf8");
const tokenHelperStart = source.indexOf("function gsPersistTvBearerAndScrubAddress(");
const tokenHelperEnd = source.indexOf("/** Параметры гибрида:", tokenHelperStart);
assert.ok(tokenHelperStart >= 0 && tokenHelperEnd > tokenHelperStart, "TV token scrub helper not found");
const tokenHelper = source.slice(tokenHelperStart, tokenHelperEnd);
const helpersStart = source.indexOf("function gsPwaIsStandalone()");
const helpersEnd = source.indexOf("/** Панель ⚙:", helpersStart);
assert.ok(helpersStart >= 0 && helpersEnd > helpersStart, "PWA install helpers not found");
const helpers = source.slice(helpersStart, helpersEnd);

async function makeContext({
  userAgent,
  platform = "",
  standalone = false,
  secure = true,
  code = "",
  token = "",
}) {
  const elements = {
    "gs-device-pwa-install-row": { hidden: true },
    "gs-device-pwa-install-status": { dataset: {}, hidden: true, textContent: "" },
  };
  const context = {
    URL,
    console,
    location: { origin: "https://school.example", hostname: "school.example" },
    navigator: null,
    document: {
      getElementById: (id) => elements[id] || null,
      querySelector: () => ({ href: "https://school.example/pwa/screen/test.webmanifest" }),
    },
    fetch: async () => ({
      json: async () => ({ name: "GuardSchool", short_name: "GuardSchool" }),
    }),
    getSlug: () => "test",
    gsPwaTvCodeForPage: () => code,
    getGsTvBearer: () => token,
    gsBuildTvPairPageUrl: (slug, pairCode, pairToken, withPwa) => {
      const query = [];
      if (pairToken) query.push(`gs_tv_token=${encodeURIComponent(pairToken)}`);
      if (withPwa) query.push("pwa=1");
      return `/t/${pairCode}/${slug}${query.length ? `?${query.join("&")}` : ""}`;
    },
  };
  context.window = {
    isSecureContext: secure,
    matchMedia: () => ({ matches: standalone }),
    navigator: {
      userAgent,
      platform,
      maxTouchPoints: 0,
      standalone: false,
    },
  };
  context.navigator = context.window.navigator;
  vm.runInNewContext(helpers, context);
  context.elements = elements;
  return context;
}

const iphoneSafari = await makeContext({
  userAgent:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1",
  platform: "iPhone",
});
assert.match(await iphoneSafari.gsPwaInstallFallbackMessage(), /Поделиться.*На экран Домой/);

const firefoxAndroid = await makeContext({
  userAgent: "Mozilla/5.0 (Android 15; Mobile; rv:143.0) Gecko/143.0 Firefox/143.0",
  platform: "Linux armv8l",
});
assert.match(await firefoxAndroid.gsPwaInstallFallbackMessage(), /меню Firefox.*Установить/);

const firefoxWindows = await makeContext({
  userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0) Gecko/20100101 Firefox/143.0",
  platform: "Win32",
});
assert.match(await firefoxWindows.gsPwaInstallFallbackMessage(), /значок веб-приложения.*адресной строке Firefox/);

const safariMac = await makeContext({
  userAgent:
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15",
  platform: "MacIntel",
});
assert.match(await safariMac.gsPwaInstallFallbackMessage(), /Safari.*Добавить в Dock/);

const yandexWindows = await makeContext({
  userAgent:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0.0.0 YaBrowser/24.10.0.0 Safari/537.36",
  platform: "Win32",
});
assert.match(await yandexWindows.gsPwaInstallFallbackMessage(), /Умной строке Яндекс Браузера.*Установить как приложение/);

const insecureChrome = await makeContext({
  userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36",
  platform: "Win32",
  secure: false,
});
assert.match(await insecureChrome.gsPwaInstallFallbackMessage(), /нужен HTTPS/);

const installed = await makeContext({
  userAgent: "Mozilla/5.0 Chrome/128.0.0.0 Safari/537.36",
  platform: "Win32",
  standalone: true,
});
assert.equal(installed.gsPwaIsStandalone(), true);
assert.equal(installed.gsPwaCanOfferInstall(), false);
installed.gsSyncPwaInstallRow();
assert.equal(installed.elements["gs-device-pwa-install-row"].hidden, true);

const browserMode = await makeContext({
  userAgent: "Mozilla/5.0 Chrome/128.0.0.0 Safari/537.36",
  platform: "Win32",
});
browserMode.gsSyncPwaInstallRow();
assert.equal(browserMode.elements["gs-device-pwa-install-row"].hidden, false);
browserMode.gsSetPwaInstallStatus("Тихая подсказка");
assert.equal(browserMode.elements["gs-device-pwa-install-status"].textContent, "Тихая подсказка");
assert.equal(browserMode.elements["gs-device-pwa-install-status"].hidden, false);

const pairedScreen = await makeContext({
  userAgent: "Mozilla/5.0 Chrome/128.0.0.0 Safari/537.36",
  platform: "Win32",
  code: "school-code",
  token: "SECRET_BEARER_TOKEN",
});
const pairedMessage = await pairedScreen.gsPwaInstallFallbackMessage();
assert.match(pairedMessage, /\/t\/school-code\/test\?pwa=1/);
assert.ok(!pairedMessage.includes("SECRET_BEARER_TOKEN"), "Visible install guidance must not expose bearer tokens");
assert.ok(!pairedMessage.includes("gs_tv_token"), "Visible install guidance must not expose token parameters");

const tokenStorage = new Map();
let replacedUrl = "";
const tokenContext = {
  sanitizeGsTvBearerToken: (value) => String(value || ""),
  gsScopedKey: (suffix) => `gs_${suffix}__school.example`,
  getSlug: () => "test",
  gsTvPairCodeFromCurrentPath: () => "abcd-efgh-ijkl",
  localStorage: {
    setItem: (key, value) => tokenStorage.set(key, value),
  },
  window: {
    location: {
      hash: "#section",
      pathname: "/t/abcd-efgh-ijkl/test",
    },
    history: {
      replaceState: (_state, _title, url) => {
        replacedUrl = url;
      },
    },
  },
};
vm.runInNewContext(tokenHelper, tokenContext);
const tokenQuery = new URLSearchParams("gs_tv_token=SECRET_BEARER_TOKEN&gs_menu=1");
assert.equal(tokenContext.gsPersistTvBearerAndScrubAddress("SECRET_BEARER_TOKEN", tokenQuery), true);
assert.equal(tokenStorage.get("gs_tv_bearer__school.example"), "SECRET_BEARER_TOKEN");
assert.equal(tokenStorage.get("gs_pwa_tv_token__abcd-efgh-ijkl__test"), "SECRET_BEARER_TOKEN");
assert.equal(replacedUrl, "/t/abcd-efgh-ijkl/test?gs_menu=1&pwa=1#section");
assert.ok(!replacedUrl.includes("SECRET_BEARER_TOKEN"));
assert.ok(!replacedUrl.includes("gs_tv_token"));

const installUxStart = source.indexOf("// PWA install UX:");
const installUxEnd = source.indexOf("// Push UI.", installUxStart);
assert.ok(installUxStart >= 0 && installUxEnd > installUxStart, "PWA install UI block not found");
const installUx = source.slice(installUxStart, installUxEnd);
assert.ok(!installUx.includes("alert("), "PWA install UI must not use alert dialogs");
assert.match(installUx, /gsSetPwaInstallStatus/);
assert.match(source, /if \(bearer && !code\) qParts\.push\(`gs_tv_token=/);
assert.match(source, /gs_pwa_tv_token__\$\{code\}__\$\{slug\}/);

console.log("PWA install UI checks passed");
