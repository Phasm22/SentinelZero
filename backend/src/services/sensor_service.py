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


def get_telemetry_window(
    db,
    agent_id: str,
    anchor_ts: datetime,
    before: int = 15,
    after: int = 15,
) -> List[SensorTelemetry]:
    """Telemetry rows within ±window minutes of an anchor timestamp.

    Used to align sensor data to a scan's actual completion time
    (scan.completed_at) instead of a fixed sliding window from 'now'.
    """
    start = anchor_ts - timedelta(minutes=before)
    end = anchor_ts + timedelta(minutes=after)
    return (
        SensorTelemetry.query
        .filter(
            SensorTelemetry.agent_id == agent_id,
            SensorTelemetry.collected_at >= start,
            SensorTelemetry.collected_at <= end,
        )
        .order_by(SensorTelemetry.collected_at.asc())
        .all()
    )


def get_process_events(
    db,
    agent_id: str,
    minutes: int = 120,
    process_name: Optional[str] = None,
    anchor_ts: Optional[datetime] = None,
    before: int = 15,
    after: int = 15,
) -> List[dict]:
    """
    Walk consecutive telemetry rows and return process start/stop events.

    This is the primary endpoint for the analysis agent — it answers questions
    like "when did proxmox-backup-proxy start and what ports did it open?"

    When ``anchor_ts`` is given, rows are scoped to ±window minutes around it
    (the scan's completion time); otherwise a sliding ``minutes`` window from now.
    """
    if anchor_ts is not None:
        rows = get_telemetry_window(db, agent_id, anchor_ts, before, after)
    else:
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


def _loads(blob) -> dict:
    try:
        return json.loads(blob or '{}')
    except (json.JSONDecodeError, TypeError):
        return {}


def _rows_for(db, agent_id, anchor_ts=None, minutes=120, before=15, after=15):
    if anchor_ts is not None:
        return get_telemetry_window(db, agent_id, anchor_ts, before, after)
    return get_timeline(db, agent_id, minutes)


def _closest_row(rows, anchor_ts=None):
    if not rows:
        return None
    if anchor_ts is None:
        return rows[-1]
    return min(rows, key=lambda r: abs((r.collected_at - anchor_ts).total_seconds()))


# Auth events worth surfacing to the analyst by default (the rest is login noise).
_NOTABLE_AUTH = {'ssh_login_fail', 'sudo_command', 'user_change'}


def get_auth_events(db, agent_id, anchor_ts=None, minutes=120, only_notable=True) -> List[dict]:
    """Deduplicated auth events (ssh failures, sudo, user add/del) in the window.

    Consecutive telemetry rows carry overlapping tails of recent auth events, so
    dedup by (ts, event, user, source, command).
    """
    rows = _rows_for(db, agent_id, anchor_ts, minutes)
    seen = set()
    events: List[dict] = []
    for row in rows:
        for ev in _loads(row.collectors_json).get('auth') or []:
            if not isinstance(ev, dict):
                continue
            if only_notable and ev.get('event') not in _NOTABLE_AUTH:
                continue
            key = (
                ev.get('ts'), ev.get('event'), ev.get('user'),
                ev.get('source'), ev.get('command'), ev.get('action'),
            )
            if key in seen:
                continue
            seen.add(key)
            events.append(ev)
    return events


def get_failed_services(db, agent_id, anchor_ts=None, minutes=120) -> List[dict]:
    """Failed systemd units from the telemetry row closest to the anchor."""
    row = _closest_row(_rows_for(db, agent_id, anchor_ts, minutes), anchor_ts)
    if not row:
        return []
    return [
        s for s in (_loads(row.collectors_json).get('services') or [])
        if isinstance(s, dict) and s.get('state') == 'failed'
    ]


def get_connections_at(db, agent_id, anchor_ts=None, minutes=120, cap=60) -> dict:
    """ESTABLISHED + LISTEN connections from the row closest to the anchor."""
    row = _closest_row(_rows_for(db, agent_id, anchor_ts, minutes), anchor_ts)
    if not row:
        return {}
    conns = _loads(row.collectors_json).get('connections') or []
    established = [c for c in conns if isinstance(c, dict) and c.get('state') == 'ESTABLISHED']
    listening = [c for c in conns if isinstance(c, dict) and c.get('state') == 'LISTEN']
    return {
        'collected_at': row.collected_at.isoformat(),
        'established_count': len(established),
        'listen_count': len(listening),
        'established': established[:cap],
        'listening': listening[:cap],
    }


def get_proxmox_context(db, agent_id, anchor_ts=None, minutes=120) -> dict:
    """Proxmox node / guest snapshot from the row closest to the anchor."""
    row = _closest_row(_rows_for(db, agent_id, anchor_ts, minutes), anchor_ts)
    if not row:
        return {}
    return _loads(row.collectors_json).get('proxmox') or {}


def get_endpoint_security_context(db, agent_id, anchor_ts=None, minutes=120) -> dict:
    """Compact security signals (auth failures, failed services, proxmox) for
    pre-enrichment — attached to insights so the LLM sees them without a tool call."""
    ctx: dict = {}
    auth = get_auth_events(db, agent_id, anchor_ts, minutes)
    fails = [a for a in auth if a.get('event') == 'ssh_login_fail']
    if fails:
        by_source: dict = {}
        for a in fails:
            by_source[a.get('source') or 'unknown'] = by_source.get(a.get('source') or 'unknown', 0) + 1
        ctx['ssh_failures'] = {'total': len(fails), 'by_source': by_source}
    other = [a for a in auth if a.get('event') in ('sudo_command', 'user_change')]
    if other:
        ctx['auth_changes'] = other[:8]
    failed_services = get_failed_services(db, agent_id, anchor_ts, minutes)
    if failed_services:
        ctx['failed_services'] = [s.get('name') for s in failed_services][:12]
    pmx = get_proxmox_context(db, agent_id, anchor_ts, minutes)
    if pmx:
        ctx['proxmox'] = {
            'node': pmx.get('node'),
            'node_status': pmx.get('node_status'),
            'running_guests': pmx.get('running_guests'),
            'guest_count': pmx.get('guest_count'),
        }
    return ctx


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
