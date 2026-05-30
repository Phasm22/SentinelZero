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

