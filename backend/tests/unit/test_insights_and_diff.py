import json
import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app import create_app, db
from src.models import Scan
from src.services.diff import compute_scan_diff
from src.services.insights import InsightsGenerator, generate_and_store_insights


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


def _scan(scan_type='Full TCP', hosts=None, vulns=None, created_at=None):
    return Scan(
        scan_type=scan_type,
        status='complete',
        hosts_json=json.dumps(hosts or []),
        vulns_json=json.dumps(vulns or []),
        created_at=created_at or datetime.utcnow(),
    )


def test_compute_scan_diff_baseline(app):
    with app.app_context():
        scan = _scan(hosts=[{'ip': '192.168.1.10', 'ports': [{'port': 22, 'service': 'ssh'}]}], vulns=[{'id': 'CVE-1'}])
        db.session.add(scan)
        db.session.commit()

        diff = compute_scan_diff(scan.id)

        assert diff['baseline'] is True
        assert diff['summary']['new_hosts'] == 1
        assert diff['summary']['new_vulns'] == 1
        assert diff['hosts']['new'] == ['192.168.1.10']


def test_compute_scan_diff_detects_host_port_and_vuln_changes(app):
    with app.app_context():
        older = _scan(
            hosts=[{'ip': '192.168.1.10', 'ports': [{'port': 22, 'service': 'ssh'}]}, {'ip': '192.168.1.11', 'ports': [{'port': 80, 'service': 'http'}]}],
            vulns=[{'id': 'CVE-old', 'host': '192.168.1.10'}],
            created_at=datetime.utcnow() - timedelta(hours=2),
        )
        newer = _scan(
            hosts=[{'ip': '192.168.1.10', 'ports': [{'port': 22, 'service': 'ssh'}, {'port': 443, 'service': 'https'}]}, {'ip': '192.168.1.12', 'ports': [{'port': 8080, 'service': 'http-alt'}]}],
            vulns=[{'id': 'CVE-new', 'host': '192.168.1.12'}],
            created_at=datetime.utcnow() - timedelta(hours=1),
        )
        db.session.add_all([older, newer])
        db.session.commit()

        diff = compute_scan_diff(newer.id)

        assert diff['baseline'] is False
        assert diff['summary']['new_hosts'] == 1
        assert diff['summary']['removed_hosts'] == 1
        assert diff['summary']['new_vulns'] == 1
        assert diff['summary']['resolved_vulns'] == 1
        assert diff['hosts']['new'] == ['192.168.1.12']
        assert diff['hosts']['removed'] == ['192.168.1.11']
        assert diff['hosts']['changed'][0]['ip'] == '192.168.1.10'
        assert diff['hosts']['changed'][0]['new_ports'][0]['port'] == 443


def test_insights_generator_compares_scans_and_persists(app):
    with app.app_context():
        previous = _scan(
            hosts=[{'ip': '192.168.1.10', 'ports': [{'port': 22, 'service': 'ssh'}]}],
            vulns=[{'id': 'CVE-old', 'host': '192.168.1.10', 'output': 'medium disclosure'}],
            created_at=datetime.utcnow() - timedelta(days=1),
        )
        current = _scan(
            hosts=[
                {'ip': '192.168.1.10', 'ports': [{'port': 22, 'service': 'ssh'}, {'port': 443, 'service': 'https'}]},
                {'ip': '192.168.1.20', 'ports': [{'port': 80, 'service': 'http'}]},
            ],
            vulns=[{'id': 'CVE-critical', 'host': '192.168.1.20', 'output': 'critical remote code'}],
            created_at=datetime.utcnow(),
        )
        db.session.add_all([previous, current])
        db.session.commit()

        generator = InsightsGenerator()
        insights = generator.generate_insights(current)
        assert any(item['type'] == 'new_host' for item in insights)
        assert any(item['type'] == 'new_port' for item in insights)
        assert any(item['type'] == 'new_vuln_critical' for item in insights)
        assert all('id' in item and item['scan_id'] == current.id for item in insights)

        stored = generate_and_store_insights(current.id)
        db.session.expire_all()
        refreshed = db.session.get(Scan, current.id)
        assert len(stored) == len(insights)
        assert refreshed.insights_json is not None
        persisted = json.loads(refreshed.insights_json)
        assert len(persisted) == len(stored)
