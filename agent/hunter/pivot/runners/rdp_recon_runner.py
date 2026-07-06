from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from typing import Any

from ..rdp_recon_parse import RDP_RECON_SCRIPT_IDS, parse_rdp_scripts


# Real nmap `--script rdp-ntlm-info,rdp-enum-encryption -oX -` shape, seeded with
# NLA DISABLED (no CredSSP layer) so the fixture exercises the deterministic
# ``escalate`` path without a live probe.
FIXTURE_RDP_RECON_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="{ip}" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="{port}">
        <state state="open"/>
        <service name="ms-wbt-server"/>
        <script id="rdp-enum-encryption" output="&#10;  Security layer&#10;    Native RDP: SUCCESS&#10;    SSL: SUCCESS&#10;"/>
        <script id="rdp-ntlm-info" output="&#10;  Target_Name: DESKTOP-LAB&#10;  NetBIOS_Domain_Name: DESKTOP-LAB&#10;  NetBIOS_Computer_Name: DESKTOP-LAB&#10;  DNS_Domain_Name: DESKTOP-LAB&#10;  DNS_Computer_Name: DESKTOP-LAB&#10;  Product_Version: 10.0.19041&#10;"/>
      </port>
    </ports>
  </host>
</nmaprun>
"""


def parse_rdp_recon_xml(xml_text: str, ip: str, port: int) -> dict[str, Any]:
    scripts: dict[str, str] = {}
    try:
        root = ET.fromstring(xml_text)
        for port_el in root.findall(".//port"):
            if port_el.get("portid") != str(port):
                continue
            for script_el in port_el.findall("script"):
                script_id = script_el.get("id", "")
                if script_id in RDP_RECON_SCRIPT_IDS:
                    scripts[script_id] = script_el.get("output", "")
    except ET.ParseError as exc:
        return {"ip": ip, "port": port, "error": f"nmap XML parse failed: {exc}"}

    fields = parse_rdp_scripts(scripts)
    responded = bool(scripts)
    return {"ip": ip, "port": port, "responded": responded, **fields}


def run_rdp_recon(ip: str, port: int = 3389, *, fixture: bool = False, timeout: int = 120) -> dict[str, Any]:
    if fixture:
        return parse_rdp_recon_xml(FIXTURE_RDP_RECON_XML.format(ip=ip, port=port), ip, port)

    result = subprocess.run(
        [
            "nmap",
            "-Pn",
            "--script", "rdp-ntlm-info,rdp-enum-encryption",
            "-p", str(port),
            "-oX", "-",
            ip,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0 and not result.stdout:
        return {"ip": ip, "port": port, "error": result.stderr.strip() or "rdp_recon failed"}
    return parse_rdp_recon_xml(result.stdout, ip, port)
