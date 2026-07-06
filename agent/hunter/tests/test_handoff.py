from pathlib import Path

from hunter.handoff import HuntReportWriter
from hunter.missions import Mission
from hunter.seed import SeedResult


def _mission(max_hosts: int | None) -> Mission:
    return Mission(
        mission_id="home_inventory",
        objective="test",
        target_network="192.168.68.0/22",
        profile="white",
        executor="local",
        iface="enp6s19",
        max_turns=40,
        parallel_workers=1,
        handoff_scan_type="Discovery Scan",
        handoff_trigger_discovery_scan=False,
        handoff_min_new_hosts=1,
        handoff_max_recommended_hosts=max_hosts,
        allowed_cidrs=["192.168.68.0/22"],
    )


def _seed() -> SeedResult:
    return SeedResult(
        mission_id="home_inventory",
        target_network="192.168.68.0/22",
        registry_hosts=["192.168.68.10"],
        passive_hosts=["192.168.68.10", "192.168.68.11", "192.168.68.12"],
        last_scan_hosts=["192.168.68.10"],
        unknown_in_passive=["192.168.68.11", "192.168.68.12"],
        missing_from_scan=[],
        stale=[],
        last_scan_id=3,
        last_scan_timestamp="2026-05-30T00:00:00Z",
    )


def test_handoff_caps_recommendations_and_prefers_findings(tmp_path: Path):
    writer = HuntReportWriter(
        mission=_mission(max_hosts=2),
        seed_result=_seed(),
        ranked_candidates=[
            {"ip": "192.168.68.11", "score": 5, "reason": "unknown"},
            {"ip": "192.168.68.12", "score": 4, "reason": "missing"},
        ],
        findings=[{"ip": "192.168.68.20", "type": "new_host"}],
        worker_summaries=[],
        reports_dir=tmp_path,
    )

    out = writer.write(no_trigger_scan=True, request_scan=lambda *_: {"status": "unused"})
    report = out["report"]
    assert report["hosts_recommended_for_scan"] == ["192.168.68.20", "192.168.68.11"]
    assert report["hosts_recommended_total"] == 3
    assert report["hosts_recommended_capped"] is True

