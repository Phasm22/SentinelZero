"""
Insights generation service for scan comparison and network analysis
"""
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from ..models.scan import Scan
from ..config.database import db
from ..services import sensor_service
from ..services import asset_registry
from ..services.scan_scope import (
    effective_target_network,
    find_previous_scan,
    network_short_label,
    normalize_cidr,
)


class InsightsGenerator:
    """Generate insights by comparing scan results"""
    
    PRIORITY_WEIGHTS = {
        'new_vuln_critical': 100,
        'correlated': 95,
        'new_vuln_high': 90,
        'missing_host': 80,
        'registry_gap': 75,
        'new_vuln_medium': 70,
        'new_host': 60,
        'sensor_gap': 55,
        'new_port': 50,
        'service_change': 40,
        'vuln_resolved': 35,
        'new_vuln_low': 30,
        'port_closed': 20,
        'baseline_inventory': 15,
        'scan_performance': 10,
    }

    INSIGHT_MESSAGES = {
        'new_vuln_critical': "🚨 Critical vulnerability discovered",
        'new_vuln_high': "⚠️ High severity vulnerability found",
        'new_vuln_medium': "⚠️ Medium severity vulnerability detected",
        'new_vuln_low': "ℹ️ Low severity vulnerability identified",
        'new_host': "🔍 New host discovered on network",
        'missing_host': "📴 Previously active host is offline",
        'new_port': "🔓 New open port detected",
        'port_closed': "🔒 Previously open port is now closed",
        'service_change': "🔄 Service version or type changed",
        'vuln_resolved': "✅ Vulnerability resolved since last scan",
        'registry_gap': "📋 Hosts not in asset registry",
        'sensor_gap': "📡 Hosts without endpoint sensor coverage",
        'baseline_inventory': "📊 First-scan network inventory",
        'correlated': "🔗 Correlated finding cluster",
        'scan_performance': "📊 Scan duration changed significantly",
    }
    
    def __init__(self):
        pass
    
    def generate_insights(self, current_scan: Scan) -> List[Dict[str, Any]]:
        """
        Generate insights by comparing current scan with previous scan of same type
        
        Args:
            current_scan: The completed scan to analyze
            
        Returns:
            List of insight dictionaries
        """
        self._target_network = effective_target_network(current_scan)
        self._network_label = network_short_label(self._target_network)
        self._scan_id = current_scan.id
        # Anchor sensor correlation to the scan's own clock. completed_at is often
        # still unset at insight-generation time (runs before status=complete), so
        # fall back to created_at.
        self._scan_anchor = current_scan.completed_at or current_scan.created_at
        insights = []
        
        # Find previous scan of same type on the same target network (CIDR)
        previous_scan = self._get_previous_scan(current_scan)
        if not previous_scan:
            # First scan of this type - generate baseline insights
            insights = self._generate_baseline_insights(current_scan)
        else:
            # Compare with previous scan
            insights = self._compare_scans(current_scan, previous_scan)
        
        # Sort by priority and add timestamps + network scope
        insights = self._finalize_insights(insights, current_scan)
        
        return insights
    
    def _get_previous_scan(self, current_scan: Scan) -> Optional[Scan]:
        """Find the most recent completed scan of the same type and target network."""
        return find_previous_scan(current_scan)
    
    def _generate_baseline_insights(self, scan: Scan) -> List[Dict[str, Any]]:
        """First scan of this type: inventory + actionable backlog (registry/sensor/vulns)."""
        insights = []

        try:
            hosts = json.loads(scan.hosts_json) if scan.hosts_json else []
            vulns = json.loads(scan.vulns_json) if scan.vulns_json else []
            ips = [h.get('ip') for h in hosts if h.get('ip')]

            net = effective_target_network(scan) or 'unknown network'
            net_label = network_short_label(net)
            if hosts:
                insights.append({
                    'type': 'baseline_inventory',
                    'host': net,
                    'message': (
                        f"First {scan.scan_type} on {net_label} ({net}): "
                        f"{len(hosts)} active hosts recorded"
                    ),
                    'priority': self.PRIORITY_WEIGHTS['baseline_inventory'],
                    'details': {
                        'host_count': len(hosts),
                        'is_baseline': True,
                        'scan_type': scan.scan_type,
                        'target_network': net,
                        'network_label': net_label,
                    },
                })

            unregistered = asset_registry.hosts_for_registry_gap(ips, net)
            if unregistered:
                preview = ', '.join(unregistered[:8])
                if len(unregistered) > 8:
                    preview += f", +{len(unregistered) - 8} more"
                insights.append({
                    'type': 'registry_gap',
                    'host': f"{len(unregistered)} hosts",
                    'message': (
                        f"Register {len(unregistered)} lab hosts in asset registry: {preview}"
                    ),
                    'priority': self.PRIORITY_WEIGHTS['registry_gap'],
                    'details': {
                        'ips': unregistered,
                        'is_baseline': True,
                        'target_network': net,
                        'network_label': net_label,
                        'scope': 'lab_registry',
                    },
                })

            no_sensor = asset_registry.hosts_for_sensor_gap(ips, net)
            if no_sensor:
                preview = ', '.join(no_sensor[:8])
                if len(no_sensor) > 8:
                    preview += f", +{len(no_sensor) - 8} more"
                if net_label == 'Home':
                    msg = (
                        f"{len(no_sensor)} registered home host(s) lack endpoint sensor: {preview}"
                    )
                else:
                    msg = f"Deploy endpoint sensor on {len(no_sensor)} hosts: {preview}"
                insights.append({
                    'type': 'sensor_gap',
                    'host': f"{len(no_sensor)} hosts",
                    'message': msg,
                    'priority': self.PRIORITY_WEIGHTS['sensor_gap'],
                    'details': {
                        'ips': no_sensor,
                        'is_baseline': True,
                        'target_network': net,
                        'network_label': net_label,
                    },
                })

            for vuln in vulns:
                severity = self._get_vuln_severity(vuln)
                if severity not in ('critical', 'high'):
                    continue
                vuln_id = self._get_vuln_id(vuln)
                host_ip = vuln.get('host', 'unknown')
                insights.append({
                    'type': f'new_vuln_{severity}',
                    'host': host_ip,
                    'message': f"Baseline {severity} vulnerability: {vuln_id} on {host_ip}",
                    'priority': self.PRIORITY_WEIGHTS.get(f'new_vuln_{severity}', 50),
                    'details': {
                        'vuln_id': vuln_id,
                        'severity': severity,
                        'ip': host_ip,
                        'is_baseline': True,
                    },
                })

        except (json.JSONDecodeError, TypeError) as e:
            print(f"Error parsing scan data for baseline insights: {e}")

        return insights
    
    def _compare_scans(self, current: Scan, previous: Scan) -> List[Dict[str, Any]]:
        """Compare two scans and generate insights"""
        insights = []
        
        try:
            current_hosts = json.loads(current.hosts_json) if current.hosts_json else []
            previous_hosts = json.loads(previous.hosts_json) if previous.hosts_json else []
            current_vulns = json.loads(current.vulns_json) if current.vulns_json else []
            previous_vulns = json.loads(previous.vulns_json) if previous.vulns_json else []
            
            # Compare hosts
            insights.extend(self._compare_hosts(current_hosts, previous_hosts))
            
            # Compare vulnerabilities
            insights.extend(self._compare_vulnerabilities(current_vulns, previous_vulns))
            
            # Compare scan performance
            insights.extend(self._compare_performance(current, previous))
            
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Error parsing scan data for comparison: {e}")
        
        return insights
    
    def _compare_hosts(self, current_hosts: List[Dict], previous_hosts: List[Dict]) -> List[Dict[str, Any]]:
        """Compare host lists between scans"""
        insights = []
        
        current_ips = {host.get('ip') for host in current_hosts if host.get('ip')}
        previous_ips = {host.get('ip') for host in previous_hosts if host.get('ip')}
        
        # New hosts
        new_ips = current_ips - previous_ips
        for ip in new_ips:
            insight = {
                'type': 'new_host',
                'host': ip,
                'message': f"New host discovered: {ip}",
                'priority': self.PRIORITY_WEIGHTS.get('new_host', 60),
                'details': {'ip': ip}
            }
            insights.append(self._attach_asset_context(insight, ip))
        
        # Missing hosts
        missing_ips = previous_ips - current_ips
        for ip in missing_ips:
            insights.append({
                'type': 'missing_host',
                'host': ip,
                'message': f"Host no longer responding: {ip}",
                'priority': self.PRIORITY_WEIGHTS.get('missing_host', 80),
                'details': {'ip': ip}
            })
        
        # Compare ports for existing hosts
        for current_host in current_hosts:
            if not current_host.get('ip'):
                continue
                
            previous_host = next((h for h in previous_hosts if h.get('ip') == current_host.get('ip')), None)
            if previous_host:
                insights.extend(self._compare_host_ports(current_host, previous_host))
        
        return insights
    
    def _compare_host_ports(self, current_host: Dict, previous_host: Dict) -> List[Dict[str, Any]]:
        """Compare ports between same host in different scans"""
        insights = []
        
        current_ports = {p.get('port') for p in current_host.get('ports', []) if p.get('port')}
        previous_ports = {p.get('port') for p in previous_host.get('ports', []) if p.get('port')}
        
        host_ip = current_host.get('ip')
        
        # New ports
        new_ports = current_ports - previous_ports
        for port in new_ports:
            port_info = next((p for p in current_host.get('ports', []) if p.get('port') == port), {})
            service = port_info.get('service', 'unknown')
            insight = {
                'type': 'new_port',
                'host': host_ip,
                'message': f"New open port {port}/{service} on {host_ip}",
                'priority': self.PRIORITY_WEIGHTS.get('new_port', 50),
                'details': {'port': port, 'service': service, 'ip': host_ip}
            }
            insight = self._enrich_new_port(insight, port, host_ip)
            insights.append(insight)
        
        # Closed ports
        closed_ports = previous_ports - current_ports
        for port in closed_ports:
            insights.append({
                'type': 'port_closed',
                'host': host_ip,
                'message': f"Port {port} closed on {host_ip}",
                'priority': self.PRIORITY_WEIGHTS.get('port_closed', 20),
                'details': {'port': port, 'ip': host_ip}
            })

        # Service fingerprint changes on ports that stayed open
        stable_ports = current_ports & previous_ports
        for port in stable_ports:
            curr_info = next(
                (p for p in current_host.get('ports', []) if p.get('port') == port), {}
            )
            prev_info = next(
                (p for p in previous_host.get('ports', []) if p.get('port') == port), {}
            )
            if not self._port_service_changed(prev_info, curr_info):
                continue
            insight = {
                'type': 'service_change',
                'host': host_ip,
                'message': self._service_change_message(host_ip, port, prev_info, curr_info),
                'priority': self.PRIORITY_WEIGHTS['service_change'],
                'details': {
                    'ip': host_ip,
                    'port': port,
                    'previous': self._port_signature(prev_info),
                    'current': self._port_signature(curr_info),
                },
            }
            insight = self._attach_asset_context(insight, host_ip)
            insights.append(insight)

        return insights

    @staticmethod
    def _port_signature(port_info: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'service': port_info.get('service') or '',
            'product': port_info.get('product') or '',
            'version': port_info.get('version') or '',
        }

    def _port_service_changed(self, prev_info: Dict, curr_info: Dict) -> bool:
        return self._port_signature(prev_info) != self._port_signature(curr_info)

    def _service_change_message(
        self, host_ip: str, port: int, prev_info: Dict, curr_info: Dict
    ) -> str:
        prev = self._port_signature(prev_info)
        curr = self._port_signature(curr_info)
        prev_label = prev['service'] or 'unknown'
        curr_label = curr['service'] or 'unknown'
        if prev['version'] or curr['version']:
            return (
                f"Service on {host_ip}:{port} changed: "
                f"{prev_label} {prev['version']} → {curr_label} {curr['version']}".strip()
            )
        if prev['product'] or curr['product']:
            return (
                f"Service on {host_ip}:{port} changed: "
                f"{prev_label}/{prev['product']} → {curr_label}/{curr['product']}"
            )
        return f"Service on {host_ip}:{port} changed: {prev_label} → {curr_label}"
    
    def _attach_asset_context(self, insight: Dict[str, Any], host_ip: str) -> Dict[str, Any]:
        """Add asset registry role/trust/expected ports for host-scoped insights."""
        try:
            net = getattr(self, '_target_network', None)
            asset = asset_registry.get_asset_context(host_ip, network_cidr=net)
            details = insight.setdefault('details', {})
            details['asset_context'] = asset
            from ..models.scan import Scan
            from .host_context import get_host_entry

            scan_id = insight.get('scan_id') or getattr(self, '_scan_id', None)
            if scan_id:
                scan_row = Scan.query.get(scan_id)
                if scan_row:
                    hc = get_host_entry(scan_row, host_ip)
                    if hc:
                        details['host_context'] = {
                            'display_name': hc.get('display_name'),
                            'summary_line': hc.get('summary_line'),
                            'dhcp': hc.get('dhcp'),
                            'arp': hc.get('arp'),
                            'manufacturer': hc.get('manufacturer'),
                            'user_label': hc.get('user_label'),
                        }
            hc = details.get('host_context') or {}
            name = hc.get('display_name') or asset.get('name') or host_ip
            role = asset.get('role', 'unknown')
            if insight['type'] == 'new_host':
                insight['message'] = f"New host discovered: {name} ({role}) — {host_ip}"
            port = insight.get('details', {}).get('port')
            if port is not None:
                expected = asset_registry.is_expected_port(
                    host_ip, int(port), network_cidr=net,
                )
                if expected is False:
                    insight['details']['unexpected_port'] = True
        except Exception as e:
            print(f"[asset enrich] {host_ip} - {e}")
        return insight

    def _port_on_addrs(self, port: int, addrs: list) -> bool:
        port_s = str(port)
        for addr in addrs:
            if not addr:
                continue
            part = str(addr).rsplit(':', 1)[-1]
            if part == port_s:
                return True
        return False

    def _endpoint_process_context(self, agent_id: str, port: int) -> Optional[Dict[str, Any]]:
        """Match port to a process via start events, then latest snapshot."""
        anchor = getattr(self, '_scan_anchor', None)
        events = sensor_service.get_process_events(
            db, agent_id, minutes=120, anchor_ts=anchor,
        )
        ref_ts = anchor or datetime.utcnow()
        for event in reversed(events):
            if event.get('event_type') != 'process_started':
                continue
            if self._port_on_addrs(port, event.get('listening_ports', [])):
                proc = event['process']
                started_at = datetime.fromisoformat(
                    event['collected_at'].replace('Z', '')
                )
                minutes_ago = max(
                    0,
                    int((ref_ts - started_at.replace(tzinfo=None)).total_seconds() / 60),
                )
                cmdline = proc.get('cmdline', '')
                if isinstance(cmdline, list):
                    cmdline = ' '.join(cmdline)
                return {
                    'process_name': proc.get('name'),
                    'pid': proc.get('pid'),
                    'cmdline': cmdline,
                    'started_at': event['collected_at'],
                    'minutes_before_scan': minutes_ago,
                    'source': 'process_timeline',
                }

        collectors = sensor_service.get_latest_collectors(db, agent_id)
        conns = collectors.get('connections', [])
        pid_ports: Dict[int, list] = {}
        for c in conns:
            if c.get('state') == 'LISTEN' and c.get('pid') and c.get('local_addr'):
                pid_ports.setdefault(c['pid'], []).append(c['local_addr'])
        for proc in collectors.get('processes', []):
            pid = proc.get('pid')
            if pid is None:
                continue
            addrs = pid_ports.get(pid, [])
            if self._port_on_addrs(port, addrs):
                cmdline = proc.get('cmdline', '')
                if isinstance(cmdline, list):
                    cmdline = ' '.join(cmdline)
                return {
                    'process_name': proc.get('name'),
                    'pid': pid,
                    'cmdline': cmdline,
                    'listening_ports': addrs,
                    'source': 'latest_snapshot',
                }
        return None

    def _enrich_new_port(self, insight: Dict[str, Any], port: int, host_ip: str) -> Dict[str, Any]:
        """Annotate new_port with endpoint process, network segment, and asset registry context."""
        insight = self._attach_asset_context(insight, host_ip)
        try:
            sensor_ctx: Dict[str, Any] = {}

            agent = sensor_service.get_agent_by_ip(db, host_ip)
            if agent:
                tags = json.loads(agent.tags or '[]')
                if 'category:network' not in tags:
                    proc_ctx = self._endpoint_process_context(agent.agent_id, port)
                    if proc_ctx:
                        sensor_ctx['endpoint'] = proc_ctx
                        pname = proc_ctx.get('process_name', 'unknown')
                        mins = proc_ctx.get('minutes_before_scan')
                        if mins is not None:
                            insight['message'] = (
                                f"New open port {port} on {host_ip} — "
                                f"{pname} (PID {proc_ctx.get('pid')}) started {mins} min before scan"
                            )
                        else:
                            insight['message'] = (
                                f"New open port {port} on {host_ip} — {pname} (PID {proc_ctx.get('pid')}) listening"
                            )
                    sec_ctx = sensor_service.get_endpoint_security_context(
                        db, agent.agent_id,
                        anchor_ts=getattr(self, '_scan_anchor', None),
                    )
                    if sec_ctx:
                        sensor_ctx['endpoint_security'] = sec_ctx

            net_ctx = sensor_service.get_network_sensor_context(db, host_ip)
            if net_ctx:
                sensor_ctx['network'] = net_ctx

            if sensor_ctx:
                insight.setdefault('details', {})['sensor_context'] = sensor_ctx
        except Exception as e:
            print(f"[sensor enrich] {host_ip}:{port} - {e}")
        return insight

    def _compare_vulnerabilities(self, current_vulns: List[Dict], previous_vulns: List[Dict]) -> List[Dict[str, Any]]:
        """Compare vulnerabilities between scans"""
        insights = []
        
        # Create sets of vulnerability identifiers
        current_vuln_ids = {self._get_vuln_id(v) for v in current_vulns}
        previous_vuln_ids = {self._get_vuln_id(v) for v in previous_vulns}
        
        # New vulnerabilities
        new_vuln_ids = current_vuln_ids - previous_vuln_ids
        for vuln_id in new_vuln_ids:
            vuln = next((v for v in current_vulns if self._get_vuln_id(v) == vuln_id), None)
            if vuln:
                severity = self._get_vuln_severity(vuln)
                host_ip = vuln.get('host', 'unknown')

                insights.append({
                    'type': f'new_vuln_{severity}',
                    'host': host_ip,
                    'message': f"New {severity} vulnerability: {vuln_id} on {host_ip}",
                    'priority': self.PRIORITY_WEIGHTS.get(f'new_vuln_{severity}', 50),
                    'details': {'vuln_id': vuln_id, 'severity': severity, 'ip': host_ip},
                })

        resolved_vuln_ids = previous_vuln_ids - current_vuln_ids
        for vuln_id in resolved_vuln_ids:
            vuln = next((v for v in previous_vulns if self._get_vuln_id(v) == vuln_id), None)
            if not vuln:
                continue
            severity = self._get_vuln_severity(vuln)
            host_ip = vuln.get('host', 'unknown')
            insights.append({
                'type': 'vuln_resolved',
                'host': host_ip,
                'message': f"Resolved {severity} vulnerability: {vuln_id} on {host_ip}",
                'priority': self.PRIORITY_WEIGHTS['vuln_resolved'],
                'details': {'vuln_id': vuln_id, 'severity': severity, 'ip': host_ip},
            })

        return insights
    
    def _compare_performance(self, current: Scan, previous: Scan) -> List[Dict[str, Any]]:
        """Compare scan performance metrics"""
        insights = []
        
        if current.created_at and previous.created_at:
            # This is a simplified performance comparison
            # In a real implementation, you'd want to track scan duration
            time_diff = (current.created_at - previous.created_at).total_seconds()
            
            if time_diff > 0:  # Current scan is newer
                current_hosts = len(json.loads(current.hosts_json)) if current.hosts_json else 0
                previous_hosts = len(json.loads(previous.hosts_json)) if previous.hosts_json else 0
                
                if abs(current_hosts - previous_hosts) > 5:  # Significant change
                    insights.append({
                        'type': 'scan_performance',
                        'host': f"{current_hosts} vs {previous_hosts}",
                        'message': f"Network size changed: {current_hosts} hosts (was {previous_hosts})",
                        'priority': self.PRIORITY_WEIGHTS.get('scan_performance', 10),
                        'details': {'current_hosts': current_hosts, 'previous_hosts': previous_hosts}
                    })
        
        return insights
    
    def _get_vuln_id(self, vuln: Dict) -> str:
        """Extract vulnerability identifier"""
        return vuln.get('id', vuln.get('vuln_id', str(uuid.uuid4())))
    
    def _get_vuln_severity(self, vuln: Dict) -> str:
        """Determine vulnerability severity"""
        # Try to extract CVSS score or use heuristics
        output = vuln.get('output', '').lower()
        vuln_id = vuln.get('id', '').lower()
        
        if any(word in output or word in vuln_id for word in ['critical', 'rce', 'remote code']):
            return 'critical'
        elif any(word in output or word in vuln_id for word in ['high', 'privilege escalation']):
            return 'high'
        elif any(word in output or word in vuln_id for word in ['medium', 'disclosure']):
            return 'medium'
        else:
            return 'low'
    
    def _finalize_insights(self, insights: List[Dict[str, Any]], scan: Scan) -> List[Dict[str, Any]]:
        """Add final metadata to insights and sort by priority"""
        timestamp = datetime.now().isoformat()
        net = getattr(self, '_target_network', None) or effective_target_network(scan)
        net_label = getattr(self, '_network_label', None) or network_short_label(net)
        
        for insight in insights:
            details = insight.setdefault('details', {})
            details.setdefault('target_network', net)
            details.setdefault('network_label', net_label)
            insight.update({
                'id': str(uuid.uuid4()),
                'scan_id': scan.id,
                'timestamp': timestamp,
                'is_read': False,
            })
        
        # Sort by priority (highest first)
        insights.sort(key=lambda x: x.get('priority', 0), reverse=True)
        
        return insights


