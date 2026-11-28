/* Service Worker — Galerie Médias.
 * Le shell (HTML, CSS, JS) passe d’abord par le réseau.
 * Les requêtes /api/*, /thumb/* et /photo/* ne sont pas mises en cache.
 */

const CACHE = "galerie-v82";
const SHELL = [
  "/",
  "/static/styles.css",
  "/static/i18n.js",
  "/static/app.js",
  "/static/help/fr.html",
  "/static/help/en.html",
  "/static/help/es.html",
  "/static/help/de.html",
  "/static/install/fr.html",
  "/static/install/en.html",
  "/static/install/es.html",
  "/static/install/de.html",
  "/static/favicon.svg",
  "/static/apple-touch-icon.png",
  "/manifest.json",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const { url, method } = e.request;
  if (method !== "GET") return;

  // API, miniatures et photos : pas de cache.
  const { pathname } = new URL(url);
  if (
    pathname.startsWith("/api/") ||
    pathname.startsWith("/thumb/") ||
    pathname.startsWith("/photo/")
  ) {
    return;
  }

  // Shell : le réseau d’abord, pour qu’un rechargement voie le nouveau JS.
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        if (res && res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => {});
        }
        return res;
      })
      .catch(() => caches.match(e.request))
  );
});
