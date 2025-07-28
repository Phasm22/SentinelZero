"""
Notification service for alerts and messaging
"""
import os
import requests
from ..models import Alert
from ..config.database import db

def send_pushover_alert(message, level='info', scan_id=None, socketio=None):
    """Send Pushover notification and log to database"""
    try:
        PUSHOVER_API_TOKEN = os.environ.get('PUSHOVER_API_TOKEN')
        PUSHOVER_USER_KEY = os.environ.get('PUSHOVER_USER_KEY')
        
        if not PUSHOVER_API_TOKEN or not PUSHOVER_USER_KEY:
            print(f'[PUSHOVER] Missing credentials, skipping notification: {message}')
            return
            
        resp = requests.post('https://api.pushover.net/1/messages.json', data={
            'token': PUSHOVER_API_TOKEN,
            'user': PUSHOVER_USER_KEY,
            'message': message,
            'priority': 1 if level == 'danger' else 0,
            'title': 'SentinelZero',
        })
        
        if resp.status_code == 200:
            if socketio:
                socketio.emit('scan_log', {'msg': f'Pushover alert sent: {message}'})
        else:
            if socketio:
                socketio.emit('scan_log', {'msg': f'Pushover failed: {resp.text}'})
        
        # Log to database
        alert = Alert(message=message, level=level, scan_id=scan_id)
        db.session.add(alert)
        db.session.commit()
        
    except Exception as e:
        if socketio:
            socketio.emit('scan_log', {'msg': f'Pushover error: {str(e)}'})
        print(f'Pushover error: {str(e)}')
