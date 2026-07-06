from __future__ import annotations

import random
import socket
import struct
from typing import Any

from ..mdns_discover_parse import build_mdns_fields

# The service-enumeration meta-query every mDNS responder answers.
_SERVICE_ENUM_QNAME = "_services._dns-sd._udp.local"

# Canned mDNS result for a host advertising services -- exercises the
# deterministic ``escalate`` path without a live probe.
FIXTURE_MDNS_RESULT = {
    "responded": True,
    "services": ["_http._tcp.local", "_workstation._tcp.local"],
    "names": ["porttest.local"],
}


def _encode_qname(name: str) -> bytes:
    return b"".join(bytes([len(p)]) + p.encode("ascii") for p in name.split(".")) + b"\x00"


def _read_name(data: bytes, offset: int) -> tuple[str, int]:
    """Read a (possibly compressed) DNS name; return (name, offset_after)."""
    labels: list[str] = []
    jumped = False
    end_offset = offset
    steps = 0
    while offset < len(data) and steps < 128:
        steps += 1
        length = data[offset]
        if length == 0:
            offset += 1
            break
        if length & 0xC0 == 0xC0:
            pointer = ((length & 0x3F) << 8) | data[offset + 1]
            if not jumped:
                end_offset = offset + 2
            offset = pointer
            jumped = True
            continue
        labels.append(data[offset + 1:offset + 1 + length].decode("ascii", "replace"))
        offset += 1 + length
    if not jumped:
        end_offset = offset
    return ".".join(labels), end_offset


def _parse_mdns(data: bytes) -> dict[str, list[str]]:
    services: list[str] = []
    names: list[str] = []
    try:
        qd, an = struct.unpack(">HH", data[4:8])
        offset = 12
        for _ in range(qd):
            _, offset = _read_name(data, offset)
            offset += 4
        for _ in range(an):
            rname, offset = _read_name(data, offset)
            rtype, _rclass, _ttl, rdlength = struct.unpack(">HHIH", data[offset:offset + 10])
            offset += 10
            if rtype == 12:  # PTR -> service instance / type
                target, _ = _read_name(data, offset)
                if target:
                    services.append(target)
            elif rtype in (1, 28):  # A / AAAA -> host name
                if rname:
                    names.append(rname)
            offset += rdlength
    except (struct.error, IndexError):
        pass
    return {"services": services, "names": names}


def run_mdns_discover(ip: str, port: int = 5353, *, fixture: bool = False, timeout: float = 3.0) -> dict[str, Any]:
    """Unicast mDNS service-enumeration query to the seed host -- unprivileged UDP.

    Host-scoped (unicast, not the 224.0.0.251 multicast group), asking the
    responder to list the service types it advertises.
    """
    if fixture:
        fields = build_mdns_fields(**FIXTURE_MDNS_RESULT)
        return {"ip": ip, "port": port, **fields}

    tid = random.randint(0, 0xFFFF)
    header = struct.pack(">HHHHHH", tid, 0x0000, 1, 0, 0, 0)
    # QU bit (0x8000) in qclass requests a unicast response.
    query = header + _encode_qname(_SERVICE_ENUM_QNAME) + struct.pack(">HH", 12, 0x8001)

    services: list[str] = []
    names: list[str] = []
    responded = False
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(query, (ip, port))
        while True:
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                break
            if str(addr[0]) == ip and data:
                responded = True
                parsed = _parse_mdns(data)
                services.extend(parsed["services"])
                names.extend(parsed["names"])
    except Exception as exc:
        return {"ip": ip, "port": port, "error": str(exc), "responded": False,
                "services": [], "names": [], "service_count": 0}
    finally:
        sock.close()

    fields = build_mdns_fields(responded=responded, services=services, names=names)
    return {"ip": ip, "port": port, **fields}
