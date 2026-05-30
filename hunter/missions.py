from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Mission:
    mission_id: str
    objective: str
    target_network: str
    profile: str
    executor: str
    iface: str
    max_turns: int
    parallel_workers: int
    handoff_scan_type: str
    handoff_trigger_discovery_scan: bool
    handoff_min_new_hosts: int
    handoff_max_recommended_hosts: int | None
    allowed_cidrs: list[str]


def _normalize_allowed_cidrs(target_network: str, allowed: list[str] | None) -> list[str]:
    cidrs = allowed or [target_network]
    out: list[str] = []
    for cidr in cidrs:
        net = ipaddress.ip_network(str(cidr).strip(), strict=False)
        out.append(str(net))
    return out


def load_mission(path: Path) -> Mission:
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Mission file {path} must contain a mapping")

    mission_id = str(data.get("id") or "").strip()
    if not mission_id:
        raise ValueError(f"Mission file {path} missing required field: id")

    objective = str(data.get("objective") or "").strip()
    if not objective:
        raise ValueError(f"Mission file {path} missing required field: objective")

    target_network = str(data.get("target_network") or "").strip()
    if not target_network:
        raise ValueError(f"Mission file {path} missing required field: target_network")
    target_network = str(ipaddress.ip_network(target_network, strict=False))

    profile = str(data.get("profile") or "white").strip().lower()
    if profile not in {"white", "assess"}:
        raise ValueError(f"Mission {mission_id}: unsupported profile '{profile}'")

    executor = str(data.get("executor") or "local").strip().lower()
    if executor != "local":
        raise ValueError(f"Mission {mission_id}: only 'local' executor is supported in phase 1")

    iface = str(data.get("iface") or "").strip()
    if not iface:
        raise ValueError(f"Mission {mission_id}: missing required field iface")

    max_turns = int(data.get("max_turns", 40))
    parallel_workers = int(data.get("parallel_workers", 1))

    handoff = data.get("handoff") or {}
    if not isinstance(handoff, dict):
        raise ValueError(f"Mission {mission_id}: handoff must be a mapping")
    handoff_scan_type = str(handoff.get("scan_type") or "Discovery Scan")
    handoff_trigger_discovery_scan = bool(handoff.get("trigger_discovery_scan", True))
    handoff_min_new_hosts = int(handoff.get("min_new_hosts", 1))
    max_hosts_raw = handoff.get("max_recommended_hosts")
    handoff_max_recommended_hosts = None
    if max_hosts_raw is not None:
        handoff_max_recommended_hosts = max(int(max_hosts_raw), 1)

    scope = data.get("scope") or {}
    if not isinstance(scope, dict):
        raise ValueError(f"Mission {mission_id}: scope must be a mapping")
    allowed_cidrs = _normalize_allowed_cidrs(target_network, scope.get("allowed_cidrs"))

    return Mission(
        mission_id=mission_id,
        objective=objective,
        target_network=target_network,
        profile=profile,
        executor=executor,
        iface=iface,
        max_turns=max_turns,
        parallel_workers=parallel_workers,
        handoff_scan_type=handoff_scan_type,
        handoff_trigger_discovery_scan=handoff_trigger_discovery_scan,
        handoff_min_new_hosts=handoff_min_new_hosts,
        handoff_max_recommended_hosts=handoff_max_recommended_hosts,
        allowed_cidrs=allowed_cidrs,
    )


def mission_path(base_dir: Path, mission_name: str) -> Path:
    if mission_name.endswith(".yaml"):
        return base_dir / mission_name
    return base_dir / f"{mission_name}.yaml"

