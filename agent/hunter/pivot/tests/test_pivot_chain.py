from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hunter.pivot.event_log import EventLog
from hunter.pivot.orchestrator import PivotMissionConfig, run_pivot_mission
from hunter.pivot.scope import ScopeGuard
from hunter.executors.local import ip_in_allowed


def test_scope_guard_rejects_out_of_scope():
    guard = ScopeGuard(allowed_cidrs=["10.99.1.0/24"])
    assert guard.check_ip("10.99.1.10") is None
    assert guard.check_ip("172.16.0.1") is not None


def test_ip_in_allowed_fixture_cidr():
    assert ip_in_allowed("10.99.1.10", ["10.99.1.0/24"])


def test_event_log_parent_chain():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.sqlite"
        log = EventLog(db)
        e1 = log.append(
            task_id="t1",
            parent_event_id=None,
            ip="10.99.1.10",
            type="nmap_scan",
            description="scan",
            action="nmap_scan",
        )
        e2 = log.append(
            task_id="t2",
            parent_event_id=e1.event_id,
            ip="10.99.1.10",
            type="smb_enum",
            description="enum",
            action="smb_enum",
        )
        events = log.all_events()
        log.close()
        assert len(events) == 2
        assert events[1].parent_event_id == e1.event_id
        assert events[0].seq == 1
        assert events[1].seq == 2


def test_fixture_pivot_chain_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        reports = tmp_path / "reports"
        state = tmp_path / "state"
        config = PivotMissionConfig(
            mission_id="pivot-test-fixture",
            seed={"ip": "10.99.1.10", "type": "new_port", "scan_id": 1, "network_label": "Fixture"},
            allowed_cidrs=["10.99.1.0/24"],
            reports_dir=reports,
            state_dir=state,
            target_network="10.99.1.0/24",
            fixture=True,
            allow_active=True,
            max_turns=10,
        )
        result = run_pivot_mission(config)
        assert result["status"] == "done"
        assert result["event_count"] >= 3
        assert result["findings_count"] >= 1

        status_path = reports / "hunt-pivot-test-fixture.status.json"
        assert status_path.exists()
        status = json.loads(status_path.read_text())
        assert status["state"] == "done"

        report_files = list(reports.glob("hunt-pivot-test-fixture-*.json"))
        assert report_files
        report = json.loads(report_files[0].read_text())
        assert report["mission_type"] == "pivot"
        assert len(report["pivot_events"]) >= 3
        assert report["findings"]

        # Verify causal chain
        events = report["pivot_events"]
        ids = {e["event_id"] for e in events}
        for event in events[1:]:
            parent = event.get("parent_event_id")
            if parent:
                assert parent in ids
