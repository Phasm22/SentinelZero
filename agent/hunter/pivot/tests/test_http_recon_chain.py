from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from hunter.pivot.blackboard import Blackboard
from hunter.pivot.event_log import EventLog
from hunter.pivot.http_recon_parse import recommend_http_action
from hunter.pivot.orchestrator import (
    PivotMissionConfig,
    PivotRuntime,
    _fixture_next_action,
    _parse_action,
    _select_http_port,
    run_pivot_mission,
)
from hunter.pivot.scope import ScopeGuard


ALT_PORT_FIXTURE_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="{ip}" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="8080">
        <state state="open"/>
        <service name="http-proxy"/>
      </port>
      <port protocol="tcp" portid="22">
        <state state="open"/>
        <service name="ssh"/>
      </port>
    </ports>
  </host>
</nmaprun>
"""


WEB_ONLY_FIXTURE_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="{ip}" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="80">
        <state state="open"/>
        <service name="http"/>
      </port>
      <port protocol="tcp" portid="22">
        <state state="open"/>
        <service name="ssh"/>
      </port>
    </ports>
  </host>
</nmaprun>
"""


def test_fixture_next_action_chooses_http_recon_when_port_80_open():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        event_log = EventLog(db)
        seed = {"ip": "10.99.1.20", "type": "new_port", "scan_id": None, "network_label": "Fixture"}
        board = Blackboard.from_seed(seed, ["10.99.1.0/24"])
        board.open_ports = [{"port": 80, "protocol": "tcp", "service": "http"}]
        config = PivotMissionConfig(
            mission_id="pivot-http-unit",
            seed=seed,
            allowed_cidrs=["10.99.1.0/24"],
            reports_dir=tmp_path / "reports",
            state_dir=tmp_path / "state",
            target_network="10.99.1.0/24",
            fixture=True,
        )
        runtime = PivotRuntime(
            config=config,
            event_log=event_log,
            board=board,
            scope=ScopeGuard(allowed_cidrs=["10.99.1.0/24"]),
        )
        # Simulate that nmap_scan and the port-agnostic asset drift check already
        # ran, so the fixture driver's next pick is the http_recon service runner.
        event_log.append(
            task_id="t1", parent_event_id=None, ip="10.99.1.20",
            type="nmap_scan", description="scan", action="nmap_scan",
        )
        event_log.append(
            task_id="t2", parent_event_id=None, ip="10.99.1.20",
            type="asset_expectation_check", description="drift", action="asset_expectation_check",
        )

        action = _fixture_next_action(runtime, 1)
        event_log.close()

        assert action == {"action": "http_recon", "ip": "10.99.1.20"}


def test_fixture_pivot_chain_http_recon_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        reports = tmp_path / "reports"
        state = tmp_path / "state"
        config = PivotMissionConfig(
            mission_id="pivot-test-http",
            seed={"ip": "10.99.1.20", "type": "new_port", "scan_id": None, "network_label": "Fixture"},
            allowed_cidrs=["10.99.1.0/24"],
            reports_dir=reports,
            state_dir=state,
            target_network="10.99.1.0/24",
            fixture=True,
            allow_active=True,
            max_turns=10,
        )
        with patch("hunter.pivot.runners.nmap_runner.FIXTURE_NMAP_XML", WEB_ONLY_FIXTURE_XML):
            result = run_pivot_mission(config)

        assert result["status"] == "done"

        report_files = list(reports.glob("hunt-pivot-test-http-*.json"))
        assert report_files
        report = json.loads(report_files[0].read_text())

        event_types = {e["type"] for e in report["pivot_events"]}
        assert "http_recon" in event_types
        assert "smb_enum" not in event_types

        finding_types = {f["type"] for f in report["findings"]}
        assert "pivot_http_exposure" in finding_types
        http_finding = next(f for f in report["findings"] if f["type"] == "pivot_http_exposure")
        assert http_finding["title"] == "Welcome to nginx!"
        assert http_finding["server_header"] == "nginx/1.18.0 (Ubuntu)"