def generate_and_store_insights(scan_id: int) -> List[Dict[str, Any]]:
    """
    Generate insights for a scan with parsed hosts and store on the scan record.
    Called during postprocessing before status is set to complete.
    """
    from . import scan_analysis

    scan = Scan.query.get(scan_id)
    if not scan or not scan.hosts_json:
        return []
    if scan.status in ('failed', 'cancelled'):
        return []

    from .host_context import store_host_context

    try:
        ctx = store_host_context(scan_id)
        scan_analysis.record_host_context(
            scan_id, host_count=ctx.get("host_count", 0),
        )
        scan = Scan.query.get(scan_id)
    except Exception as ctx_exc:
        print(f"[insights] host context enrichment failed for scan {scan_id}: {ctx_exc}")
        scan_analysis.record_host_context(scan_id, error=str(ctx_exc))

    previous = InsightsGenerator()._get_previous_scan(scan)
    try:
        from .diff import compute_scan_diff

        generator = InsightsGenerator()
        insights = generator.generate_insights(scan)
        scan.insights_json = json.dumps(insights)
        try:
            diff = compute_scan_diff(scan_id, require_complete=False)
            scan.diff_from_previous = json.dumps(diff)
        except Exception as diff_exc:
            print(f"[insights] diff compute failed for scan {scan_id}: {diff_exc}")
        db.session.commit()
        scan_analysis.record_insights_generation(
            scan_id,
            count=len(insights),
            previous_scan_id=previous.id if previous else None,
            target_network=effective_target_network(scan),
        )
        return insights
    except Exception as exc:
        scan_analysis.record_insights_generation(
            scan_id,
            count=0,
            previous_scan_id=previous.id if previous else None,
            error=str(exc),
        )
        raise
