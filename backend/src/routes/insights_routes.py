"""
Insights API routes
"""
import json
import os
from flask import Blueprint, jsonify, request
from ..models.scan import Scan
from ..config.database import db
from ..services import scan_analysis
from ..services.scan_scope import effective_target_network, network_short_label

insights_bp = Blueprint('insights', __name__)


def _attach_scan_context(insight: dict, scan: Scan) -> dict:
    insight['scan_timestamp'] = scan.created_at.isoformat() if scan.created_at else None
    insight['scan_type'] = scan.scan_type
    net = effective_target_network(scan)
    insight['target_network'] = net
    insight['network_label'] = network_short_label(net)
    return insight

SENSOR_API_KEY = os.environ.get("SENSOR_API_KEY", "")


def _sensor_auth_failed():
    if not SENSOR_API_KEY:
        return None
    if request.headers.get("X-Sensor-Key", "") != SENSOR_API_KEY:
        return jsonify({"error": "unauthorized"}), 401
    return None

@insights_bp.route('/api/insights', methods=['GET'])
def get_insights():
    """Get insights across all scans with filtering and pagination"""

    # Query parameters
    limit        = request.args.get('limit', 20, type=int)
    filter_type  = request.args.get('type', None)
    priority_min = request.args.get('priority_min', 0, type=int)
    unread_only  = request.args.get('unread_only', 'false').lower() == 'true'
    verdict_filter = request.args.get('verdict', None)

    limit = min(limit, 100)

    try:
        scans = Scan.query.filter(
            Scan.insights_json.isnot(None),
            Scan.status == 'complete'
        ).order_by(Scan.created_at.desc()).limit(50).all()

        all_insights = []

        for scan in scans:
            try:
                insights = json.loads(scan.insights_json) if scan.insights_json else []

                for insight in insights:
                    _attach_scan_context(insight, scan)
                    scan_analysis.attach_verdict_status(insight, scan)

                    if filter_type and insight.get('type') != filter_type:
                        continue
                    if insight.get('priority', 0) < priority_min:
                        continue
                    if unread_only and insight.get('is_read', False):
                        continue
                    if verdict_filter == 'actionable':
                        if insight.get('verdict') == 'dismiss':
                            continue
                        if (
                            insight.get('type') == 'correlated'
                            and insight.get('verdict') != 'escalate'
                        ):
                            continue
                    elif verdict_filter and insight.get('verdict') != verdict_filter:
                        continue

                    all_insights.append(insight)

            except (json.JSONDecodeError, TypeError) as e:
                print(f"Error parsing insights for scan {scan.id}: {e}")
                continue

        all_insights.sort(key=lambda x: (x.get('priority', 0), x.get('timestamp', '')), reverse=True)
        limited_insights = all_insights[:limit]

        summary = {
            'total':     len(all_insights),
            'unread':    len([i for i in all_insights if not i.get('is_read', False)]),
            'critical':  len([i for i in all_insights if i.get('priority', 0) >= 80]),
            'escalated': len([i for i in all_insights if i.get('verdict') == 'escalate']),
            'by_type':   {},
        }
        for insight in all_insights:
            t = insight.get('type', 'unknown')
            summary['by_type'][t] = summary['by_type'].get(t, 0) + 1

        return jsonify({'insights': limited_insights, 'summary': summary})

    except Exception as e:
        print(f"Error fetching insights: {e}")
        return jsonify({'error': 'Failed to fetch insights'}), 500


@insights_bp.route('/api/insights/escalated', methods=['GET'])
def get_escalated_insights():
    """Return only escalated insights, highest priority first"""
    limit = request.args.get('limit', 50, type=int)
    limit = min(limit, 200)

    try:
        scans = Scan.query.filter(
            Scan.insights_json.isnot(None),
            Scan.status == 'complete'
        ).order_by(Scan.created_at.desc()).limit(50).all()

        escalated = []
        for scan in scans:
            try:
                insights = json.loads(scan.insights_json) if scan.insights_json else []
                for insight in insights:
                    if insight.get('verdict') == 'escalate':
                        _attach_scan_context(insight, scan)
                        escalated.append(insight)
            except (json.JSONDecodeError, TypeError):
                continue

        escalated.sort(key=lambda x: (x.get('priority', 0), x.get('timestamp', '')), reverse=True)
        return jsonify({'insights': escalated[:limit], 'total': len(escalated)})

    except Exception as e:
        print(f"Error fetching escalated insights: {e}")
        return jsonify({'error': 'Failed to fetch escalated insights'}), 500


@insights_bp.route('/api/port-history/<ip>/<int:port>', methods=['GET'])
def get_port_history(ip, port):
    """Return per-scan presence history for a specific port on a host"""
    limit = request.args.get('limit', 10, type=int)
    limit = min(limit, 50)

    try:
        scans = Scan.query.filter(
            Scan.hosts_json.isnot(None),
            Scan.status == 'complete'
        ).order_by(Scan.created_at.desc()).limit(limit).all()

        history = []
        for scan in scans:
            try:
                hosts = json.loads(scan.hosts_json)
            except (json.JSONDecodeError, TypeError):
                continue

            host_seen = False
            port_seen = False
            for host in hosts:
                if host.get('ip') == ip:
                    host_seen = True
                    port_seen = any(p.get('port') == port for p in host.get('ports', []))
                    break

            history.append({
                'scan_id':   scan.id,
                'scan_type': scan.scan_type,
                'timestamp': scan.created_at.isoformat() if scan.created_at else None,
                'host_seen': host_seen,
                'port_seen': port_seen,
            })

        seen_count = sum(1 for h in history if h['port_seen'])
        return jsonify({
            'ip':          ip,
            'port':        port,
            'history':     history,
            'seen_in':     seen_count,
            'total_scans': len(history),
        })

    except Exception as e:
        print(f"Error fetching port history: {e}")
        return jsonify({'error': 'Failed to fetch port history'}), 500

