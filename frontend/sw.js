// =========================================================================
// sw.js · "Service worker": un pequeño programa que el navegador deja
// corriendo aparte de la página. Es lo que permite INSTALAR la app en el
// celular (junto con manifest.webmanifest) y que abra aunque no haya señal.
//
// Estrategia "primero la red": siempre pedimos la versión nueva al servidor
// (así nunca te quedás con una app vieja después de un cambio) y guardamos
// una copia. Si no hay internet, usamos la copia.
// Los datos de la API (/api/...) NUNCA se guardan: son tus finanzas.
// =========================================================================

const CACHE = "vaultbase-v2";
const OFFLINE_PAGES = ["/", "/dashboard.html", "/offline.html"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(OFFLINE_PAGES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  // Borramos copias de versiones viejas del service worker
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  // Solo GET de nuestro propio sitio, y nunca la API
  if (req.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;

  // "no-cache": preguntamos al servidor si hay versión nueva aunque el navegador tenga una copia guardada
  const fresh = req.mode === "navigate" ? fetch(req) : fetch(req, { cache: "no-cache" });
  event.respondWith(
    fresh
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      })
      .catch(async () => {
        const cached = await caches.match(req);
        if (cached) return cached;
        // Sin internet y sin copia de esa página: la pantalla "sin conexión"
        if (req.mode === "navigate") return caches.match("/offline.html");
        return Response.error();
      }),
  );
});
