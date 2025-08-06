"""
What's Up monitoring routes for network health status
"""
from flask import Blueprint, jsonify
from datetime import datetime
from ..services.whats_up import get_loopbacks_data, get_services_data, get_infrastructure_data

bp = Blueprint('whatsup', __name__)

@bp.route('/api/whatsup/summary')
def whatsup_summary():
    """Combined summary of all monitoring layers"""
    try:
        loopbacks = get_loopbacks_data()
        services = get_services_data()
        infrastructure = get_infrastructure_data()
        
        # Calculate overall health
        all_items = loopbacks + services + infrastructure
        total_items = len(all_items)
        up_items = len([item for item in all_items if item.get('status') == 'up' or item.get('overall_status') == 'up'])
        
        if total_items > 0:
            health_percentage = (up_items / total_items) * 100
            overall_status = 'healthy' if health_percentage >= 80 else 'degraded' if health_percentage >= 50 else 'critical'
        else:
            health_percentage = 0
            overall_status = 'unknown'
        
        # Count up items per layer
        loopbacks_up = len([l for l in loopbacks if l['status'] == 'up'])
        services_up = len([s for s in services if s['overall_status'] == 'up'])
        infrastructure_up = len([i for i in infrastructure if i['status'] == 'up'])
        
        return jsonify({
            'overall_status': overall_status,
            'health_percentage': round(health_percentage, 1),
            'total_items': total_items,
            'up_items': up_items,
            'down_items': total_items - up_items,
            # Add fields that frontend expects
            'total_up': up_items,
            'total_checks': total_items,
            'timestamp': datetime.now().isoformat(),
            'layers': {
                'loopbacks': {
                    'total': len(loopbacks),
                    'up': loopbacks_up
                },
                'services': {
                    'total': len(services),
                    'up': services_up
                },
                'infrastructure': {
                    'total': len(infrastructure),
                    'up': infrastructure_up
                }
            },
            'categories': {
                'loopbacks': {
                    'total': len(loopbacks),
                    'up': loopbacks_up,
                    'items': loopbacks
                },
                'services': {
                    'total': len(services),
                    'up': services_up,
                    'items': services
                },
                'infrastructure': {
                    'total': len(infrastructure),
                    'up': infrastructure_up,
                    'items': infrastructure
                }
            }
        })
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
