import sys
import os
from datetime import datetime, timedelta
import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from backend.app import create_app, db
from backend.src.models import Scan, Alert

@pytest.fixture
def app():
    """Create test app with in-memory database"""
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'ENABLE_BACKGROUND_SERVICES': False,
    })
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()

def test_dashboard_stats(client):
    response = client.get('/api/dashboard-stats')
    assert response.status_code == 200
    assert response.is_json
    data = response.get_json()
    assert 'totalScans' in data
    assert 'totalAlerts' in data
    assert 'systemStatus' in data 


def test_metrics_endpoint(client, app):
    now = datetime.utcnow()
    with app.app_context():
        db.session.add_all([
            Scan(
                scan_type='Full TCP',
                status='complete',
                created_at=now - timedelta(seconds=20),
                completed_at=now,
            ),
            Scan(scan_type='Full TCP', status='failed'),
            Scan(scan_type='Discovery Scan', status='running'),
        ])
        db.session.commit()

    response = client.get('/api/metrics')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'sentinelzero_scans_total 3' in body
    assert 'sentinelzero_scans_active 1' in body
    assert 'sentinelzero_scans_failed_total 1' in body
    assert 'sentinelzero_scans_completed_total 1' in body
    assert 'sentinelzero_scans_failure_rate_ratio' in body
    assert 'sentinelzero_scans_duration_seconds_avg 20.0' in body


def test_request_id_header_round_trip(client):
    response = client.get('/api/ping', headers={'X-Request-ID': 'req-test-123'})
    assert response.status_code == 200
    assert response.headers.get('X-Request-ID') == 'req-test-123'


def test_data_delete_endpoint_scopes(client, app):
    with app.app_context():
        db.session.add(Scan(scan_type='Full TCP', status='complete'))
        db.session.add(Alert(title='A', message='B', severity='high', read=False))
        db.session.commit()

    scans_only = client.post('/api/data/delete', json={'scope': 'scans', 'delete_files': False})
    assert scans_only.status_code == 200
    payload = scans_only.get_json()
    assert payload['status'] == 'success'
    assert payload['summary']['deleted_scans'] == 1
    assert payload['summary']['deleted_alerts'] == 0

    with app.app_context():
        db.session.add(Scan(scan_type='Discovery Scan', status='complete'))
        db.session.commit()

    full = client.post('/api/data/delete', json={'scope': 'all', 'delete_files': False})
    assert full.status_code == 200
    payload = full.get_json()
    assert payload['summary']['deleted_scans'] == 1
    assert payload['summary']['deleted_alerts'] == 1


@pytest.mark.local
def test_sync_scans_reconcile_mode(client):
    response = client.post('/api/sync-scans', json={'mode': 'reconcile_db'})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['mode'] == 'reconcile_db'
    assert 'sync_result' in payload
