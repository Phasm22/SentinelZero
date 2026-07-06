from __future__ import annotations

import socket
from typing import Any

from ..upnp_discover_parse import build_upnp_fields, parse_ssdp_response


# Canned SSDP responses for a UPnP IGD -- exercises the deterministic ``escalate``
# path without a live probe.
FIXTURE_UPNP_RESULT = {
    "responded": True,
    "responses": [
        {
            "server": "Linux/3.14 UPnP/1.0 MiniUPnPd/2.1",
            "st": "urn:schemas-upnp-org:device:InternetGatewayDevice:1",
            "usn": "uuid:abcd::urn:schemas-upnp-org:device:InternetGatewayDevice:1",
            "location": "http://10.0.0.1:5000/rootDesc.xml",
        },
    ],
}


def _msearch_packet(ip: str, port: int) -> bytes:
    return (
        "M-SEARCH * HTTP/1.1\r\n"
        f"HOST: {ip}:{port}\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 1\r\n"
        "ST: ssdp:all\r\n"
        "\r\n"
    ).encode("ascii")


def run_upnp_discover(ip: str, port: int = 1900, *, fixture: bool = False, timeout: float = 3.0) -> dict[str, Any]:
    """Unicast SSDP M-SEARCH to the seed host -- unprivileged UDP, no root.

    Host-scoped (unicast, not the 239.255.255.250 multicast group) so it probes
    only the pivot target, never the whole segment.
    """
    if fixture:
        fields = build_upnp_fields(
            responded=FIXTURE_UPNP_RESULT["responded"],
            responses=FIXTURE_UPNP_RESULT["responses"],
        )
        return {"ip": ip, "port": port, **fields}

    responses: list[dict[str, Any]] = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(_msearch_packet(ip, port), (ip, port))
        while True:
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                break
            if str(addr[0]) == ip and data:
                responses.append(parse_ssdp_response(data))
    except Exception as exc:
        return {"ip": ip, "port": port, "error": str(exc), "responded": False,
                "servers": [], "locations": [], "service_types": [], "response_count": 0}
    finally:
        sock.close()

    fields = build_upnp_fields(responded=bool(responses), responses=responses)
    return {"ip": ip, "port": port, **fields}
