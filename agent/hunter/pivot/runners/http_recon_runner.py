from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from typing import Any

from ..http_recon_parse import HTTP_RECON_SCRIPT_IDS, parse_recon_scripts


FIXTURE_HTTP_RECON_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="{ip}" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="{port}">
        <state state="open"/>
        <service name="http"/>
        <script id="http-title" output="Welcome to nginx!"/>
        <script id="http-server-header" output="nginx/1.18.0 (Ubuntu)"/>
        <script id="http-headers" output="  Server: nginx/1.18.0 (Ubuntu)&#10;  Date: Mon, 01 Jan 2024 00:00:00 GMT&#10;  Content-Type: text/html&#10;"/>
      </port>
    </ports>
  </host>
</nmaprun>
"""


def parse_http_recon_xml(xml_text: str, ip: str, port: int) -> dict[str, Any]:
    scripts: dict[str, str] = {}
    try:
        root = ET.fromstring(xml_text)
        for port_el in root.findall(".//port"):
            if port_el.get("portid") != str(port):
                continue
            for script_el in port_el.findall("script"):
                script_id = script_el.get("id", "")
                if script_id in HTTP_RECON_SCRIPT_IDS:
                    scripts[script_id] = script_el.get("output", "")
    except ET.ParseError as exc:
        return {"ip": ip, "port": port, "error": f"nmap XML parse failed: {exc}"}

    fields = parse_recon_scripts(scripts)
    return {"ip": ip, "port": port, **fields}


def run_http_recon(ip: str, port: int = 80, *, fixture: bool = False, timeout: int = 60) -> dict[str, Any]:
    if fixture:
        return parse_http_recon_xml(FIXTURE_HTTP_RECON_XML.format(ip=ip, port=port), ip, port)

    result = subprocess.run(
        [
            "nmap",
            "-Pn",
            "--script", "http-title,http-headers,http-server-header,http-generator",
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
        return {"ip": ip, "port": port, "error": result.stderr.strip() or "http_recon failed"}
    return parse_http_recon_xml(result.stdout, ip, port)
