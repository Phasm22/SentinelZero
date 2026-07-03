"""Unit tests for scanner timeout and pre-discovery helpers."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app import create_app, db
from src.services import scanner as scanner_module


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


def test_get_scan_timeout_defaults_for_lab():
    os.environ.pop('SCAN_TIMEOUT_SECONDS', None)
    os.environ.pop('SCAN_TIMEOUT_HOME_SECONDS', None)
    os.environ.pop('SCAN_TIMEOUT_IOT_HOME_SECONDS', None)
    assert scanner_module._get_scan_timeout_seconds('full tcp', '172.16.0.0/22', True) == 1800


def test_get_scan_timeout_home_routed():
    os.environ.pop('SCAN_TIMEOUT_HOME_SECONDS', None)
    assert scanner_module._get_scan_timeout_seconds('full tcp', '192.168.68.0/22', False) == 5400


def test_get_scan_timeout_iot_home():
    os.environ.pop('SCAN_TIMEOUT_IOT_HOME_SECONDS', None)
    assert scanner_module._get_scan_timeout_seconds('iot scan', '192.168.68.0/22', False) == 7200


def test_get_scan_timeout_respects_env_override():
    os.environ['SCAN_TIMEOUT_IOT_HOME_SECONDS'] = '9999'
    try:
        assert scanner_module._get_scan_timeout_seconds('iot scan', '192.168.68.0/22', False) == 9999
    finally:
        os.environ.pop('SCAN_TIMEOUT_IOT_HOME_SECONDS', None)


def test_get_scan_timeout_vuln_scripts_default():
    os.environ.pop('SCAN_TIMEOUT_VULN_SECONDS', None)
    assert scanner_module._get_scan_timeout_seconds('vuln scripts', '172.16.0.0/22', True) == 10800


def test_get_open_ports_from_recent_full_tcp(app):
    import json
    from src.models.scan import Scan
    from datetime import datetime

    with app.app_context():
        scan = Scan(
            scan_type='Full TCP',
            status='complete',
            target_network='172.16.0.0/22',
            hosts_json=json.dumps([
                {'ip': '172.16.0.1', 'ports': [{'port': 443, 'protocol': 'tcp'}, {'port': 80, 'protocol': 'tcp'}]},
                {'ip': '172.16.0.9', 'ports': [{'port': 22, 'protocol': 'tcp'}]},
            ]),
            completed_at=datetime.utcnow(),
        )
        db.session.add(scan)
        db.session.commit()

        ports = scanner_module._get_open_ports_from_recent_full_tcp('172.16.0.0/22')
        assert ports == [22, 80, 443]

        spec, source = scanner_module._vuln_scripts_port_spec('172.16.0.0/22')
        assert spec == '22,80,443'
        assert 'latest Full TCP' in source


def test_vuln_scripts_port_spec_falls_back_without_prior_scan(app):
    with app.app_context():
        spec, source = scanner_module._vuln_scripts_port_spec('10.99.0.0/24')
        assert spec == scanner_module._FULL_TCP_PORT_SPEC
        assert 'no recent Full TCP' in source


def test_should_run_pre_discovery_auto_for_routed_iot():
    assert scanner_module._should_run_pre_discovery('iot scan', '192.168.68.0/22', False, False) is True


def test_should_run_pre_discovery_respects_explicit_setting_on_lab():
    assert scanner_module._should_run_pre_discovery('full tcp', '172.16.0.0/22', True, True) is True


def test_should_not_pre_discover_discovery_scan():
    assert scanner_module._should_run_pre_discovery('discovery scan', '192.168.68.0/22', False, True) is False
    assert scanner_module._should_run_pre_discovery('discovery scan', '192.168.68.0/22', False, False) is False
