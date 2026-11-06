"""Unit tests for collectors.wifi normalize + query helpers."""
import json
from datetime import datetime

from src.models import SensorAgent, SensorTelemetry
from src.services import sensor_service


def test_normalize_wifi_collector_strips_secrets_and_shapes():
    raw = {
        'aps': [{'bssid': 'aa:bb:cc:dd:ee:01', 'channel': '5g-36', 'rssi_dbm': -50}],
        'clients_summary': {'associated': 3, 'probe_noise_count': 12, 'psk': 'SHOULD_NOT_STORE'},
        'channels': [{'id': '5g-36', 'neighbor_count': 2}],
        'events': [{'event': 'new_client', 'entity': 'wifi_mac:aa:bb:cc:dd:ee:ff@home'}],
        'password': 'nope',
        'source': 'sensor:rf@phasm-t470s',
    }
    out = sensor_service.normalize_wifi_collector(raw)
    assert 'password' not in out
    assert 'psk' not in out.get('clients_summary', {})
    assert out['aps'][0]['bssid'] == 'aa:bb:cc:dd:ee:01'
    assert out['clients_summary']['associated'] == 3
    assert out['source'] == 'sensor:rf@phasm-t470s'
    assert len(json.dumps(out).encode('utf-8')) <= sensor_service._WIFI_MAX_BYTES


def test_normalize_wifi_collector_enforces_size_budget():
    huge = {
        'aps': [{'bssid': f'aa:bb:cc:dd:ee:{i:02x}', 'note': 'x' * 200} for i in range(80)],
        'clients_summary': {'associated': 1},
        'channels': [],
        'events': [{'event': 'noise', 'blob': 'y' * 200} for _ in range(80)],
    }
    out = sensor_service.normalize_wifi_collector(huge)
    assert len(json.dumps(out, separators=(',', ':')).encode('utf-8')) <= sensor_service._WIFI_MAX_BYTES


def test_normalize_wifi_collector_rejects_empty():
    assert sensor_service.normalize_wifi_collector(None) == {}
    assert sensor_service.normalize_wifi_collector([]) == {}
    assert sensor_service.normalize_wifi_collector({}) == {}


def test_get_wifi_context_reads_latest(app):
    with app.app_context():
        from app import db

        db.session.add(SensorAgent(
            agent_id='t470s-rf',
            hostname='phasm-T470s',
            host_ip='192.168.68.111',
            role='wireless',
            tags=json.dumps(['rf', 'passive']),
            last_seen_at=datetime.utcnow(),
        ))
        wifi = {
            'aps': [{'bssid': 'a8:42:a1:00:00:01', 'channel': '2g-6'}],
            'clients_summary': {'associated': 2, 'probe_noise_count': 0, 'unresolved': 0},
            'channels': [{'id': '2g-6', 'busy_pct': 12}],
            'events': [],
        }
        db.session.add(SensorTelemetry(
            agent_id='t470s-rf',
            collected_at=datetime.utcnow(),
            collectors_json=json.dumps({'system': {'cpu_pct': 1.0}, 'wifi': wifi}),
        ))
        db.session.commit()

        ctx = sensor_service.get_wifi_context(db, 't470s-rf')
        assert ctx['wifi']['clients_summary']['associated'] == 2
        assert ctx['wifi']['aps'][0]['bssid'] == 'a8:42:a1:00:00:01'
