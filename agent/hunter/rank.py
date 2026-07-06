from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .seed import SeedResult


@dataclass
class Candidate:
    ip: str
    score: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"ip": self.ip, "score": self.score, "reason": self.reason}


def rank_candidates(seed: SeedResult) -> list[Candidate]:
    return rank_candidates_with_context(seed, device_context=seed.device_context)


def _is_home_network(cidr: str) -> bool:
    return cidr.startswith("192.168.")


def _baseline_stale(last_seen: str | None, *, days: int = 7) -> bool:
    if not last_seen:
        return True
    try:
        dt = datetime.fromisoformat(str(last_seen).replace("Z", "+00:00"))
    except Exception:
        return True
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt < datetime.now(timezone.utc) - timedelta(days=days)


def rank_candidates_with_context(
    seed: SeedResult,
    *,
    device_context: dict[str, dict[str, Any]] | None = None,
) -> list[Candidate]:
    out: dict[str, Candidate] = {}
    ctx_map = device_context or {}
    home_mode = _is_home_network(seed.target_network)

    for ip in seed.unknown_in_passive:
        out[ip] = Candidate(
            ip=ip,
            score=6 if home_mode else 5,
            reason="passive_seen_not_in_registry",
        )

    for ip in seed.missing_from_scan:
        current = out.get(ip)
        candidate = Candidate(ip=ip, score=4, reason="in_registry_missing_from_last_scan")
        if current is None or candidate.score > current.score:
            out[ip] = candidate

    for ip in seed.stale:
        current = out.get(ip)
        candidate = Candidate(ip=ip, score=2, reason="scan_data_stale")
        if current is None or candidate.score > current.score:
            out[ip] = candidate

    if home_mode:
        candidate_pool = set(seed.passive_hosts) | set(seed.registry_hosts) | set(seed.unknown_in_passive)
        for ip in candidate_pool:
            ctx = ctx_map.get(ip) or {}
            role = str(ctx.get("role") or "")
            expected_udp_ports = list(ctx.get("expected_udp_ports") or [])
            baseline_entry = ctx.get("baseline_entry") or {}
            baseline_last_seen = str(baseline_entry.get("last_seen") or "")
            current = out.get(ip)

            if "iot" in role:
                candidate = Candidate(ip=ip, score=5, reason="iot_role_target")
                if current is None or candidate.score > current.score:
                    out[ip] = candidate
                    current = candidate

            if expected_udp_ports and not (ctx.get("baseline_udp_ports") or []):
                candidate = Candidate(ip=ip, score=5, reason="expected_udp_needs_baseline")
                if current is None or candidate.score > current.score:
                    out[ip] = candidate
                    current = candidate

            if baseline_entry and _baseline_stale(baseline_last_seen):
                candidate = Candidate(ip=ip, score=4, reason="iot_baseline_stale")
                if current is None or candidate.score > current.score:
                    out[ip] = candidate

    ranked = sorted(out.values(), key=lambda c: (-c.score, tuple(int(p) for p in c.ip.split("."))))
    return ranked

