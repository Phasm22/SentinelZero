"""
What's Up monitoring routes for network health status
"""
from flask import Blueprint, jsonify
from ..services.whats_up import get_loopbacks_data, get_services_data, get_infrastructure_data, get_summary_data

bp = Blueprint('whatsup', __name__)

@bp.route('/api/whatsup/summary')
def whatsup_summary():
    """Combined summary of all monitoring layers.

    Serves the cached snapshot (refresh=False) so the request never blocks on
    network probes. The snapshot is kept fresh by a background scheduler job
    (see refresh_whats_up_snapshot in app.py). On a cold cache the monitor
    collects once, then subsequent requests are served from memory.
    """
    try:
        return jsonify(get_summary_data(refresh=False))
    except Exception as e:
        return jsonify({'error': f'Failed to get monitoring summary: {str(e)}'}), 500

@bp.route('/api/whatsup/loopbacks')
def check_loopbacks():
    """Layer 1: Check loopback sentinels for network health"""
    try:
        return jsonify({"loopbacks": get_loopbacks_data()})
    except Exception as e:
        return jsonify({'error': f'Failed to check loopbacks: {str(e)}'}), 500

@bp.route('/api/whatsup/services')
def check_services():
    """Layer 2: Check DNS resolution and service reachability"""
    try:
        return jsonify({"services": get_services_data()})
    except Exception as e:
        return jsonify({'error': f'Failed to check services: {str(e)}'}), 500

@bp.route('/api/whatsup/infrastructure')
def check_infrastructure():
    """Layer 3: Check critical infrastructure components"""
    try:
        return jsonify({"infrastructure": get_infrastructure_data()})
    except Exception as e:
        return jsonify({'error': f'Failed to check infrastructure: {str(e)}'}), 500
