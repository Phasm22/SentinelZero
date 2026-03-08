import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.services.whats_up import WhatsUpMonitor


class FakeProbe:
    def __init__(self):
        self.resolved = {'example.internal': '10.0.0.5'}

    def ping(self, host, timeout=0.5, ports=None):
        return {
            'success': host not in {'172.16.0.254', '10.0.0.9'},
            'method': f'tcp:{(ports or [80])[0]}',
            'response_time': 12.5,
            'error': None if host not in {'172.16.0.254', '10.0.0.9'} else 'timeout',
        }

    def tcp_connect(self, host, port, timeout=1.0):
        success = not (host == '10.0.0.9' and port == 443)
        return {
            'success': success,
            'method': f'tcp:{port}',
            'response_time': 7.1 if success else None,
            'error': None if success else 'connection refused',
        }

    def resolve(self, host):
        return self.resolved.get(host)

    def http_check(self, host, port, path='/', use_https=False, timeout=2.0):
        return {
            'success': True,
            'status_code': 200,
            'response_time': 25.0,
            'error': None,
        }


class FakeSocket:
    def __init__(self):
        self.emitted = []

    def emit(self, event, payload):
        self.emitted.append((event, payload))


def test_whats_up_monitor_builds_snapshot_with_expected_shape():
    monitor = WhatsUpMonitor(
        probe=FakeProbe(),
        loopbacks=[
            {'name': 'Localhost', 'ip': '127.0.0.1', 'interface': 'lo'},
            {'name': 'Sentinel', 'ip': '172.16.0.254', 'interface': 'dummy0'},
        ],
        services=[
            {'name': 'Internal API', 'domain': 'example.internal', 'port': 443, 'type': 'https', 'path': '/health'},
        ],
        infrastructure=[
            {'name': 'Edge VM', 'ip': '10.0.0.9', 'port': 443, 'type': 'https'},
        ],
    )

    snapshot = monitor.collect_snapshot()

    assert snapshot['total_checks'] == 4
    assert snapshot['layers']['loopbacks']['total'] == 2
    assert snapshot['layers']['services']['total'] == 1
    assert snapshot['layers']['infrastructure']['total'] == 1
    assert snapshot['categories']['loopbacks']['items'][0]['status'] == 'up'
    assert snapshot['categories']['loopbacks']['items'][1]['status'] == 'down'
    assert snapshot['categories']['services']['items'][0]['overall_status'] == 'up'
    assert snapshot['categories']['infrastructure']['items'][0]['status'] == 'up'


def test_whats_up_monitor_emits_snapshot_events():
    monitor = WhatsUpMonitor(
        probe=FakeProbe(),
        loopbacks=[{'name': 'Localhost', 'ip': '127.0.0.1', 'interface': 'lo'}],
        services=[],
        infrastructure=[],
    )
    socket = FakeSocket()

    payload = monitor.emit_snapshot(socket, monitor.collect_snapshot())

    emitted_events = [event for event, _ in socket.emitted]
    assert payload['total_checks'] == 1
    assert emitted_events == ['whats_up.snapshot', 'whats_up_update', 'health_update']
