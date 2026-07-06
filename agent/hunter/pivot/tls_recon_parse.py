from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

# NSE script ids the pivot engine treats as passive TLS posture fingerprinting --
# certificate + offered-cipher identification, never exploitation.
TLS_RECON_SCRIPT_IDS = frozenset({
    "ssl-cert",
    "ssl-enum-ciphers",
})

# Ports the pivot engine treats as TLS surfaces, in the priority order tls_recon
# should target when several are open on one host.
TLS_PORTS: tuple[int, ...] = (443, 8443)

# Protocol versions considered weak/deprecated -- their presence is a posture
# signal worth escalating regardless of cipher grade.
_WEAK_PROTOCOLS = ("SSLv2", "SSLv3", "TLSv1.0", "TLSv1.1")

# nmap ssl-enum-ciphers "least strength" grades that warrant escalation.
_WEAK_CIPHER_GRADES = frozenset({"C", "D", "E", "F"})

_CERT_TIME_FORMATS = ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z")


def _parse_cert_time(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    for fmt in _CERT_TIME_FORMATS:
        try:
            dt = datetime.strptime(value, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def recommend_tls_action(
    *,
    expired: bool,
    self_signed: bool,
    weak_protocols: list[str] | None,
    cipher_grade: str | None,
    cert_parsed: bool,
) -> str:
    """Decision-grade triage for a tls_recon finding.

    Returns one of ``escalate`` | ``next_scan`` | ``observe`` (never a blue-team
    verdict). Shared by the live tls_recon dispatch and the hydrated-evidence
    finding so both paths grade identically.

    - ``escalate``: the cert is expired, self-signed (no trusted chain), a
      deprecated protocol (SSLv3/TLSv1.0/TLSv1.1) is offered, or nmap graded the
      weakest cipher C or worse.
    - ``next_scan``: the port answered but no certificate could be parsed --
      worth a deeper look before deciding.
    - ``observe``: CA-signed cert, modern TLS only, grade A/B.
    """
    if not cert_parsed:
        return "next_scan"

    grade = (cipher_grade or "").strip().upper()
    if (
        expired
        or self_signed
        or (weak_protocols or [])
        or grade in _WEAK_CIPHER_GRADES
    ):
        return "escalate"

    return "observe"


def _parse_ssl_cert(output: str) -> dict[str, Any]:
    subject_cn = None
    match = re.search(r"^Subject:.*?commonName=([^\n/]+)", output, re.MULTILINE)
    if match:
        subject_cn = match.group(1).strip() or None

    issuer_cn = None
    match = re.search(r"^Issuer:.*?commonName=([^\n/]+)", output, re.MULTILINE)
    if match:
        issuer_cn = match.group(1).strip() or None

    sans: list[str] = []
    match = re.search(r"^Subject Alternative Name:\s*(.+)$", output, re.MULTILINE)
    if match:
        for entry in match.group(1).split(","):
            entry = entry.strip()
            if entry:
                sans.append(entry)

    not_before = None
    match = re.search(r"^Not valid before:\s*(.+)$", output, re.MULTILINE)
    if match:
        not_before = match.group(1).strip() or None

    not_after = None
    match = re.search(r"^Not valid after:\s*(.+)$", output, re.MULTILINE)
    if match:
        not_after = match.group(1).strip() or None

    self_signed = bool(subject_cn and issuer_cn and subject_cn == issuer_cn)

    expired = False
    days_to_expiry = None
    after_dt = _parse_cert_time(not_after)
    if after_dt is not None:
        now = datetime.now(timezone.utc)
        delta = after_dt - now
        days_to_expiry = delta.days
        expired = delta.total_seconds() < 0

    return {
        "subject_cn": subject_cn,
        "issuer_cn": issuer_cn,
        "sans": sans,
        "not_before": not_before,
        "not_after": not_after,
        "self_signed": self_signed,
        "expired": expired,
        "days_to_expiry": days_to_expiry,
        "cert_parsed": bool(subject_cn or not_after),
    }


def _parse_ssl_ciphers(output: str) -> dict[str, Any]:
    tls_versions = sorted(set(re.findall(r"^\s*(SSLv[23]|TLSv1\.[0-3]):", output, re.MULTILINE)))
    weak_protocols = [v for v in tls_versions if v in _WEAK_PROTOCOLS]

    cipher_grade = None
    match = re.search(r"least strength:\s*([A-F])", output)
    if match:
        cipher_grade = match.group(1).strip() or None

    return {
        "tls_versions": tls_versions,
        "weak_protocols": weak_protocols,
        "cipher_grade": cipher_grade,
    }


def parse_tls_scripts(scripts: dict[str, str]) -> dict[str, Any]:
    """Turn a {script_id: raw nmap script output} map into structured tls_recon fields.

    Shared by hydration.py (reading a prior scan's vulns_json) and tls_recon_runner.py
    (reading a fresh nmap NSE run) so both sources produce identical finding shapes.
    """
    cert = _parse_ssl_cert(scripts.get("ssl-cert") or "")
    ciphers = _parse_ssl_ciphers(scripts.get("ssl-enum-ciphers") or "")
    return {**cert, **ciphers}
