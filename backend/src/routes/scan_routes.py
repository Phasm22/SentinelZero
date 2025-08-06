"""
Scan-related API routes
"""
import json
import threading
from flask import Blueprint, request, jsonify
from ..models import Scan
from ..services.scanner import run_nmap_scan
from ..services.notifications import send_pushover_alert

def create_scan_blueprint(db, socketio):
    """Create and configure scan routes blueprint"""
    bp = Blueprint('scan', __name__)
    
    @bp.route('/scan', methods=['POST'])
    def trigger_scan():
        """Trigger a new network scan"""
        scan_type = request.form.get('scan_type', 'Full TCP')
        
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
        try:
            import os
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
            else:
                print(f'[DEBUG] No network_settings.json found, using default: {target_network}')
        except Exception as e:
            print(f'[DEBUG] Could not load network settings: {e}, using default: {target_network}')
        
        # Start scan in background thread with proper app context
        from flask import current_app
        app = current_app._get_current_object()  # Get the actual app instance
        threading.Thread(
            target=run_nmap_scan, 
            args=(scan_type, security_settings, socketio, app, target_network),
            daemon=True
        ).start()
        
        return jsonify({'status': 'success', 'message': f'{scan_type} scan started'})
    
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
    
    return bp
