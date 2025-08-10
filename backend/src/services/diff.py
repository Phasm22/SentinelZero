"""Smart diff service for comparing a scan with the previous scan of the same type.

Produces a lightweight, structured diff without persisting additional state.
"""
from __future__ import annotations
import json
from typing import Dict, Any, List, Optional
from ..models.scan import Scan


def _get_previous_scan(current: Scan) -> Optional[Scan]:
    return (Scan.query
            .filter(Scan.scan_type == current.scan_type,
                    Scan.id != current.id,
                    Scan.status == 'complete')
            .order_by(Scan.created_at.desc())
            .first())


def _index_hosts(hosts: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    indexed = {}
    for h in hosts or []:
        ip = h.get('ip')
        if ip:
            indexed[ip] = h
    return indexed


def _extract_ports(host: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    result = {}
    for p in (host.get('ports') or []):
        try:
            port_no = int(p.get('port'))
        except Exception:
            continue
        result[port_no] = p
    return result


def _get_vuln_id(v: Dict[str, Any]) -> str:
    return v.get('id') or v.get('vuln_id') or v.get('plugin_id') or v.get('cve') or v.get('name') or ''


def compute_scan_diff(scan_id: int) -> Dict[str, Any]:
    """Compute a structured diff for the given scan id.

    Returns a dict with baseline flag when no previous scan exists.
    """
    scan = Scan.query.get(scan_id)
    if not scan or scan.status != 'complete':
        return {'error': 'Scan not found or not complete'}

    try:
        current_hosts = json.loads(scan.hosts_json) if scan.hosts_json else []
        current_vulns = json.loads(scan.vulns_json) if scan.vulns_json else []
    except Exception:
        current_hosts, current_vulns = [], []

    previous = _get_previous_scan(scan)
    if not previous:
        return {
            'scan_id': scan.id,
            'previous_scan_id': None,
            'baseline': True,
            'summary': {
                'new_hosts': len(current_hosts),
                'removed_hosts': 0,
                'new_ports': sum(len(h.get('ports') or []) for h in current_hosts),
                'closed_ports': 0,
                'new_vulns': len(current_vulns),
                'resolved_vulns': 0
            },
            'hosts': {
                'new': [h.get('ip') for h in current_hosts if h.get('ip')],
                'removed': [],
                'changed': []
            },
            'vulns': {
                'new': current_vulns,
                'resolved': []
            }
        }

    try:
        previous_hosts = json.loads(previous.hosts_json) if previous.hosts_json else []
        previous_vulns = json.loads(previous.vulns_json) if previous.vulns_json else []
    except Exception:
        previous_hosts, previous_vulns = [], []

    prev_hosts_index = _index_hosts(previous_hosts)
    curr_hosts_index = _index_hosts(current_hosts)

    prev_ips = set(prev_hosts_index.keys())
    curr_ips = set(curr_hosts_index.keys())

    new_ips = sorted(curr_ips - prev_ips)
    removed_ips = sorted(prev_ips - curr_ips)

    changed_hosts: List[Dict[str, Any]] = []
    total_new_ports = 0
    total_closed_ports = 0

    for ip in sorted(curr_ips & prev_ips):
        curr_host = curr_hosts_index[ip]
        prev_host = prev_hosts_index[ip]
        curr_ports = _extract_ports(curr_host)
        prev_ports = _extract_ports(prev_host)
        curr_port_set = set(curr_ports.keys())
        prev_port_set = set(prev_ports.keys())
        host_new_ports = sorted(curr_port_set - prev_port_set)
        host_closed_ports = sorted(prev_port_set - curr_port_set)
        if host_new_ports or host_closed_ports:
            changed_hosts.append({
                'ip': ip,
                'new_ports': [
                    {
                        'port': p,
                        'service': curr_ports[p].get('service'),
                        'protocol': curr_ports[p].get('protocol')
                    } for p in host_new_ports
                ],
                'closed_ports': host_closed_ports
            })
            total_new_ports += len(host_new_ports)
            total_closed_ports += len(host_closed_ports)

    # Vulnerability diffs
    curr_vuln_map = {_get_vuln_id(v): v for v in current_vulns if _get_vuln_id(v)}
    prev_vuln_map = {_get_vuln_id(v): v for v in previous_vulns if _get_vuln_id(v)}
    curr_vuln_ids = set(curr_vuln_map.keys())
    prev_vuln_ids = set(prev_vuln_map.keys())
    new_vuln_ids = curr_vuln_ids - prev_vuln_ids
    resolved_vuln_ids = prev_vuln_ids - curr_vuln_ids

    diff = {
        'scan_id': scan.id,
        'previous_scan_id': previous.id,
        'baseline': False,
        'summary': {
            'new_hosts': len(new_ips),
            'removed_hosts': len(removed_ips),
            'new_ports': total_new_ports + sum(len(h.get('ports') or []) for h in current_hosts if h.get('ip') in new_ips),
            'closed_ports': total_closed_ports + sum(len(h.get('ports') or []) for h in previous_hosts if h.get('ip') in removed_ips),
            'new_vulns': len(new_vuln_ids),
            'resolved_vulns': len(resolved_vuln_ids)
        },
        'hosts': {
            'new': new_ips,
            'removed': removed_ips,
            'changed': changed_hosts
        },
        'vulns': {
            'new': [curr_vuln_map[i] for i in sorted(new_vuln_ids)],
            'resolved': [prev_vuln_map[i] for i in sorted(resolved_vuln_ids)]
        }
    }
    return diff
