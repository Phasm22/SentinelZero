from __future__ import annotations

import re
from typing import Any

# NSE script ids the pivot engine treats as passive SSH posture fingerprinting --
# algorithm/host-key enumeration, never authentication or brute force.
SSH_AUDIT_SCRIPT_IDS = frozenset({
    "ssh-hostkey",
    "ssh2-enum-algos",
})

# Port the pivot engine treats as an SSH surface.
SSH_PORTS: tuple[int, ...] = (22,)

# Substrings marking a deprecated key exchange -- SHA-1 based or small-group DH.
_WEAK_KEX = ("group1-sha1", "group14-sha1", "group-exchange-sha1", "gss-group1-",
             "gss-group14-", "rsa1024-")
# Substrings marking a broken/legacy cipher -- CBC mode, RC4, DES family.
_WEAK_CIPHERS = ("-cbc", "arcfour", "3des", "blowfish", "cast128", "des-")
# Substrings marking a broken MAC -- MD5 or truncated.
_WEAK_MACS = ("hmac-md5", "-96")
# Exact host-key signature algorithms with a SHA-1/DSA weakness.
_WEAK_HOST_KEY_ALGOS = frozenset({"ssh-rsa", "ssh-dss"})


def recommend_ssh_action(
    *,
    weak_kex: list[str] | None,
    weak_ciphers: list[str] | None,
    weak_macs: list[str] | None,
    weak_host_key_algos: list[str] | None,
    algos_parsed: bool,
) -> str:
    """Decision-grade triage for an ssh_audit finding.

    Returns one of ``escalate`` | ``next_scan`` | ``observe`` (never a blue-team
    verdict). Shared by the live ssh_audit dispatch and the hydrated-evidence
    finding so both paths grade identically.

    - ``escalate``: the server offers a deprecated key exchange, a broken/legacy
      cipher, a broken MAC, or a SHA-1/DSA host-key signature algorithm.
    - ``next_scan``: the port answered but no algorithms could be parsed.
    - ``observe``: only modern algorithms are offered.
    """
    if not algos_parsed:
        return "next_scan"
    if (weak_kex or []) or (weak_ciphers or []) or (weak_macs or []) or (weak_host_key_algos or []):
        return "escalate"
    return "observe"


def _parse_algo_sections(output: str) -> dict[str, list[str]]:
    """Parse the ssh2-enum-algos ``output`` text into {section: [algorithm,...]}.

    Section headers look like ``kex_algorithms: (12)`` followed by indented
    algorithm names, one per line, until the next header.
    """
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw in output.splitlines():
        header = re.match(r"^\s*([a-z_]+):\s*\(\d+\)\s*$", raw)
        if header:
            current = header.group(1)
            sections[current] = []
            continue
        if current is not None:
            token = raw.strip()
            if token:
                sections[current].append(token)
    return sections


def _parse_host_keys(output: str) -> list[dict[str, Any]]:
    """Parse the ssh-hostkey ``output`` text into a list of host key descriptors.

    Lines look like ``2048 aa:bb:cc:... (RSA)`` or
    ``256 SHA256:abc... (ED25519)``.
    """
    keys: list[dict[str, Any]] = []
    for raw in output.splitlines():
        match = re.match(r"^\s*(\d+)\s+(\S+)\s+\((\w+)\)\s*$", raw)
        if match:
            keys.append({
                "bits": int(match.group(1)),
                "fingerprint": match.group(2),
                "type": match.group(3),
            })
    return keys


def _match_weak(algorithms: list[str], substrings: tuple[str, ...]) -> list[str]:
    return [a for a in algorithms if any(s in a for s in substrings)]


def parse_ssh_scripts(scripts: dict[str, str]) -> dict[str, Any]:
    """Turn a {script_id: raw nmap script output} map into structured ssh_audit fields.

    Shared by hydration.py (reading a prior scan's vulns_json) and ssh_audit_runner.py
    (reading a fresh nmap NSE run) so both sources produce identical finding shapes.
    """
    sections = _parse_algo_sections(scripts.get("ssh2-enum-algos") or "")
    kex = sections.get("kex_algorithms", [])
    host_key_algos = sections.get("server_host_key_algorithms", [])
    ciphers = sections.get("encryption_algorithms", [])
    macs = sections.get("mac_algorithms", [])

    host_keys = _parse_host_keys(scripts.get("ssh-hostkey") or "")

    algos_parsed = bool(kex or ciphers or macs or host_key_algos)

    return {
        "kex_algorithms": kex,
        "server_host_key_algorithms": host_key_algos,
        "encryption_algorithms": ciphers,
        "mac_algorithms": macs,
        "host_keys": host_keys,
        "weak_kex": _match_weak(kex, _WEAK_KEX),
        "weak_ciphers": _match_weak(ciphers, _WEAK_CIPHERS),
        "weak_macs": _match_weak(macs, _WEAK_MACS),
        "weak_host_key_algos": [a for a in host_key_algos if a in _WEAK_HOST_KEY_ALGOS],
        "algos_parsed": algos_parsed,
    }
