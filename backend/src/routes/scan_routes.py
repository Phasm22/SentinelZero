"""
Scan-related API routes
"""
import json
import threading
from flask import Blueprint, request, jsonify
from ..models import Scan
from ..services.scanner import run_nmap_scan
from ..services.notifications import send_pushover_alert
import os, json as _json

def create_scan_blueprint(db, socketio):
    """Create and configure scan routes blueprint"""
    bp = Blueprint('scan', __name__)
    
    @bp.route('/scan', methods=['POST'])
    def trigger_scan():
        """Trigger a new network scan"""
        scan_type = request.form.get('scan_type', 'Full TCP')
        try:
            print(f"[DEBUG] /scan requested with scan_type='{scan_type}'")
        except Exception:
            pass
        
        # Load security settings
        security_settings = {
            'vuln_scanning_enabled': True,
            'os_detection_enabled': True,
            'service_detection_enabled': True,
            'aggressive_scanning': False
        }
        
        try:
            import os
            if os.path.exists('security_settings.json'):
                with open('security_settings.json', 'r') as f:
                    security_settings.update(json.load(f))
        except Exception as e:
            print(f'[DEBUG] Could not load security settings: {e}')
        
        # Load network settings to get target network
        target_network = '172.16.0.0/22'  # Default fallback
        max_concurrent = None
        pre_discovery_enabled = False
        try:
            if os.path.exists('network_settings.json'):
                with open('network_settings.json', 'r') as f:
                    network_data = json.load(f)
                    # Try both field names for compatibility
                    target_network = (network_data.get('defaultTargetNetwork') or 
                                      network_data.get('default_target_network') or 
                                      '172.16.0.0/22')
                    if not target_network or target_network.strip() == '':
                        target_network = '172.16.0.0/22'
                    print(f'[DEBUG] Using target network from settings: {target_network}')
                    # Concurrency limit
                    max_concurrent = (network_data.get('concurrentScans') or 
                                      network_data.get('concurrent_scans'))
                    pre_discovery_enabled = bool(network_data.get('preDiscoveryEnabled') or network_data.get('pre_discovery_enabled') or False)
            else:
                print(f'[DEBUG] No network_settings.json found, using default: {target_network}')
        except Exception as e:
            print(f'[DEBUG] Could not load network settings: {e}, using default: {target_network}')
        
        # Enforce concurrency limit (skip for lightweight Discovery Scan)
        scan_type_lower = (scan_type or '').strip().lower()
        if scan_type_lower != 'discovery scan' and max_concurrent is not None:
            try:
                max_concurrent_val = int(float(max_concurrent))
            except Exception:
                max_concurrent_val = 1
            if max_concurrent_val < 1:
                max_concurrent_val = 1
            # Only count "heavy" scans toward concurrency: exclude Discovery Scan
            active_count = (Scan.query
                                .filter(Scan.status.in_(['running', 'parsing', 'saving', 'postprocessing']))
                                .filter(Scan.scan_type != 'Discovery Scan')
                                .count())
            if active_count >= max_concurrent_val:
                # Emit socket log so UI sees reason even without HTTP body inspection
                if socketio:
                    try:
                        socketio.emit('scan_log', {'msg': f'Concurrency limit reached ({active_count}/{max_concurrent_val}) – waiting for existing scans to finish'})
                    except Exception:
                        pass
                return jsonify({
                    'status': 'error',
                    'message': f'Max concurrent scans ({max_concurrent_val}) reached'
                }), 429

        # Validate target network CIDR
        try:
            import ipaddress
            _ = ipaddress.ip_network(target_network, strict=False)
        except Exception:
            return jsonify({'status': 'error', 'message': f'Invalid target network CIDR: {target_network}'}), 400

        # Start scan in background thread with proper app context
        from flask import current_app
        app = current_app._get_current_object()  # Get the actual app instance
        threading.Thread(
            target=run_nmap_scan, 
            args=(scan_type, security_settings, socketio, app, target_network),
            kwargs={'pre_discovery': pre_discovery_enabled},
            daemon=True
        ).start()
        # Inform clients via socket immediately (especially helpful for very fast discovery scans)
        if socketio:
            try:
                socketio.emit('scan_log', {'msg': f'Launching scan thread for: {scan_type}'})
            except Exception:
                pass
        
        return jsonify({'status': 'success', 'message': f'{scan_type} scan started'})

    @bp.route('/kill-all-scans', methods=['POST'])
    def kill_all_scans():
        """Mark all active scans as cancelled and kill their processes."""
        try:
            active_scans = Scan.query.filter(Scan.status.in_(['running', 'parsing', 'saving', 'postprocessing'])).all()
            count = 0
            killed_processes = 0
            
            for s in active_scans:
                if s.status != 'cancelled':
                    s.status = 'cancelled'
                    count += 1
                    
                    # Kill the process if we have a PID
                    if s.process_id:
                        try:
                            import psutil
                            process = psutil.Process(s.process_id)
                            if process.is_running():
                                # Kill the process and its children
                                children = process.children(recursive=True)
                                for child in children:
                                    child.terminate()
                                process.terminate()
                                
                                # Wait for processes to terminate gracefully
                                psutil.wait_procs(children + [process], timeout=5)
                                
                                # Force kill any remaining processes
                                for child in children:
                                    if child.is_running():
                                        child.kill()
                                if process.is_running():
                                    process.kill()
                                
                                killed_processes += 1
                                print(f'[DEBUG] Killed process {s.process_id} for scan {s.id}')
                        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception) as e:
                            print(f'[WARN] Could not kill process {s.process_id}: {e}')
            
            if count:
                from ..config.database import db as _db
                _db.session.commit()
            
            msg = f'Cancelled {count} active scans, killed {killed_processes} processes'
            print(f'[DEBUG] {msg}')
            if socketio:
                try:
                    socketio.emit('scan_log', {'msg': msg})
                except Exception:
                    pass
            return jsonify({'status': 'success', 'message': msg, 'cancelled': count, 'killed_processes': killed_processes})
        except Exception as e:
            from ..config.database import db as _db
            _db.session.rollback()
            return jsonify({'status': 'error', 'message': f'Failed to cancel scans: {str(e)}'}), 500

    @bp.route('/cancel-scan/<int:scan_id>', methods=['POST'])
    def cancel_scan(scan_id):
        """Cancel a single running scan and kill its process."""
        try:
            scan = Scan.query.get(scan_id)
            if not scan:
                return jsonify({'status': 'error', 'message': 'Scan not found'}), 404
            if scan.status in ['complete', 'error', 'cancelled']:
                return jsonify({'status': 'success', 'message': f'Scan already {scan.status}', 'scan_id': scan_id})
            
            scan.status = 'cancelled'
            killed_process = False
            
            # Kill the process if we have a PID
            if scan.process_id:
                try:
                    import psutil
                    process = psutil.Process(scan.process_id)
                    if process.is_running():
                        # Kill the process and its children
                        children = process.children(recursive=True)
                        for child in children:
                            child.terminate()
                        process.terminate()
                        
                        # Wait for processes to terminate gracefully
                        psutil.wait_procs(children + [process], timeout=5)
                        
                        # Force kill any remaining processes
                        for child in children:
                            if child.is_running():
                                child.kill()
                        if process.is_running():
                            process.kill()
                        
                        killed_process = True
                        print(f'[DEBUG] Killed process {scan.process_id} for scan {scan_id}')
                except (psutil.NoSuchProcess, psutil.AccessDenied, Exception) as e:
                    print(f'[WARN] Could not kill process {scan.process_id}: {e}')
            
            from ..config.database import db as _db
            _db.session.commit()
            
            msg = f'Scan {scan_id} cancelled' + (f' and process killed' if killed_process else '')
            print(f'[DEBUG] {msg}')
            if socketio:
                try:
                    socketio.emit('scan_log', {'msg': msg})
                except Exception:
                    pass
            return jsonify({'status': 'success', 'message': msg, 'scan_id': scan_id, 'killed_process': killed_process})
        except Exception as e:
            from ..config.database import db as _db
            _db.session.rollback()
            return jsonify({'status': 'error', 'message': f'Failed to cancel scan: {str(e)}'}), 500
    
    @bp.route('/clear-scan/<int:scan_id>', methods=['POST'])
    def clear_scan(scan_id):
        """Delete a specific scan"""
        try:
            scan = Scan.query.get(scan_id)
            if scan:
                db.session.delete(scan)
                db.session.commit()
                print(f'[DEBUG] Scan {scan_id} deleted.')
                return jsonify({'status': 'success', 'message': 'Scan cleared'})
            else:
                print(f'[DEBUG] Scan {scan_id} not found for deletion.')
                return jsonify({'status': 'error', 'message': 'Scan not found'}), 404
        except Exception as e:
            db.session.rollback()
            print(f'[DEBUG] Error deleting scan {scan_id}: {e}')
            return jsonify({'status': 'error', 'message': f'Error clearing scan: {str(e)}'}), 500
    
    @bp.route('/delete-all-scans', methods=['POST'])
    def delete_all_scans():
        """Delete all scan records"""
        try:
            # Delete all scans
            deleted_count = Scan.query.count()
            Scan.query.delete()
            db.session.commit()
            print(f'[DEBUG] {deleted_count} scans deleted.')
            return jsonify({'status': 'success', 'message': f'{deleted_count} scans deleted'})
        except Exception as e:
            db.session.rollback()
            print(f'[DEBUG] Error deleting all scans: {e}')
            return jsonify({'status': 'error', 'message': f'Error deleting all scans: {str(e)}'}), 500

    @bp.route('/scan-status/<int:scan_id>', methods=['GET'])
    def get_scan_status(scan_id):
        """Get the status of a specific scan"""
        try:
            scan = Scan.query.get(scan_id)
            if not scan:
                return jsonify({'error': 'Scan not found'}), 404
            
            return jsonify({
                'scan_id': scan.id,
                'status': scan.status,
                'percent': scan.percent,
                'message': f'Status: {scan.status}, {scan.percent:.1f}%',
            })
        except Exception as e:
            print(f'[DEBUG] Error getting scan status for {scan_id}: {e}')
            return jsonify({'error': 'Failed to get scan status'}), 500

    @bp.route('/scan/<int:scan_id>', methods=['GET'])
    def get_scan(scan_id):
        """Get detailed scan information"""
        try:
            scan = Scan.query.get(scan_id)
            if not scan:
                return jsonify({'error': 'Scan not found'}), 404
            
            # Convert scan to dictionary with processed hosts and vulns
            scan_data = scan.as_dict()
            
            # Ensure timestamp is properly set for frontend
            if not scan_data.get('timestamp') and scan_data.get('created_at'):
                scan_data['timestamp'] = scan_data['created_at']
            
            # Parse hosts and vulns JSON
            try:
                hosts = _json.loads(scan.hosts_json) if scan.hosts_json else []
                scan_data['hosts'] = hosts
                scan_data['hosts_count'] = len(hosts)
            except Exception:
                scan_data['hosts'] = []
                scan_data['hosts_count'] = 0
            
            try:
                vulns = _json.loads(scan.vulns_json) if scan.vulns_json else []
                scan_data['vulns'] = vulns
                scan_data['vulns_count'] = len(vulns)
            except Exception:
                scan_data['vulns'] = []
                scan_data['vulns_count'] = 0
            
            return jsonify(scan_data)
        except Exception as e:
            print(f'[DEBUG] Error getting scan {scan_id}: {e}')
            return jsonify({'error': 'Failed to get scan'}), 500
    
    return bp
