from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hunter.pivot.runners.asset_expectation_runner import (
    recommend_asset_action,
    run_asset_expectation_check,
)
from hunter.pivot.orchestrator import PivotMissionConfig, run_pivot_mission


ASSETS_FIXTURE = {
    "10.99.1.50": {
        "name": "lab-web",
        "role": "linux-server",
        "trust_zone": "lab",
        "expected_ports": [22, 80],
    },
    "10.99.1.60": {
        "name": "core-monitor",
        "role": "security-monitor",
        "trust_zone": "management",
        "expected_ports": [22, 5000],
    },
}


def _write_assets(tmp_path: Path) -> Path:
    p = tmp_path / "assets.json"
    p.write_text(json.dumps(ASSETS_FIXTURE), encoding="utf-8")
    return p


def _ports(*nums: int) -> list[dict]:
    return [{"port": n, "protocol": "tcp", "service": "x"} for n in nums]


def test_registered_host_extra_port_is_unexpected():
    with tempfile.TemporaryDirectory() as tmp:
        assets = _write_assets(Path(tmp))
        result = run_asset_expectation_check(
            "10.99.1.50", _ports(22, 80, 6379), assets_path=assets
        )
        assert result["registered"] is True
        assert result["unexpected_ports"] == [6379]
        assert result["missing_ports"] == []
        # Unexpected port on a lab host -> corroborate before escalating.
        assert recommend_asset_action(result) == "next_scan"


def test_registered_host_subset_is_observe():
    with tempfile.TemporaryDirectory() as tmp:
        assets = _write_assets(Path(tmp))
        result = run_asset_expectation_check(
            "10.99.1.50", _ports(22), assets_path=assets
        )
        assert result["unexpected_ports"] == []
        assert result["missing_ports"] == [80]
        assert recommend_asset_action(result) == "observe"


def test_unexpected_port_on_management_host_escalates():
    with tempfile.TemporaryDirectory() as tmp:
        assets = _write_assets(Path(tmp))
        result = run_asset_expectation_check(
            "10.99.1.60", _ports(22, 5000, 3389), assets_path=assets
        )
        assert result["trust_zone"] == "management"
        assert result["unexpected_ports"] == [3389]
        assert recommend_asset_action(result) == "escalate"


def test_unregistered_host_escalates():
    with tempfile.TemporaryDirectory() as tmp:
        assets = _write_assets(Path(tmp))
        result = run_asset_expectation_check(
            "10.99.1.99", _ports(22, 6379), assets_path=assets
        )
        assert result["registered"] is False
        assert result["unexpected_ports"] == [22, 6379]
        assert recommend_asset_action(result) == "escalate"


def test_fixture_mode_returns_canned_payload():
    result = run_asset_expectation_check("10.99.1.50", _ports(22), fixture=True)
    assert result["ip"] == "10.99.1.50"
    assert result["unexpected_ports"] == [6379]


def test_fixture_pivot_chain_emits_asset_drift_finding():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        reports = tmp_path / "reports"
        config = PivotMissionConfig(
            mission_id="pivot-test-asset",
            seed={"ip": "10.99.1.10", "type": "new_port", "scan_id": None, "network_label": "Fixture"},
            allowed_cidrs=["10.99.1.0/24"],
            reports_dir=reports,
            state_dir=tmp_path / "state",
            target_network="10.99.1.0/24",
            fixture=True,
            allow_active=True,
            max_turns=10,
        )
        result = run_pivot_mission(config)
        assert result["status"] == "done"

        report = json.loads(list(reports.glob("hunt-pivot-test-asset-*.json"))[0].read_text())
        finding_types = {f["type"] for f in report["findings"]}
        assert "pivot_asset_drift" in finding_types
        assert "asset_expectation_check" in {e["type"] for e in report["pivot_events"]}
        drift = next(f for f in report["findings"] if f["type"] == "pivot_asset_drift")
        assert drift["recommended_action"] in ("observe", "next_scan", "escalate")
