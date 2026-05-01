// Smart Virtual Queue - Service Worker for Push Notifications
const CACHE_NAME = 'svq-v1';

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
});

// Handle notification clicks - open the gate page
self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    event.waitUntil(
        clients.matchAll({ type: 'window' }).then(windowClients => {
            // Focus existing window or open new one
            for (const client of windowClients) {
                if (client.url.includes('gate.html') && 'focus' in client) {
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow('gate.html');
            }
        })
    );
});
