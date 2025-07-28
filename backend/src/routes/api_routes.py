"""
General API routes for dashboard and system status
"""
import json
import os
from datetime import datetime
from flask import Blueprint, jsonify
from ..models import Scan, Alert

def create_api_blueprint(db):
    """Create and configure general API routes blueprint"""
    bp = Blueprint('api', __name__)
    
    @bp.route('/dashboard-stats', methods=['GET'])
    def dashboard_stats():
        """Get dashboard statistics"""
        try:
            # Get scan statistics
            total_scans = Scan.query.count()
            recent_scan = Scan.query.order_by(Scan.id.desc()).first()
            
            # Get alert statistics
            total_alerts = Alert.query.count()
            unread_alerts = Alert.query.filter_by(read=False).count()
            
            # Prepare recent scan info
            recent_scan_info = None
            if recent_scan:
                recent_scan_info = {
                    'id': recent_scan.id,
                    'scan_type': recent_scan.scan_type,
                    'status': recent_scan.status,
                    'percent': recent_scan.percent,
                    'created_at': recent_scan.created_at.isoformat() if recent_scan.created_at else None,
                    'completed_at': recent_scan.completed_at.isoformat() if recent_scan.completed_at else None
                }
            
            stats = {
                'totalScans': total_scans,
                'totalAlerts': total_alerts,
                'unreadAlerts': unread_alerts,
                'recentScan': recent_scan_info,
                'systemStatus': 'operational'
            }
            
            return jsonify(stats)
            
        except Exception as e:
            print(f'[DEBUG] Error getting dashboard stats: {e}')
            return jsonify({
                'totalScans': 0,
                'totalAlerts': 0, 
                'unreadAlerts': 0,
                'recentScan': None,
                'systemStatus': 'error'
            }), 500
    
    @bp.route('/scans', methods=['GET'])
    def get_scans():
        """Get all scans with pagination"""
        try:
            scans = Scan.query.order_by(Scan.id.desc()).all()
            scans_data = []
            
            for scan in scans:
                scan_data = {
                    'id': scan.id,
                    'scan_type': scan.scan_type,
                    'status': scan.status,
                    'percent': scan.percent,
                    'created_at': scan.created_at.isoformat() if scan.created_at else None,
                    'completed_at': scan.completed_at.isoformat() if scan.completed_at else None,
                    'total_hosts': scan.total_hosts,
                    'hosts_up': scan.hosts_up,
                    'total_ports': scan.total_ports,
                    'open_ports': scan.open_ports
                }
                scans_data.append(scan_data)
            
            return jsonify(scans_data)
            
        except Exception as e:
            print(f'[DEBUG] Error getting scans: {e}')
            return jsonify({'status': 'error', 'message': f'Error retrieving scans: {str(e)}'}), 500

    @bp.route('/scan-history', methods=['GET'])
    def get_scan_history():
        """Get scan history (alias for scans)"""
        return get_scans()
    
    @bp.route('/active-scans', methods=['GET'])
    def get_active_scans():
        """Get currently active scans"""
        try:
            active_scans = Scan.query.filter(
                Scan.status.in_(['running', 'starting', 'in_progress'])
            ).order_by(Scan.id.desc()).all()
            
            scans_data = []
            for scan in active_scans:
                scan_data = {
                    'id': scan.id,
                    'scan_type': scan.scan_type,
                    'status': scan.status,
                    'percent': scan.percent,
                    'created_at': scan.created_at.isoformat() if scan.created_at else None,
                    'total_hosts': scan.total_hosts,
                    'hosts_up': scan.hosts_up
                }
                scans_data.append(scan_data)
            
            return jsonify(scans_data)
            
        except Exception as e:
            print(f'[DEBUG] Error getting active scans: {e}')
            return jsonify([])  # Return empty array on error
    
    @bp.route('/alerts', methods=['GET'])
    def get_alerts():
        """Get all alerts"""
        try:
            alerts = Alert.query.order_by(Alert.id.desc()).all()
            alerts_data = []
            
            for alert in alerts:
                alert_data = {
                    'id': alert.id,
                    'title': alert.title,
                    'message': alert.message,
                    'severity': alert.severity,
                    'read': alert.read,
                    'created_at': alert.created_at.isoformat() if alert.created_at else None
                }
                alerts_data.append(alert_data)
            
            return jsonify(alerts_data)
            
        except Exception as e:
            print(f'[DEBUG] Error getting alerts: {e}')
            return jsonify({'status': 'error', 'message': f'Error retrieving alerts: {str(e)}'}), 500
    
    @bp.route('/alerts/<int:alert_id>/mark-read', methods=['POST'])
    def mark_alert_read(alert_id):
        """Mark an alert as read"""
        try:
            alert = Alert.query.get(alert_id)
            if alert:
                alert.read = True
                db.session.commit()
                return jsonify({'status': 'success', 'message': 'Alert marked as read'})
            else:
                return jsonify({'status': 'error', 'message': 'Alert not found'}), 404
                
        except Exception as e:
            db.session.rollback()
            print(f'[DEBUG] Error marking alert as read: {e}')
            return jsonify({'status': 'error', 'message': f'Error marking alert as read: {str(e)}'}), 500
    
    @bp.route('/network-interfaces', methods=['GET'])
    def get_network_interfaces():
        """Get available network interfaces"""
        try:
            import psutil
            import ipaddress
            interfaces = []
            
            # Get network interface information
            net_if_addrs = psutil.net_if_addrs()
            net_if_stats = psutil.net_if_stats()
            
            for interface_name, addresses in net_if_addrs.items():
                # Skip loopback and inactive interfaces
                if interface_name == 'lo' or interface_name.startswith('lo'):
                    continue
                    
                stats = net_if_stats.get(interface_name)
                if stats and stats.isup:
                    # Process IPv4 addresses
                    for addr in addresses:
                        if addr.family.name == 'AF_INET':  # IPv4 only for network scanning
                            ip = addr.address
                            netmask = addr.netmask
                            
                            # Skip loopback and link-local addresses
                            if ip.startswith('127.') or ip.startswith('169.254.'):
                                continue
                                
                            try:
                                # Calculate CIDR notation and network address
                                netmask_bits = sum([bin(int(x)).count('1') for x in netmask.split('.')])
                                network = ipaddress.IPv4Network(f"{ip}/{netmask_bits}", strict=False)
                                network_addr = str(network.network_address)
                                cidr = f"{network_addr}/{netmask_bits}"
                                hosts = network.num_addresses - 2  # Subtract network and broadcast
                                
                                interface_info = {
                                    'interface': interface_name,
                                    'name': interface_name,
                                    'ip': ip,
                                    'netmask': netmask,
                                    'network': network_addr,
                                    'cidr': cidr,
                                    'broadcast': str(network.broadcast_address),
                                    'hosts': hosts,
                                    'display': f"{interface_name} - {cidr} ({hosts} hosts)",
                                    'isUp': stats.isup
                                }
                                interfaces.append(interface_info)
                            except ValueError as e:
                                print(f"[DEBUG] Error calculating network for {interface_name} {ip}/{netmask}: {e}")
                                continue
            
            # Sort interfaces by preference (en0, eth0 first, then others)
            def interface_priority(iface):
                name = iface['interface']
                if name == 'en0':
                    return 0
                elif name.startswith('en'):
                    return 1
                elif name.startswith('eth'):
                    return 2
                elif name.startswith('bridge'):
                    return 3
                else:
                    return 4
            
            interfaces.sort(key=interface_priority)
            
            return jsonify({
                'interfaces': interfaces,
                'count': len(interfaces)
            })
            
        except ImportError:
            # Fallback if psutil is not available
            print('[DEBUG] psutil not available, using fallback network interface detection')
            return jsonify({
                'interfaces': [
                    {
                        'interface': 'eth0',
                        'name': 'eth0',
                        'ip': '192.168.1.100',
                        'netmask': '255.255.255.0',
                        'network': '192.168.1.0',
                        'cidr': '192.168.1.0/24',
                        'broadcast': '192.168.1.255',
                        'hosts': 254,
                        'display': 'eth0 - 192.168.1.0/24 (254 hosts)',
                        'isUp': True
                    }
                ],
                'count': 1
            })
        except Exception as e:
            print(f'[DEBUG] Error getting network interfaces: {e}')
            return jsonify({
                'interfaces': [],
                'count': 0
            })

    @bp.route('/whatsup/summary', methods=['GET'])
    def get_whatsup_summary():
        """Get What's Up monitoring summary"""
        try:
            # This would typically come from a shared state or cache
            # For now, return a basic structure that matches the monitoring service
            summary = {
                'overall_status': 'degraded',  # healthy, degraded, critical
                'health_percentage': 57.1,
                'last_check': datetime.utcnow().isoformat(),
                'categories': {
                    'loopbacks': {
                        'total': 2,
                        'up': 2,
                        'status': 'healthy'
                    },
                    'services': {
                        'total': 3,
                        'up': 2,
                        'status': 'degraded'
                    },
                    'infrastructure': {
                        'total': 2,
                        'up': 0,
                        'status': 'critical'
                    }
                },
                'alerts': [
                    {
                        'type': 'warning',
                        'message': 'Some services may be unreachable',
                        'timestamp': datetime.utcnow().isoformat()
                    }
                ]
            }
            return jsonify(summary)
        except Exception as e:
            print(f'[DEBUG] Error getting What\'s Up summary: {e}')
            return jsonify({
                'overall_status': 'unknown',
                'health_percentage': 0,
                'last_check': datetime.utcnow().isoformat(),
                'categories': {},
                'alerts': []
            })

    @bp.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0'
        })
    
    return bp
