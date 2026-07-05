from __future__ import annotations

from typing import Any

from .baseline import extract_udp_ports


def _port_set(rows: list[dict[str, Any]]) -> set[int]:
    out: set[int] = set()
    for row in rows:
        try:
            out.add(int(row.get("port")))
        except Exception:
            continue
    return out


def build_fingerprint_findings(
    *,
    ip: str,
    probe_result: dict[str, Any],
    baseline_entry: dict[str, Any] | None,
    device_context: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    observed = extract_udp_ports(probe_result)
    observed_ports = _port_set(observed)
    baseline_ports = _port_set(list((baseline_entry or {}).get("udp_ports") or []))
    ctx = device_context or {}
    device_hint = str(ctx.get("device_hint") or ip)
    findings: list[dict[str, Any]] = []

    if baseline_entry is None and observed_ports:
        findings.append({
            "ip": ip,
            "type": "new_device",
            "description": f"New IoT-profile device observed: {device_hint}",
            "udp_ports": sorted(observed_ports),
            "open_ports": observed,
            "device_hint": device_hint,
        })

    for port in sorted(observed_ports - baseline_ports):
        findings.append({
            "ip": ip,
            "type": "new_udp_port",
            "description": f"{device_hint} exposed new UDP port {port}.",
            "udp_ports": [port],
            "open_ports": [row for row in observed if int(row.get("port", -1)) == port],
            "device_hint": device_hint,
        })

    for port in sorted(baseline_ports - observed_ports):
        findings.append({
            "ip": ip,
            "type": "lost_udp_port",
            "description": f"{device_hint} no longer exposes previously seen UDP port {port}.",
            "udp_ports": [port],
            "device_hint": device_hint,
            "severity": "info",
        })

    expected_udp_ports = {
        int(p) for p in (ctx.get("expected_udp_ports") or []) if isinstance(p, int) or str(p).isdigit()
    }
    if expected_udp_ports:
        unexpected = sorted(observed_ports - expected_udp_ports)
        if unexpected:
            findings.append({
                "ip": ip,
                "type": "expected_udp_violation",
                "description": f"{device_hint} exposed unexpected UDP ports: {', '.join(str(p) for p in unexpected)}.",
                "udp_ports": unexpected,
                "device_hint": device_hint,
            })
    return findings
