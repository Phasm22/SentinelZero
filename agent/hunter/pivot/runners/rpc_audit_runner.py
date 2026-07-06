from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from typing import Any

from ..rpc_audit_parse import RPC_AUDIT_SCRIPT_IDS, parse_rpc_scripts


# Real nmap `--script rpcinfo -oX -` shape for a portmapper exposing NFS +
# mountd -- exercises the deterministic ``escalate`` path (sensitive services)
# without a live probe.
FIXTURE_RPC_AUDIT_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="{ip}" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="{port}">
        <state state="open"/>
        <service name="rpcbind" version="2-4"/>
        <script id="rpcinfo" output="&#10;  program version    port/proto  service&#10;  100000  2,3,4        111/tcp   rpcbind&#10;  100003  3,4         2049/tcp   nfs&#10;  100005  1,2,3      56401/tcp   mountd&#10;  100021  1,3,4      33929/tcp   nlockmgr&#10;  100024  1          45953/tcp   status&#10;  100227  3           2049/tcp   nfs_acl&#10;"/>
      </port>
    </ports>
  </host>
</nmaprun>
"""


def parse_rpc_audit_xml(xml_text: str, ip: str, port: int) -> dict[str, Any]:
    scripts: dict[str, str] = {}
    try:
        root = ET.fromstring(xml_text)
        for port_el in root.findall(".//port"):
            if port_el.get("portid") != str(port):
                continue
            for script_el in port_el.findall("script"):
                script_id = script_el.get("id", "")
                if script_id in RPC_AUDIT_SCRIPT_IDS:
                    scripts[script_id] = script_el.get("output", "")
    except ET.ParseError as exc:
        return {"ip": ip, "port": port, "error": f"nmap XML parse failed: {exc}"}

    fields = parse_rpc_scripts(scripts)
    return {"ip": ip, "port": port, **fields}


def run_rpc_audit(ip: str, port: int = 111, *, fixture: bool = False, timeout: int = 120) -> dict[str, Any]:
    if fixture:
        return parse_rpc_audit_xml(FIXTURE_RPC_AUDIT_XML.format(ip=ip, port=port), ip, port)

    result = subprocess.run(
        [
            "nmap",
            "--script", "rpcinfo",
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
        return {"ip": ip, "port": port, "error": result.stderr.strip() or "rpc_audit failed"}
    return parse_rpc_audit_xml(result.stdout, ip, port)
