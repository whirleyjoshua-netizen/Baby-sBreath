const CACHE_NAME = 'babys-breath-v1';
const SHELL = ['/', '/static/style.css', '/static/app.js'];

self.addEventListener('install', (e) => {
    e.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(SHELL))
    );
    self.skipWaiting();
});

self.addEventListener('activate', (e) => {
    e.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', (e) => {
    // Never cache API or WebSocket requests
    if (e.request.url.includes('/api/') || e.request.url.includes('/ws')) return;

    e.respondWith(
        caches.match(e.request).then(cached => cached || fetch(e.request))
    );
});
