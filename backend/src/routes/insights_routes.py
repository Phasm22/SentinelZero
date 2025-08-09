"""
Insights API routes
"""
import json
from flask import Blueprint, jsonify, request
from ..models.scan import Scan
from ..config.database import db

insights_bp = Blueprint('insights', __name__)

@insights_bp.route('/api/insights', methods=['GET'])
def get_insights():
    """Get insights across all scans with filtering and pagination"""
    
    # Query parameters
    limit = request.args.get('limit', 20, type=int)
    insight_type = request.args.get('type', None)
    priority_min = request.args.get('priority_min', 0, type=int)
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    
    # Limit to reasonable bounds
    limit = min(limit, 100)
    
    try:
        # Get scans with insights, ordered by most recent
        scans = Scan.query.filter(
            Scan.insights_json.isnot(None),
            Scan.status == 'complete'
        ).order_by(Scan.created_at.desc()).limit(50).all()  # Look at last 50 scans
        
        all_insights = []
        
        for scan in scans:
            try:
                insights = json.loads(scan.insights_json) if scan.insights_json else []
                
                for insight in insights:
                    # Add scan timestamp to insight
                    insight['scan_timestamp'] = scan.created_at.isoformat() if scan.created_at else None
                    insight['scan_type'] = scan.scan_type
                    
                    # Apply filters
                    if insight_type and insight.get('type') != insight_type:
                        continue
                    
                    if insight.get('priority', 0) < priority_min:
                        continue
                    
                    if unread_only and insight.get('is_read', False):
                        continue
                    
                    all_insights.append(insight)
                    
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Error parsing insights for scan {scan.id}: {e}")
                continue
        
        # Sort by priority and timestamp
        all_insights.sort(key=lambda x: (x.get('priority', 0), x.get('timestamp', '')), reverse=True)
        
        # Apply limit
        limited_insights = all_insights[:limit]
        
        # Generate summary
        summary = {
            'total': len(all_insights),
            'unread': len([i for i in all_insights if not i.get('is_read', False)]),
            'critical': len([i for i in all_insights if i.get('priority', 0) >= 80]),
            'by_type': {}
        }
        
        # Count by type
        for insight in all_insights:
            insight_type = insight.get('type', 'unknown')
            summary['by_type'][insight_type] = summary['by_type'].get(insight_type, 0) + 1
        
        return jsonify({
            'insights': limited_insights,
            'summary': summary
        })
        
    except Exception as e:
        print(f"Error fetching insights: {e}")
        return jsonify({'error': 'Failed to fetch insights'}), 500

@insights_bp.route('/api/insights/scan/<int:scan_id>', methods=['GET'])
def get_scan_insights(scan_id):
    """Get insights for a specific scan"""
    
    try:
        scan = Scan.query.get_or_404(scan_id)
        
        if not scan.insights_json:
            return jsonify({'insights': []})
        
        insights = json.loads(scan.insights_json)
        
        # Add scan metadata
        for insight in insights:
            insight['scan_timestamp'] = scan.created_at.isoformat() if scan.created_at else None
            insight['scan_type'] = scan.scan_type
        
        return jsonify({'insights': insights})
        
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
