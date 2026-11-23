"""Scheduler-related API routes."""
from flask import Blueprint, request, jsonify, current_app

from ..services import hunter_timers, schedule_service

def create_schedule_blueprint(db, socketio, scheduler):
    """Create and configure schedule routes blueprint"""
    bp = Blueprint('schedule', __name__)
    
    @bp.route('/scheduled-scans', methods=['GET'])
    def get_scheduled_scans():
        """Get all scheduled nmap scans."""
        try:
            jobs = schedule_service.load_scheduled_jobs()
            enriched = schedule_service.enrich_jobs_with_next_run(scheduler, jobs)
            return jsonify({'jobs': enriched, 'count': len(enriched)})
        except Exception as e:
            print(f'[DEBUG] Error loading scheduled scans: {e}')
            return jsonify({'status': 'error', 'message': f'Error loading scheduled scans: {str(e)}'}), 500
    
    @bp.route('/scheduled-scans', methods=['POST'])
    def save_scheduled_scans():
        """Save scheduled scans configuration and register APScheduler jobs."""
        try:
            data = request.get_json()
            if data is None:
                return jsonify({'status': 'error', 'message': 'No data provided'}), 400

            raw_jobs = data.get('jobs') if isinstance(data, dict) and 'jobs' in data else data
            if isinstance(raw_jobs, dict):
                raw_jobs = schedule_service.migrate_legacy_settings(raw_jobs)
            if not isinstance(raw_jobs, list):
                return jsonify({'status': 'error', 'message': 'Expected a list of job configs'}), 400

            jobs = schedule_service.save_scheduled_jobs(raw_jobs)
            app = current_app._get_current_object()
            registered = schedule_service.register_nmap_jobs(scheduler, app, socketio, jobs)
            enriched = schedule_service.enrich_jobs_with_next_run(scheduler, jobs)

            return jsonify({
                'status': 'success',
                'message': 'Scheduled scans updated successfully',
                'jobs': enriched,
                'registered': registered,
            })
        except Exception as e:
            print(f'[DEBUG] Error saving scheduled scans: {e}')
            return jsonify({'status': 'error', 'message': f'Error saving scheduled scans: {str(e)}'}), 500

    @bp.route('/scheduled-scans/maintenance', methods=['GET'])
    def get_maintenance_jobs():
        """List read-only background maintenance jobs."""
        try:
            return jsonify({'jobs': schedule_service.list_maintenance_jobs(scheduler)})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @bp.route('/hunter/timers', methods=['GET'])
    def get_hunter_timers():
        try:
            timers = hunter_timers.list_timers()
            return jsonify({'timers': timers, 'count': len(timers)})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @bp.route('/hunter/timers/<name>', methods=['PATCH'])
    def patch_hunter_timer(name):
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({'status': 'error', 'message': 'JSON body required'}), 400

        result = hunter_timers.patch_timer(name, payload)
        status = 200 if result.get('status') == 'success' else 400
        if result.get('status') == 'error' and 'Unknown timer' in (result.get('message') or ''):
            status = 404
        return jsonify(result), status
    
    return bp
