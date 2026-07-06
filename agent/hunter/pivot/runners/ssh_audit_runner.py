from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from typing import Any

from ..ssh_audit_parse import SSH_AUDIT_SCRIPT_IDS, parse_ssh_scripts


# Real nmap `--script ssh-hostkey,ssh2-enum-algos -oX -` shape, seeded with one
# legacy cipher (aes256-cbc) + kex (diffie-hellman-group14-sha1) so the fixture
# exercises the deterministic ``escalate`` path without a live probe.
FIXTURE_SSH_AUDIT_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="{ip}" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="{port}">
        <state state="open"/>
        <service name="ssh" product="OpenSSH" version="8.9p1 Ubuntu"/>
        <script id="ssh-hostkey" output="&#10;  256 SHA256:abc123def456 (ED25519)&#10;  3072 SHA256:rsa789xyz (RSA)"/>
        <script id="ssh2-enum-algos" output="&#10;  kex_algorithms: (3)&#10;      curve25519-sha256&#10;      diffie-hellman-group14-sha256&#10;      diffie-hellman-group14-sha1&#10;  server_host_key_algorithms: (2)&#10;      ssh-ed25519&#10;      rsa-sha2-512&#10;  encryption_algorithms: (3)&#10;      chacha20-poly1305@openssh.com&#10;      aes256-ctr&#10;      aes256-cbc&#10;  mac_algorithms: (2)&#10;      hmac-sha2-256&#10;      hmac-sha2-512&#10;  compression_algorithms: (1)&#10;      none"/>
      </port>
    </ports>
  </host>
</nmaprun>
"""


def parse_ssh_audit_xml(xml_text: str, ip: str, port: int) -> dict[str, Any]:
    scripts: dict[str, str] = {}
    try:
        root = ET.fromstring(xml_text)
        for port_el in root.findall(".//port"):
            if port_el.get("portid") != str(port):
                continue
            for script_el in port_el.findall("script"):
                script_id = script_el.get("id", "")
                if script_id in SSH_AUDIT_SCRIPT_IDS:
                    scripts[script_id] = script_el.get("output", "")
    except ET.ParseError as exc:
        return {"ip": ip, "port": port, "error": f"nmap XML parse failed: {exc}"}

    fields = parse_ssh_scripts(scripts)
    return {"ip": ip, "port": port, **fields}


def run_ssh_audit(ip: str, port: int = 22, *, fixture: bool = False, timeout: int = 120) -> dict[str, Any]:
    if fixture:
        return parse_ssh_audit_xml(FIXTURE_SSH_AUDIT_XML.format(ip=ip, port=port), ip, port)

    result = subprocess.run(
        [
            "nmap",
            "--script", "ssh-hostkey,ssh2-enum-algos",
            "--script-args", "ssh_hostkey=full",
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
        return {"ip": ip, "port": port, "error": result.stderr.strip() or "ssh_audit failed"}
    return parse_ssh_audit_xml(result.stdout, ip, port)
