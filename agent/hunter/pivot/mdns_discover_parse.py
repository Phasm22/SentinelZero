from __future__ import annotations

from typing import Any

# UDP port the pivot engine treats as an mDNS surface.
MDNS_PORTS: tuple[int, ...] = (5353,)


def recommend_mdns_action(*, responded: bool) -> str:
    """Decision-grade triage for an mdns_discover finding.

    - ``escalate``: the host answered an unauthenticated mDNS query -- it
      discloses its hostname and advertised service inventory to the segment.
    - ``observe``: no mDNS response.
    """
    return "escalate" if responded else "observe"


def build_mdns_fields(*, responded: bool, services: list[str], names: list[str]) -> dict[str, Any]:
    return {
        "responded": responded,
        "services": sorted(set(services)),
        "names": sorted(set(names)),
        "service_count": len(set(services)),
    }
