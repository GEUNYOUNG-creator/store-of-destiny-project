const CACHE_NAME = 'fortune-shop-pwa-v6';
const CORE_ASSETS = ['/', '/manifest.json', '/icon-192.png', '/icon-512.png', '/og-preview.jpg'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE_NAME).then((c) => c.addAll(CORE_ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith('/api/') || (url.pathname.endsWith('.mp4') || url.pathname.endsWith('.mp3') || url.pathname.endsWith('.glb')) || e.request.method !== 'GET') return;
  e.respondWith(
    fetch(e.request).then((res) => {
      if (res && res.status === 200 && url.origin === self.location.origin) {
        const clone = res.clone();
        caches.open(CACHE_NAME).then((c) => c.put(e.request, clone));
      }
      return res;
    }).catch(() => caches.match(e.request))
  );
});
