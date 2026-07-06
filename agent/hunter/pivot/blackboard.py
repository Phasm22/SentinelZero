from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .event_log import EventLog, PivotEvent


@dataclass
class Blackboard:
    """Mutable working state derived from the append-only event log."""

    seed_ip: str
    seed_type: str
    scan_id: int | None
    network_label: str
    allowed_cidrs: list[str]
    last_event_id: str | None = None
    current_ip: str = ""
    open_ports: list[dict[str, Any]] = field(default_factory=list)
    udp_ports: list[dict[str, Any]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    worker_summaries: list[str] = field(default_factory=list)
    completed: bool = False

    @classmethod
    def from_seed(cls, seed: dict[str, Any], allowed_cidrs: list[str]) -> Blackboard:
        ip = str(seed.get("ip") or "").strip()
        return cls(
            seed_ip=ip,
            seed_type=str(seed.get("type") or "unknown"),
            scan_id=seed.get("scan_id"),
            network_label=str(seed.get("network_label") or ""),
            allowed_cidrs=allowed_cidrs,
            current_ip=ip,
        )

    def apply_event(self, event: PivotEvent, result: dict[str, Any] | None = None) -> None:
        self.last_event_id = event.event_id
        if event.ip:
            self.current_ip = event.ip
        if result and isinstance(result.get("open_ports"), list):
            self.open_ports = result["open_ports"]
        if event.type == "mission_complete":
            self.completed = True

    def snapshot_for_llm(self, events: list[PivotEvent]) -> dict[str, Any]:
        return {
            "seed": {
                "ip": self.seed_ip,
                "type": self.seed_type,
                "scan_id": self.scan_id,
                "network_label": self.network_label,
            },
            "current_ip": self.current_ip,
            "open_ports": self.open_ports,
            "findings_count": len(self.findings),
            "event_count": len(events),
            "recent_events": [e.to_dict() for e in events[-6:]],
            "completed": self.completed,
        }

    @staticmethod
    def rebuild_from_log(event_log: EventLog, seed: dict[str, Any], allowed_cidrs: list[str]) -> Blackboard:
        board = Blackboard.from_seed(seed, allowed_cidrs)
        for event in event_log.all_events():
            board.last_event_id = event.event_id
            if event.ip:
                board.current_ip = event.ip
            if event.type == "mission_complete":
                board.completed = True
        return board
