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

// Pass-through fetch handler (no caching).
self.addEventListener("fetch", (event) => {
  // No-op: default network behavior.
});

function safeJsonParse(s) {
  try {
    return JSON.parse(String(s || ""));
  } catch (_) {
    return null;
  }
}

self.addEventListener("push", (event) => {
  try {
    const data = event && event.data ? safeJsonParse(event.data.text()) : null;
    const title = (data && data.title) || "GuardSchool";
    const body = (data && data.body) || "";
    const url = (data && data.url) || "/";
    const tag = (data && data.tag) || undefined;
    const opts = {
      body,
      tag,
      renotify: true,
      data: { url },
    };
    event.waitUntil(self.registration.showNotification(title, opts));
  } catch (_) {}
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

