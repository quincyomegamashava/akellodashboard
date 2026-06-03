/* Akello Learn — minimal PWA shell (network-first; extend for offline assets). */
self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", () => {
  /* Placeholder: pass-through. Add caching rules when you need offline learn pages. */
});
