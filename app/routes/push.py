"""
Push Notification routes - Register tokens and send notifications
"""

from flask import Blueprint, request, session, jsonify
import requests
import json
from app.services.db import get_connection, generate_id, now_iso

push_bp = Blueprint('push', __name__, url_prefix='/push')

TENANT_ID = "MARAGON"

# Firebase Cloud Messaging API endpoint
FCM_URL = "https://fcm.googleapis.com/v1/projects/schoolops-d8bdd/messages:send"

# Note: For production, you'll need a service account key file
# For now, we'll use the legacy HTTP API which is simpler
FCM_LEGACY_URL = "https://fcm.googleapis.com/fcm/send"
FCM_SERVER_KEY = None  # Will be set from environment or config


@push_bp.route('/register', methods=['POST'])
def register_token():
    """Register a device token for push notifications."""
    data = request.get_json()
    token = data.get('token')
    
    if not token:
        return jsonify({'error': 'No token provided'}), 400
    
    staff_id = session.get('staff_id')
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Check if token already exists
        cursor.execute('SELECT id, staff_id FROM push_token WHERE token = ?', (token,))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing token with current staff_id
            cursor.execute('''
                UPDATE push_token 
                SET staff_id = ?, last_used_at = ?, tenant_id = ?
                WHERE token = ?
            ''', (staff_id, now_iso(), TENANT_ID, token))
        else:
            # Insert new token
            token_id = generate_id()
            cursor.execute('''
                INSERT INTO push_token (id, tenant_id, staff_id, token, created_at, last_used_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (token_id, TENANT_ID, staff_id, token, now_iso(), now_iso()))
        
        conn.commit()
    
    return jsonify({'success': True, 'message': 'Token registered'})


@push_bp.route('/unregister', methods=['POST'])
def unregister_token():
    """Remove a device token."""
    data = request.get_json()
    token = data.get('token')
    
    if not token:
        return jsonify({'error': 'No token provided'}), 400
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM push_token WHERE token = ?', (token,))
        conn.commit()
    
    return jsonify({'success': True, 'message': 'Token removed'})


@push_bp.route('/test', methods=['POST'])
def test_push():
    """Send a test push notification to current user."""
    staff_id = session.get('staff_id')
    
    if not staff_id:
        return jsonify({'error': 'Not logged in'}), 401
    
    # Get user's tokens
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT token FROM push_token WHERE staff_id = ?', (staff_id,))
        tokens = [row['token'] for row in cursor.fetchall()]
    
    if not tokens:
        return jsonify({'error': 'No push tokens registered for this user'}), 400
    
    # Send test notification
    results = send_push_to_tokens(
        tokens,
        title='SchoolOps Test',
        body='Push notifications are working!',
        data={'url': '/'}
    )
    
    return jsonify({'success': True, 'sent_to': len(tokens), 'results': results})


def get_all_tenant_tokens(tenant_id=TENANT_ID):
    """Get all push tokens for a tenant."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT token FROM push_token WHERE tenant_id = ?
        ''', (tenant_id,))
        return [row['token'] for row in cursor.fetchall()]


def send_push_to_tokens(tokens, title, body, data=None):
    """
    Send push notification to multiple FCM tokens.
    Uses Firebase HTTP v1 API via service account.
    """
    if not tokens:
        return {'sent': 0, 'failed': 0}
    
    # For each token, send a message
    sent = 0
    failed = 0
    failed_tokens = []
    
    for token in tokens:
        try:
            success = send_single_push(token, title, body, data)
            if success:
                sent += 1
            else:
                failed += 1
                failed_tokens.append(token)
        except Exception as e:
            print(f"Error sending push to {token[:20]}...: {e}")
            failed += 1
            failed_tokens.append(token)
    
    # Clean up invalid tokens
    if failed_tokens:
        cleanup_invalid_tokens(failed_tokens)
    
    return {'sent': sent, 'failed': failed}


def send_single_push(token, title, body, data=None):
    """
    Send push notification to a single FCM token.
    Uses the legacy HTTP API for simplicity.
    """
    import os
    
    server_key = os.environ.get('FCM_SERVER_KEY')
    
    if not server_key:
        # Log but don't fail - push is optional during development
        print("FCM_SERVER_KEY not set - push notification skipped")
        return False
    
    headers = {
        'Authorization': f'key={server_key}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'to': token,
        'notification': {
            'title': title,
            'body': body,
            'icon': '/static/icon-192.png',
            'click_action': data.get('url', '/emergency/') if data else '/emergency/'
        },
        'data': data or {},
        'priority': 'high',
        'time_to_live': 60  # Message expires after 60 seconds
    }
    
    try:
        response = requests.post(
            FCM_LEGACY_URL,
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get('success', 0) > 0
        else:
            print(f"FCM error: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"FCM request error: {e}")
        return False


def cleanup_invalid_tokens(tokens):
    """Remove invalid tokens from database."""
    if not tokens:
        return
    
    with get_connection() as conn:
        cursor = conn.cursor()
        placeholders = ','.join(['?' for _ in tokens])
        cursor.execute(f'DELETE FROM push_token WHERE token IN ({placeholders})', tokens)
        conn.commit()
        print(f"Cleaned up {cursor.rowcount} invalid tokens")


def send_emergency_alert_push(alert_type, location, triggered_by):
    """
    Send emergency alert push to all staff.
    Called from emergency.send_alert route.
    """
    tokens = get_all_tenant_tokens()
    
    if not tokens:
        print("No push tokens registered - skipping push notification")
        return {'sent': 0, 'failed': 0}
    
    # Emoji for alert type
    emoji = {
        'Medical': '🏥',
        'Security': '🔒', 
        'Fire': '🔥',
        'General': '⚠️'
    }.get(alert_type, '🚨')
    
    title = f'{emoji} EMERGENCY: {alert_type}'
    body = f'Location: {location}\nTriggered by: {triggered_by}'
    
    return send_push_to_tokens(
        tokens,
        title=title,
        body=body,
        data={
            'url': '/emergency/',
            'type': 'emergency',
            'alert_type': alert_type
        }
    )
