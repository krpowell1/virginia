// Defense Case Manager - Service Worker v1
// Strategy: cache app shell, network-first for dynamic content, offline fallback.

const CACHE_NAME = "dcm-v1";

// App shell resources to pre-cache on install.
const APP_SHELL = [
  "/",
  "/accounts/login/",
  "https://cdn.tailwindcss.com",
  "https://unpkg.com/htmx.org@2.0.4",
  "https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js",
];

// Offline fallback HTML (self-contained, no external deps).
const OFFLINE_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Offline - DCM</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',Helvetica,Arial,sans-serif;
background:#f8fafc;display:flex;align-items:center;justify-content:center;min-height:100vh;
color:#334155;padding:1rem}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:1rem;padding:2.5rem;
max-width:20rem;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.06)}
h1{font-size:1.125rem;font-weight:600;margin-bottom:.5rem}
p{font-size:.875rem;color:#64748b;line-height:1.5}
.dot{width:3rem;height:3rem;border-radius:50%;background:#e2e8f0;margin:0 auto 1.25rem;
display:flex;align-items:center;justify-content:center}
.dot svg{width:1.25rem;height:1.25rem;color:#94a3b8}
button{margin-top:1.25rem;background:#1e293b;color:#fff;border:none;border-radius:.5rem;
padding:.625rem 1.25rem;font-size:.875rem;font-weight:500;cursor:pointer}
</style>
</head>
<body>
<div class="card">
<div class="dot">
<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
d="M18.364 5.636a9 9 0 11-12.728 0M12 9v4m0 4h.01"/>
</svg>
</div>
<h1>You're offline</h1>
<p>Connect to the internet to view your cases and deadlines.</p>
<button onclick="location.reload()">Try again</button>
</div>
</body>
</html>`;

// Install: pre-cache the app shell.
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      // Store the offline fallback page directly.
      cache.put(
        new Request("/_offline"),
        new Response(OFFLINE_HTML, {
          headers: { "Content-Type": "text/html; charset=utf-8" },
        })
      );
      // Attempt to cache app shell resources (best-effort for CDN).
      return Promise.allSettled(
        APP_SHELL.map((url) =>
          cache.add(url).catch(() => {
            // CDN resources may fail in dev — skip silently.
          })
        )
      );
    })
  );
  self.skipWaiting();
});

// Activate: clean old caches.
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// Fetch: network-first for navigations and API, cache-first for static assets.
self.addEventListener("fetch", (event) => {
  const { request } = event;

  // Only handle GET requests.
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // Static assets and CDN: cache-first.
  if (
    url.pathname.startsWith("/static/") ||
    url.hostname === "cdn.tailwindcss.com" ||
    url.hostname === "unpkg.com" ||
    url.hostname === "cdn.jsdelivr.net"
  ) {
    event.respondWith(
      caches.match(request).then(
        (cached) =>
          cached ||
          fetch(request).then((response) => {
            if (response.ok) {
              const clone = response.clone();
              caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
            }
            return response;
          })
      )
    );
    return;
  }

  // HTML navigations: network-first with offline fallback.
  if (request.mode === "navigate" || request.headers.get("Accept")?.includes("text/html")) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Cache successful page responses for offline access.
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() =>
          // Network failed: try cache, then offline fallback.
          caches.match(request).then((cached) => cached || caches.match("/_offline"))
        )
    );
    return;
  }

  // Everything else (API calls, etc): network-first, cache fallback.
  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return response;
      })
      .catch(() => caches.match(request))
  );
});
