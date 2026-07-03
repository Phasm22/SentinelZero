import json
import os
import sys
import tempfile
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app import create_app, db, _ensure_database_schema
from src.models import Scan, SensorAgent, SensorTelemetry
from src.services import sensor_service


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'ENABLE_BACKGROUND_SERVICES': False,
    })
    with app.app_context():
        yield app
        db.session.remove()
    os.unlink(db_path)


def test_ensure_database_schema_creates_composite_index(app):
    with app.app_context():
        rows = db.session.execute(
            db.text(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND name='ix_sensor_telemetry_agent_collected'"
            )
        ).fetchall()
        assert len(rows) == 1


def test_get_latest_collectors_returns_most_recent_row(app):
    with app.app_context():
        agent = SensorAgent(agent_id='opnsense', hostname='opnsense')
        db.session.add(agent)
        now = datetime.utcnow()
        for offset in range(5):
            db.session.add(SensorTelemetry(
                agent_id='opnsense',
                collected_at=now - timedelta(minutes=offset),
                collectors_json=json.dumps({'seq': offset}),
            ))
        db.session.commit()

        payload = sensor_service.get_latest_collectors(db, 'opnsense')
        assert payload.get('seq') == 0


def test_get_scan_host_context_returns_pending_without_build(app, monkeypatch):
    build_called = {'count': 0}

    def _fake_build(*args, **kwargs):
        build_called['count'] += 1
        return {}

    monkeypatch.setattr(
        'src.services.host_context.build_host_context',
        _fake_build,
    )

    with app.app_context():
        scan = Scan(
            scan_type='Quick',
            status='complete',
            hosts_json=json.dumps([{'ip': '172.16.0.1', 'ports': []}]),
        )
        db.session.add(scan)
        db.session.commit()
        scan_id = scan.id

    client = app.test_client()
    resp = client.get(f'/api/scans/{scan_id}/host-context')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['host_context'] is None
    assert data['status'] == 'pending'
    assert build_called['count'] == 0


def test_prune_old_telemetry_vacuums_when_rows_deleted(app, monkeypatch):
    vacuum_calls = {'count': 0}

    def _fake_vacuum():
        vacuum_calls['count'] += 1

    monkeypatch.setattr(sensor_service, 'vacuum_database', _fake_vacuum)

    with app.app_context():
        agent = SensorAgent(agent_id='lab-node', hostname='lab')
        db.session.add(agent)
        db.session.add(SensorTelemetry(
            agent_id='lab-node',
            collected_at=datetime.utcnow() - timedelta(days=30),
            collectors_json='{}',
        ))
        db.session.commit()

        deleted = sensor_service.prune_old_telemetry(days=7)
        assert deleted == 1
        assert vacuum_calls['count'] == 1
