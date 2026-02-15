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
  console.log('[SW] Background message received:', payload);
  
  const data = payload.data || {};
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
