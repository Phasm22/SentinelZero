import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import app as app_module
from app import create_app, db
from src.models import Scan


@pytest.fixture
def app():
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'ENABLE_BACKGROUND_SERVICES': False,
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def socket_client(app, client):
    sio_client = app_module.socketio.test_client(app, flask_test_client=client)
    yield sio_client
    sio_client.disconnect()


def test_scan_socket_flow_emits_events_and_persists_state(app, socket_client):
    with app.app_context():
        runtime = app.extensions['scan_runtime']
        scan = runtime.create_scan('Full TCP', state='queued', message='Queued')
        scan_id = scan.id

    socket_client.emit('scan.subscribe', {'scan_id': scan_id})
    _ = socket_client.get_received()

    with app.app_context():
        runtime = app.extensions['scan_runtime']
        runtime.set_state(scan_id, 'running', 'Scanning')
        runtime.complete_scan(scan_id, 'Scan complete!')

    events = socket_client.get_received()
    names = [event['name'] for event in events]
    assert 'scan.progress' in names
    assert 'scan.completed' in names

    completed_payload = next(event['args'][0] for event in events if event['name'] == 'scan.completed')
    assert completed_payload['scan_id'] == scan_id
    assert completed_payload['state'] == 'complete'

    with app.app_context():
        persisted = db.session.get(Scan, scan_id)
        assert persisted.status == 'complete'


def test_trigger_scan_route_completes_and_snapshot_reflects_final_state(app, client, socket_client):
    class _ImmediateThread:
        def __init__(self, target=None, args=(), kwargs=None, daemon=None):
            self._target = target
            self._args = args
            self._kwargs = kwargs or {}

        def start(self):
            self._target(*self._args, **self._kwargs)

    def fake_scan_worker(scan_id, scan_type, security_settings, socketio, app, target_network, pre_discovery=False):
        with app.app_context():
            runtime = app.extensions['scan_runtime']
            runtime.set_state(scan_id, 'running', 'Halfway')
            scan = runtime.get_scan(scan_id)
            scan.total_hosts = 3
            scan.hosts_up = 2
            db.session.commit()
            runtime.complete_scan(scan_id, 'Done from fake worker')

    with patch('src.routes.scan_routes.threading.Thread', _ImmediateThread), patch(
        'src.routes.scan_routes.run_nmap_scan',
        side_effect=fake_scan_worker,
    ):
        response = client.post('/api/scan', data={'scan_type': 'Full TCP'})

    assert response.status_code == 200
    payload = response.get_json()
    scan_id = payload['scan_id']

    socket_client.emit('scan.subscribe', {'scan_id': scan_id})
    subscribed_events = socket_client.get_received()
    snapshot_event = next(event for event in subscribed_events if event['name'] == 'scan.snapshot')
    snapshot = snapshot_event['args'][0]
    assert snapshot['scan_id'] == scan_id
    assert snapshot['state'] == 'complete'
    assert snapshot['total_hosts'] == 3
    assert snapshot['hosts_up'] == 2

    status = client.get(f'/api/scan-status/{scan_id}')
    assert status.status_code == 200
    status_payload = status.get_json()
    assert status_payload['state'] == 'complete'
