"""
Push notification routes using Firebase Cloud Messaging V1 API
Uses service account authentication (modern approach)
"""
from flask import Blueprint, request, jsonify, session
from app.services.db import get_connection, generate_id, now_iso
import os
import json
import time
import requests

push_bp = Blueprint('push', __name__, url_prefix='/push')

TENANT_ID = "MARAGON"

# Firebase project ID
FIREBASE_PROJECT_ID = "schoolops-d8bdd"

# Cache for access token
_token_cache = {
    'token': None,
    'expires_at': 0
}


def get_service_account_info():
    """Get service account info from environment variable"""
    sa_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
    if not sa_json:
        return None
    try:
        return json.loads(sa_json)
    except json.JSONDecodeError:
        print("ERROR: Invalid FIREBASE_SERVICE_ACCOUNT JSON")
        return None


def get_access_token():
    """
    Get OAuth2 access token for Firebase API using service account.
    Uses JWT to request access token from Google.
    """
    import jwt  # PyJWT library
    
    # Check cache first
    if _token_cache['token'] and time.time() < _token_cache['expires_at'] - 60:
        return _token_cache['token']
    
    sa_info = get_service_account_info()
    if not sa_info:
        return None
    
    # Create JWT
    now = int(time.time())
    payload = {
        'iss': sa_info['client_email'],
        'sub': sa_info['client_email'],
        'aud': 'https://oauth2.googleapis.com/token',
        'iat': now,
        'exp': now + 3600,
        'scope': 'https://www.googleapis.com/auth/firebase.messaging'
    }
    
    # Sign with private key
    signed_jwt = jwt.encode(
        payload,
        sa_info['private_key'],
        algorithm='RS256'
    )
    
    # Exchange JWT for access token
    response = requests.post(
        'https://oauth2.googleapis.com/token',
        data={
            'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
            'assertion': signed_jwt
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        _token_cache['token'] = data['access_token']
        _token_cache['expires_at'] = now + data.get('expires_in', 3600)
        return data['access_token']
    else:
        print(f"ERROR getting access token: {response.status_code} {response.text}")
        return None


def send_push_notification(token, title, body, data=None, badge_url=None):
    """
    Send push notification to a single device using FCM V1 API
    
    Args:
        token: FCM device token
        title: Notification title
        body: Notification body
        data: Optional dict of custom data
        badge_url: Optional URL for notification icon
    
    Returns:
        True if successful, False otherwise
    """
    access_token = get_access_token()
    if not access_token:
        print("WARNING: No Firebase access token available - push disabled")
        return False
    
    url = f"https://fcm.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/messages:send"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    # Build message payload
    message = {
        'message': {
            'token': token,
            'notification': {
                'title': title,
                'body': body
            },
            'webpush': {
                'notification': {
                    'icon': badge_url or '/static/icon-192.png',
                    'badge': '/static/icon-192.png',
                    'vibrate': [200, 100, 200, 100, 200],
                    'requireInteraction': True
                },
                'fcm_options': {
                    'link': '/emergency/'
                }
            }
        }
    }
    
    # Add custom data if provided
    if data:
        message['message']['data'] = {k: str(v) for k, v in data.items()}
    
    try:
        response = requests.post(url, headers=headers, json=message, timeout=10)
        
        if response.status_code == 200:
            return True
        elif response.status_code == 404 or 'NOT_FOUND' in response.text:
            # Token is invalid/expired - should be removed from database
            print(f"Invalid token (will be cleaned): {token[:20]}...")
            return False
        else:
            print(f"FCM error: {response.status_code} {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"FCM request failed: {e}")
        return False


def send_emergency_alert_push(alert_type, location, triggered_by):
    """
    Send emergency alert to all registered devices for the tenant.
    Called when an emergency is triggered.
    """
    access_token = get_access_token()
    if not access_token:
        print("WARNING: Push notifications not configured - skipping")
        return 0
    
    # Get all tokens for this tenant
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, token FROM push_token 
            WHERE tenant_id = ?
        ''', (TENANT_ID, substitute_id))
        tokens = cursor.fetchall()
    
    if not tokens:
        print("No push tokens registered")
        return 0
    
    # Emoji for alert type
    type_emoji = {
        'Medical': '🏥',
        'Security': '🔒',
        'Fire': '🔥',
        'General': '⚠️'
    }.get(alert_type, '🚨')
    
    title = f"{type_emoji} EMERGENCY: {alert_type}"
    body = f"Location: {location}\nTriggered by: {triggered_by}"
    
    success_count = 0
    invalid_tokens = []
    
    for token_row in tokens:
        token_id, token = token_row['id'], token_row['token']
        if send_push_notification(token, title, body, data={'type': 'emergency', 'alert_type': alert_type}):
            success_count += 1
            # Update last_used_at
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE push_token SET last_used_at = ? WHERE id = ?
                ''', (now_iso(), token_id))
                conn.commit()
        else:
            # Check if we should remove this token
            invalid_tokens.append(token_id)
    
    # Clean up invalid tokens
    if invalid_tokens:
        with get_connection() as conn:
            cursor = conn.cursor()
            for token_id in invalid_tokens:
                cursor.execute('DELETE FROM push_token WHERE id = ?', (token_id,))
            conn.commit()
        print(f"Cleaned {len(invalid_tokens)} invalid tokens")
    
    print(f"Push sent to {success_count}/{len(tokens)} devices")
    return success_count




def send_all_clear_push(alert_type, location, resolved_by):
    """
    Send 'All Clear' notification to all registered devices.
    Called when an emergency is resolved.
    """
    access_token = get_access_token()
    if not access_token:
        print("WARNING: Push notifications not configured - skipping")
        return 0
    
    # Get all tokens for this tenant
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, token FROM push_token 
            WHERE tenant_id = ?
        ''', (TENANT_ID, substitute_id))
        tokens = cursor.fetchall()
    
    if not tokens:
        print("No push tokens registered")
        return 0
    
    title = "✅ ALL CLEAR"
    body = f"{alert_type} emergency at {location} has been resolved by {resolved_by}"
    
    success_count = 0
    for token_row in tokens:
        token_id, token = token_row['id'], token_row['token']
        if send_push_notification(token, title, body, data={'type': 'resolved', 'alert_type': alert_type}):
            success_count += 1
    
    print(f"All Clear push sent to {success_count}/{len(tokens)} devices")
    return success_count

@push_bp.route('/register', methods=['POST'])
def register_token():
    """Register a device token for push notifications"""
    data = request.get_json()
    token = data.get('token')
    
    if not token:
        return jsonify({'error': 'Token required'}), 400
    
    staff_id = session.get('staff_id')
    device_info = data.get('device_info', request.headers.get('User-Agent', '')[:200])
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Check if token already exists
        cursor.execute('SELECT id FROM push_token WHERE token = ?', (token,))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing token
            cursor.execute('''
                UPDATE push_token 
                SET staff_id = ?, device_info = ?, last_used_at = ?
                WHERE token = ?
            ''', (staff_id, device_info, now_iso(), token))
        else:
            # Insert new token
            cursor.execute('''
                INSERT INTO push_token (id, tenant_id, staff_id, token, device_info, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (generate_id(), TENANT_ID, staff_id, token, device_info, now_iso()))
        
        conn.commit()
    
    return jsonify({'success': True, 'message': 'Token registered'})


@push_bp.route('/unregister', methods=['POST'])
def unregister_token():
    """Remove a device token"""
    data = request.get_json()
    token = data.get('token')
    
    if not token:
        return jsonify({'error': 'Token required'}), 400
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM push_token WHERE token = ?', (token,))
        conn.commit()
    
    return jsonify({'success': True, 'message': 'Token removed'})


@push_bp.route('/test', methods=['POST'])
def test_push():
    """Send a test notification to the current user's devices"""
    staff_id = session.get('staff_id')
    
    if not staff_id:
        return jsonify({'error': 'Not logged in'}), 401
    
    # Check if push is configured
    if not get_service_account_info():
        return jsonify({'error': 'Push notifications not configured'}), 503
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT token FROM push_token 
            WHERE tenant_id = ? AND staff_id = ?
        ''', (TENANT_ID, staff_id))
        tokens = cursor.fetchall()
    
    if not tokens:
        return jsonify({'error': 'No devices registered'}), 404
    
    success_count = 0
    for row in tokens:
        if send_push_notification(
            row['token'],
            '🔔 Test Notification',
            'Push notifications are working!',
            data={'type': 'test'}
        ):
            success_count += 1
    
    return jsonify({
        'success': True,
        'message': f'Sent to {success_count}/{len(tokens)} devices'
    })


@push_bp.route('/status', methods=['GET'])
def push_status():
    """Check if push notifications are configured"""
    configured = get_service_account_info() is not None
    
    # Count registered tokens
    token_count = 0
    if configured:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as count FROM push_token WHERE tenant_id = ?', (TENANT_ID,))
            result = cursor.fetchone()
            token_count = result['count'] if result else 0
    
    return jsonify({
        'configured': configured,
        'registered_devices': token_count
    })


@push_bp.route('/test-allclear', methods=['POST'])
def test_all_clear():
    """Test All Clear push notification"""
    staff_id = session.get('staff_id')
    if not staff_id:
        return jsonify({'error': 'Not logged in'}), 401
    
    count = send_all_clear_push('Medical', 'Test Location', 'Test User')
    return jsonify({'success': True, 'sent_to': count})


def send_substitute_assigned_push(substitute_id, absent_teacher_name, period_info, date_str, venue):
    """
    Send push to substitute teacher when assigned.
    Args:
        substitute_id: staff_id of substitute
        absent_teacher_name: name of absent teacher
        period_info: e.g., "Period 1" or "Roll Call"
        date_str: e.g., "Thu 15 Jan"
        venue: room code
    """
    print(f"PUSH DEBUG: send_substitute_assigned_push called for {substitute_id}")
    access_token = get_access_token()
    if not access_token:
        print("PUSH DEBUG: No access token")
        return 0
    
    with get_connection() as conn:
        cursor = conn.cursor()
        # Send to specific substitute only
        cursor.execute('''
            SELECT pt.token FROM push_token pt
            WHERE pt.tenant_id = ? AND pt.staff_id = ?
        ''', (TENANT_ID, substitute_id))
        tokens = cursor.fetchall()
    
    print(f"PUSH DEBUG: Found {len(tokens)} tokens for substitute")
    if not tokens:
        return 0
    
    title = f"📚 Sub Duty: {period_info}"
    body = f"Cover for {absent_teacher_name}\n{date_str} • {venue}"
    
    success_count = 0
    for row in tokens:
        if send_push_notification(
            row['token'], title, body,
            data={'type': 'substitute', 'link': '/duty/my-day?tab=tomorrow'}
        ):
            success_count += 1
    
    return success_count


def send_absence_covered_push(absent_staff_id, covered_count, total_count, date_range):
    """
    Send push to absent teacher confirming coverage.
    """
    access_token = get_access_token()
    if not access_token:
        return 0
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT token FROM push_token
            WHERE tenant_id = ? AND staff_id = ?
        ''', (TENANT_ID, absent_staff_id))
        tokens = cursor.fetchall()
    
    if not tokens:
        return 0
    
    if covered_count == total_count:
        title = "✅ All Classes Covered"
        body = f"{covered_count} periods covered for {date_range}"
    else:
        title = "⚠️ Partial Coverage"
        body = f"{covered_count}/{total_count} periods covered for {date_range}"
    
    success_count = 0
    for row in tokens:
        if send_push_notification(
            row['token'], title, body,
            data={'type': 'absence_confirmed', 'link': '/substitute/my-assignments'}
        ):
            success_count += 1
    
    return success_count


def send_absence_reported_push(absent_teacher_name, date_str, period_count):
    """
    Send push to principal when any teacher reports absence.
    """
    print(f"PUSH DEBUG: send_absence_reported_push for {absent_teacher_name}")
    access_token = get_access_token()
    if not access_token:
        print("PUSH DEBUG: No access token")
        return 0
    
    with get_connection() as conn:
        cursor = conn.cursor()
        # Get Pierre's staff_id via magic link
        cursor.execute('''
            SELECT s.id FROM staff s
            JOIN user_session us ON s.id = us.staff_id
            WHERE us.tenant_id = ? AND us.magic_link = 'pierre'
        ''', (TENANT_ID, substitute_id))
        pierre = cursor.fetchone()
        
        if not pierre:
            print("PUSH DEBUG: Pierre not found")
            return 0
        
        pierre_id = pierre['id']
        cursor.execute('''
            SELECT token FROM push_token
            WHERE tenant_id = ? AND staff_id = ?
        ''', (TENANT_ID, pierre_id))
        tokens = cursor.fetchall()
    
    print(f"PUSH DEBUG: Found {len(tokens)} tokens for Pierre")
    if not tokens:
        return 0
    
    title = "📋 Absence Reported"
    body = f"{absent_teacher_name} • {date_str} • {period_count} periods need cover"
    
    success_count = 0
    for row in tokens:
        if send_push_notification(
            row['token'], title, body,
            data={'type': 'absence_reported', 'link': '/substitute/mission-control'}
        ):
            print(f"PUSH DEBUG: Absence notification sent to Pierre")
            success_count += 1
    
    return success_count
