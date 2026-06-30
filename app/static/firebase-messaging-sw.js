// Firebase Messaging Service Worker

// Auto-activate new service worker versions immediately
self.addEventListener("install", (event) => { self.skipWaiting(); });
self.addEventListener("activate", (event) => { event.waitUntil(clients.claim()); });
// Handles background push notifications AND foreground relay via postMessage

importScripts('https://www.gstatic.com/firebasejs/10.7.1/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging-compat.js');

firebase.initializeApp({
  apiKey: "AIzaSyCia8Pd8idl1BrzMeAs_Pvv44jO5QLpysM",
  authDomain: "schoolops-d8bdd.firebaseapp.com",
  projectId: "schoolops-d8bdd",
  storageBucket: "schoolops-d8bdd.firebasestorage.app",
  messagingSenderId: "263463533186",
  appId: "1:263463533186:web:9f4307bc3966a7b255129b"
});

const messaging = firebase.messaging();

// Handle background messages (data-only payloads)
messaging.onBackgroundMessage((payload) => {
  // Display is handled by the native 'push' listener below (single path).
  // This handler stays registered for Firebase but does NOT render, to
  // avoid a duplicate banner (the two handlers previously used different
  // tags and could both fire for one FCM data message).
  console.log('[SW] onBackgroundMessage (display deferred to push):', payload);
});

// Handle background push natively (primary path).
// A stopped SW wakes via this event; event.waitUntil keeps it alive
// until showNotification resolves. Reads the data-only FCM payload
// (push.py sends {title, body, icon, link, type} under 'data').
// Falls back to raw text for DevTools 'Push' (non-FCM bodies).
self.addEventListener('push', (event) => {
  let data = {};
  if (event.data) {
    try {
      const json = event.data.json();
      data = json.data || json || {};
    } catch (e) {
      data = { title: 'SchoolOps Alert', body: event.data.text() };
    }
  }
  const notificationType = data.type || 'general';
  console.log('[SW] push event received:', data);
  // macOS Chrome silently drops a notification whose icon is a root-relative
  // path the SW cannot resolve at paint time. Normalise to an absolute URL on
  // the SW's own origin so the banner (with icon) always renders. Proven fix.
  const ORIGIN = self.location.origin;
  function absIcon(p, fallback) {
    if (!p) return ORIGIN + (fallback || '/static/icon-192.png');
    if (p.startsWith('http://') || p.startsWith('https://')) return p;
    return ORIGIN + (p.startsWith('/') ? p : '/' + p);
  }
  event.waitUntil(
    self.registration.showNotification(data.title || 'SchoolOps Alert', {
      body: data.body || 'You have a new notification',
      icon: absIcon(data.icon),
      badge: absIcon(data.badge, '/static/badge-72.png'),
      tag: 'schoolops-' + notificationType,
      requireInteraction: true,
      vibrate: [200, 100, 200, 100, 200],
      data: {
        url: data.link || data.url || '/'
      }
    })
  );
});

// Handle foreground relay from push.js via postMessage
// Ref: https://web.dev/articles/codelab-notifications-service-worker
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SHOW_NOTIFICATION') {
    console.log('[SW] postMessage relay received:', event.data);
    const data = event.data.data || {};
    const notificationType = data.type || 'general';
    
    self.registration.showNotification(data.title || 'SchoolOps Alert', {
      body: data.body || 'You have a new notification',
      icon: data.icon || '/static/icon-192.png',
      badge: '/static/icon-192.png',
      tag: 'schoolops-' + notificationType + '-' + Date.now(),
      requireInteraction: true,
      vibrate: [200, 100, 200, 100, 200],
      data: {
        url: data.link || data.url || '/emergency/'
      }
    });
  }
});

// Handle notification click
self.addEventListener('notificationclick', (event) => {
  console.log('[SW] Notification clicked');
  event.notification.close();
  
  const urlToOpen = event.notification.data?.url || '/emergency/';
  
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      for (let client of windowClients) {
        if (client.url.includes('schoolops.co.za') && 'focus' in client) {
          client.navigate(urlToOpen);
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(urlToOpen);
      }
    })
  );
});
