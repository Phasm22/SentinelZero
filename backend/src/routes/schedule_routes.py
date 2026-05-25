"""
Scheduler-related API routes
"""
import json
import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from apscheduler.triggers.cron import CronTrigger

def create_schedule_blueprint(db, socketio, scheduler):
    """Create and configure schedule routes blueprint"""
    bp = Blueprint('schedule', __name__)
    
    @bp.route('/scheduled-scans', methods=['GET'])
    def get_scheduled_scans():
        """Get all scheduled scans"""
        try:
            if os.path.exists('scheduled_scans_settings.json'):
                with open('scheduled_scans_settings.json', 'r') as f:
                    scheduled_scans = json.load(f)
                    return jsonify(scheduled_scans)
            return jsonify([])
        except Exception as e:
            print(f'[DEBUG] Error loading scheduled scans: {e}')
            return jsonify({'status': 'error', 'message': f'Error loading scheduled scans: {str(e)}'}), 500
    
    @bp.route('/scheduled-scans', methods=['POST'])
    def save_scheduled_scans():
        """Save scheduled scans configuration"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': 'No data provided'}), 400
            
            # Save to file
            with open('scheduled_scans_settings.json', 'w') as f:
                json.dump(data, f, indent=4)
            
            # Clear existing scheduled jobs
            if scheduler:
                for job in scheduler.get_jobs():
                    if job.id.startswith('scheduled_scan_'):
                        scheduler.remove_job(job.id)
            
            # Add new scheduled jobs
            from ..services.scanner import run_nmap_scan
            app = current_app._get_current_object()
            runtime = current_app.extensions['scan_runtime']
            
            for i, scan_config in enumerate(data):
                if scan_config.get('enabled', False):
                    if scheduler is None:
                        continue
                    job_id = f'scheduled_scan_{i}'
                    
                    # Create cron trigger from configuration
                    trigger = CronTrigger(
                        minute=scan_config.get('minute', '0'),
                        hour=scan_config.get('hour', '0'),
                        day=scan_config.get('day', '*'),
                        month=scan_config.get('month', '*'),
                        day_of_week=scan_config.get('dayOfWeek', '*')
                    )
                    
                    def scheduled_scan_wrapper(
                        scan_type=scan_config['scanType'],
                        scheduled_network=scan_config.get('targetNetwork')
                        or scan_config.get('target_network')
                        or '172.16.0.0/22',
                    ):
                        """Wrapper function for scheduled scans"""
                        with app.app_context():
                            security_settings = {
                                'vuln_scanning_enabled': True,
                                'os_detection_enabled': True,
                                'service_detection_enabled': True,
                                'aggressive_scanning': False
                            }
                            
                            try:
                                if os.path.exists('security_settings.json'):
                                    with open('security_settings.json', 'r') as f:
                                        security_settings.update(json.load(f))
                            except Exception as e:
                                print(f'[DEBUG] Could not load security settings for scheduled scan: {e}')
                            
                            scan = runtime.create_scan(
                                scan_type=scan_type,
                                target_network=scheduled_network,
                                source='scheduled',
                                initiated_by='scheduler',
                                correlation_id=str(uuid.uuid4()),
                                state='queued',
                                message=f'Queued scheduled {scan_type} on {scheduled_network}',
                            )
                            runtime.emit_scan_event('scan.started', scan)
                            runtime.emit_snapshot(scan)
                            run_nmap_scan(scan.id, scan_type, security_settings, socketio, app, scheduled_network)
                    
                    scheduler.add_job(
                        func=scheduled_scan_wrapper,
                        trigger=trigger,
                        id=job_id,
                        name=f'Scheduled {scan_config["scanType"]} Scan'
                    )
                    
                    print(f'[DEBUG] Scheduled scan job created: {job_id}')
            
            return jsonify({'status': 'success', 'message': 'Scheduled scans updated successfully'})
            
        except Exception as e:
            print(f'[DEBUG] Error saving scheduled scans: {e}')
            return jsonify({'status': 'error', 'message': f'Error saving scheduled scans: {str(e)}'}), 500
    
    return bp
