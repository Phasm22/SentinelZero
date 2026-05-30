#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from agent import ASSETS, BASE_URL, _http
from hunter.executors.local import LocalExecutor
from hunter.loop import run_hunter_loop
from hunter.missions import Mission, load_mission, mission_path
from hunter.rank import rank_candidates
from hunter.seed import build_seed_result
from hunter.tools import HunterRuntime
from hunter.verify import verify_findings


def _pihole_source_for_mission(mission: Mission) -> str:
    return "pihole-lab" if mission.target_network.startswith("172.16.") else "pihole-home"


def _fetch_seed_sources(mission: Mission) -> tuple[dict, dict, dict]:
    opn = _http.get(f"{BASE_URL}/api/sensor/latest/opnsense", timeout=15)
    opn.raise_for_status()

    pihole = _http.get(f"{BASE_URL}/api/sensor/latest/{_pihole_source_for_mission(mission)}", timeout=15)
    pihole.raise_for_status()

    scans = _http.get(f"{BASE_URL}/api/scans", timeout=20)
    scans.raise_for_status()
    return opn.json(), pihole.json(), scans.json()


def _reports_dir() -> Path:
    raw = os.environ.get("HUNTER_REPORTS_DIR", str(Path(__file__).parent / "reports"))
    return Path(raw)


def _load_assets() -> dict:
    try:
        return json.loads(ASSETS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _build_runtime(mission: Mission, *, no_trigger_scan: bool) -> HunterRuntime:
    opnsense, pihole, scans = _fetch_seed_sources(mission)
    seed = build_seed_result(
        mission_id=mission.mission_id,
        target_network=mission.target_network,
        allowed_cidrs=mission.allowed_cidrs,
        assets_path=ASSETS,
        opnsense_latest=opnsense,
        pihole_latest=pihole,
        scans_payload=scans,
    )
    ranked = [c.to_dict() for c in rank_candidates(seed)]
    executor = LocalExecutor(iface=mission.iface, allowed_cidrs=mission.allowed_cidrs)
    return HunterRuntime(
        mission=mission,
        executor=executor,
        seed_result=seed,
        ranked_candidates=ranked,
        reports_dir=_reports_dir(),
        no_trigger_scan=no_trigger_scan,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="SentinelZero Hunter Agent")
    parser.add_argument("--mission", required=True, help="Mission name (without .yaml) or mission YAML filename")
    parser.add_argument("--seed-only", action="store_true", help="Run deterministic seed/rank only")
    parser.add_argument("--no-trigger-scan", action="store_true", help="Do not POST /api/scan on handoff")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    mission_dir = Path(__file__).parent / "hunter" / "missions"
    mission_file = mission_path(mission_dir, args.mission)
    if not mission_file.exists():
        raise SystemExit(f"Mission file not found: {mission_file}")
    mission = load_mission(mission_file)

    runtime = _build_runtime(mission, no_trigger_scan=args.no_trigger_scan)
    if args.seed_only:
        output = {
            "mission": mission.mission_id,
            "seed": runtime.seed_result.to_dict(),
            "ranked_candidates": runtime.ranked_candidates,
        }
        print(json.dumps(output, indent=2))
        return

    result = run_hunter_loop(runtime, verbose=args.verbose)
    runtime.findings = verify_findings(
        runtime.findings,
        runtime.seed_result,
        _load_assets(),
        runtime.ranked_candidates,
    )
    if not isinstance(result, dict):
        result = {"status": "unknown", "raw": str(result)}
    result["finalize_result"] = runtime.finalize_hunt_report()
    result["auto_finalized"] = not bool(result.get("finalize_requested"))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        raise SystemExit(130)

