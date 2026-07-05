from __future__ import annotations

from typing import Any

from .seed import SeedResult


def _is_offline_note(text: str) -> bool:
    lowered = text.lower()
    return ("offline" in lowered) or ("unreachable" in lowered)


def verify_findings(
    findings: list[dict[str, Any]],
    seed: SeedResult,
    assets: dict[str, Any],
    ranked: list[dict[str, Any]],
    *,
    baseline: dict[str, Any] | None = None,
    device_context: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen_ips: set[str] = set()
    passive = set(seed.passive_hosts)
    in_last_scan = set(seed.last_scan_hosts)
    ranked_lookup = {str(item.get("ip")): int(item.get("score") or 0) for item in ranked}

    for item in findings:
        ip = str(item.get("ip") or "").strip()
        if not ip:
            continue
        finding_type = str(item.get("type") or "")
        preserve = finding_type in {"new_device", "new_udp_port", "lost_udp_port", "expected_udp_violation", "iot_observation"}
        if ip in seen_ips and not preserve:
            continue
        if not preserve:
            seen_ips.add(ip)

        asset = assets.get(ip) or {}
        notes = str(asset.get("notes") or "")
        if notes and _is_offline_note(notes):
            verified = dict(item)
            verified["recommended_action"] = "none_until_online"
            out.append(verified)
            continue

        if ip in in_last_scan and ip not in passive:
            continue

        verified = dict(item)
        if ip not in passive and ranked_lookup.get(ip, 0) < 4:
            verified.setdefault("confidence", "low")
        if finding_type in {"new_device", "new_udp_port", "expected_udp_violation"}:
            verified.setdefault("recommended_action", "trigger_iot_scan")
        out.append(verified)

    return out

