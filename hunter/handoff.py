from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .missions import Mission
from .seed import SeedResult


@dataclass
class HuntReportWriter:
    mission: Mission
    seed_result: SeedResult
    ranked_candidates: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    worker_summaries: list[str]
    reports_dir: Path

    def _recommended_hosts(self) -> tuple[list[str], int]:
        recommended: list[str] = []
        seen: set[str] = set()
        for item in self.findings:
            ip = str(item.get("ip") or "").strip()
            if not ip or ip in seen:
                continue
            seen.add(ip)
            recommended.append(ip)
        for item in self.ranked_candidates:
            ip = str(item.get("ip") or "").strip()
            if not ip or ip in seen:
                continue
            seen.add(ip)
            recommended.append(ip)

        total = len(recommended)
        cap = self.mission.handoff_max_recommended_hosts
        if cap is not None:
            recommended = recommended[:cap]
        return recommended, total

    def write(
        self,
        *,
        no_trigger_scan: bool,
        request_scan: Callable[[str, str], dict[str, Any]],
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        iso = now.isoformat().replace("+00:00", "Z")
        recommended, recommended_total = self._recommended_hosts()
        recommended_capped = recommended_total > len(recommended)

        report: dict[str, Any] = {
            "mission_id": self.mission.mission_id,
            "target_network": self.mission.target_network,
            "executor": self.mission.executor,
            "iface": self.mission.iface,
            "completed_at": iso,
            "seed_summary": {
                "passive_hosts": len(self.seed_result.passive_hosts),
                "registry_hosts": len(self.seed_result.registry_hosts),
                "last_scan_hosts": len(self.seed_result.last_scan_hosts),
                "last_scan_id": self.seed_result.last_scan_id,
            },
            "findings": self.findings,
            "hosts_recommended_for_scan": recommended,
            "hosts_recommended_total": recommended_total,
            "hosts_recommended_capped": recommended_capped,
            "worker_summaries": self.worker_summaries,
            "scan_triggered": None,
        }

        should_trigger = (
            self.mission.handoff_trigger_discovery_scan
            and len(recommended) >= self.mission.handoff_min_new_hosts
            and not no_trigger_scan
        )
        if should_trigger:
            report["scan_triggered"] = request_scan(self.mission.handoff_scan_type, self.mission.target_network)
        elif no_trigger_scan:
            report["scan_triggered"] = {"status": "skipped", "reason": "no-trigger-scan set"}
        else:
            report["scan_triggered"] = {
                "status": "skipped",
                "reason": f"min_new_hosts not met ({len(recommended)} < {self.mission.handoff_min_new_hosts})",
            }

        self.reports_dir.mkdir(parents=True, exist_ok=True)
        filename = f"hunt-{self.mission.mission_id}-{now.strftime('%Y%m%dT%H%M%SZ')}.json"
        out_path = self.reports_dir / filename
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return {"status": "ok", "path": str(out_path), "report": report}

