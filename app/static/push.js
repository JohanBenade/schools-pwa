// SchoolOps Push Notification Registration
// Include this script on pages where push should be enabled

const VAPID_KEY = 'BMdMtLurIzu3UpjvHibI_dGMjuLjDr-ffD4ytFYI7wVI36f4BuAmfeiQl8_sSQWDQ79G6yNN1eyQP5ztBdD0mU';

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

// Initialize Firebase and request permission
async function initializePush() {
  try {
    // Check if browser supports notifications
    if (!('Notification' in window)) {
      console.log('This browser does not support notifications');
      return false;
    }

    // Check if service worker is supported
    if (!('serviceWorker' in navigator)) {
      console.log('Service workers not supported');
      return false;
    }

    // Register service worker
    const registration = await navigator.serviceWorker.register('/static/firebase-messaging-sw.js');
    console.log('Service worker registered:', registration.scope);

    // Initialize Firebase
    if (!firebase.apps.length) {
      firebase.initializeApp(firebaseConfig);
    }
    
    messaging = firebase.messaging();
    
    // Use our service worker
    messaging.useServiceWorker(registration);

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
    if (!messaging) {
      await initializePush();
    }
    
    const token = await messaging.getToken({ vapidKey: VAPID_KEY });
    
    if (token) {
      console.log('FCM Token:', token);
      
      // Send token to backend
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

// Handle foreground messages
function setupForegroundHandler() {
  if (!messaging) return;
  
  messaging.onMessage((payload) => {
    console.log('Foreground message received:', payload);
    
    // Show notification even when app is open
    if (Notification.permission === 'granted') {
      const notification = new Notification(payload.notification?.title || 'SchoolOps Alert', {
        body: payload.notification?.body || 'Emergency alert!',
        icon: '/static/icon-192.png',
        tag: 'schoolops-emergency',
        requireInteraction: true
      });
      
      notification.onclick = () => {
        window.focus();
        window.location.href = payload.data?.url || '/emergency/';
        notification.close();
      };
    }
  });
}

// Check if already registered
function isRegistered() {
  return localStorage.getItem('fcm_token') !== null;
}

// Main initialization function - call this on page load
async function setupPushNotifications() {
  const initialized = await initializePush();
  if (!initialized) return;
  
  setupForegroundHandler();
  
  // If already granted, ensure token is registered
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
