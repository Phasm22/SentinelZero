import os
import sys
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app import create_app, db
from src.models import Scan
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


class _FakeProcess:
    def __init__(self, stdout_lines, returncode=0, pid=4321):
        self.stdout = iter(stdout_lines)
        self.returncode = returncode
        self.pid = pid

    def terminate(self):
        return None

    def kill(self):
        return None

    def wait(self, timeout=None):
        return self.returncode


class _PopenFactory:
    def __init__(self, processes):
        self._processes = list(processes)
        self.calls = []

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        if not self._processes:
            raise AssertionError('No fake processes left to return')
        return self._processes.pop(0)


def _sample_xml_tree():
    xml = """
    <nmaprun>
      <host>
        <status state="up" />
        <address addr="192.168.1.10" addrtype="ipv4" />
        <ports>
          <port protocol="tcp" portid="22">
            <state state="open" />
            <service name="ssh" product="OpenSSH" version="9.0" />
          </port>
        </ports>
      </host>
    </nmaprun>
    """
    return ET.ElementTree(ET.fromstring(xml))


def test_scan_runtime_transitions_emit_scoped_events(app, monkeypatch):
    with app.app_context():
        runtime = app.extensions['scan_runtime']
        emitted = []
        monkeypatch.setattr(runtime.socketio, 'emit', lambda event, payload, room=None: emitted.append((event, room, payload)))

        scan = runtime.create_scan('Full TCP', state='queued', message='Queued')
        assert scan.id is not None

        runtime.append_log(scan.id, 'starting thread')
        runtime.set_state(scan.id, 'running', 10.0, 'Running scan')
        runtime.complete_scan(scan.id, 'Done')

        updated = db.session.get(Scan, scan.id)
        assert updated.status == 'complete'
        assert updated.status_message == 'Done'
        assert any(event == 'scan.log' and room == runtime.scan_room(scan.id) for event, room, _ in emitted)
        assert any(event == 'scan.progress' and room == runtime.scan_room(scan.id) for event, room, _ in emitted)
        assert any(event == 'scan.completed' and room == runtime.scan_room(scan.id) for event, room, _ in emitted)


def test_run_nmap_scan_completes_existing_scan_record(app, monkeypatch):
    with app.app_context():
        runtime = app.extensions['scan_runtime']
        monkeypatch.setattr(runtime.socketio, 'emit', lambda *args, **kwargs: None)
        monkeypatch.setattr(scanner_module, 'generate_and_store_insights', lambda scan_id: [])
        monkeypatch.setattr(scanner_module.shutil, 'which', lambda name: f'/usr/bin/{name}')
        monkeypatch.setattr(scanner_module.os, 'makedirs', lambda *args, **kwargs: None)
        monkeypatch.setattr(scanner_module.os.path, 'exists', lambda path: True)
        monkeypatch.setattr(scanner_module.os.path, 'getsize', lambda path: 2048)
        monkeypatch.setattr(scanner_module.ET, 'parse', lambda path: _sample_xml_tree())

        popen = _PopenFactory([_FakeProcess(['About 42.50% done\n', 'done\n'], returncode=0, pid=9001)])
        monkeypatch.setattr(scanner_module.subprocess, 'Popen', popen)

        scan = runtime.create_scan('Full TCP', state='queued', message='Queued')
        scanner_module.run_nmap_scan(
            scan.id,
            'Full TCP',
            security_settings={
                'vuln_scanning_enabled': False,
                'os_detection_enabled': False,
                'service_detection_enabled': False,
                'aggressive_scanning': False,
            },
            socketio=runtime.socketio,
            app=app,
            target_network='192.168.1.0/24',
        )

        db.session.expire_all()
        refreshed = db.session.get(Scan, scan.id)
        assert refreshed.status == 'complete'
        assert refreshed.status_message == 'Scan complete!'
        assert refreshed.execution_mode == 'normal'
        assert refreshed.process_id == 9001
        assert refreshed.total_hosts == 1
        assert refreshed.open_ports == 1
        assert Scan.query.count() == 1
        assert popen.calls, 'expected subprocess.Popen to be called'


def test_run_nmap_scan_retries_in_degraded_mode_without_new_scan(app, monkeypatch):
    with app.app_context():
        runtime = app.extensions['scan_runtime']
        monkeypatch.setattr(runtime.socketio, 'emit', lambda *args, **kwargs: None)
        monkeypatch.setattr(scanner_module, 'generate_and_store_insights', lambda scan_id: [])
        monkeypatch.setattr(scanner_module.shutil, 'which', lambda name: f'/usr/bin/{name}')
        monkeypatch.setattr(scanner_module.os, 'makedirs', lambda *args, **kwargs: None)
        monkeypatch.setattr(scanner_module.os.path, 'exists', lambda path: True)
        monkeypatch.setattr(scanner_module.os.path, 'getsize', lambda path: 2048)
        monkeypatch.setattr(scanner_module.ET, 'parse', lambda path: _sample_xml_tree())

        first = _FakeProcess(['This scan requires root privileges\n'], returncode=1, pid=1111)
        second = _FakeProcess(['About 88.00% done\n', 'done\n'], returncode=0, pid=2222)
        popen = _PopenFactory([first, second])
        monkeypatch.setattr(scanner_module.subprocess, 'Popen', popen)

        scan = runtime.create_scan('Full TCP', state='queued', message='Queued')
        scanner_module.run_nmap_scan(
            scan.id,
            'Full TCP',
            security_settings={
                'vuln_scanning_enabled': False,
                'os_detection_enabled': False,
                'service_detection_enabled': False,
                'aggressive_scanning': False,
            },
            socketio=runtime.socketio,
            app=app,
            target_network='192.168.1.0/24',
        )

        db.session.expire_all()
        refreshed = db.session.get(Scan, scan.id)
        assert refreshed.status == 'complete'
        assert refreshed.execution_mode == 'degraded'
        assert refreshed.process_id == 2222
        assert Scan.query.count() == 1
        assert len(popen.calls) == 2
