from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from typing import Any


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


def run_nmap_scan(ip: str, *, fixture: bool = False, timeout: int = 120) -> dict[str, Any]:
    if fixture:
        return parse_nmap_xml(FIXTURE_NMAP_XML.format(ip=ip), ip)

    result = subprocess.run(
        ["nmap", "-sV", "--open", "-T4", "-oX", "-", ip],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0 and not result.stdout:
        return {"ip": ip, "error": result.stderr.strip() or "nmap failed"}
    return parse_nmap_xml(result.stdout, ip)


def triage_ports(scan_result: dict[str, Any]) -> dict[str, Any]:
    """Deterministic triage: recommend SMB enum if 445/tcp is open, http_recon if
    80/tcp or 443/tcp is open."""
    open_ports = scan_result.get("open_ports") or []
    port_nums = {int(p.get("port", 0)) for p in open_ports}
    recommendations: list[str] = []
    if 445 in port_nums:
        recommendations.append("smb_enum")
    if 80 in port_nums or 443 in port_nums:
        recommendations.append("http_recon")
    return {
        "ip": scan_result.get("ip"),
        "recommendations": recommendations,
        "open_ports": open_ports,
    }
