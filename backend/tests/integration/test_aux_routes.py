import json
import os
import sys
from unittest.mock import mock_open, patch

import pytest
from flask import Flask

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app import create_app, db
from src.config.database import init_db
from src.routes.schedule_routes import create_schedule_blueprint
from src.models import Scan
from src.services.scan_runtime import ScanRuntime


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


def test_whatsup_routes_return_monitor_snapshot(client):
    snapshot = {
        'overall_status': 'healthy',
        'health_percentage': 100.0,
        'total_items': 3,
        'up_items': 3,
        'down_items': 0,
        'total_up': 3,
        'total_checks': 3,
        'timestamp': '2026-03-08T00:00:00',
        'last_update': '2026-03-08T00:00:00',
        'layers': {
            'loopbacks': {'total': 1, 'up': 1},
            'services': {'total': 1, 'up': 1},
            'infrastructure': {'total': 1, 'up': 1},
        },
        'categories': {
            'loopbacks': {'total': 1, 'up': 1, 'items': [{'name': 'Localhost', 'status': 'up'}]},
            'services': {'total': 1, 'up': 1, 'items': [{'name': 'DNS', 'overall_status': 'up'}]},
            'infrastructure': {'total': 1, 'up': 1, 'items': [{'name': 'Gateway', 'status': 'up'}]},
        },
    }

    with patch('src.routes.whatsup_routes.get_summary_data', return_value=snapshot), \
         patch('src.routes.whatsup_routes.get_loopbacks_data', return_value=snapshot['categories']['loopbacks']['items']), \
         patch('src.routes.whatsup_routes.get_services_data', return_value=snapshot['categories']['services']['items']), \
         patch('src.routes.whatsup_routes.get_infrastructure_data', return_value=snapshot['categories']['infrastructure']['items']):
        summary = client.get('/api/whatsup/summary')
        loopbacks = client.get('/api/whatsup/loopbacks')
        services = client.get('/api/whatsup/services')
        infrastructure = client.get('/api/whatsup/infrastructure')

    assert summary.status_code == 200
    assert summary.get_json()['overall_status'] == 'healthy'
    assert loopbacks.get_json()['loopbacks'][0]['name'] == 'Localhost'
    assert services.get_json()['services'][0]['name'] == 'DNS'
    assert infrastructure.get_json()['infrastructure'][0]['name'] == 'Gateway'


def test_insights_routes_support_filters_and_mutation(client, app):
    with app.app_context():
        old_scan = Scan(
            scan_type='Full TCP',
            status='complete',
            insights_json=json.dumps([
                {'id': 'a', 'type': 'new_host', 'priority': 60, 'timestamp': '2026-03-07T00:00:00', 'is_read': False},
                {'id': 'b', 'type': 'new_port', 'priority': 50, 'timestamp': '2026-03-07T00:01:00', 'is_read': False},
            ]),
        )
        db.session.add(old_scan)
        db.session.commit()
        scan_id = old_scan.id

    response = client.get('/api/insights?type=new_host&priority_min=50&unread_only=true')
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['summary']['total'] == 1
    assert payload['insights'][0]['id'] == 'a'

    scan_response = client.get(f'/api/insights/scan/{scan_id}')
    assert scan_response.status_code == 200
    assert scan_response.get_json()['insights'][0]['scan_type'] == 'Full TCP'

    mark_read = client.post('/api/insights/mark-read', json={'insight_ids': ['a']})
    assert mark_read.status_code == 200
    assert mark_read.get_json()['updated_count'] == 1

    clear_old = client.post('/api/insights/clear-old', json={'days': 0})
    assert clear_old.status_code == 200
    assert clear_old.get_json()['cleared_count'] == 1


def test_diff_route_returns_baseline_and_404(client, app):
    with app.app_context():
        scan = Scan(
            scan_type='Full TCP',
            status='complete',
            hosts_json=json.dumps([{'ip': '192.168.1.10', 'ports': [{'port': 22, 'service': 'ssh'}]}]),
            vulns_json=json.dumps([]),
        )
        db.session.add(scan)
        db.session.commit()
        scan_id = scan.id

    missing = client.get('/api/scan-diff/999')
    assert missing.status_code == 404

    baseline = client.get(f'/api/scan-diff/{scan_id}')
    assert baseline.status_code == 200
    assert baseline.get_json()['baseline'] is True


class FakeScheduler:
    def __init__(self):
        self.jobs = []
        self.removed = []

    def get_jobs(self):
        return list(self.jobs)

    def remove_job(self, job_id):
        self.removed.append(job_id)
        self.jobs = [job for job in self.jobs if job.id != job_id]

    def add_job(self, func, trigger, id, name):
        job = type('Job', (), {'id': id, 'name': name, 'func': func, 'trigger': trigger})
        self.jobs.append(job)
        return job


class FakeSocketIO:
    def emit(self, *args, **kwargs):
        return None


def test_scheduled_scan_route_registers_job_and_executes_wrapper(tmp_path):
    app = Flask(__name__)
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SECRET_KEY': 'test',
    })
    db_local = init_db(app)
    scheduler = FakeScheduler()
    runtime = None
    socketio = FakeSocketIO()

    with app.app_context():
        db_local.create_all()
        runtime = ScanRuntime(db_local, socketio)
        app.extensions['scan_runtime'] = runtime
        app.register_blueprint(create_schedule_blueprint(db_local, socketio, scheduler), url_prefix='/api')

    client = app.test_client()
    payload = [{
        'enabled': True,
        'scanType': 'Discovery Scan',
        'minute': '0',
        'hour': '1',
        'day': '*',
        'month': '*',
        'dayOfWeek': '*',
        'targetNetwork': '192.168.1.0/24',
    }]

    mocked_open = mock_open()
    with patch('src.routes.schedule_routes.open', mocked_open), \
         patch('src.services.scanner.run_nmap_scan') as mock_run:
        response = client.post('/api/scheduled-scans', json=payload)
        assert response.status_code == 200
        assert len(scheduler.jobs) == 1

        with app.app_context():
            scheduler.jobs[0].func()
            created = Scan.query.one()
            assert created.source == 'scheduled'
            mock_run.assert_called_once()
            assert mock_run.call_args.args[0] == created.id
            assert mock_run.call_args.args[1] == 'Discovery Scan'
