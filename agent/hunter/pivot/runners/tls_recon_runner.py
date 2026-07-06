from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from typing import Any

from ..tls_recon_parse import TLS_RECON_SCRIPT_IDS, parse_tls_scripts


# Real nmap `--script ssl-cert,ssl-enum-ciphers -oX -` output for a self-signed
# cert on TLSv1.2/1.3 (grade A) -- exercises the deterministic ``escalate`` path
# (self-signed) without a live probe. Only the `output` attributes are read.
FIXTURE_TLS_RECON_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="{ip}" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="{port}">
        <state state="open"/>
        <service name="https"/>
        <script id="ssl-cert" output="Subject: commonName=porttest.lab&#10;Subject Alternative Name: DNS:porttest.lab, DNS:www.porttest.lab&#10;Issuer: commonName=porttest.lab&#10;Public Key type: rsa&#10;Public Key bits: 2048&#10;Signature Algorithm: sha256WithRSAEncryption&#10;Not valid before: 2026-07-06T01:19:02&#10;Not valid after:  2099-07-06T01:19:02&#10;MD5:   a5fb 7896 daba 7de2 e010 20fd e611 b0c0&#10;SHA-1: 234a e71c e85d e397 a276 0649 731c 564d e6a5 7cb6"/>
        <script id="ssl-enum-ciphers" output="&#10;  TLSv1.2: &#10;    ciphers: &#10;      TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384 (secp256r1) - A&#10;    compressors: &#10;      NULL&#10;    cipher preference: server&#10;  TLSv1.3: &#10;    ciphers: &#10;      TLS_AKE_WITH_AES_256_GCM_SHA384 (ecdh_x25519) - A&#10;    cipher preference: server&#10;  least strength: A"/>
      </port>
    </ports>
  </host>
</nmaprun>
"""


def parse_tls_recon_xml(xml_text: str, ip: str, port: int) -> dict[str, Any]:
    scripts: dict[str, str] = {}
    try:
        root = ET.fromstring(xml_text)
        for port_el in root.findall(".//port"):
            if port_el.get("portid") != str(port):
                continue
            for script_el in port_el.findall("script"):
                script_id = script_el.get("id", "")
                if script_id in TLS_RECON_SCRIPT_IDS:
                    scripts[script_id] = script_el.get("output", "")
    except ET.ParseError as exc:
        return {"ip": ip, "port": port, "error": f"nmap XML parse failed: {exc}"}

    fields = parse_tls_scripts(scripts)
    return {"ip": ip, "port": port, **fields}


def run_tls_recon(ip: str, port: int = 443, *, fixture: bool = False, timeout: int = 120) -> dict[str, Any]:
    if fixture:
        return parse_tls_recon_xml(FIXTURE_TLS_RECON_XML.format(ip=ip, port=port), ip, port)

    result = subprocess.run(
        [
            "nmap",
            "-Pn",
            "--script", "ssl-cert,ssl-enum-ciphers",
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
        return {"ip": ip, "port": port, "error": result.stderr.strip() or "tls_recon failed"}
    return parse_tls_recon_xml(result.stdout, ip, port)
