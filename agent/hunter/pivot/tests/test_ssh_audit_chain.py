from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from hunter.pivot.blackboard import Blackboard
from hunter.pivot.event_log import EventLog
from hunter.pivot.orchestrator import (
    PivotMissionConfig,
    PivotRuntime,
    _fixture_next_action,
    run_pivot_mission,
)
from hunter.pivot.runners.ssh_audit_runner import FIXTURE_SSH_AUDIT_XML, parse_ssh_audit_xml
from hunter.pivot.scope import ScopeGuard
from hunter.pivot.ssh_audit_parse import parse_ssh_scripts, recommend_ssh_action


# A 22-only host so the fixture driver unambiguously selects ssh_audit.
SSH_ONLY_FIXTURE_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="{ip}" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="22">
        <state state="open"/>
        <service name="ssh"/>
      </port>
    </ports>
  </host>
</nmaprun>
"""


_MODERN_ALGOS = (
    "\n  kex_algorithms: (2)\n      curve25519-sha256\n      diffie-hellman-group16-sha512\n"
    "  server_host_key_algorithms: (2)\n      ssh-ed25519\n      rsa-sha2-512\n"
    "  encryption_algorithms: (2)\n      chacha20-poly1305@openssh.com\n      aes256-ctr\n"
    "  mac_algorithms: (2)\n      hmac-sha2-256\n      hmac-sha2-512\n"
)
_WEAK_ALGOS = (
    "\n  kex_algorithms: (2)\n      curve25519-sha256\n      diffie-hellman-group14-sha1\n"
    "  server_host_key_algorithms: (2)\n      ssh-ed25519\n      ssh-rsa\n"
    "  encryption_algorithms: (2)\n      aes256-ctr\n      aes256-cbc\n"
    "  mac_algorithms: (2)\n      hmac-sha2-256\n      hmac-md5\n"
)
_HOSTKEYS = "\n  256 SHA256:abc (ED25519)\n  3072 SHA256:def (RSA)"


def test_parse_ssh_scripts_modern():
    fields = parse_ssh_scripts({"ssh2-enum-algos": _MODERN_ALGOS, "ssh-hostkey": _HOSTKEYS})
    assert fields["kex_algorithms"] == ["curve25519-sha256", "diffie-hellman-group16-sha512"]
    assert fields["encryption_algorithms"] == ["chacha20-poly1305@openssh.com", "aes256-ctr"]
    assert fields["host_keys"] == [
        {"bits": 256, "fingerprint": "SHA256:abc", "type": "ED25519"},
        {"bits": 3072, "fingerprint": "SHA256:def", "type": "RSA"},
    ]
    assert fields["weak_kex"] == []
    assert fields["weak_ciphers"] == []
    assert fields["weak_macs"] == []
    assert fields["weak_host_key_algos"] == []
    assert fields["algos_parsed"] is True


def test_parse_ssh_scripts_weak():
    fields = parse_ssh_scripts({"ssh2-enum-algos": _WEAK_ALGOS})
    assert fields["weak_kex"] == ["diffie-hellman-group14-sha1"]
    assert fields["weak_ciphers"] == ["aes256-cbc"]
    assert fields["weak_macs"] == ["hmac-md5"]
    assert fields["weak_host_key_algos"] == ["ssh-rsa"]


def test_recommend_ssh_action_grades_decision():
    # Any weak class -> escalate.
    assert recommend_ssh_action(
        weak_kex=["diffie-hellman-group14-sha1"], weak_ciphers=[], weak_macs=[],
        weak_host_key_algos=[], algos_parsed=True,
    ) == "escalate"
    assert recommend_ssh_action(
        weak_kex=[], weak_ciphers=["aes256-cbc"], weak_macs=[], weak_host_key_algos=[],
        algos_parsed=True,
    ) == "escalate"
    # No algorithms parsed -> next_scan.
    assert recommend_ssh_action(
        weak_kex=[], weak_ciphers=[], weak_macs=[], weak_host_key_algos=[], algos_parsed=False,
    ) == "next_scan"
    # Modern only -> observe.
    assert recommend_ssh_action(
        weak_kex=[], weak_ciphers=[], weak_macs=[], weak_host_key_algos=[], algos_parsed=True,
    ) == "observe"


def test_parse_ssh_audit_xml_fixture_shape():
    recon = parse_ssh_audit_xml(
        FIXTURE_SSH_AUDIT_XML.format(ip="10.99.1.70", port=22), "10.99.1.70", 22
    )
    # Fixture is seeded with legacy cipher + kex to exercise escalate.
    assert recon["weak_kex"] == ["diffie-hellman-group14-sha1"]
    assert recon["weak_ciphers"] == ["aes256-cbc"]
    assert recon["host_keys"][0]["type"] == "ED25519"


def test_fixture_next_action_chooses_ssh_audit_when_22_open():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        event_log = EventLog(tmp_path / "test.sqlite")
        seed = {"ip": "10.99.1.70", "type": "new_port", "scan_id": None, "network_label": "Fixture"}
        board = Blackboard.from_seed(seed, ["10.99.1.0/24"])
        board.open_ports = [{"port": 22, "protocol": "tcp", "service": "ssh"}]
        config = PivotMissionConfig(
            mission_id="pivot-ssh-unit",
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
        event_log.append(
            task_id="t1", parent_event_id=None, ip="10.99.1.70",
            type="nmap_scan", description="scan", action="nmap_scan",
        )
        event_log.append(
            task_id="t2", parent_event_id=None, ip="10.99.1.70",
            type="asset_expectation_check", description="drift", action="asset_expectation_check",
        )

        action = _fixture_next_action(runtime, 1)
        event_log.close()

        assert action == {"action": "ssh_audit", "ip": "10.99.1.70"}


def test_fixture_pivot_chain_ssh_audit_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        reports = tmp_path / "reports"
        state = tmp_path / "state"
        config = PivotMissionConfig(
            mission_id="pivot-test-ssh",
            seed={"ip": "10.99.1.70", "type": "new_port", "scan_id": None, "network_label": "Fixture"},
            allowed_cidrs=["10.99.1.0/24"],
            reports_dir=reports,
            state_dir=state,
            target_network="10.99.1.0/24",
            fixture=True,
            allow_active=True,
            max_turns=10,
        )
        with patch("hunter.pivot.runners.nmap_runner.FIXTURE_NMAP_XML", SSH_ONLY_FIXTURE_XML):
            result = run_pivot_mission(config)

        assert result["status"] == "done"
        report = json.loads(list(reports.glob("hunt-pivot-test-ssh-*.json"))[0].read_text())

        event_types = {e["type"] for e in report["pivot_events"]}
        assert "ssh_audit" in event_types
        assert "http_recon" not in event_types

        finding_types = {f["type"] for f in report["findings"]}
        assert "pivot_ssh_posture" in finding_types
        ssh_finding = next(f for f in report["findings"] if f["type"] == "pivot_ssh_posture")
        assert ssh_finding["port"] == 22
        # Fixture seeds a legacy cipher/kex -> escalate.
        assert ssh_finding["recommended_action"] == "escalate"
        assert ssh_finding["weak_ciphers"] == ["aes256-cbc"]


def test_seed_hydration_ssh_skips_redundant_scan():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        reports = tmp_path / "reports"
        state = tmp_path / "state"
        config = PivotMissionConfig(
            mission_id="pivot-test-ssh-hydration",
            seed={"ip": "10.99.1.80", "type": "correlated", "scan_id": 7, "network_label": "Fixture"},
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
                ],
                "http_recon": None,
                "tls_recon": None,
                "ssh_audit": parse_ssh_scripts({"ssh2-enum-algos": _MODERN_ALGOS, "ssh-hostkey": _HOSTKEYS}),
                "source_scan_id": 7,
            },
        )
        result = run_pivot_mission(config)

        assert result["status"] == "done"
        report = json.loads(list(reports.glob("hunt-pivot-test-ssh-hydration-*.json"))[0].read_text())

        event_types_in_order = [e["type"] for e in report["pivot_events"]]
        assert event_types_in_order[0] == "seed_hydration"
        assert "nmap_scan" not in event_types_in_order
        assert "ssh_audit" not in event_types_in_order
        assert "ssh_posture" in event_types_in_order

        finding_types = {f["type"] for f in report["findings"]}
        assert "pivot_ssh_posture" in finding_types
        assert "pivot_recon" not in finding_types
        ssh_finding = next(f for f in report["findings"] if f["type"] == "pivot_ssh_posture")
        # Modern algorithms hydrated -> observe.
        assert ssh_finding["recommended_action"] == "observe"
