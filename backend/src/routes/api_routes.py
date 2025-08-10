"""
General API routes for dashboard and system status
"""
import json
import os
import pytz
from datetime import datetime
from flask import Blueprint, jsonify, Response
from ..models import Scan, Alert

def create_api_blueprint(db):
    """Create and configure general API routes blueprint"""
    bp = Blueprint('api', __name__)
    
    @bp.route('/ping', methods=['GET'])
    def ping():
        """Simple ping endpoint for health checks"""
        return jsonify({
            'status': 'success',
            'message': 'Server received ping',
            'timestamp': datetime.utcnow().isoformat()
        })
    
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
        """Get scan history for the React frontend"""
        try:
            import pytz
            
            scans = Scan.query.order_by(Scan.created_at.desc()).all()
            denver = pytz.timezone('America/Denver')
            scans_data = []
            
            for scan in scans:
                scan_dict = {
                    'id': scan.id,
                    'scan_type': scan.scan_type,
                    'status': scan.status,
                    'percent': scan.percent,
                    'created_at': scan.created_at.isoformat() if scan.created_at else None,
                    'completed_at': scan.completed_at.isoformat() if scan.completed_at else None,
                    'timestamp': scan.created_at,  # Add timestamp field for frontend compatibility
                    'total_hosts': scan.total_hosts,
                    'hosts_up': scan.hosts_up,
                    'total_ports': scan.total_ports,
                    'open_ports': scan.open_ports
                }
                
                # Convert timestamp to Denver timezone
                if scan_dict['timestamp']:
                    scan_dict['timestamp'] = scan_dict['timestamp'].astimezone(denver)
                
                # Parse hosts and vulns for count
                try:
                    hosts = json.loads(scan.hosts_json) if scan.hosts_json else []
                    scan_dict['hosts_count'] = len(hosts)
                except Exception:
                    scan_dict['hosts_count'] = 0
                
                try:
                    vulns = json.loads(scan.vulns_json) if scan.vulns_json else []
                    scan_dict['vulns_count'] = len(vulns)
                except Exception:
                    scan_dict['vulns_count'] = 0
                    
                scans_data.append(scan_dict)
            
            return jsonify({'scans': scans_data})
            
        except Exception as e:
            print(f'[DEBUG] Error getting scan history: {e}')
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/active-scans', methods=['GET'])
    def get_active_scans():
        """Get currently active scans.
        Returns shape { scans: [...], count: n } for frontend compatibility.
        Treat the following statuses as active: running, parsing, saving, postprocessing.
        Older transitional statuses (starting, in_progress) are also included for backward compatibility.
        """
        try:
            active_statuses = ['running', 'parsing', 'saving', 'postprocessing', 'starting', 'in_progress']
            active_scans = (Scan.query
                                .filter(Scan.status.in_(active_statuses))
                                .order_by(Scan.id.desc())
                                .all())

            scans_data = []
            for scan in active_scans:
                scans_data.append({
                    'id': scan.id,
                    'scan_type': scan.scan_type,
                    'status': scan.status,
                    'percent': scan.percent,
                    'created_at': scan.created_at.isoformat() if scan.created_at else None,
                    'total_hosts': scan.total_hosts,
                    'hosts_up': scan.hosts_up
                })

            return jsonify({'scans': scans_data, 'count': len(scans_data)})

        except Exception as e:
            print(f'[DEBUG] Error getting active scans: {e}')
            return jsonify({'scans': [], 'count': 0})
    
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

    @bp.route('/scan/<int:scan_id>', methods=['GET'])
    def get_scan(scan_id):
        """Get individual scan details"""
        try:
            scan = Scan.query.get(scan_id)
            if not scan:
                return jsonify({'error': 'Scan not found'}), 404
            
            # Convert scan to dictionary
            scan_data = {
                'id': scan.id,
                'scan_type': scan.scan_type,
                'status': scan.status,
                'percent': scan.percent,
                'created_at': scan.created_at.isoformat() if scan.created_at else None,
                'completed_at': scan.completed_at.isoformat() if scan.completed_at else None,
                'timestamp': scan.created_at,
                'total_hosts': scan.total_hosts,
                'hosts_up': scan.hosts_up,
                'total_ports': scan.total_ports,
                'open_ports': scan.open_ports,
                'raw_xml_path': scan.raw_xml_path
            }
            
            # Convert timestamp to ISO string in Denver timezone for frontend parsing
            if scan_data['timestamp']:
                denver = pytz.timezone('America/Denver')
                scan_data['timestamp'] = scan_data['timestamp'].astimezone(denver).isoformat()
            
            # Add hosts and vulns count
            try:
                hosts = json.loads(scan.hosts_json) if scan.hosts_json else []
                scan_data['hosts_count'] = len(hosts)
            except Exception:
                scan_data['hosts_count'] = 0
            
            try:
                vulns = json.loads(scan.vulns_json) if scan.vulns_json else []
                scan_data['vulns_count'] = len(vulns)
            except Exception:
                scan_data['vulns_count'] = 0
                
            return jsonify(scan_data)
            
        except Exception as e:
            print(f'[DEBUG] Error getting scan {scan_id}: {e}')
            return jsonify({'error': f'Error retrieving scan: {str(e)}'}), 500

    @bp.route('/hosts/<int:scan_id>', methods=['GET'])
    def get_scan_hosts(scan_id):
        """Get hosts for a specific scan"""
        try:
            scan = Scan.query.get(scan_id)
            if not scan:
                return jsonify({'error': 'Scan not found'}), 404
            
            if scan.hosts_json:
                hosts = json.loads(scan.hosts_json)
                return jsonify({'hosts': hosts})
            return jsonify({'hosts': []})
            
        except Exception as e:
            print(f'[DEBUG] Error getting hosts for scan {scan_id}: {e}')
            return jsonify({'error': f'Error retrieving hosts: {str(e)}'}), 500

    @bp.route('/vulns/<int:scan_id>', methods=['GET'])
    def get_scan_vulns(scan_id):
        """Get vulnerabilities for a specific scan"""
        try:
            scan = Scan.query.get(scan_id)
            if not scan:
                return jsonify({'error': 'Scan not found'}), 404
            
            if scan.vulns_json:
                vulns = json.loads(scan.vulns_json)
                return jsonify({'vulns': vulns})
            return jsonify({'vulns': []})
            
        except Exception as e:
            print(f'[DEBUG] Error getting vulns for scan {scan_id}: {e}')
            return jsonify({'error': f'Error retrieving vulnerabilities: {str(e)}'}), 500

    @bp.route('/scan-xml/<int:scan_id>', methods=['GET'])
    def get_scan_xml(scan_id):
        """Get raw XML data for a scan"""
        try:
            from flask import Response
            
            scan = Scan.query.get(scan_id)
            if not scan:
                return jsonify({'error': 'Scan not found'}), 404
            
            if not scan.raw_xml_path:
                return jsonify({'error': 'No XML file path recorded for this scan'}), 404
            
            if not os.path.exists(scan.raw_xml_path):
                return jsonify({'error': f'XML file not found at path: {scan.raw_xml_path}'}), 404
            
            try:
                with open(scan.raw_xml_path, 'r', encoding='utf-8') as f:
                    xml_content = f.read()
                
                # Return as plain text for frontend processing
                return Response(xml_content, mimetype='text/plain')
                
            except Exception as e:
                return jsonify({'error': f'Error reading XML file: {str(e)}'}), 500
                
        except Exception as e:
            print(f'[DEBUG] Error getting XML for scan {scan_id}: {e}')
            return jsonify({'error': f'Error retrieving XML: {str(e)}'}), 500
                
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

    @bp.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0'
        })
    
    @bp.route('/test-pushover', methods=['POST', 'GET', 'OPTIONS'])
    def test_pushover():
        """Test Pushover notification system"""
        from flask import request, make_response
        import requests
        import logging
        
        if request.method == 'OPTIONS':
            response = make_response()
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return response, 204
            
        if request.method == 'GET':
            return jsonify({'status': 'ok', 'message': 'GET method works. Use POST to send a test notification.'})
        
        try:
            PUSHOVER_API_TOKEN = os.environ.get('PUSHOVER_API_TOKEN')
            PUSHOVER_USER_KEY = os.environ.get('PUSHOVER_USER_KEY')
            
            if not PUSHOVER_API_TOKEN or not PUSHOVER_USER_KEY:
                return jsonify({
                    'status': 'error', 
                    'message': 'Pushover credentials not configured on server'
                }), 400
            
            message = 'Test notification from SentinelZero!'
            resp = requests.post('https://api.pushover.net/1/messages.json', data={
                'token': PUSHOVER_API_TOKEN,
                'user': PUSHOVER_USER_KEY,
                'message': message,
                'priority': 0,
                'title': 'SentinelZero',
            })
            
            logging.info(f"[PUSHOVER TEST] Status: {resp.status_code}, Response: {resp.text}")
            
            if resp.status_code == 200:
                return jsonify({'status': 'ok', 'message': 'Pushover test sent successfully!'})
            else:
                return jsonify({
                    'status': 'error', 
                    'message': f'Pushover failed: {resp.text}', 
                    'code': resp.status_code
                }), 500
                
        except Exception as e:
            logging.exception('[PUSHOVER TEST] Exception:')
            return jsonify({'status': 'error', 'message': str(e)}), 500
    
    return bp
