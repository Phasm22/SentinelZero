import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app import create_app, db
from src.models import Scan
from src.services.host_context import (
    apply_user_labels,
    build_host_context,
    store_host_context,
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


def test_build_host_context_merges_nmap_and_registry(app, monkeypatch, tmp_path):
    registry = {
        "192.168.68.1": {
            "name": "home-router",
            "role": "router",
            "trust_zone": "home-infrastructure",
            "expected_ports": [80, 443],
        },
    }
    path = tmp_path / "assets.json"
    path.write_text(json.dumps(registry))
    monkeypatch.setenv("SENTINEL_ASSETS_PATH", str(path))
    from src.services import asset_registry
    asset_registry._load_registry.cache_clear()

    monkeypatch.setattr(
        'src.services.host_context.sensor_service.get_latest_collectors',
        lambda db, agent_id: {
            'dhcp_leases': [{
                'ip': '192.168.68.25',
                'hostname': 'living-room-tv',
                'mac': 'aa:bb:cc:dd:ee:01',
                'manufacturer': 'Samsung',
            }],
            'arp_table': [],
        } if agent_id == 'opnsense' else {},
    )
    monkeypatch.setattr(
        'src.services.host_context.sensor_service.get_agent_by_ip',
        lambda db, ip: None,
    )

    with app.app_context():
        scan = Scan(
            scan_type='Full TCP',
            status='complete',
            target_network='192.168.68.0/22',
            hosts_json=json.dumps([
                {
                    'ip': '192.168.68.1',
                    'ports': [{'port': 80, 'service': 'http'}],
                },
                {
                    'ip': '192.168.68.25',
                    'hostnames': ['android-abc'],
                    'ports': [{'port': 8008, 'service': 'http'}],
                },
            ]),
        )
        db.session.add(scan)
        db.session.commit()

        ctx = build_host_context(scan)
        assert ctx['network_label'] == 'Home'
        assert ctx['hosts']['192.168.68.1']['display_name'] == 'home-router'
        assert ctx['hosts']['192.168.68.25']['display_name'] == 'living-room-tv'
        assert 'dhcp' in ctx['hosts']['192.168.68.25']['identification_sources']

        stored = store_host_context(scan.id)
        assert stored['host_count'] == 2
        updated = apply_user_labels(scan.id, {'192.168.68.25': 'Living Room TV'})
        assert updated['hosts']['192.168.68.25']['display_name'] == 'Living Room TV'
        assert updated['hosts']['192.168.68.25']['user_label'] == 'Living Room TV'
