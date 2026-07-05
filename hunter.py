#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from agent import ASSETS, BASE_URL, _http
from hunter.executors.local import LocalExecutor
from hunter.baseline import get_fingerprint, load_baseline
from hunter.device_context import build_device_context
from hunter.fingerprint import build_fingerprint_findings
from hunter.loop import run_hunter_loop
from hunter.missions import Mission, load_mission, mission_path
from hunter.rank import rank_candidates_with_context
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
    assets = _load_assets()
    baseline = load_baseline()
    seed = build_seed_result(
        mission_id=mission.mission_id,
        target_network=mission.target_network,
        allowed_cidrs=mission.allowed_cidrs,
        assets_path=ASSETS,
        opnsense_latest=opnsense,
        pihole_latest=pihole,
        scans_payload=scans,
    )
    device_context = build_device_context(seed, assets=assets, pihole_latest=pihole, baseline=baseline)
    seed.device_context = device_context
    ranked = [c.to_dict() for c in rank_candidates_with_context(seed, device_context=device_context)]
    executor = LocalExecutor(iface=mission.iface, allowed_cidrs=mission.allowed_cidrs)
    return HunterRuntime(
        mission=mission,
        executor=executor,
        seed_result=seed,
        ranked_candidates=ranked,
        reports_dir=_reports_dir(),
        no_trigger_scan=no_trigger_scan,
        device_context=device_context,
        baseline=baseline,
    )


def _run_assess_probes(runtime: HunterRuntime, *, verbose: bool = False) -> None:
    if runtime.mission.profile != "assess":
        return
    targets = [
        str(item.get("ip") or "").strip()
        for item in runtime.ranked_candidates
        if str(item.get("ip") or "").strip() and int(item.get("score") or 0) >= 4
    ]
    seen: set[str] = set()
    selected: list[str] = []
    for ip in targets:
        if ip in seen:
            continue
        seen.add(ip)
        selected.append(ip)
    for ip in selected[: runtime.mission.assess_max_hosts]:
        probe = runtime.probe_iot_direct(ip)
        if isinstance(probe, dict) and probe.get("error"):
            runtime.worker_summaries.append(f"port_scan_iot skipped for {ip}: {probe['error']}")
            continue
        runtime.probe_results[ip] = probe
        open_ports = list(probe.get("open_ports") or [])
        runtime.fingerprints.append({"ip": ip, "udp_ports": open_ports, "count": int(probe.get("count") or 0)})
        baseline_entry = get_fingerprint(runtime.baseline, ip)
        diffs = build_fingerprint_findings(
            ip=ip,
            probe_result=probe,
            baseline_entry=baseline_entry,
            device_context=runtime.device_context.get(ip),
        )
        runtime.fingerprint_diffs.extend(diffs)
        for diff in diffs:
            runtime.submit_finding(diff)
        runtime.submit_finding({
            "ip": ip,
            "type": "iot_observation",
            "description": f"Observed {len(open_ports)} UDP IoT-profile ports for {ip}.",
            "open_ports": open_ports,
            "profile": "iot",
        })
        if verbose:
            print(f"[hunter] assess probe {ip} count={len(open_ports)}", file=sys.stderr)


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

    _run_assess_probes(runtime, verbose=args.verbose)
    result = run_hunter_loop(runtime, verbose=args.verbose)
    runtime.findings = verify_findings(
        runtime.findings,
        runtime.seed_result,
        _load_assets(),
        runtime.ranked_candidates,
        baseline=runtime.baseline,
        device_context=runtime.device_context,
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

