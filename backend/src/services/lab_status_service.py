"""Dashboard-ready lab status aggregation.

Combines the cached What's Up reachability snapshot with the latest sensor
telemetry. The service is deliberately read-only and uses a small in-memory
cache because network sensor payloads can be large.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func

from ..models.sensor import SensorAgent, SensorTelemetry
from . import sensor_service
from .whats_up import get_summary_data


DNS_TOP_CAP = 10
FLOW_HOST_CAP = 15
ATTENTION_CAP = 20
DEFAULT_WINDOW_MINUTES = 120
CACHE_TTL_SECONDS = 20

_CACHE_LOCK = threading.Lock()
_CACHE: dict[tuple[int], tuple[float, dict]] = {}


def _utcnow() -> datetime:
    return datetime.utcnow()


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _age_seconds(dt: datetime | None, now: datetime | None = None) -> int | None:
    if not dt:
        return None
    return max(0, int(((now or _utcnow()) - dt).total_seconds()))


def _loads(blob: str | None) -> dict:
    try:
        data = json.loads(blob or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        rows = value.get("rows") or value.get("items") or value.get("data")
        if isinstance(rows, list):
            return [item for item in rows if isinstance(item, dict)]
        return [
            {"name": key, "count": val}
            for key, val in value.items()
            if not isinstance(val, (dict, list))
        ]
    return []


def _to_number(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().rstrip("%"))
        except ValueError:
            return default
    return default


def _total_bytes(item: dict) -> float:
    return _to_number(item.get("bytes_sent")) + _to_number(item.get("bytes_rcvd"))


def _row_collectors(row: SensorTelemetry | None) -> dict:
    return _loads(row.collectors_json) if row else {}


def _latest_rows_by_agent() -> dict[str, SensorTelemetry]:
    latest_times = (
        SensorTelemetry.query
        .with_entities(
            SensorTelemetry.agent_id.label("agent_id"),
            func.max(SensorTelemetry.collected_at).label("collected_at"),
        )
        .group_by(SensorTelemetry.agent_id)
        .subquery()
    )
    rows = (
        SensorTelemetry.query
        .join(
            latest_times,
            and_(
                SensorTelemetry.agent_id == latest_times.c.agent_id,
                SensorTelemetry.collected_at == latest_times.c.collected_at,
            ),
        )
        .all()
    )
    latest: dict[str, SensorTelemetry] = {}
    for row in rows:
        latest.setdefault(row.agent_id, row)
    return latest


def _timeline_rows_by_agent(window_minutes: int) -> dict[str, list[SensorTelemetry]]:
    cutoff = _utcnow() - timedelta(minutes=window_minutes)
    rows = (
        SensorTelemetry.query
        .filter(SensorTelemetry.collected_at >= cutoff)
        .order_by(SensorTelemetry.agent_id.asc(), SensorTelemetry.collected_at.asc())
        .all()
    )
    by_agent: dict[str, list[SensorTelemetry]] = {}
    for row in rows:
        by_agent.setdefault(row.agent_id, []).append(row)
    return by_agent


def _collector_warning(value: Any) -> str | None:
    if isinstance(value, dict) and value.get("error"):
        return str(value.get("error"))
    return None


def normalize_ntop_active_hosts(raw: Any) -> dict:
    """Normalize current and legacy ntopng active host payloads.

    Current sensors emit ``{"total_active": n, "flagged": [...]}``. Older code
    treated ``active_hosts`` as a list. This function accepts both.
    """
    if isinstance(raw, dict):
        flagged = _as_list(raw.get("flagged") or raw.get("hosts"))
        total_active = int(_to_number(raw.get("total_active"), len(flagged)))
    elif isinstance(raw, list):
        hosts = [item for item in raw if isinstance(item, dict)]
        total_active = len(hosts)
        flagged = []
        for host in hosts:
            score = host.get("score", 0)
            score_total = score.get("total", 0) if isinstance(score, dict) else score
            if _to_number(score_total) > 0 or _to_number(host.get("num_alerts")) > 0:
                flagged.append({
                    "ip": host.get("ip") or host.get("host"),
                    "name": host.get("name") or host.get("hostname"),
                    "score": _to_number(score_total),
                    "num_alerts": int(_to_number(host.get("num_alerts"))),
                    "bytes_sent": host.get("bytes_sent"),
                    "bytes_rcvd": host.get("bytes_rcvd"),
                })
    else:
        total_active = 0
        flagged = []

    normalized = []
    for host in flagged:
        score = host.get("score", 0)
        normalized.append({
            "ip": host.get("ip") or host.get("host"),
            "name": host.get("name") or host.get("hostname"),
            "score": _to_number(score.get("total", 0) if isinstance(score, dict) else score),
            "num_alerts": int(_to_number(host.get("num_alerts"))),
            "bytes_sent": host.get("bytes_sent"),
            "bytes_rcvd": host.get("bytes_rcvd"),
        })

    normalized.sort(key=lambda item: (item.get("score") or 0, _total_bytes(item)), reverse=True)
    return {
        "total_active": total_active,
        "flagged": normalized[:FLOW_HOST_CAP],
        "flagged_count": len(normalized),
    }


def normalize_ntopng_payload(payload: dict, row: SensorTelemetry | None = None) -> dict:
    active_hosts = normalize_ntop_active_hosts(payload.get("active_hosts"))
    alerts = _as_list(payload.get("alerts"))[:ATTENTION_CAP]
    interfaces = _as_list(payload.get("interface_stats"))
    traffic_total_bps = sum(_to_number(item.get("throughput_bps")) for item in interfaces)
    return {
        "status": "available" if payload else "unavailable",
        "agent_id": row.agent_id if row else None,
        "collected_at": _iso(row.collected_at) if row else None,
        "active_host_count": active_hosts["total_active"],
        "flagged_hosts": active_hosts["flagged"],
        "flagged_host_count": active_hosts["flagged_count"],
        "alerts": alerts,
        "alert_count": len(alerts),
        "interface_stats": interfaces,
        "traffic_total_bps": traffic_total_bps,
        "top_protocols": _as_list(payload.get("l7_stats"))[:DNS_TOP_CAP],
    }


def _normalize_dns_entries(value: Any, cap: int = DNS_TOP_CAP) -> list[dict]:
    entries = _as_list(value)
    out = []
    for entry in entries:
        name = (
            entry.get("domain") or entry.get("name") or entry.get("client")
            or entry.get("ip") or entry.get("host")
        )
        count = entry.get("count")
        if count is None:
            count = entry.get("queries") or entry.get("total") or entry.get("value")
        out.append({**entry, "name": name, "count": count})
    return out[:cap]


def normalize_pihole_payload(payload: dict, row: SensorTelemetry | None = None, source: str = "") -> dict:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    return {
        "status": "available" if payload else "unavailable",
        "source": source,
        "agent_id": row.agent_id if row else None,
        "collected_at": _iso(row.collected_at) if row else None,
        "summary": {
            "total_queries": summary.get("total"),
            "blocked_queries": summary.get("blocked"),
            "percent_blocked": _to_number(summary.get("percent_blocked")),
            "unique_domains": summary.get("unique_domains"),
            "forwarded": summary.get("forwarded"),
            "cached": summary.get("cached"),
            "query_types": summary.get("query_types") or {},
        },
        "top_clients": _normalize_dns_entries(payload.get("top_clients")),
        "top_domains": _normalize_dns_entries(payload.get("top_domains")),
        "top_blocked": _normalize_dns_entries(payload.get("top_blocked")),
    }


def normalize_opnsense_payload(payload: dict, row: SensorTelemetry | None = None) -> dict:
    dhcp_leases = _as_list(payload.get("dhcp_leases"))
    arp_table = _as_list(payload.get("arp_table"))
    gateways = _as_list(payload.get("gateway_status"))
    ids_alerts = _as_list(payload.get("ids_alerts"))
    interfaces = _as_list(payload.get("interface_stats"))
    traffic = _as_list(payload.get("traffic"))
    gateway_down = [
        gw for gw in gateways
        if "down" in str(gw.get("status") or "").lower()
        or "offline" in str(gw.get("status") or "").lower()
    ]
    return {
        "status": "available" if payload else "unavailable",
        "agent_id": row.agent_id if row else None,
        "collected_at": _iso(row.collected_at) if row else None,
        "system_info": payload.get("system_info") if isinstance(payload.get("system_info"), dict) else {},
        "gateways": gateways,
        "gateway_count": len(gateways),
        "gateway_down_count": len(gateway_down),
        "interface_stats": interfaces,
        "traffic": traffic,
        "dhcp": {
            "lease_count": len(dhcp_leases),
            "online_count": sum(1 for lease in dhcp_leases if str(lease.get("status")).lower() == "online"),
            "offline_count": sum(1 for lease in dhcp_leases if str(lease.get("status")).lower() == "offline"),
            "leases": dhcp_leases[:25],
        },
        "arp": {
            "entry_count": len(arp_table),
            "active_count": sum(1 for entry in arp_table if not entry.get("expired")),
            "entries": arp_table[:25],
        },
        "ids": {
            "alert_count": len(ids_alerts),
            "alerts": ids_alerts[:ATTENTION_CAP],
        },
    }


def _normalize_proxmox(agents: list[SensorAgent], latest_rows: dict[str, SensorTelemetry]) -> dict:
    nodes = []
    guest_total = 0
    running_guest_total = 0
    for agent in agents:
        row = latest_rows.get(agent.agent_id)
        proxmox = _row_collectors(row).get("proxmox") if row else None
        tags = []
        try:
            tags = json.loads(agent.tags or "[]")
        except (json.JSONDecodeError, TypeError):
            tags = []
        if not proxmox and "proxmox" not in tags and agent.role != "proxmox-node":
            continue
        proxmox = proxmox if isinstance(proxmox, dict) else {}
        guest_count = int(_to_number(proxmox.get("guest_count")))
        running_guests = int(_to_number(proxmox.get("running_guests")))
        guest_total += guest_count
        running_guest_total += running_guests
        nodes.append({
            "agent_id": agent.agent_id,
            "hostname": agent.hostname,
            "host_ip": agent.host_ip,
            "status": sensor_service.compute_agent_status(agent),
            "collected_at": _iso(row.collected_at) if row else None,
            "node": proxmox.get("node") or agent.hostname,
            "node_status": proxmox.get("node_status") or "unknown",
            "guest_count": guest_count,
            "running_guests": running_guests,
        })
    return {
        "status": "available" if nodes else "unavailable",
        "node_count": len(nodes),
        "guest_count": guest_total,
        "running_guests": running_guest_total,
        "nodes": nodes,
    }


def _collector_names(collectors: dict) -> list[str]:
    return sorted(name for name, value in collectors.items() if value is not None)


def normalize_sensor_fleet(
    agents: list[SensorAgent],
    latest_rows: dict[str, SensorTelemetry],
    now: datetime | None = None,
) -> dict:
    now = now or _utcnow()
    inventory = []
    counts = {"active": 0, "stale": 0, "offline": 0, "unknown": 0}
    coverage: dict[str, int] = {}
    warnings = []

    for agent in agents:
        status = sensor_service.compute_agent_status(agent)
        counts[status] = counts.get(status, 0) + 1
        row = latest_rows.get(agent.agent_id)
        collectors = _row_collectors(row)
        for name, value in collectors.items():
            coverage[name] = coverage.get(name, 0) + 1
            warning = _collector_warning(value)
            if warning:
                warnings.append({"agent_id": agent.agent_id, "collector": name, "warning": warning})
        try:
            tags = json.loads(agent.tags or "[]")
        except (json.JSONDecodeError, TypeError):
            tags = []
        inventory.append({
            "agent_id": agent.agent_id,
            "hostname": agent.hostname,
            "host_ip": agent.host_ip,
            "role": agent.role,
            "tags": tags,
            "status": status,
            "last_seen_at": _iso(agent.last_seen_at),
            "last_seen_age_seconds": _age_seconds(agent.last_seen_at, now),
            "latest_collected_at": _iso(row.collected_at) if row else None,
            "latest_collected_age_seconds": _age_seconds(row.collected_at, now) if row else None,
            "collectors": _collector_names(collectors),
        })

    return {
        "count": len(agents),
        **counts,
        "agents": inventory,
        "collector_coverage": coverage,
        "collector_warnings": warnings[:ATTENTION_CAP],
    }


def _source_freshness(source_rows: dict[str, SensorTelemetry | None], now: datetime) -> dict:
    out = {}
    for source, row in source_rows.items():
        out[source] = {
            "status": "available" if row else "unavailable",
            "collected_at": _iso(row.collected_at) if row else None,
            "age_seconds": _age_seconds(row.collected_at, now) if row else None,
        }
    return out


def _reachability_categories(snapshot: dict) -> dict:
    categories = snapshot.get("categories") or {}
    return {
        "overall_status": snapshot.get("overall_status"),
        "health_percentage": snapshot.get("health_percentage"),
        "total_items": snapshot.get("total_items"),
        "up_items": snapshot.get("up_items"),
        "down_items": snapshot.get("down_items"),
        "loopbacks": categories.get("loopbacks", {}),
        "services": categories.get("services", {}),
        "infrastructure": categories.get("infrastructure", {}),
    }


def build_attention(
    reachability: dict,
    sensor_fleet: dict,
    network: dict,
    dns: dict,
    flows: dict,
    infrastructure: dict,
) -> list[dict]:
    items = []

    for category_name in ("loopbacks", "services", "infrastructure"):
        category = reachability.get(category_name) or {}
        for target in category.get("items") or []:
            status = target.get("overall_status") or target.get("status")
            if status != "up":
                items.append({
                    "severity": "critical",
                    "score": 95,
                    "source": "reachability",
                    "title": f"{target.get('name') or target.get('ip')} is down",
                    "details": target,
                })

    for agent in sensor_fleet.get("agents") or []:
        if agent.get("status") in ("stale", "offline"):
            items.append({
                "severity": "high" if agent.get("status") == "offline" else "medium",
                "score": 85 if agent.get("status") == "offline" else 65,
                "source": "sensor_fleet",
                "title": f"{agent.get('agent_id')} sensor is {agent.get('status')}",
                "details": agent,
            })

    if (network.get("opnsense") or {}).get("gateway_down_count"):
        items.append({
            "severity": "critical",
            "score": 92,
            "source": "opnsense",
            "title": "OPNsense reports gateway degradation",
            "details": network.get("opnsense"),
        })

    ids = ((network.get("opnsense") or {}).get("ids") or {})
    if ids.get("alert_count"):
        items.append({
            "severity": "high",
            "score": 82,
            "source": "opnsense_ids",
            "title": f"{ids.get('alert_count')} IDS alert(s) present",
            "details": ids.get("alerts", [])[:5],
        })

    for scope in ("lab", "home"):
        pct = (((dns.get(scope) or {}).get("summary") or {}).get("percent_blocked") or 0)
        if pct >= 30:
            items.append({
                "severity": "medium",
                "score": 62,
                "source": f"pihole_{scope}",
                "title": f"Pi-hole {scope} block rate is high",
                "details": dns.get(scope),
            })

    for host in flows.get("flagged_hosts") or []:
        if _to_number(host.get("score")) >= 50:
            items.append({
                "severity": "high",
                "score": min(90, 70 + int(_to_number(host.get("score")) / 5)),
                "source": "ntopng",
                "title": f"High ntopng flow score for {host.get('ip') or host.get('name')}",
                "details": host,
            })

    proxmox = infrastructure.get("proxmox") or {}
    for node in proxmox.get("nodes") or []:
        if node.get("status") != "active" or node.get("node_status") not in ("online", "unknown", None):
            items.append({
                "severity": "medium",
                "score": 60,
                "source": "proxmox",
                "title": f"Proxmox node {node.get('node') or node.get('agent_id')} needs attention",
                "details": node,
            })

    items.sort(key=lambda item: item.get("score", 0), reverse=True)
    return items[:ATTENTION_CAP]


def _health_score(reachability: dict, fleet: dict, attention: list[dict]) -> int:
    reach_score = _to_number(reachability.get("health_percentage"), 0)
    fleet_count = fleet.get("count") or 0
    if fleet_count:
        fleet_score = ((fleet.get("active", 0) + (fleet.get("stale", 0) * 0.5)) / fleet_count) * 100
    else:
        fleet_score = 50
    penalty = sum(12 if item.get("severity") == "critical" else 8 if item.get("severity") == "high" else 4 for item in attention[:8])
    return max(0, min(100, int(round((reach_score * 0.55) + (fleet_score * 0.45) - penalty))))


def build_overview(window_minutes: int = DEFAULT_WINDOW_MINUTES, *, use_cache: bool = True) -> dict:
    window_minutes = max(15, min(int(window_minutes or DEFAULT_WINDOW_MINUTES), 1440))
    cache_key = (window_minutes,)
    if use_cache:
        with _CACHE_LOCK:
            cached = _CACHE.get(cache_key)
            if cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
                return cached[1]

    now = _utcnow()
    warnings = []
    try:
        whatsup = get_summary_data(refresh=False)
    except Exception as exc:
        warnings.append(f"whatsup unavailable: {exc}")
        whatsup = {}

    agents = SensorAgent.query.order_by(SensorAgent.last_seen_at.desc()).all()
    latest_rows = _latest_rows_by_agent()
    opnsense_row = latest_rows.get("opnsense")
    ntopng_row = latest_rows.get("opnsense-ntopng")
    pihole_lab_row = latest_rows.get("pihole-lab")
    pihole_home_row = latest_rows.get("pihole-home")

    opnsense = normalize_opnsense_payload(_row_collectors(opnsense_row), opnsense_row)
    ntopng = normalize_ntopng_payload(_row_collectors(ntopng_row), ntopng_row)
    dns = {
        "lab": normalize_pihole_payload(_row_collectors(pihole_lab_row), pihole_lab_row, "lab"),
        "home": normalize_pihole_payload(_row_collectors(pihole_home_row), pihole_home_row, "home"),
    }
    sensor_fleet = normalize_sensor_fleet(agents, latest_rows, now)
    reachability = _reachability_categories(whatsup)
    network = {
        "opnsense": opnsense,
        "inventory": {
            "dhcp_lease_count": opnsense["dhcp"]["lease_count"],
            "arp_entry_count": opnsense["arp"]["entry_count"],
            "active_arp_count": opnsense["arp"]["active_count"],
        },
    }
    flows = ntopng
    infrastructure = {
        "reachability": reachability.get("infrastructure", {}),
        "proxmox": _normalize_proxmox(agents, latest_rows),
    }
    attention = build_attention(reachability, sensor_fleet, network, dns, flows, infrastructure)
    health_score = _health_score(reachability, sensor_fleet, attention)
    status = "healthy" if health_score >= 80 else "degraded" if health_score >= 50 else "critical"
    if not agents and not whatsup:
        status = "unknown"

    missing_sources = [
        name for name, row in {
            "opnsense": opnsense_row,
            "opnsense-ntopng": ntopng_row,
            "pihole-lab": pihole_lab_row,
            "pihole-home": pihole_home_row,
        }.items()
        if row is None
    ]

    payload = {
        "summary": {
            "overall_status": status,
            "health_score": health_score,
            "generated_at": now.isoformat(),
            "window_minutes": window_minutes,
            "source_freshness": _source_freshness({
                "whatsup": None,
                "opnsense": opnsense_row,
                "opnsense-ntopng": ntopng_row,
                "pihole-lab": pihole_lab_row,
                "pihole-home": pihole_home_row,
            }, now),
        },
        "attention": attention,
        "reachability": reachability,
        "sensor_fleet": sensor_fleet,
        "network": network,
        "dns": dns,
        "flows": flows,
        "infrastructure": infrastructure,
        "metadata": {
            "missing_sources": missing_sources,
            "parser_warnings": warnings + [
                item["warning"] for item in sensor_fleet.get("collector_warnings", [])
            ],
            "capped_result_counts": {
                "dns_top_clients": DNS_TOP_CAP,
                "dns_top_domains": DNS_TOP_CAP,
                "flagged_hosts": FLOW_HOST_CAP,
                "attention": ATTENTION_CAP,
            },
        },
    }

    payload["summary"]["source_freshness"]["whatsup"] = {
        "status": "available" if whatsup else "unavailable",
        "collected_at": whatsup.get("last_update") or whatsup.get("timestamp"),
        "age_seconds": None,
    }

    if use_cache:
        with _CACHE_LOCK:
            _CACHE[cache_key] = (time.monotonic(), payload)
    return payload


def clear_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()
