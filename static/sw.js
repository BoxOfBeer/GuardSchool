// Minimal service worker for PWA install eligibility.
// Intentionally avoids custom caching logic to not break Smart TV/WebView.

self.addEventListener("install", (event) => {
  try {
    self.skipWaiting();
  } catch (_) {}
});

self.addEventListener("activate", (event) => {
  try {
    event.waitUntil(self.clients.claim());
  } catch (_) {}
});

// ВАЖНО: не добавляем fetch handler.
// Chrome предупреждает, что no-op fetch handler даёт overhead на навигации.
// Нам SW нужен для PWA eligibility + push, а не для проксирования fetch/caching.

function safeJsonParse(s) {
  try {
    return JSON.parse(String(s || ""));
  } catch (_) {
    return null;
  }
}

self.addEventListener("push", (event) => {
  event.waitUntil(
    (async () => {
      let rawText = "";
      try {
        rawText = event && event.data ? String(event.data.text() || "") : "";
      } catch (_) {
        rawText = "";
      }
      const data = rawText ? safeJsonParse(rawText) : null;
      const title = (data && data.title) || "GuardSchool";
      const body = (data && data.body) || "";
      const url = (data && data.url) || "/";
      const tag = (data && data.tag) || undefined;
      const receivedAt = new Date().toISOString();
      const dbg = {
        type: "gs-push-debug",
        receivedAt,
        title,
        body,
        url,
        tag: tag || "",
        rawLen: rawText.length,
        parseOk: Boolean(data),
      };
      try {
        console.log("[GuardSchool SW push]", receivedAt, title, body, "parseOk=", Boolean(data), "rawLen=", rawText.length);
      } catch (_) {}
      try {
        const clientsArr = await self.clients.matchAll({ type: "window", includeUncontrolled: false });
        for (let i = 0; i < (clientsArr || []).length; i++) {
          try {
            clientsArr[i].postMessage(dbg);
          } catch (_) {}
        }
      } catch (_) {}
      const opts = {
        body,
        tag,
        renotify: true,
        data: { url },
      };
      await self.registration.showNotification(title, opts);
    })()
  );
});

self.addEventListener("notificationclick", (event) => {
  try {
    event.notification && event.notification.close && event.notification.close();
  } catch (_) {}
  const url = (event && event.notification && event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientsArr) => {
      for (const c of clientsArr || []) {
        try {
          if (c && "focus" in c) {
            c.focus();
            if (url && "navigate" in c) c.navigate(url);
            return;
          }
        } catch (_) {}
      }
      try {
        return self.clients.openWindow(url);
      } catch (_) {
        return;
      }
    })
  );
});