@insights_bp.route('/api/scans/<int:scan_id>/analysis/scan-analyst', methods=['POST'])
def post_scan_analyst(scan_id):
    """Ingest scan-level analyst narrative (timer agent or CLI)."""
    auth_err = _sensor_auth_failed()
    if auth_err:
        return auth_err

    scan = Scan.query.get(scan_id)
    if not scan:
        return jsonify({"error": "Scan not found"}), 404

    body = request.get_json(silent=True) or {}
    scan_analysis.record_scan_analyst(
        scan_id,
        status="success",
        source=body.get("source", "timer"),
        verdict=body.get("verdict"),
        summary=body.get("summary"),
        findings=body.get("findings"),
        reasoning=body.get("reasoning"),
    )
    return jsonify({"status": "ok", "scan_id": scan_id})


@insights_bp.route('/api/scans/<int:scan_id>/host-context', methods=['GET'])
def get_scan_host_context(scan_id):
    """Per-scan host identification context (DHCP, ARP, registry, nmap, user labels)."""
    from ..services.host_context import load_host_context

    scan = Scan.query.get(scan_id)
    if not scan:
        return jsonify({"error": "Scan not found"}), 404
    ctx = load_host_context(scan)
    if not ctx:
        return jsonify({"scan_id": scan_id, "host_context": None, "status": "pending"})
    return jsonify({"scan_id": scan_id, "host_context": ctx, "status": "ready"})


@insights_bp.route('/api/scans/<int:scan_id>/host-context/labels', methods=['PATCH'])
def patch_scan_host_labels(scan_id):
    """Set friendly names for hosts, e.g. room or device labels."""
    scan = Scan.query.get(scan_id)
    if not scan:
        return jsonify({"error": "Scan not found"}), 404
    body = request.get_json(silent=True) or {}
    labels = body.get("labels") or body
    if not isinstance(labels, dict):
        return jsonify({"error": "Expected JSON object of {ip: label}"}), 400
    from ..services.host_context import apply_user_labels

    ctx = apply_user_labels(scan_id, labels)
    return jsonify({"status": "ok", "scan_id": scan_id, "host_context": ctx})


@insights_bp.route('/api/insights/scan/<int:scan_id>', methods=['GET'])
def get_scan_insights(scan_id):
    """Get insights for a specific scan"""
    
    try:
        scan = Scan.query.get_or_404(scan_id)
        
        from ..services import scan_analysis

        if not scan.insights_json:
            return jsonify({
                'insights': [],
                'scan_id': scan_id,
                'analysis': scan_analysis.load_analysis(scan),
                'summary': scan_analysis.insight_counts(scan),
            })

        insights = json.loads(scan.insights_json)

        for insight in insights:
            _attach_scan_context(insight, scan)
            scan_analysis.attach_verdict_status(insight, scan)

        from ..services.scan_scope import scan_scope_dict

        return jsonify({
            'insights': insights,
            'scan_id': scan_id,
            'analysis': scan_analysis.load_analysis(scan),
            'summary': scan_analysis.insight_counts(scan),
            **scan_scope_dict(scan),
        })
        
    except (json.JSONDecodeError, TypeError) as e:
        print(f"Error parsing insights for scan {scan_id}: {e}")
        return jsonify({'insights': []})
    except Exception as e:
        print(f"Error fetching insights for scan {scan_id}: {e}")
        return jsonify({'error': 'Failed to fetch scan insights'}), 500

@insights_bp.route('/api/insights/mark-read', methods=['POST'])
def mark_insights_read():
    """Mark insights as read"""
    
    try:
        data = request.get_json()
        insight_ids = data.get('insight_ids', [])
        
        if not insight_ids:
            return jsonify({'error': 'No insight IDs provided'}), 400
        
        updated_count = 0
        
        # Find and update insights across all scans
        scans = Scan.query.filter(Scan.insights_json.isnot(None)).all()
        
        for scan in scans:
            try:
                insights = json.loads(scan.insights_json) if scan.insights_json else []
                modified = False
                
                for insight in insights:
                    if insight.get('id') in insight_ids and not insight.get('is_read', False):
                        insight['is_read'] = True
                        modified = True
                        updated_count += 1
                
                if modified:
                    scan.insights_json = json.dumps(insights)
                    
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Error updating insights for scan {scan.id}: {e}")
                continue
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'updated_count': updated_count
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error marking insights as read: {e}")
        return jsonify({'error': 'Failed to mark insights as read'}), 500

@insights_bp.route('/api/insights/clear-old', methods=['POST'])
def clear_old_insights():
    """Clear insights older than specified days"""
    
    try:
        data = request.get_json()
        days_old = data.get('days', 30)
        
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        # Find scans older than cutoff
        old_scans = Scan.query.filter(
            Scan.created_at < cutoff_date,
            Scan.insights_json.isnot(None)
        ).all()
        
        cleared_count = 0
        for scan in old_scans:
            scan.insights_json = None
            cleared_count += 1
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'cleared_count': cleared_count
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error clearing old insights: {e}")
        return jsonify({'error': 'Failed to clear old insights'}), 500
