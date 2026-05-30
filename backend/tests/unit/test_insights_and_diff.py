import json
import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app import create_app, db
from src.models import Scan
from src.services.diff import compute_scan_diff
from src.models.sensor import SensorAgent, SensorTelemetry
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


def test_generate_and_store_insights_before_complete_status(app):
    """Insights run during postprocessing while status is still running."""
    with app.app_context():
        previous = _scan(
            hosts=[{'ip': '10.0.0.1', 'ports': [{'port': 22, 'service': 'ssh'}]}],
            created_at=datetime.utcnow() - timedelta(days=1),
        )
        current = _scan(
            hosts=[{'ip': '10.0.0.1', 'ports': [{'port': 22, 'service': 'ssh'}, {'port': 443, 'service': 'https'}]}],
            created_at=datetime.utcnow(),
        )
        current.status = 'running'
        db.session.add_all([previous, current])
        db.session.commit()

        stored = generate_and_store_insights(current.id)
        assert len(stored) >= 1
        refreshed = db.session.get(Scan, current.id)
        assert refreshed.insights_json is not None
        analysis = json.loads(refreshed.analysis_json or '{}')
        assert analysis['insights_generation']['count'] == len(stored)


def test_new_port_enrichment_endpoint_and_asset(app, monkeypatch):
    with app.app_context():
        monkeypatch.setattr(
            'src.services.insights.asset_registry.get_asset_context',
            lambda ip, **kwargs: {
                'name': 'proxBig.prox',
                'role': 'proxmox-hypervisor',
                'trust_zone': 'infrastructure',
                'expected_ports': [22, 8006],
            },
        )
        monkeypatch.setattr(
            'src.services.insights.asset_registry.is_expected_port',
            lambda ip, port, **kwargs: port in [22, 8006],
        )

        agent = SensorAgent(
            agent_id='proxbig',
            host_ip='172.16.0.10',
            hostname='proxBig.prox',
            role='proxmox-node',
            tags='["category:endpoint"]',
        )
        db.session.add(agent)

        t0 = datetime.utcnow() - timedelta(minutes=30)
        t1 = datetime.utcnow() - timedelta(minutes=5)
        db.session.add(SensorTelemetry(
            agent_id='proxbig',
            collected_at=t0,
            collectors_json=json.dumps({
                'processes': [{'pid': 100, 'name': 'oldproc'}],
                'connections': [],
            }),
        ))
        db.session.add(SensorTelemetry(
            agent_id='proxbig',
            collected_at=t1,
            collectors_json=json.dumps({
                'processes': [
                    {'pid': 100, 'name': 'oldproc'},
                    {'pid': 9999, 'name': 'proxmox-backup-proxy', 'cmdline': '/usr/bin/proxmox-backup-proxy'},
                ],
                'connections': [
                    {'pid': 9999, 'state': 'LISTEN', 'local_addr': '0.0.0.0:8443'},
                ],
            }),
        ))

        previous = _scan(
            hosts=[{'ip': '172.16.0.10', 'ports': [{'port': 22, 'service': 'ssh'}]}],
            created_at=datetime.utcnow() - timedelta(days=1),
        )
        current = _scan(
            hosts=[{'ip': '172.16.0.10', 'ports': [
                {'port': 22, 'service': 'ssh'},
                {'port': 8443, 'service': 'https-alt'},
            ]}],
            created_at=datetime.utcnow(),
        )
        db.session.add_all([previous, current])
        db.session.commit()

        insights = InsightsGenerator().generate_insights(current)
        new_port = next(i for i in insights if i['type'] == 'new_port')
        assert new_port['details']['unexpected_port'] is True
        assert new_port['details']['asset_context']['role'] == 'proxmox-hypervisor'
        assert new_port['details']['sensor_context']['endpoint']['process_name'] == 'proxmox-backup-proxy'
        assert 'proxmox-backup-proxy' in new_port['message']


def test_service_change_on_stable_port(app):
    with app.app_context():
        previous = _scan(
            hosts=[{'ip': '10.0.0.5', 'ports': [{'port': 443, 'service': 'https', 'version': '1.0'}]}],
            created_at=datetime.utcnow() - timedelta(hours=2),
        )
        current = _scan(
            hosts=[{'ip': '10.0.0.5', 'ports': [{'port': 443, 'service': 'https', 'version': '2.0'}]}],
            created_at=datetime.utcnow(),
        )
        db.session.add_all([previous, current])
        db.session.commit()

        insights = InsightsGenerator().generate_insights(current)
        changes = [i for i in insights if i['type'] == 'service_change']
        assert len(changes) == 1
        assert changes[0]['details']['port'] == 443
        assert changes[0]['details']['previous']['version'] == '1.0'
        assert changes[0]['details']['current']['version'] == '2.0'


