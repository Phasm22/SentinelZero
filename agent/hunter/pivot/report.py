from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_pivot_report(
    *,
    reports_dir: Path,
    mission_id: str,
    seed: dict[str, Any],
    pivot_events: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    worker_summaries: list[str],
    target_network: str,
    iface: str = "enp6s18",
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    iso = now.isoformat().replace("+00:00", "Z")
    seed_ip = str(seed.get("ip") or "")

    report: dict[str, Any] = {
        "mission_id": mission_id,
        "mission_type": "pivot",
        "target_network": target_network,
        "executor": "local",
        "iface": iface,
        "completed_at": iso,
        "seed_summary": {
            "seed_ip": seed_ip,
            "seed_type": seed.get("type"),
            "scan_id": seed.get("scan_id"),
            "network_label": seed.get("network_label"),
        },
        "pivot_events": pivot_events,
        "findings": findings,
        "fingerprints": [],
        "fingerprint_diffs": [],
        "baseline_updated": {"updated": False, "count": 0},
        "device_context_summary": {},
        "hosts_recommended_for_scan": [seed_ip] if seed_ip else [],
        "hosts_recommended_total": 1 if seed_ip else 0,
        "hosts_recommended_capped": False,
        "worker_summaries": worker_summaries,
        "scan_triggered": {"status": "skipped", "reason": "pivot mission — no auto scan trigger"},
    }

    reports_dir.mkdir(parents=True, exist_ok=True)
    filename = f"hunt-{mission_id}-{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path = reports_dir / filename
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return {"status": "ok", "path": str(out_path), "report": report}
