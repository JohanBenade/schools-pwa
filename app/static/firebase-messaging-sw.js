// Firebase Messaging Service Worker
// Handles background push notifications

importScripts('https://www.gstatic.com/firebasejs/10.7.1/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging-compat.js');

// Firebase configuration
firebase.initializeApp({
  apiKey: "AIzaSyCia8Pd8idl1BrzMeAs_Pvv44jO5QLpysM",
  authDomain: "schoolops-d8bdd.firebaseapp.com",
  projectId: "schoolops-d8bdd",
  storageBucket: "schoolops-d8bdd.firebasestorage.app",
  messagingSenderId: "263463533186",
  appId: "1:263463533186:web:9f4307bc3966a7b255129b"
});

const messaging = firebase.messaging();

// Handle background messages
messaging.onBackgroundMessage((payload) => {
  console.log('[firebase-messaging-sw.js] Background message received:', payload);
  
  const notificationTitle = payload.notification?.title || 'SchoolOps Alert';
  const notificationType = payload.data?.type || 'general';
  const notificationTag = 'schoolops-' + notificationType + '-' + Date.now();
  
  const notificationOptions = {
    body: payload.notification?.body || 'You have a new notification',
    icon: '/static/icon-192.png',
    badge: '/static/icon-192.png',
    tag: notificationTag,
    requireInteraction: true,  // Keep notification visible until user interacts
    vibrate: [200, 100, 200, 100, 200],  // Vibration pattern
    data: {
      url: payload.data?.link || payload.data?.url || '/emergency/'
    }
  };

  self.registration.showNotification(notificationTitle, notificationOptions);
});

// Handle notification click
self.addEventListener('notificationclick', (event) => {
  console.log('[firebase-messaging-sw.js] Notification clicked');
  event.notification.close();
  
  const urlToOpen = event.notification.data?.url || '/emergency/';
  
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      // Check if app is already open
      for (let client of windowClients) {
        if (client.url.includes('schoolops.co.za') && 'focus' in client) {
          client.navigate(urlToOpen);
          return client.focus();
        }
      }
      // Open new window if not open
      if (clients.openWindow) {
        return clients.openWindow(urlToOpen);
      }
    })
  );
});
