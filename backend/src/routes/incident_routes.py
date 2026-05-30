"""Incident memory endpoints: store incident embeddings and query for similar past incidents.

The agent owns embedding (it has the LLM client), so it sends pre-computed vectors here:
  POST /api/incidents          {ip, port, scan_id, vector, summary, source}
  POST /api/incidents/search   {vector, days, top_k, exclude_scan_id}
  GET  /api/incidents          recent stored incidents (metadata only)
"""
from __future__ import annotations

import os

from flask import Blueprint, request, jsonify

from ..models.incident import IncidentEmbedding
from ..services import incident_memory

SENSOR_API_KEY = os.environ.get('SENSOR_API_KEY', '')


def _auth_check():
    if not SENSOR_API_KEY:
        return None
    if request.headers.get('X-Sensor-Key', '') != SENSOR_API_KEY:
        return jsonify({'error': 'unauthorized'}), 401
    return None


def create_incident_blueprint(db):
    bp = Blueprint('incident', __name__)

    @bp.route('/incidents', methods=['POST'])
    def store_incident():
        denied = _auth_check()
        if denied:
            return denied
        payload = request.get_json(silent=True) or {}
        vector = payload.get('vector')
        if not isinstance(vector, list) or not vector:
            return jsonify({'error': 'vector (non-empty list) required'}), 400
        try:
            result = incident_memory.store_incident(
                db,
                ip=payload.get('ip'),
                port=payload.get('port'),
                scan_id=payload.get('scan_id'),
                vector=vector,
                summary=payload.get('summary', ''),
                source=payload.get('source', 'verdict'),
                embedding_model=payload.get('embedding_model'),
            )
            return jsonify(result), 201 if result.get('status') == 'stored' else 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    @bp.route('/incidents/search', methods=['POST'])
    def search_incidents():
        payload = request.get_json(silent=True) or {}
        vector = payload.get('vector')
        if not isinstance(vector, list) or not vector:
            return jsonify({'error': 'vector (non-empty list) required'}), 400
        days = min(int(payload.get('days', 90)), 365)
        top_k = min(int(payload.get('top_k', 5)), 25)
        matches = incident_memory.search_similar(
            db,
            vector=vector,
            days=days,
            top_k=top_k,
            min_score=float(payload.get('min_score', 0.0)),
            exclude_scan_id=payload.get('exclude_scan_id'),
        )
        return jsonify({'matches': matches, 'count': len(matches)})

    @bp.route('/incidents', methods=['GET'])
    def list_incidents():
        limit = min(int(request.args.get('limit', 50)), 200)
        rows = (
            IncidentEmbedding.query
            .order_by(IncidentEmbedding.created_at.desc())
            .limit(limit)
            .all()
        )
        return jsonify({'incidents': [r.as_dict() for r in rows], 'count': len(rows)})

    return bp
