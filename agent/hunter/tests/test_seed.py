import json
from pathlib import Path

from hunter.seed import build_seed_result


def test_seed_builds_passive_and_gap_sets(tmp_path: Path):
    assets = {
        "172.16.0.10": {"name": "proxbig"},
        "172.16.0.11": {"name": "yin"},
    }
    assets_path = tmp_path / "assets.json"
    assets_path.write_text(json.dumps(assets), encoding="utf-8")

    opnsense = {
        "collectors": {
            "arp_table": {"entries": [{"ip": "172.16.0.10"}, {"ip": "172.16.0.184"}]},
            "dhcp_leases": {"entries": [{"ip": "172.16.0.11"}]},
        }
    }
    pihole = {"collectors": {"top_clients": {"entries": [{"client": "172.16.0.184"}]}}}
    scans = {
        "scans": [
            {
                "id": 2,
                "status": "complete",
                "target_network": "172.16.0.0/22",
                "completed_at": "2026-05-30T01:00:00Z",
                "hosts": [{"ip": "172.16.0.10"}],
            }
        ]
    }

    seed = build_seed_result(
        mission_id="lab_inventory",
        target_network="172.16.0.0/22",
        allowed_cidrs=["172.16.0.0/22"],
        assets_path=assets_path,
        opnsense_latest=opnsense,
        pihole_latest=pihole,
        scans_payload=scans,
    )
    assert seed.unknown_in_passive == ["172.16.0.184"]
    assert seed.missing_from_scan == ["172.16.0.11"]

