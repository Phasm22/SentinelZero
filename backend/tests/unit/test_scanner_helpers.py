"""Unit tests for scanner timeout and pre-discovery helpers."""
import os

from src.services import scanner as scanner_module


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


def test_should_run_pre_discovery_auto_for_routed_iot():
    assert scanner_module._should_run_pre_discovery('iot scan', '192.168.68.0/22', False, False) is True


def test_should_run_pre_discovery_respects_explicit_setting_on_lab():
    assert scanner_module._should_run_pre_discovery('full tcp', '172.16.0.0/22', True, True) is True


def test_should_not_pre_discover_discovery_scan():
    assert scanner_module._should_run_pre_discovery('discovery scan', '192.168.68.0/22', False, True) is False
    assert scanner_module._should_run_pre_discovery('discovery scan', '192.168.68.0/22', False, False) is False
