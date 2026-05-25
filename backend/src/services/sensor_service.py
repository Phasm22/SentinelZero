"""Query helpers for sensor agent data, used by routes and InsightsGenerator."""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from typing import List, Optional

from ..models.sensor import SensorAgent, SensorTelemetry


def get_agent_by_ip(db, ip: str) -> Optional[SensorAgent]:
    return SensorAgent.query.filter_by(host_ip=ip).first()


def get_agent_by_id(db, agent_id: str) -> Optional[SensorAgent]:
    return SensorAgent.query.filter_by(agent_id=agent_id).first()


def get_latest_collectors(db, agent_id: str) -> dict:
    """Most recent telemetry payload for an agent, or empty dict."""
    row = (
        SensorTelemetry.query
        .filter_by(agent_id=agent_id)
        .order_by(SensorTelemetry.collected_at.desc())
        .first()
    )
    if not row:
        return {}
    try:
        return json.loads(row.collectors_json or '{}')
    except (json.JSONDecodeError, TypeError):
        return {}


def get_timeline(db, agent_id: str, minutes: int = 120) -> List[SensorTelemetry]:
    from_dt = datetime.utcnow() - timedelta(minutes=minutes)
    return (
        SensorTelemetry.query
        .filter(
            SensorTelemetry.agent_id == agent_id,
            SensorTelemetry.collected_at >= from_dt,
        )
        .order_by(SensorTelemetry.collected_at.asc())
        .all()
    )


def get_process_events(
    db,
    agent_id: str,
    minutes: int = 120,
    process_name: Optional[str] = None,
) -> List[dict]:
    """
    Walk consecutive telemetry rows and return process start/stop events.

    This is the primary endpoint for the analysis agent — it answers questions
    like "when did proxmox-backup-proxy start and what ports did it open?"
    """
    rows = get_timeline(db, agent_id, minutes)
    events = []
    prev_proc_map: dict = {}  # pid -> process dict

    for row in rows:
        try:
            collectors = json.loads(row.collectors_json or '{}')
        except (json.JSONDecodeError, TypeError):
            collectors = {}

        procs = collectors.get('processes', [])
        conns = collectors.get('connections', [])

        # Build pid -> process for this row
        curr_proc_map = {p['pid']: p for p in procs if isinstance(p.get('pid'), int)}

        # Build pid -> listening ports for this row
        pid_ports: dict = {}
        for c in conns:
            if c.get('state') == 'LISTEN' and c.get('pid') and c.get('local_addr'):
                pid_ports.setdefault(c['pid'], []).append(c['local_addr'])

        # New PIDs that weren't in the previous row
        for pid, proc in curr_proc_map.items():
            if pid not in prev_proc_map:
                name = proc.get('name', '')
                if process_name and name != process_name:
                    continue
                events.append({
                    'collected_at': row.collected_at.isoformat(),
                    'event_type': 'process_started',
                    'process': proc,
                    'listening_ports': pid_ports.get(pid, []),
                })

        # PIDs that disappeared
        for pid, proc in prev_proc_map.items():
            if pid not in curr_proc_map:
                name = proc.get('name', '')
                if process_name and name != process_name:
                    continue
                events.append({
                    'collected_at': row.collected_at.isoformat(),
                    'event_type': 'process_stopped',
                    'process': proc,
                    'listening_ports': [],
                })

        prev_proc_map = curr_proc_map

    return events


def compute_agent_status(agent: SensorAgent) -> str:
    if not agent.last_seen_at:
        return 'unknown'
    age = (datetime.utcnow() - agent.last_seen_at).total_seconds()
    if age < 300:
        return 'active'
    if age < 900:
        return 'stale'
    return 'offline'


def prune_old_telemetry(days: int = 30) -> int:
    """APScheduler entry point — uses the app db session."""
    from ..config.database import db

    cutoff = datetime.utcnow() - timedelta(days=days)
    deleted = (
        SensorTelemetry.query
        .filter(SensorTelemetry.collected_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.session.commit()
    return deleted


def network_segment_for_ip(ip: str) -> str:
    """Map a host IP to lab or home for Pi-hole context selection."""
    if ip.startswith(("172.16.", "10.")):
        return "lab"
    if ip.startswith(("192.168.68.", "192.168.71.")):
        return "home"
    return "lab"


def get_network_sensor_context(db, host_ip: str) -> dict:
    """
    Pull recent DNS/flow context from network sensors for the host's segment.
    Used when enriching host-level scan insights (not tied to the sensor agent IP).
    """
    segment = network_segment_for_ip(host_ip)
    ctx: dict = {"segment": segment}

    pihole_id = "pihole-lab" if segment == "lab" else "pihole-home"
    pihole = get_latest_collectors(db, pihole_id)
    if pihole:
        blocked = pihole.get("top_blocked") or []
        if isinstance(blocked, dict):
            blocked = [{"domain": k, "count": v} for k, v in list(blocked.items())[:5]]
        ctx["top_blocked"] = blocked[:5]
        ctx["top_clients"] = (pihole.get("top_clients") or [])[:5]

    ntop = get_latest_collectors(db, "opnsense-ntopng")
    if ntop:
        alerts = ntop.get("alerts") or []
        if isinstance(alerts, dict):
            alerts = alerts.get("engaged", alerts.get("items", []))
        ctx["alerted_flows"] = alerts[:5]
        flagged = [
            h for h in (ntop.get("active_hosts") or [])
            if h.get("ip") == host_ip or str(h.get("ip", "")).startswith(host_ip)
        ]
        if flagged:
            ctx["host_flow_score"] = flagged[:3]

    opn = get_latest_collectors(db, "opnsense")
    if opn:
        ids = opn.get("ids_alerts") or []
        host_ids = [a for a in ids if host_ip in json.dumps(a)][:5]
        if host_ids:
            ctx["ids_alerts"] = host_ids

    return {k: v for k, v in ctx.items() if v}
