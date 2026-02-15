// SchoolOps Push Notification Registration
// Include this script on pages where push should be enabled

const VAPID_KEY = 'BEbEm9F2pbxVU0cDQKsN03gxV7QnR9yBUiZ7dKdEmNXFicbeSDXKKHl665vLnw14OjxI2ULnG_VwWke8FSWEwo8';

// Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyCia8Pd8idl1BrzMeAs_Pvv44jO5QLpysM",
  authDomain: "schoolops-d8bdd.firebaseapp.com",
  projectId: "schoolops-d8bdd",
  storageBucket: "schoolops-d8bdd.firebasestorage.app",
  messagingSenderId: "263463533186",
  appId: "1:263463533186:web:9f4307bc3966a7b255129b"
};

let messaging = null;
let swRegistration = null;

// Wait for service worker to be ready
async function waitForServiceWorkerActive(registration) {
  if (registration.active) {
    return registration;
  }
  
  return new Promise((resolve) => {
    const sw = registration.installing || registration.waiting;
    if (sw) {
      sw.addEventListener('statechange', () => {
        if (sw.state === 'activated') {
          resolve(registration);
        }
      });
    } else {
      resolve(registration);
    }
  });
}

// Initialize Firebase and request permission
async function initializePush() {
  try {
    if (!('Notification' in window)) {
      console.log('This browser does not support notifications');
      return false;
    }

    if (!('serviceWorker' in navigator)) {
      console.log('Service workers not supported');
      return false;
    }

    const registration = await navigator.serviceWorker.register('/firebase-messaging-sw.js');
    console.log('Service worker registered:', registration.scope);
    
    swRegistration = await waitForServiceWorkerActive(registration);
    console.log('Service worker active');

    if (!firebase.apps.length) {
      firebase.initializeApp(firebaseConfig);
    }
    
    messaging = firebase.messaging();

    return true;
  } catch (error) {
    console.error('Error initializing push:', error);
    return false;
  }
}

// Request notification permission and get token
async function requestNotificationPermission() {
  try {
    const permission = await Notification.requestPermission();
    
    if (permission === 'granted') {
      console.log('Notification permission granted');
      return await getAndSaveToken();
    } else {
      console.log('Notification permission denied');
      return false;
    }
  } catch (error) {
    console.error('Error requesting permission:', error);
    return false;
  }
}

// Get FCM token and save to backend
async function getAndSaveToken() {
  try {
    if (!messaging || !swRegistration) {
      await initializePush();
    }
    
    const token = await messaging.getToken({ 
      vapidKey: VAPID_KEY,
      serviceWorkerRegistration: swRegistration
    });
    
    if (token) {
      console.log('FCM Token:', token);
      
      const response = await fetch('/push/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ token: token })
      });
      
      if (response.ok) {
        console.log('Token registered with backend');
        localStorage.setItem('fcm_token', token);
        return true;
      } else {
        console.error('Failed to register token with backend');
        return false;
      }
    } else {
      console.log('No token received');
      return false;
    }
  } catch (error) {
    console.error('Error getting token:', error);
    return false;
  }
}

// Relay notification data to service worker via postMessage.
// Why: Firebase SDK compat library wraps onMessage callbacks and suppresses
// showNotification() calls made from page context. By relaying to the SW,
// showNotification runs in the service worker scope where it works reliably.
// Ref: https://web.dev/articles/codelab-notifications-service-worker
function relayToServiceWorker(data) {
  // Primary path: use controller (fastest, direct reference)
  if (navigator.serviceWorker.controller) {
    console.log('Relaying via controller');
    navigator.serviceWorker.controller.postMessage({
      type: 'SHOW_NOTIFICATION',
      data: data
    });
    return;
  }
  
  // Fallback: controller is null after hard refresh (Shift+Reload).
  // Use registration.active instead.
  if (swRegistration && swRegistration.active) {
    console.log('Relaying via registration.active (hard-refresh fallback)');
    swRegistration.active.postMessage({
      type: 'SHOW_NOTIFICATION',
      data: data
    });
    return;
  }
  
  // Last resort: wait for ready
  console.log('Relaying via serviceWorker.ready (last resort)');
  navigator.serviceWorker.ready.then(reg => {
    if (reg.active) {
      reg.active.postMessage({
        type: 'SHOW_NOTIFICATION',
        data: data
      });
    }
  });
}

// Handle foreground messages
function setupForegroundHandler() {
  if (!messaging) return;
  
  messaging.onMessage((payload) => {
    console.log('Foreground message received:', payload);
    
    const data = payload.data || {};
    if (Notification.permission === 'granted') {
      relayToServiceWorker(data);
    } else {
      console.log('Notification permission not granted:', Notification.permission);
    }
  });
}

// Check if already registered
function isRegistered() {
  return localStorage.getItem('fcm_token') !== null;
}

// Main initialization function
async function setupPushNotifications() {
  const initialized = await initializePush();
  if (!initialized) return;
  
  setupForegroundHandler();
  
  if (Notification.permission === 'granted') {
    await getAndSaveToken();
  }
}

// Auto-initialize when script loads
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', setupPushNotifications);
} else {
  setupPushNotifications();
}
