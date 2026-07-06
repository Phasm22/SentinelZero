from __future__ import annotations

from typing import Any

# Port the pivot engine treats as a DNS surface.
DNS_PORTS: tuple[int, ...] = (53,)

# Substrings that identify the resolver software from a version.bind string.
_SOFTWARE_MARKERS = (
    ("pi-hole", "pi-hole"),
    ("dnsmasq", "dnsmasq"),
    ("unbound", "unbound"),
    ("powerdns", "powerdns"),
    ("bind", "bind"),
    ("knot", "knot"),
    ("coredns", "coredns"),
)


def identify_software(version: str | None) -> str | None:
    if not version:
        return None
    v = version.lower()
    for marker, name in _SOFTWARE_MARKERS:
        if marker in v:
            return name
    return None


def recommend_dns_action(
    *,
    responded: bool,
    recursion_available: bool,
    recursion_tested: bool,
) -> str:
    """Decision-grade triage for a dns_recon finding.

    Returns one of ``escalate`` | ``next_scan`` | ``observe`` (never a blue-team
    verdict).

    - ``escalate``: the server recursively resolved an external name for us -- an
      open resolver reachable from the pivot host is a DNS amplification / cache
      poisoning surface.
    - ``next_scan``: the server answered but recursion could not be tested.
    - ``observe``: recursion refused (authoritative-only), or no response.
    """
    if not responded:
        return "observe"
    if recursion_available:
        return "escalate"
    if not recursion_tested:
        return "next_scan"
    return "observe"


def build_dns_fields(
    *,
    responded: bool,
    recursion_available: bool,
    recursion_tested: bool,
    version: str | None,
) -> dict[str, Any]:
    """Assemble structured dns_recon fields from a runner probe result."""
    return {
        "responded": responded,
        "recursion_available": recursion_available,
        "recursion_tested": recursion_tested,
        "version": version,
        "software": identify_software(version),
    }
