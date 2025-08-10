"""Diff API routes"""
from flask import Blueprint, jsonify
from ..models.scan import Scan
from ..services.diff import compute_scan_diff

diff_bp = Blueprint('diff', __name__)

@diff_bp.route('/api/scan-diff/<int:scan_id>', methods=['GET'])
def get_scan_diff(scan_id):
    scan = Scan.query.get(scan_id)
    if not scan:
        return jsonify({'error': 'Scan not found'}), 404
    result = compute_scan_diff(scan_id)
    if 'error' in result:
        return jsonify(result), 400
    return jsonify(result)