def test_seed_hydration_skips_redundant_scans():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        reports = tmp_path / "reports"
        state = tmp_path / "state"
        config = PivotMissionConfig(
            mission_id="pivot-test-hydration",
            seed={"ip": "10.99.1.30", "type": "correlated", "scan_id": 3, "network_label": "Fixture"},
            allowed_cidrs=["10.99.1.0/24"],
            reports_dir=reports,
            state_dir=state,
            target_network="10.99.1.0/24",
            fixture=True,
            allow_active=True,
            max_turns=10,
            fixture_hydration={
                "open_ports": [
                    {"port": 22, "protocol": "tcp", "service": "ssh", "product": "OpenSSH", "version": "8.9"},
                    {"port": 80, "protocol": "tcp", "service": "http", "product": "nginx", "version": "1.18.0"},
                ],
                "http_recon": {
                    "title": "Welcome to nginx!",
                    "server_header": "nginx/1.18.0 (Ubuntu)",
                    "generator": None,
                    "missing_security_headers": ["Strict-Transport-Security", "Content-Security-Policy"],
                },
                "source_scan_id": 3,
            },
        )
        result = run_pivot_mission(config)

        assert result["status"] == "done"

        report_files = list(reports.glob("hunt-pivot-test-hydration-*.json"))
        assert report_files
        report = json.loads(report_files[0].read_text())

        event_types_in_order = [e["type"] for e in report["pivot_events"]]
        assert event_types_in_order[0] == "seed_hydration"
        assert "nmap_scan" not in event_types_in_order
        # No live http_recon NSE run occurred -- evidence came from the seed scan.
        assert "http_recon" not in event_types_in_order

        # Reused http_recon evidence must terminate to a typed finding, not the
        # generic pivot_recon fallback (the "dead-end at turn 1" regression).
        finding_types = {f["type"] for f in report["findings"]}
        assert "pivot_http_exposure" in finding_types
        assert "pivot_recon" not in finding_types
        http_finding = next(f for f in report["findings"] if f["type"] == "pivot_http_exposure")
        assert http_finding["title"] == "Welcome to nginx!"
        assert http_finding["port"] == 80


def test_parse_action_takes_first_of_multiple_objects():
    # Small models often emit several action objects at once; act on the first
    # rather than dead-ending on an unparseable first-brace..last-brace span.
    text = '{"action": "asset_expectation_check", "ip": "1.2.3.4"}\n{"action": "http_recon", "ip": "1.2.3.4"}'
    assert _parse_action(text) == {"action": "asset_expectation_check", "ip": "1.2.3.4"}


def test_parse_action_ignores_braces_inside_strings():
    text = 'noise {"action": "complete", "summary": "found {nested} braces"} trailing'
    assert _parse_action(text) == {"action": "complete", "summary": "found {nested} braces"}


def test_select_http_port_prefers_high_value_surface():
    # 443 outranks 80; an 8080-only host targets 8080 (not a 80/443 default).
    assert _select_http_port([{"port": 80}, {"port": 443}]) == 443
    assert _select_http_port([{"port": 22}, {"port": 8080}]) == 8080
    assert _select_http_port([{"port": 22}]) is None


def test_recommend_http_action_grades_decision():
    # Admin/login page title -> escalate.
    assert recommend_http_action(
        port=80, title="Proxmox Virtual Environment", server_header="nginx",
        generator=None, missing_security_headers=[],
    ) == "escalate"
    # TLS surface missing both HSTS and CSP -> escalate.
    assert recommend_http_action(
        port=443, title="Welcome", server_header="nginx", generator=None,
        missing_security_headers=["Strict-Transport-Security", "Content-Security-Policy"],
    ) == "escalate"
    # Answered HTTP but nothing identifies it -> next_scan.
    assert recommend_http_action(
        port=8080, title=None, server_header=None, generator=None,
        missing_security_headers=[],
    ) == "next_scan"
    # Identified, benign static content -> observe.
    assert recommend_http_action(
        port=80, title="Welcome to nginx!", server_header="nginx/1.18.0 (Ubuntu)",
        generator=None, missing_security_headers=[],
    ) == "observe"


def test_fixture_pivot_chain_targets_alt_http_port():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        reports = tmp_path / "reports"
        state = tmp_path / "state"
        config = PivotMissionConfig(
            mission_id="pivot-test-altport",
            seed={"ip": "10.99.1.40", "type": "new_port", "scan_id": None, "network_label": "Fixture"},
            allowed_cidrs=["10.99.1.0/24"],
            reports_dir=reports,
            state_dir=state,
            target_network="10.99.1.0/24",
            fixture=True,
            allow_active=True,
            max_turns=10,
        )
        with patch("hunter.pivot.runners.nmap_runner.FIXTURE_NMAP_XML", ALT_PORT_FIXTURE_XML):
            result = run_pivot_mission(config)

        assert result["status"] == "done"
        report = json.loads(list(reports.glob("hunt-pivot-test-altport-*.json"))[0].read_text())
        http_finding = next(f for f in report["findings"] if f["type"] == "pivot_http_exposure")
        # Triage/port-selection must pick 8080, not default to 80/443.
        assert http_finding["port"] == 8080
