import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.services import hunter_reports


HOME_ASSESS_SAMPLE = {
    "mission_id": "home_assess",
    "target_network": "192.168.68.0/22",
    "executor": "local",
    "iface": "enp6s19",
    "completed_at": "2026-05-30T21:01:28Z",
    "seed_summary": {"passive_hosts": 23, "registry_hosts": 6, "last_scan_hosts": 0, "last_scan_id": None},
    "findings": [
        {"ip": "192.168.68.55", "type": "new_udp_port", "description": "new udp", "udp_ports": [68]},
        {"ip": "192.168.68.57", "type": "lost_udp_port", "description": "lost udp", "udp_ports": [67]},
        {"ip": "192.168.68.57", "type": "iot_observation", "description": "observed", "open_ports": []},
    ],
    "fingerprints": [{"ip": "192.168.68.55", "count": 2}],
    "fingerprint_diffs": [
        {"ip": "192.168.68.58", "type": "new_device", "description": "new device", "udp_ports": [5353]},
    ],
    "baseline_updated": {"updated": True, "count": 10},
    "device_context_summary": {"known": 6, "unknown": 17, "total": 23},
    "hosts_recommended_for_scan": ["192.168.68.55", "192.168.68.57", "192.168.68.58"],
    "hosts_recommended_total": 23,
    "hosts_recommended_capped": True,
    "worker_summaries": ["summary"],
    "scan_triggered": {"status": "skipped", "reason": "no-trigger-scan set"},
}

LAB_SAMPLE = {
    "mission_id": "lab_inventory",
    "target_network": "172.16.0.0/22",
    "executor": "local",
    "iface": "enp6s18",
    "completed_at": "2026-05-30T20:28:42Z",
    "seed_summary": {"passive_hosts": 14, "registry_hosts": 13, "last_scan_hosts": 0, "last_scan_id": None},
    "findings": [
        {"ip": "172.16.0.1", "description": "opnsense found", "open_ports": [{"port": 22, "protocol": "tcp"}]},
    ],
    "hosts_recommended_for_scan": ["172.16.0.1"],
    "hosts_recommended_total": 14,
    "hosts_recommended_capped": False,
    "worker_summaries": [],
    "scan_triggered": {"status": "success", "scan_id": 31},
}

PIVOT_SAMPLE = {
    "mission_id": "pivot-abc123",
    "mission_type": "pivot",
    "target_network": "172.16.0.0/22",
    "executor": "local",
    "iface": "enp6s18",
    "completed_at": "2026-07-03T20:00:00Z",
    "seed_summary": {"seed_ip": "172.16.0.10", "seed_type": "new_port", "scan_id": 42},
    "pivot_events": [
        {
            "event_id": "evt-1",
            "seq": 1,
            "ts": "2026-07-03T19:58:00Z",
            "task_id": "task-a",
            "parent_event_id": None,
            "ip": "172.16.0.10",
            "type": "nmap_scan",
            "description": "nmap found 2 open ports",
            "action": "nmap_scan",
        },
        {
            "event_id": "evt-2",
            "seq": 2,
            "ts": "2026-07-03T19:59:00Z",
            "task_id": "task-b",
            "parent_event_id": "evt-1",
            "ip": "172.16.0.10",
            "type": "smb_enum",
            "description": "smb enum: 2 shares",
            "action": "smb_enum",
        },
    ],
    "findings": [
        {
            "ip": "172.16.0.10",
            "type": "pivot_smb_exposure",
            "description": "smb enum on 172.16.0.10: 2 shares",
            "recommended_action": "observe",
        }
    ],
    "hosts_recommended_for_scan": ["172.16.0.10"],
    "hosts_recommended_total": 1,
    "hosts_recommended_capped": False,
    "worker_summaries": ["SMB pivot complete"],
    "scan_triggered": {"status": "skipped", "reason": "pivot mission"},
}


def test_normalize_report_produces_canonical_sections():
    normalized = hunter_reports.normalize_report(HOME_ASSESS_SAMPLE, report_name="hunt-home_assess-example.json")
    assert set(normalized.keys()) >= {
        "huntRun",
        "huntHost",
        "huntEvent",
        "huntRecommendation",
        "whatChanged",
        "deterministicNarrative",
        "llmContextPack",
    }
    assert normalized["huntRun"]["missionId"] == "home_assess"
    assert normalized["huntRun"]["scanTriggerStatus"] == "skipped"
    assert normalized["whatChanged"]["eventHistogram"]["new_udp_port"] == 1
    assert normalized["whatChanged"]["eventHistogram"]["new_device"] == 1


