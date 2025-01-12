const CACHE_NAME = 'sentinel-citizen-v2';
const urlsToCache = [
  './index.html',
  './manifest.json',
  './src/citizen_routing_worker.js',
  '/HUFP_mumbai/data/mumbai_mangroves_boundary.geojson',
  'https://cdn.tailwindcss.com',
  'https://unpkg.com/lucide@latest',
  'https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=JetBrains+Mono:wght@400;700&display=swap'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
      .catch(() => {
        // Fallback to offline page/data if needed
        return caches.match('./index.html');
      })
  );
});
