"""
Insights generation service for scan comparison and network analysis
"""
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from ..models.scan import Scan
from ..config.database import db


class InsightsGenerator:
    """Generate insights by comparing scan results"""
    
    PRIORITY_WEIGHTS = {
        'new_vuln_critical': 100,
        'new_vuln_high': 90,
        'missing_host': 80,
        'new_vuln_medium': 70,
        'new_host': 60,
        'new_port': 50,
        'service_change': 40,
        'new_vuln_low': 30,
        'port_closed': 20,
        'scan_performance': 10
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
        'scan_performance': "📊 Scan duration changed significantly"
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
        insights = []
        
        # Find previous scan of same type
        previous_scan = self._get_previous_scan(current_scan)
        if not previous_scan:
            # First scan of this type - generate baseline insights
            insights = self._generate_baseline_insights(current_scan)
        else:
            # Compare with previous scan
            insights = self._compare_scans(current_scan, previous_scan)
        
        # Sort by priority and add timestamps
        insights = self._finalize_insights(insights, current_scan.id)
        
        return insights
    
    def _get_previous_scan(self, current_scan: Scan) -> Optional[Scan]:
        """Find the most recent completed scan of the same type"""
        return Scan.query.filter(
            Scan.scan_type == current_scan.scan_type,
            Scan.id != current_scan.id,
            Scan.status == 'complete'
        ).order_by(Scan.created_at.desc()).first()
    
    def _generate_baseline_insights(self, scan: Scan) -> List[Dict[str, Any]]:
        """Generate insights for the first scan of this type"""
        insights = []
        
        try:
            hosts = json.loads(scan.hosts_json) if scan.hosts_json else []
            vulns = json.loads(scan.vulns_json) if scan.vulns_json else []
            
            # Baseline: New network discovery
            if hosts:
                insights.append({
                    'type': 'new_host',
                    'host': f"{len(hosts)} hosts",
                    'message': f"Network baseline established: {len(hosts)} active hosts discovered",
                    'priority': self.PRIORITY_WEIGHTS.get('new_host', 50),
                    'details': {'host_count': len(hosts)}
                })
            
            # Baseline: Vulnerability summary
            if vulns:
                critical_vulns = [v for v in vulns if self._get_vuln_severity(v) == 'critical']
                if critical_vulns:
                    insights.append({
                        'type': 'new_vuln_critical',
                        'host': f"{len(critical_vulns)} hosts",
                        'message': f"Security baseline: {len(critical_vulns)} critical vulnerabilities found",
                        'priority': self.PRIORITY_WEIGHTS.get('new_vuln_critical', 100),
                        'details': {'vuln_count': len(critical_vulns)}
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
            insights.append({
                'type': 'new_host',
                'host': ip,
                'message': f"New host discovered: {ip}",
                'priority': self.PRIORITY_WEIGHTS.get('new_host', 60),
                'details': {'ip': ip}
            })
        
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
            insights.append({
                'type': 'new_port',
                'host': host_ip,
                'message': f"New open port {port}/{service} on {host_ip}",
                'priority': self.PRIORITY_WEIGHTS.get('new_port', 50),
                'details': {'port': port, 'service': service, 'ip': host_ip}
            })
        
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
        
        return insights
    
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
                    'details': {'vuln_id': vuln_id, 'severity': severity, 'ip': host_ip}
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
    
    def _finalize_insights(self, insights: List[Dict[str, Any]], scan_id: int) -> List[Dict[str, Any]]:
        """Add final metadata to insights and sort by priority"""
        timestamp = datetime.now().isoformat()
        
        for insight in insights:
            insight.update({
                'id': str(uuid.uuid4()),
                'scan_id': scan_id,
                'timestamp': timestamp,
                'is_read': False
            })
        
        # Sort by priority (highest first)
        insights.sort(key=lambda x: x.get('priority', 0), reverse=True)
        
        return insights


def generate_and_store_insights(scan_id: int) -> List[Dict[str, Any]]:
    """
    Generate insights for a completed scan and store them in the scan record
    
    Args:
        scan_id: ID of the completed scan
        
    Returns:
        List of generated insights
    """
    scan = Scan.query.get(scan_id)
    if not scan or scan.status != 'complete':
        return []
    
    generator = InsightsGenerator()
    insights = generator.generate_insights(scan)
    
    # Store insights in the scan record
    scan.insights_json = json.dumps(insights)
    db.session.commit()
    
    return insights
