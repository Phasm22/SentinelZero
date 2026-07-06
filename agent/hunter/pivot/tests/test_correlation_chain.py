from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from hunter.pivot.baseline_diff_parse import diff_udp_ports, recommend_baseline_action
from hunter.pivot.opnsense_correlate_parse import recommend_opnsense_action
from hunter.pivot.orchestrator import PivotMissionConfig, run_pivot_mission
from hunter.pivot.sensor_correlate_parse import recommend_sensor_action


def test_recommend_sensor_action():
    assert recommend_sensor_action(has_sensor=True, auth_event_count=2, external_peers=[]) == "escalate"
    assert recommend_sensor_action(has_sensor=True, auth_event_count=0, external_peers=["8.8.8.8"]) == "escalate"
    assert recommend_sensor_action(has_sensor=True, auth_event_count=0, external_peers=[]) == "observe"
    assert recommend_sensor_action(has_sensor=False, auth_event_count=0, external_peers=[]) == "next_scan"


def test_recommend_opnsense_action():
    assert recommend_opnsense_action(has_data=True, ids_alert_count=3) == "escalate"
    assert recommend_opnsense_action(has_data=True, ids_alert_count=0) == "observe"
    assert recommend_opnsense_action(has_data=False, ids_alert_count=0) == "next_scan"


def test_baseline_diff_and_recommend():
    diff = diff_udp_ports(
        [{"port": 1900, "state": "open"}, {"port": 5353, "state": "open"}],
        [{"port": 5353, "state": "open"}, {"port": 554, "state": "open"}],
    )
    assert diff["new_udp_ports"] == [554]
    assert diff["removed_udp_ports"] == [1900]
    assert diff["matched_udp_ports"] == [5353]
    assert recommend_baseline_action(baseline_present=True, new_udp_ports=[554]) == "escalate"
    assert recommend_baseline_action(baseline_present=True, new_udp_ports=[]) == "observe"
    assert recommend_baseline_action(baseline_present=False, new_udp_ports=[]) == "next_scan"


def test_correlation_disabled_by_default():
    # Without enable_correlation, the post-pass must not run (existing behaviour).
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = PivotMissionConfig(
            mission_id="pivot-test-nocorr",
            seed={"ip": "10.99.1.20", "type": "new_port", "scan_id": None, "network_label": "Fixture"},
            allowed_cidrs=["10.99.1.0/24"],
            reports_dir=tmp_path / "reports",
            state_dir=tmp_path / "state",
            target_network="10.99.1.0/24",
            fixture=True,
            allow_active=True,
            max_turns=10,
        )
        result = run_pivot_mission(config)
        assert result["status"] == "done"
        report = json.loads(list((tmp_path / "reports").glob("hunt-pivot-test-nocorr-*.json"))[0].read_text())
        event_types = {e["type"] for e in report["pivot_events"]}
        assert not ({"sensor_correlate", "opnsense_correlate", "baseline_diff"} & event_types)


def test_correlation_post_pass_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        reports = tmp_path / "reports"
        config = PivotMissionConfig(
            mission_id="pivot-test-corr",
            seed={"ip": "10.99.1.20", "type": "new_port", "scan_id": None, "network_label": "Fixture"},
            allowed_cidrs=["10.99.1.0/24"],
            reports_dir=reports,
            state_dir=tmp_path / "state",
            target_network="10.99.1.0/24",
            fixture=True,
            allow_active=True,
            max_turns=10,
            enable_correlation=True,
        )
        result = run_pivot_mission(config)
        assert result["status"] == "done"
        report = json.loads(list(reports.glob("hunt-pivot-test-corr-*.json"))[0].read_text())

        event_types = {e["type"] for e in report["pivot_events"]}
        assert {"sensor_correlate", "opnsense_correlate", "baseline_diff"} <= event_types

        findings = {f["type"]: f for f in report["findings"]}
        assert findings["pivot_sensor_correlation"]["recommended_action"] == "escalate"
        assert findings["pivot_opnsense_correlation"]["recommended_action"] == "escalate"
        assert findings["pivot_opnsense_correlation"]["ids_alert_count"] == 1
        assert findings["pivot_baseline_drift"]["recommended_action"] == "escalate"
        assert findings["pivot_baseline_drift"]["new_udp_ports"] == [554]
