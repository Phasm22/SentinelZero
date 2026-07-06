from hunter.seed import SeedResult
from hunter.verify import verify_findings


def _seed() -> SeedResult:
    return SeedResult(
        mission_id="lab_inventory",
        target_network="172.16.0.0/22",
        registry_hosts=["172.16.0.10", "172.16.0.11"],
        passive_hosts=["172.16.0.10"],
        last_scan_hosts=["172.16.0.11"],
        unknown_in_passive=[],
        missing_from_scan=[],
        stale=[],
        last_scan_id=1,
        last_scan_timestamp="2026-05-30T00:00:00Z",
    )


def test_verify_dedupes_and_drops_stale_non_passive():
    findings = [
        {"ip": "172.16.0.11", "type": "registry_gap"},
        {"ip": "172.16.0.11", "type": "registry_gap"},
        {"ip": "172.16.0.10", "type": "new_host"},
    ]
    assets = {
        "172.16.0.11": {"notes": "Normal host"},
        "172.16.0.10": {"notes": "online"},
    }
    out = verify_findings(findings, _seed(), assets, [{"ip": "172.16.0.10", "score": 5}])
    assert [f["ip"] for f in out] == ["172.16.0.10"]


def test_verify_marks_offline_hosts_none_until_online():
    findings = [{"ip": "172.16.0.50", "type": "missing_from_scan"}]
    assets = {"172.16.0.50": {"notes": "currently OFFLINE per DHCP"}}
    out = verify_findings(findings, _seed(), assets, [])
    assert out[0]["recommended_action"] == "none_until_online"

