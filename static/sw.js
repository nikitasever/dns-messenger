/* DNS Tunnel Messenger — service worker
   Offline app shell + notification handling.
   Network-first for navigation and API; cache-first for static assets. */

const CACHE = 'dns-messenger-v3';
const SHELL = [
    '/',
    '/static/app.js',
    '/static/style.css',
    '/static/socket.io.min.js',
    '/static/manifest.json',
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE).then((cache) => cache.addAll(SHELL).catch(() => {}))
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    const req = event.request;
    if (req.method !== 'GET') return;
    const url = new URL(req.url);

    // Never cache API or socket.io traffic — always go to network
    if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/socket.io/')) {
        return; // default browser handling
    }

    // Static assets: network-first so code/style updates land immediately when
    // online; fall back to cache only when the network is unavailable (offline).
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            fetch(req).then((res) => {
                const copy = res.clone();
                caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
                return res;
            }).catch(() => caches.match(req))
        );
        return;
    }

    // Navigations: network-first, fall back to cached shell for offline
    if (req.mode === 'navigate') {
        event.respondWith(
            fetch(req).catch(() => caches.match('/'))
        );
    }
});

// Server-sent push (VAPID) — fires even with every tab closed
self.addEventListener('push', (event) => {
    let data = {};
    try { data = event.data ? event.data.json() : {}; } catch (e) { /* not JSON */ }
    const title = data.title || 'DNS Messenger';
    event.waitUntil(
        self.registration.showNotification(title, {
            body: data.body || 'Новое сообщение',
            icon: '/static/icon-192.png',
            badge: '/static/icon-192.png',
            tag: data.tag || 'dns-push',
            renotify: true,
            data: { url: '/' },
        })
    );
});

// The push service can rotate a subscription; re-register so we keep receiving
self.addEventListener('pushsubscriptionchange', (event) => {
    event.waitUntil((async () => {
        try {
            const res = await fetch('/api/push/key');
            const { key } = await res.json();
            const sub = await self.registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: key,
            });
            await fetch('/api/push/subscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ subscription: sub.toJSON() }),
            });
        } catch (e) { /* retried on next page load */ }
    })());
});

// Notification click → focus or open the app
self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    event.waitUntil(
        self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
            for (const client of clients) {
                if ('focus' in client) return client.focus();
            }
            if (self.clients.openWindow) return self.clients.openWindow('/');
        })
    );
});

// Allow the page to trigger a notification through the SW (works when backgrounded)
self.addEventListener('message', (event) => {
    const data = event.data || {};
    if (data.type === 'notify' && self.registration.showNotification) {
        self.registration.showNotification(data.title || 'DNS Messenger', {
            body: data.body || '',
            icon: '/static/icon-192.png',
            badge: '/static/icon-192.png',
            tag: data.tag || 'dns-msg',
            renotify: true,
        });
    }
});