def test_host_scoring_prefers_now_priority_events():
    normalized = hunter_reports.normalize_report(HOME_ASSESS_SAMPLE, report_name="hunt-home_assess-example.json")
    top = normalized["huntHost"][0]
    assert top["actionPriority"] in {"now", "next_scan"}
    assert top["noveltyScore"] >= 4


def test_build_context_pack_has_must_mention_facts():
    normalized = hunter_reports.normalize_report(HOME_ASSESS_SAMPLE, report_name="hunt-home_assess-example.json")
    context = normalized["llmContextPack"]
    assert "must_mention_facts" in context
    assert any(item.startswith("scan_trigger_status=") for item in context["must_mention_facts"])
    assert context["prompt_contract"]["acceptance_checks"]


def test_normalize_pivot_report_includes_hunt_pivot_chain():
    normalized = hunter_reports.normalize_report(PIVOT_SAMPLE, report_name="hunt-pivot-abc123.json")
    assert "huntPivotChain" in normalized
    chain = normalized["huntPivotChain"]
    assert chain["eventTotal"] == 2
    assert chain["edgeCount"] == 1
    assert chain["depth"] >= 2
    assert normalized["huntRun"]["missionType"] == "pivot"
    assert set(normalized.keys()) >= {
        "huntRun",
        "huntHost",
        "huntEvent",
        "huntRecommendation",
        "whatChanged",
        "deterministicNarrative",
        "llmContextPack",
        "huntPivotChain",
    }


