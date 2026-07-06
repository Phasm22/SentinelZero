from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from typing import Any

from ..http_recon_parse import HTTP_PORTS
from ..proxmox_recon_parse import PROXMOX_PORTS
from ..rpc_audit_parse import RPC_PORTS
from ..ssh_audit_parse import SSH_PORTS
from ..tls_recon_parse import TLS_PORTS

# Ports the specialized pivot runners key off. nmap's default top-1000 covers the
# common ones (22/80/443/111/445/8080/8443/3128) but misses rare management ports
# like 8006 (Proxmox) and 8581 (Homebridge), so the discovery scan sweeps these
# explicitly and merges -- otherwise those runners never trigger on a live host.
PIVOT_SERVICE_PORTS: tuple[int, ...] = tuple(sorted(set(
    HTTP_PORTS + TLS_PORTS + SSH_PORTS + RPC_PORTS + PROXMOX_PORTS + (445,)
)))


FIXTURE_NMAP_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="{ip}" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="445">
        <state state="open"/>
        <service name="microsoft-ds"/>
      </port>
      <port protocol="tcp" portid="22">
        <state state="open"/>
        <service name="ssh"/>
      </port>
    </ports>
  </host>
</nmaprun>
"""


def parse_nmap_xml(xml_text: str, ip: str) -> dict[str, Any]:
    open_ports: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_text)
        for port in root.findall(".//port"):
            state = port.find("state")
            if state is None or state.get("state") != "open":
                continue
            service = port.find("service")
            port_entry: dict[str, Any] = {
                "port": int(port.get("portid", "0")),
                "protocol": port.get("protocol", "tcp"),
                "service": (service.get("name") if service is not None else "") or "unknown",
                "product": (service.get("product") if service is not None else None) or None,
                "version": (service.get("version") if service is not None else None) or None,
            }
            extrainfo = (service.get("extrainfo") if service is not None else None) or None
            if extrainfo:
                port_entry["extrainfo"] = extrainfo
            open_ports.append(port_entry)
    except ET.ParseError as exc:
        return {"ip": ip, "error": f"nmap XML parse failed: {exc}"}
    return {"ip": ip, "open_ports": open_ports, "count": len(open_ports)}


def _run_nmap(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, capture_output=True, text=True, timeout=timeout, check=False,
    )


def run_nmap_scan(ip: str, *, fixture: bool = False, timeout: int = 120) -> dict[str, Any]:
    if fixture:
        return parse_nmap_xml(FIXTURE_NMAP_XML.format(ip=ip), ip)

    # Pass 1: default top-1000 discovery (feeds asset-drift + the common runners).
    top = _run_nmap(["nmap", "-sV", "--open", "-T4", "-oX", "-", ip], timeout)
    if top.returncode != 0 and not top.stdout:
        return {"ip": ip, "error": top.stderr.strip() or "nmap failed"}
    result = parse_nmap_xml(top.stdout, ip)
    if result.get("error"):
        return result

    # Pass 2: sweep the rare pivot service ports the top-1000 set misses, so the
    # specialized runners (e.g. proxmox_recon on 8006) actually trigger.
    port_spec = ",".join(str(p) for p in PIVOT_SERVICE_PORTS)
    extra = _run_nmap(
        ["nmap", "-sV", "--open", "-T4", "-p", port_spec, "-oX", "-", ip], timeout
    )
    if extra.stdout:
        extra_result = parse_nmap_xml(extra.stdout, ip)
        known = {int(p.get("port", 0)) for p in result["open_ports"]}
        for port_entry in extra_result.get("open_ports") or []:
            if int(port_entry.get("port", 0)) not in known:
                result["open_ports"].append(port_entry)
        result["open_ports"].sort(key=lambda p: int(p.get("port", 0)))
        result["count"] = len(result["open_ports"])
    return result


def triage_ports(scan_result: dict[str, Any]) -> dict[str, Any]:
    """Deterministic triage of open ports into recommended pivot runners.

    - ``smb_enum`` when 445/tcp is open.
    - ``http_recon`` when any HTTP(S) surface port is open (80/443/8080/8443/
      3128/8006/8581).
    - ``tls_recon`` when a TLS surface port is open (443/8443) -- cert/cipher
      posture, complementary to http_recon's content identification.
    - ``ssh_audit`` when 22/tcp is open -- host key + algorithm posture.
    - ``rpc_audit`` when 111/tcp is open -- RPC program inventory (NFS/mountd/NIS).
    - ``proxmox_recon`` when 8006/tcp is open -- Proxmox hypervisor identification.
    - ``asset_expectation_check`` whenever any port is open -- drift analysis is
      port-agnostic and never re-probes the host.

    Only wired actions are ever recommended.
    """
    open_ports = scan_result.get("open_ports") or []
    port_nums = {int(p.get("port", 0)) for p in open_ports}
    recommendations: list[str] = []
    if 445 in port_nums:
        recommendations.append("smb_enum")
    if port_nums & set(HTTP_PORTS):
        recommendations.append("http_recon")
    if port_nums & set(TLS_PORTS):
        recommendations.append("tls_recon")
    if port_nums & set(SSH_PORTS):
        recommendations.append("ssh_audit")
    if port_nums & set(RPC_PORTS):
        recommendations.append("rpc_audit")
    if port_nums & set(PROXMOX_PORTS):
        recommendations.append("proxmox_recon")
    if open_ports:
        recommendations.append("asset_expectation_check")
    return {
        "ip": scan_result.get("ip"),
        "recommendations": recommendations,
        "open_ports": open_ports,
    }