def test_vuln_resolved_insight(app):
    with app.app_context():
        previous = _scan(
            vulns=[{'id': 'CVE-OLD', 'host': '10.0.0.2', 'output': 'high severity'}],
            created_at=datetime.utcnow() - timedelta(hours=2),
        )
        current = _scan(
            vulns=[],
            created_at=datetime.utcnow(),
        )
        db.session.add_all([previous, current])
        db.session.commit()

        insights = InsightsGenerator().generate_insights(current)
        resolved = [i for i in insights if i['type'] == 'vuln_resolved']
        assert len(resolved) == 1
        assert resolved[0]['details']['vuln_id'] == 'CVE-OLD'


def test_baseline_inventory_not_new_host_rollup(app, monkeypatch):
    with app.app_context():
        monkeypatch.setattr(
            'src.services.insights.asset_registry.is_in_registry',
            lambda ip: ip == '10.0.0.1',
        )
        scan = _scan(
            hosts=[
                {'ip': '10.0.0.1', 'ports': [{'port': 22}]},
                {'ip': '10.0.0.99', 'ports': [{'port': 80}]},
            ],
        )
        db.session.add(scan)
        db.session.commit()

        insights = InsightsGenerator().generate_insights(scan)
        assert any(i['type'] == 'baseline_inventory' for i in insights)
        assert any(i['type'] == 'registry_gap' for i in insights)
        assert not any(
            i['type'] == 'new_host' and 'hosts' in (i.get('host') or '')
            for i in insights
        )


def test_baseline_inventory_gap_for_missing_registry_hosts(app, monkeypatch):
    with app.app_context():
        monkeypatch.setattr(
            'src.services.insights.asset_registry.is_in_registry',
            lambda ip: True,
        )
        monkeypatch.setattr(
            'src.services.insights.asset_registry.hosts_for_inventory_gap',
            lambda ips, net: ['172.16.0.100', '172.16.0.106'],
        )
        monkeypatch.setattr(
            'src.services.insights.asset_registry.get_asset_context',
            lambda ip, **kw: {'name': f'host-{ip}'},
        )
        scan = _scan(
            hosts=[{'ip': '172.16.0.10', 'ports': [{'port': 22}]}],
        )
        db.session.add(scan)
        db.session.commit()

        insights = InsightsGenerator().generate_insights(scan)
        gap = [i for i in insights if i['type'] == 'inventory_gap']
        assert len(gap) == 1
        assert '172.16.0.100' in gap[0]['details']['ips']


def test_home_baseline_skips_lab_registry_gap(app):
    with app.app_context():
        scan = _scan(
            scan_type='Full TCP',
            hosts=[
                {'ip': '192.168.68.1', 'ports': [{'port': 80}]},
                {'ip': '192.168.68.25', 'ports': [{'port': 443}]},
            ],
        )
        scan.target_network = '192.168.68.0/22'
        db.session.add(scan)
        db.session.commit()

        insights = InsightsGenerator().generate_insights(scan)
        assert any(i['type'] == 'baseline_inventory' for i in insights)
        assert not any(i['type'] == 'registry_gap' for i in insights)


def test_endpoint_security_context_auth_and_services(app):
    from src.services import sensor_service

    with app.app_context():
        db.session.add(SensorAgent(
            agent_id='sec1', host_ip='172.16.0.50', hostname='sec1',
            role='linux-server', tags='["category:endpoint"]',
        ))
        anchor = datetime.utcnow()
        # Two overlapping rows carry duplicate auth tails — must dedup.
        for offset in (8, 2):
            db.session.add(SensorTelemetry(
                agent_id='sec1',
                collected_at=anchor - timedelta(minutes=offset),
                collectors_json=json.dumps({
                    'auth': [
                        {'event': 'ssh_login_fail', 'method': 'password',
                         'user': 'root', 'source': '10.0.0.9', 'ts': 'May 29 10:00:00'},
                        {'event': 'sudo_command', 'user': 'tj',
                         'command': 'systemctl restart x', 'ts': 'May 29 10:01:00'},
                    ],
                    'services': [
                        {'name': 'nginx', 'state': 'active', 'sub_state': 'running'},
                        {'name': 'fail2ban', 'state': 'failed', 'sub_state': 'dead'},
                    ],
                    'connections': [
                        {'local_addr': '0.0.0.0:443', 'remote_addr': None,
                         'state': 'LISTEN', 'pid': 10, 'process': 'nginx'},
                        {'local_addr': '172.16.0.50:443', 'remote_addr': '8.8.8.8:51000',
                         'state': 'ESTABLISHED', 'pid': 10, 'process': 'nginx'},
                    ],
                }),
            ))
        db.session.commit()

        ctx = sensor_service.get_endpoint_security_context(db, 'sec1', anchor_ts=anchor)
        # Deduped: one failure, not two
        assert ctx['ssh_failures']['total'] == 1
        assert ctx['ssh_failures']['by_source'] == {'10.0.0.9': 1}
        assert ctx['failed_services'] == ['fail2ban']
        assert any(a['event'] == 'sudo_command' for a in ctx['auth_changes'])

        conns = sensor_service.get_connections_at(db, 'sec1', anchor_ts=anchor)
        assert conns['established_count'] == 1
        assert conns['listen_count'] == 1
