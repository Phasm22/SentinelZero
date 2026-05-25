import json
import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app import create_app, db
from src.models import Scan
from src.services.insights import InsightsGenerator
from src.services.scan_scope import (
    effective_target_network,
    find_previous_scan,
    infer_target_network_from_hosts,
)


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


def _scan(scan_type='Full TCP', target_network=None, hosts=None, created_at=None):
    return Scan(
        scan_type=scan_type,
        target_network=target_network,
        status='complete',
        hosts_json=json.dumps(hosts or []),
        vulns_json='[]',
        created_at=created_at or datetime.utcnow(),
    )


def test_infer_home_from_hosts():
    hosts = [{'ip': '192.168.68.1'}, {'ip': '192.168.71.25'}]
    assert infer_target_network_from_hosts(hosts) == '192.168.68.0/22'


def test_infer_lab_from_hosts():
    hosts = [{'ip': '172.16.0.10'}, {'ip': '172.16.0.1'}]
    assert infer_target_network_from_hosts(hosts) == '172.16.0.0/22'


def test_find_previous_scan_same_network_only(app):
    with app.app_context():
        lab_old = _scan(
            target_network='172.16.0.0/22',
            hosts=[{'ip': '172.16.0.10'}],
            created_at=datetime.utcnow() - timedelta(days=2),
        )
        home_old = _scan(
            target_network='192.168.68.0/22',
            hosts=[{'ip': '192.168.68.1'}],
            created_at=datetime.utcnow() - timedelta(days=1),
        )
        home_new = _scan(
            target_network='192.168.68.0/22',
            hosts=[{'ip': '192.168.68.1'}, {'ip': '192.168.68.25'}],
        )
        db.session.add_all([lab_old, home_old, home_new])
        db.session.commit()

        prev = find_previous_scan(home_new)
        assert prev is not None
        assert prev.id == home_old.id
        assert effective_target_network(prev) == '192.168.68.0/22'


def test_baseline_per_network_not_per_type(app):
    with app.app_context():
        lab = _scan(
            target_network='172.16.0.0/22',
            hosts=[{'ip': '172.16.0.10', 'ports': [{'port': 22}]}],
            created_at=datetime.utcnow() - timedelta(hours=2),
        )
        home = _scan(
            target_network='192.168.68.0/22',
            hosts=[{'ip': '192.168.68.1', 'ports': [{'port': 80}]}],
        )
        db.session.add_all([lab, home])
        db.session.commit()

        insights = InsightsGenerator().generate_insights(home)
        assert any(i['type'] == 'baseline_inventory' for i in insights)
        assert any(
            '192.168.68' in (i.get('message') or '') or i.get('details', {}).get('target_network') == '192.168.68.0/22'
            for i in insights
            if i['type'] == 'baseline_inventory'
        )
