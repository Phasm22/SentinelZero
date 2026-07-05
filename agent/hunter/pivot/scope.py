from __future__ import annotations

from dataclasses import dataclass, field

from hunter.executors.local import ip_in_allowed


@dataclass
class ScopeGuard:
    allowed_cidrs: list[str]
    per_host_budget: int = 8
    global_budget: int = 40
    host_counts: dict[str, int] = field(default_factory=dict)
    total_tasks: int = 0

    def check_ip(self, ip: str) -> str | None:
        if not ip_in_allowed(ip, self.allowed_cidrs):
            return f"Target {ip} is outside allowed CIDRs"
        return None

    def check_budget(self, ip: str) -> str | None:
        if self.total_tasks >= self.global_budget:
            return f"Global task budget exhausted ({self.global_budget})"
        count = self.host_counts.get(ip, 0)
        if count >= self.per_host_budget:
            return f"Per-host budget exhausted for {ip} ({self.per_host_budget})"
        return None

    def record_task(self, ip: str) -> None:
        self.host_counts[ip] = self.host_counts.get(ip, 0) + 1
        self.total_tasks += 1
