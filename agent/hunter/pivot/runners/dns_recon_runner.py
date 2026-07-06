from __future__ import annotations

import random
import socket
import struct
from typing import Any

from ..dns_recon_parse import build_dns_fields

# External name used to test open recursion -- the resolver must recurse off-box
# to answer it, so an answer with RA set proves the resolver is open to us.
_RECURSION_PROBE_NAME = "example.com"

# Canned probe result for a Pi-hole/dnsmasq open resolver -- exercises the
# deterministic ``escalate`` path without a live query.
FIXTURE_DNS_RESULT = {
    "responded": True,
    "recursion_available": True,
    "recursion_tested": True,
    "version": "dnsmasq-pi-hole-v2.92test21",
}


def _encode_qname(name: str) -> bytes:
    return b"".join(bytes([len(p)]) + p.encode("ascii") for p in name.split(".")) + b"\x00"


def _dns_query(ip: str, qname: str, qtype: int, qclass: int, *, rd: bool, timeout: float) -> bytes:
    tid = random.randint(0, 0xFFFF)
    flags = 0x0100 if rd else 0x0000
    header = struct.pack(">HHHHHH", tid, flags, 1, 0, 0, 0)
    packet = header + _encode_qname(qname) + struct.pack(">HH", qtype, qclass)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(packet, (ip, 53))
        data, _ = sock.recvfrom(4096)
        return data
    finally:
        sock.close()


def _skip_qname(data: bytes, offset: int) -> int:
    """Advance past a (possibly compressed) DNS name, returning the new offset."""
    while offset < len(data):
        length = data[offset]
        if length == 0:
            return offset + 1
        if length & 0xC0 == 0xC0:  # compression pointer -- 2 bytes, name ends here
            return offset + 2
        offset += 1 + length
    return offset


def _parse_first_txt(data: bytes) -> str | None:
    """Extract the first TXT rdata string from a DNS response (used for version.bind)."""
    try:
        qdcount, ancount = struct.unpack(">HH", data[4:8])
        if ancount < 1:
            return None
        offset = 12
        for _ in range(qdcount):
            offset = _skip_qname(data, offset) + 4  # qtype + qclass
        # First answer RR.
        offset = _skip_qname(data, offset)
        rtype, _rclass, _ttl, rdlength = struct.unpack(">HHIH", data[offset:offset + 10])
        offset += 10
        rdata = data[offset:offset + rdlength]
        if rtype != 16 or not rdata:  # 16 = TXT
            return None
        txt_len = rdata[0]
        return rdata[1:1 + txt_len].decode("ascii", "replace") or None
    except (struct.error, IndexError):
        return None


def _response_flags(data: bytes) -> tuple[bool, int, int]:
    """Return (recursion_available, rcode, ancount) from a DNS response header."""
    rflags, _qd, ancount = struct.unpack(">HHH", data[2:8])
    return bool(rflags & 0x0080), rflags & 0x000F, ancount


def run_dns_recon(ip: str, port: int = 53, *, fixture: bool = False, timeout: float = 5.0) -> dict[str, Any]:
    if fixture:
        fields = build_dns_fields(**FIXTURE_DNS_RESULT)
        return {"ip": ip, "port": port, **fields}

    responded = False
    recursion_available = False
    recursion_tested = False
    version: str | None = None

    # Recursion probe: ask for an external name with RD set. An RA flag + a
    # NOERROR answer means the resolver recursed off-box for us (open resolver).
    try:
        data = _dns_query(ip, _RECURSION_PROBE_NAME, 1, 1, rd=True, timeout=timeout)
        responded = True
        recursion_tested = True
        ra, rcode, ancount = _response_flags(data)
        recursion_available = ra and rcode == 0 and ancount > 0
    except Exception:
        pass

    # version.bind CHAOS TXT -- software/version disclosure.
    try:
        data = _dns_query(ip, "version.bind", 16, 3, rd=False, timeout=timeout)
        responded = True
        version = _parse_first_txt(data)
    except Exception:
        pass

    fields = build_dns_fields(
        responded=responded,
        recursion_available=recursion_available,
        recursion_tested=recursion_tested,
        version=version,
    )
    return {"ip": ip, "port": port, **fields}
