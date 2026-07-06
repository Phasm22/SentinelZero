from __future__ import annotations

from typing import Any

from .baseline import get_fingerprint
from .seed import SeedResult


def _collect_pihole_ranks(pihole_payload: dict[str, Any]) -> dict[str, int]:
    collectors = pihole_payload.get("collectors") or {}
    block = collectors.get("top_clients") or []
    if isinstance(block, dict):
        rows = block.get("entries") or []
    elif isinstance(block, list):
        rows = block
    else:
        rows = []
    out: dict[str, int] = {}
    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        raw = str((row.get("client") or row.get("ip") or row.get("name") or "")).strip()
        if not raw:
            continue
        ip = raw.split(" ")[0]
        if ip.count(".") == 3 and ip not in out:
            out[ip] = idx
    return out


def _device_hint(ip: str, asset: dict[str, Any], pihole_rank: int | None) -> str:
    name = str(asset.get("name") or "").strip()
    role = str(asset.get("role") or "").strip()
    if name and role:
        return f"{name} ({role})"
    if name:
        return name
    if role:
        return role
    if pihole_rank is not None:
        return f"pihole-client-rank-{pihole_rank}"
    return ip


def build_device_context(
    seed: SeedResult,
    *,
    assets: dict[str, Any],
    pihole_latest: dict[str, Any],
    baseline: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    pihole_rank = _collect_pihole_ranks(pihole_latest)
    universe = set(seed.registry_hosts) | set(seed.passive_hosts) | set(seed.last_scan_hosts)
    universe |= set(seed.unknown_in_passive) | set(seed.missing_from_scan)

    out: dict[str, dict[str, Any]] = {}
    for ip in sorted(universe, key=lambda value: tuple(int(p) for p in value.split("."))):
        asset = assets.get(ip) if isinstance(assets.get(ip), dict) else {}
        fp = get_fingerprint(baseline, ip) or {}
        rank = pihole_rank.get(ip)
        ctx = {
            "ip": ip,
            "in_registry": ip in seed.registry_hosts,
            "in_passive": ip in seed.passive_hosts,
            "in_last_scan": ip in seed.last_scan_hosts,
            "name": asset.get("name"),
            "role": asset.get("role"),
            "trust_zone": asset.get("trust_zone"),
            "expected_ports": list(asset.get("expected_ports") or []),
            "expected_udp_ports": list(asset.get("expected_udp_ports") or []),
            "notes": asset.get("notes"),
            "pihole_seen": rank is not None,
            "pihole_rank": rank,
            "baseline_udp_ports": [int(x.get("port")) for x in (fp.get("udp_ports") or []) if isinstance(x, dict)],
            "baseline_entry": fp if fp else None,
        }
        ctx["device_hint"] = _device_hint(ip, asset, rank)
        out[ip] = ctx
    return out
