#!/usr/bin/env python3
"""CLI entry for Hunter pivot missions."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from hunter.pivot.orchestrator import PivotMissionConfig, run_pivot_mission


def _reports_dir() -> Path:
    raw = os.environ.get("HUNTER_REPORTS_DIR", str(Path(__file__).parent / "reports"))
    return Path(raw)


def _state_dir() -> Path:
    raw = os.environ.get("HUNTER_STATE_DIR", str(Path(__file__).parent / "state"))
    return Path(raw)


def _parse_seed(raw: str | None, seed_file: str | None) -> dict:
    if seed_file:
        payload = json.loads(Path(seed_file).read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    if raw:
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else {}
    return {}


def _bootstrap_env() -> None:
    os.environ.setdefault("OLLAMA_BASE_URL", "http://192.168.68.202:11434/v1")
    os.environ.setdefault("OLLAMA_MODEL", "qwen2.5:14b")
    os.environ.setdefault("OLLAMA_EMBED_MODEL", "nomic-embed-text")


def main() -> None:
    _bootstrap_env()
    parser = argparse.ArgumentParser(description="SentinelZero Hunter Pivot Engine")
    parser.add_argument("--mission-id", required=True, help="Unique mission identifier")
    parser.add_argument("--seed", help="JSON seed payload")
    parser.add_argument("--seed-file", help="Path to JSON seed file")
    parser.add_argument(
        "--allowed-cidrs",
        default="172.16.0.0/22",
        help="Comma-separated allowed CIDRs",
    )
    parser.add_argument("--target-network", default="172.16.0.0/22")
    parser.add_argument("--iface", default="enp6s18")
    parser.add_argument("--fixture", action="store_true", help="Use fixture runners (no live nmap)")
    parser.add_argument("--allow-active", action="store_true", help="Allow active tools without approval")
    parser.add_argument("--no-correlate", action="store_true",
                        help="Skip the sensor/OPNsense/baseline correlation post-pass")
    parser.add_argument("--max-turns", type=int, default=15)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    seed = _parse_seed(args.seed, args.seed_file)
    if not seed.get("ip"):
        raise SystemExit("Seed must include 'ip'")

    allowed = [c.strip() for c in args.allowed_cidrs.split(",") if c.strip()]
    config = PivotMissionConfig(
        mission_id=args.mission_id,
        seed=seed,
        allowed_cidrs=allowed,
        reports_dir=_reports_dir(),
        state_dir=_state_dir(),
        target_network=args.target_network,
        iface=args.iface,
        max_turns=args.max_turns,
        fixture=args.fixture,
        allow_active=args.allow_active,
        verbose=args.verbose,
        enable_correlation=not args.no_correlate,
    )
    result = run_pivot_mission(config)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        raise SystemExit(130)
