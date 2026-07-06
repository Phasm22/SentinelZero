from __future__ import annotations

import re
from typing import Any

# UDP port the pivot engine treats as an SSDP/UPnP surface.
UPNP_PORTS: tuple[int, ...] = (1900,)


def recommend_upnp_action(*, responded: bool) -> str:
    """Decision-grade triage for an upnp_discover finding.

    - ``escalate``: the host answered an unauthenticated SSDP M-SEARCH -- it
      advertises UPnP services (device description + potential IGD port-mapping
      control) to any client on the segment.
    - ``observe``: no SSDP response.
    """
    return "escalate" if responded else "observe"


def parse_ssdp_response(data: bytes) -> dict[str, Any]:
    """Parse an SSDP (HTTP-over-UDP) M-SEARCH response into structured fields."""
    text = data.decode("utf-8", "replace")
    headers: dict[str, str] = {}
    for line in text.split("\r\n")[1:]:
        if ":" in line:
            key, _, value = line.partition(":")
            headers[key.strip().upper()] = value.strip()
    return {
        "server": headers.get("SERVER"),
        "st": headers.get("ST"),
        "usn": headers.get("USN"),
        "location": headers.get("LOCATION"),
    }


def build_upnp_fields(*, responded: bool, responses: list[dict[str, Any]]) -> dict[str, Any]:
    servers = sorted({r["server"] for r in responses if r.get("server")})
    locations = sorted({r["location"] for r in responses if r.get("location")})
    service_types = sorted({r["st"] for r in responses if r.get("st")})
    return {
        "responded": responded,
        "servers": servers,
        "locations": locations,
        "service_types": service_types,
        "response_count": len(responses),
    }
