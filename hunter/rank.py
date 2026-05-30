from __future__ import annotations

from dataclasses import dataclass
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
    out: dict[str, Candidate] = {}

    for ip in seed.unknown_in_passive:
        out[ip] = Candidate(ip=ip, score=5, reason="passive_seen_not_in_registry")

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

    ranked = sorted(out.values(), key=lambda c: (-c.score, tuple(int(p) for p in c.ip.split("."))))
    return ranked