def test_list_missions_reads_status_sidecars(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True)
    seeds_dir = reports_dir / "mission-logs" / "seeds"
    seeds_dir.mkdir(parents=True)
    (reports_dir / "hunt-pivot-live.status.json").write_text(
        json.dumps({
            "mission_id": "pivot-live",
            "state": "running",
            "started_at": "2026-07-03T20:00:00Z",
            "updated_at": "2026-07-03T20:01:00Z",
            "pid": 999999,
            "last_task": "turn 1",
        }),
        encoding="utf-8",
    )
    (seeds_dir / "pivot-live.json").write_text(
        json.dumps({
            "insight_id": "insight-42",
            "ip": "172.16.0.10",
            "type": "new_port",
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv("HUNTER_REPORTS_DIR", str(reports_dir))
    missions = hunter_reports.list_missions(limit=10)
    assert len(missions) == 1
    assert missions[0]["missionId"] == "pivot-live"
    assert missions[0]["state"] in {"running", "stalled"}
    assert missions[0]["insightId"] == "insight-42"
    assert missions[0]["host"] == "172.16.0.10"
    assert missions[0]["type"] == "new_port"


def test_find_blocking_mission_by_insight_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True)
    seeds_dir = reports_dir / "mission-logs" / "seeds"
    seeds_dir.mkdir(parents=True)
    (reports_dir / "hunt-pivot-done.status.json").write_text(
        json.dumps({
            "mission_id": "pivot-done",
            "state": "done",
            "started_at": "2026-07-03T20:00:00Z",
            "updated_at": "2026-07-03T20:05:00Z",
        }),
        encoding="utf-8",
    )
    (seeds_dir / "pivot-done.json").write_text(
        json.dumps({"insight_id": "insight-99", "ip": "172.16.0.20", "type": "new_host"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("HUNTER_REPORTS_DIR", str(reports_dir))
    blocked = hunter_reports.find_blocking_mission({"insight_id": "insight-99", "ip": "172.16.0.20", "type": "new_host"})
    assert blocked is not None
    assert blocked["missionId"] == "pivot-done"
    assert blocked["state"] == "done"
    allowed = hunter_reports.find_blocking_mission({"insight_id": "insight-other", "ip": "172.16.0.30", "type": "new_host"})
    assert allowed is None


def test_read_mission_log_returns_tail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    reports_dir = tmp_path / "reports"
    logs_dir = reports_dir / "mission-logs"
    logs_dir.mkdir(parents=True)
    (logs_dir / "pivot-abc.log").write_text("line one\nline two\n", encoding="utf-8")
    monkeypatch.setenv("HUNTER_REPORTS_DIR", str(reports_dir))
    assert hunter_reports.read_mission_log("pivot-abc") == "line one\nline two\n"
    assert hunter_reports.read_mission_log("missing") is None


def test_hunter_overview_reads_reports_and_baseline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    reports_dir = tmp_path / "reports"
    state_dir = tmp_path / "state"
    reports_dir.mkdir(parents=True)
    state_dir.mkdir(parents=True)

    (reports_dir / "hunt-home_assess-1.json").write_text(json.dumps(HOME_ASSESS_SAMPLE), encoding="utf-8")
    (reports_dir / "hunt-lab_inventory-1.json").write_text(json.dumps(LAB_SAMPLE), encoding="utf-8")
    (state_dir / "iot_fingerprints.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "fingerprints": {
                    "192.168.68.55": {"ip": "192.168.68.55", "observation_count": 2},
                    "192.168.68.57": {"ip": "192.168.68.57", "observation_count": 1},
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("HUNTER_REPORTS_DIR", str(reports_dir))
    monkeypatch.setenv("HUNTER_BASELINE_PATH", str(state_dir / "iot_fingerprints.json"))

    overview = hunter_reports.hunter_overview(limit=10)
    assert overview["meta"]["run_count"] == 2
    assert overview["meta"]["baseline_fingerprint_hosts"] == 2
    assert overview["latest"]["huntRun"]["missionId"] in {"home_assess", "lab_inventory"}


def _write(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def hunter_report_paths(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    baseline = tmp_path / "baseline.json"
    reports.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HUNTER_REPORTS_DIR", str(reports))
    monkeypatch.setenv("HUNTER_BASELINE_PATH", str(baseline))
    return reports, baseline


def test_baseline_status_includes_metadata(hunter_report_paths, tmp_path, monkeypatch):
    reports, baseline = hunter_report_paths
    monkeypatch.setenv("HUNTER_BASELINE_HISTORY_DIR", str(tmp_path / "history"))
    _write(baseline, {"fingerprints": {"aa:bb": {"vendor": "x"}}})
    status = hunter_reports.baseline_status()
    assert status["exists"] is True
    assert status["path_used"].endswith("baseline.json")
    assert status["size_bytes"] > 0
    assert status["sha256"] and len(status["sha256"]) == 64
    assert status["modified_at"] is not None
    assert status["snapshot_count"] == 0


def test_snapshot_baseline_is_idempotent(hunter_report_paths, tmp_path, monkeypatch):
    reports, baseline = hunter_report_paths
    monkeypatch.setenv("HUNTER_BASELINE_HISTORY_DIR", str(tmp_path / "history"))
    _write(baseline, {"fingerprints": {"aa:bb": {"vendor": "x"}}})

    first = hunter_reports.snapshot_baseline()
    assert first["status"] == "snapshotted"
    assert first["snapshot_count"] == 1

    # Unchanged baseline -> no new snapshot
    second = hunter_reports.snapshot_baseline()
    assert second["status"] == "unchanged"
    assert second["snapshot_count"] == 1

    # Changed baseline -> new snapshot
    _write(baseline, {"fingerprints": {"aa:bb": {"vendor": "x"}, "cc:dd": {"vendor": "y"}}})
    third = hunter_reports.snapshot_baseline()
    assert third["status"] == "snapshotted"
    assert third["snapshot_count"] == 2


def test_snapshot_baseline_no_baseline(hunter_report_paths, tmp_path, monkeypatch):
    reports, baseline = hunter_report_paths  # baseline file not written
    monkeypatch.setenv("HUNTER_BASELINE_HISTORY_DIR", str(tmp_path / "history"))
    result = hunter_reports.snapshot_baseline()
    assert result["status"] == "no_baseline"


def test_snapshot_baseline_prunes_to_max(hunter_report_paths, tmp_path, monkeypatch):
    reports, baseline = hunter_report_paths
    monkeypatch.setenv("HUNTER_BASELINE_HISTORY_DIR", str(tmp_path / "history"))
    for i in range(5):
        _write(baseline, {"fingerprints": {f"aa:bb:{i}": {"vendor": "x"}}})
        hunter_reports.snapshot_baseline(max_snapshots=3)
    status = hunter_reports.baseline_status()
    assert status["snapshot_count"] == 3
