from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent import ASSETS, BASE_URL, NETWORK_TOPOLOGY, _http

from .executors.local import LocalExecutor
from .handoff import HuntReportWriter
from .baseline import load_baseline, save_baseline, upsert_fingerprint
from .missions import Mission
from .seed import SeedResult


@dataclass
class HunterRuntime:
    mission: Mission
    executor: LocalExecutor
    seed_result: SeedResult
    ranked_candidates: list[dict[str, Any]]
    reports_dir: Path
    no_trigger_scan: bool = False
    findings: list[dict[str, Any]] = field(default_factory=list)
    worker_summaries: list[str] = field(default_factory=list)
    device_context: dict[str, dict[str, Any]] = field(default_factory=dict)
    baseline: dict[str, Any] = field(default_factory=dict)
    fingerprints: list[dict[str, Any]] = field(default_factory=list)
    fingerprint_diffs: list[dict[str, Any]] = field(default_factory=list)
    probe_results: dict[str, dict[str, Any]] = field(default_factory=dict)

    def _load_assets(self) -> dict[str, Any]:
        try:
            return json.loads(ASSETS.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def get_network_topology(self) -> dict[str, Any]:
        try:
            return json.loads(NETWORK_TOPOLOGY.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"error": f"network topology unavailable: {exc}"}

    def get_asset_context(self, ip: str) -> dict[str, Any]:
        entry = self._load_assets().get(ip)
        if entry:
            return {"ip": ip, "in_registry": True, **entry}
        return {"ip": ip, "in_registry": False}

    def get_network_context(self, source: str) -> dict[str, Any]:
        r = _http.get(f"{BASE_URL}/api/sensor/latest/{source}", timeout=10)
        r.raise_for_status()
        return r.json()

    def get_device_context(self, ip: str) -> dict[str, Any]:
        ctx = self.device_context.get(ip)
        if ctx is None:
            return {"ip": ip, "known": False}
        return {"ip": ip, "known": True, **ctx}

    def get_sensor_agents(self) -> dict[str, Any]:
        r = _http.get(f"{BASE_URL}/api/sensor/agents", timeout=10)
        r.raise_for_status()
        return r.json()

    def get_latest_scan_hosts(self, network: str) -> dict[str, Any]:
        r = _http.get(f"{BASE_URL}/api/scans", timeout=15)
        r.raise_for_status()
        body = r.json()
        scans = body if isinstance(body, list) else body.get("scans", [])
        scans = [s for s in scans if str(s.get("target_network") or "") == network]
        scans = [s for s in scans if str(s.get("status") or "").lower() == "complete"]
        scans.sort(key=lambda s: str(s.get("completed_at") or s.get("timestamp") or ""), reverse=True)
        if not scans:
            return {"scan_id": None, "hosts": []}
        scan = scans[0]
        hosts = [h.get("ip") for h in (scan.get("hosts") or []) if h.get("ip")]
        return {"scan_id": scan.get("id"), "hosts": sorted(set(hosts))}

    def discover_hosts(self, cidr: str) -> dict[str, Any]:
        return self.executor.discover_hosts(cidr)

    def port_scan_light(self, ip: str) -> dict[str, Any]:
        return self.executor.port_scan_light(ip)

    def _flagged_ips(self) -> set[str]:
        flagged: set[str] = set()
        for item in self.findings:
            ip = str(item.get("ip") or "").strip()
            if ip:
                flagged.add(ip)
        for item in self.ranked_candidates:
            ip = str(item.get("ip") or "").strip()
            score = int(item.get("score") or 0)
            if ip and score >= 4:
                flagged.add(ip)
        return flagged

    def port_scan_iot(self, ip: str) -> dict[str, Any]:
        if self.mission.profile != "assess":
            return {"error": "port_scan_iot is only available for assess profile missions"}
        if ip not in self._flagged_ips():
            return {"error": f"Target {ip} is not a flagged host for assess profile"}
        return self.probe_iot_direct(ip)

    def probe_iot_direct(self, ip: str) -> dict[str, Any]:
        """Run IoT UDP probe without LLM flag gate (deterministic assess pipeline)."""
        return self.executor.port_scan_iot(ip)

    def submit_finding(self, finding: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(finding, dict):
            return {"error": "finding must be an object"}
        normalized = dict(finding)
        if not normalized.get("ip") and normalized.get("ip_address"):
            normalized["ip"] = str(normalized.pop("ip_address"))
        self.findings.append(normalized)
        return {"status": "ok", "index": len(self.findings) - 1}

    def request_scan(self, scan_type: str, cidr: str) -> dict[str, Any]:
        if self.no_trigger_scan:
            return {"status": "skipped", "reason": "no-trigger-scan set"}
        r = _http.post(
            f"{BASE_URL}/api/scan",
            data={
                "scan_type": scan_type,
                "target_network": cidr,
                "source": "hunter",
                "initiated_by": self.mission.mission_id or "hunter",
            },
            timeout=20,
        )
        if r.status_code >= 400:
            return {"error": f"scan trigger failed: {r.status_code}", "body": r.text[:400]}
        return r.json()

    def finalize_hunt_report(self) -> dict[str, Any]:
        baseline_payload = self.baseline if isinstance(self.baseline, dict) else {}
        if not baseline_payload:
            baseline_payload = load_baseline()
        baseline_updates = 0
        for ip, probe_result in self.probe_results.items():
            device_hint = str((self.device_context.get(ip) or {}).get("device_hint") or ip)
            upsert_fingerprint(
                baseline_payload,
                ip=ip,
                probe_result=probe_result,
                mission_id=self.mission.mission_id,
                device_hint=device_hint,
            )
            baseline_updates += 1

        known = sum(1 for ctx in self.device_context.values() if ctx.get("in_registry"))
        unknown = len(self.device_context) - known
        writer = HuntReportWriter(
            mission=self.mission,
            seed_result=self.seed_result,
            ranked_candidates=self.ranked_candidates,
            findings=self.findings,
            worker_summaries=self.worker_summaries,
            reports_dir=self.reports_dir,
            fingerprints=self.fingerprints,
            fingerprint_diffs=self.fingerprint_diffs,
            baseline_updated_count=baseline_updates,
            device_context_summary={"known": known, "unknown": unknown, "total": len(self.device_context)},
        )
        result = writer.write(no_trigger_scan=self.no_trigger_scan, request_scan=self.request_scan)
        if baseline_updates:
            save_baseline(baseline_payload)
            self.baseline = baseline_payload
        return result


def _base_tool_schemas() -> list[dict[str, Any]]:
    return [
    {
        "type": "function",
        "function": {
            "name": "get_network_topology",
            "description": "Read static network topology context from network.json.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_device_context",
            "description": "Return merged device context for one host in this mission.",
            "parameters": {
                "type": "object",
                "properties": {"ip": {"type": "string"}},
                "required": ["ip"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_asset_context",
            "description": "Look up one host in the asset registry.",
            "parameters": {
                "type": "object",
                "properties": {"ip": {"type": "string"}},
                "required": ["ip"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_network_context",
            "description": "Fetch latest network telemetry for one sensor source.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "enum": ["opnsense", "opnsense-ntopng", "pihole-lab", "pihole-home"],
                    }
                },
                "required": ["source"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sensor_agents",
            "description": "List registered sensor agents and statuses.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_latest_scan_hosts",
            "description": "Get hosts from the latest completed scan on one network.",
            "parameters": {
                "type": "object",
                "properties": {"network": {"type": "string"}},
                "required": ["network"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "discover_hosts",
            "description": "Run on-link discovery nmap for a CIDR in mission scope.",
            "parameters": {
                "type": "object",
                "properties": {"cidr": {"type": "string"}},
                "required": ["cidr"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "port_scan_light",
            "description": "Run focused nmap -sV --open scan on a single host in scope.",
            "parameters": {
                "type": "object",
                "properties": {"ip": {"type": "string"}},
                "required": ["ip"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "port_scan_iot",
            "description": "Run constrained IoT UDP probe on one flagged host.",
            "parameters": {
                "type": "object",
                "properties": {"ip": {"type": "string"}},
                "required": ["ip"],
            },
        },
    },
        {
        "type": "function",
        "function": {
            "name": "submit_finding",
            "description": "Append one structured finding to the report buffer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "finding": {
                        "type": "object",
                        "properties": {
                            "ip": {"type": "string", "description": "Host IP address"},
                            "category": {"type": "string"},
                            "description": {"type": "string"},
                            "severity": {"type": "string"},
                            "open_ports": {"type": "array"},
                        },
                        "required": ["ip", "description"],
                    }
                },
                "required": ["finding"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_scan",
            "description": "Trigger a SentinelZero scan handoff.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scan_type": {"type": "string"},
                    "cidr": {"type": "string"},
                },
                "required": ["scan_type", "cidr"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finalize_hunt_report",
            "description": "Write report JSON and apply scan-trigger handoff rules.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    ]


def tool_schemas_for_runtime(runtime: HunterRuntime) -> list[dict[str, Any]]:
    tools = _base_tool_schemas()
    if runtime.mission.profile != "assess":
        tools = [t for t in tools if t["function"]["name"] != "port_scan_iot"]
    return tools


def _coerce_finding_input(inputs: dict[str, Any]) -> dict[str, Any]:
    finding = inputs.get("finding")
    if isinstance(finding, dict):
        return finding
    if isinstance(inputs, dict) and inputs.get("ip"):
        return inputs
    raise KeyError("finding")


def dispatch_tool(runtime: HunterRuntime, name: str, inputs: dict[str, Any]) -> Any:
    handlers = {
        "get_network_topology": lambda d: runtime.get_network_topology(),
        "get_asset_context": lambda d: runtime.get_asset_context(str(d["ip"])),
        "get_network_context": lambda d: runtime.get_network_context(str(d["source"])),
        "get_sensor_agents": lambda d: runtime.get_sensor_agents(),
        "get_device_context": lambda d: runtime.get_device_context(str(d["ip"])),
        "get_latest_scan_hosts": lambda d: runtime.get_latest_scan_hosts(str(d["network"])),
        "discover_hosts": lambda d: runtime.discover_hosts(str(d["cidr"])),
        "port_scan_light": lambda d: runtime.port_scan_light(str(d["ip"])),
        "port_scan_iot": lambda d: runtime.port_scan_iot(str(d["ip"])),
        "submit_finding": lambda d: runtime.submit_finding(_coerce_finding_input(d)),
        "request_scan": lambda d: runtime.request_scan(str(d["scan_type"]), str(d["cidr"])),
        "finalize_hunt_report": lambda d: runtime.finalize_hunt_report(),
    }
    fn = handlers.get(name)
    if fn is None:
        return {"error": f"unknown tool {name}"}
    try:
        return fn(inputs or {})
    except Exception as exc:
        return {"error": str(exc)}
