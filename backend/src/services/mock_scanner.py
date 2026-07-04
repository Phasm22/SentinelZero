"""Mock nmap scanner for CI and Playwright — no raw sockets or nmap binary."""
from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape


def mock_scanner_enabled() -> bool:
    return os.environ.get("SENTINEL_MOCK_SCANNER", "").lower() in ("1", "true", "yes")


def _sample_hosts(target_network: str) -> list[dict]:
    """Generate deterministic sample hosts inside the target network."""
    base = target_network.split("/")[0].rsplit(".", 1)[0]
    return [
        {
            "ip": f"{base}.1",
            "hostname": "mock-gateway",
            "ports": [
                {"port": 22, "protocol": "tcp", "service": "ssh", "state": "open"},
                {"port": 80, "protocol": "tcp", "service": "http", "state": "open"},
            ],
        },
        {
            "ip": f"{base}.10",
            "hostname": "mock-server",
            "ports": [
                {"port": 443, "protocol": "tcp", "service": "https", "state": "open"},
            ],
        },
    ]


def build_mock_nmap_xml(target_network: str, scan_type_normalized: str) -> str:
    """Build minimal valid nmap XML for parsing by scanner._finalize_scan_from_xml."""
    hosts = _sample_hosts(target_network)
    host_blocks = []
    for host in hosts:
        port_blocks = []
        for port in host["ports"]:
            port_blocks.append(
                f"""    <port protocol="{port['protocol']}" portid="{port['port']}">
      <state state="{port['state']}" reason="syn-ack" reason_ttl="64"/>
      <service name="{escape(port['service'])}" method="table" conf="3"/>
    </port>"""
            )
        host_blocks.append(
            f"""  <host>
    <status state="up" reason="mock-reply" reason_ttl="64"/>
    <address addr="{host['ip']}" addrtype="ipv4"/>
    <hostnames>
      <hostname name="{escape(host['hostname'])}" type="PTR"/>
    </hostnames>
    <ports>
{chr(10).join(port_blocks)}
    </ports>
  </host>"""
        )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<nmaprun scanner="mock" args="nmap mock {escape(scan_type_normalized)}" start="{int(time.time())}">
{chr(10).join(host_blocks)}
  <runstats>
    <finished time="{int(time.time())}" timestr="{datetime.utcnow().isoformat()}Z" elapsed="1.23"/>
  </runstats>
</nmaprun>
"""


def run_mock_nmap_execution(
    scan_id,
    scan_type,
    scan_type_normalized,
    target_network,
    stored_xml_path,
    absolute_xml_path,
    runtime,
    app,
    socketio,
    security_settings,
    emit_stage,
):
    """Simulate nmap execution: write XML, emit progress, finalize via shared parser."""
    from .scanner import _finalize_scan_from_xml

    Path(absolute_xml_path).parent.mkdir(parents=True, exist_ok=True)
    runtime.append_log(scan_id, "[MOCK] Using mock scanner (SENTINEL_MOCK_SCANNER=1)")
    runtime.append_log(scan_id, f"[MOCK] Target: {target_network}, type: {scan_type}")

    for pct in (25, 50, 75, 100):
        runtime.append_log(scan_id, f"About {pct}.0% done")
        time.sleep(0.05)

    xml_content = build_mock_nmap_xml(target_network, scan_type_normalized)
    Path(absolute_xml_path).write_text(xml_content, encoding="utf-8")
    runtime.append_log(scan_id, f"[MOCK] Wrote synthetic XML to {stored_xml_path}")

    _finalize_scan_from_xml(
        scan_id=scan_id,
        xml_path=str(absolute_xml_path),
        stored_xml_path=stored_xml_path,
        scan_type=scan_type,
        scan_type_normalized=scan_type_normalized,
        target_network=target_network,
        runtime=runtime,
        app=app,
        socketio=socketio,
        security_settings=security_settings,
        emit_stage=emit_stage,
    )
