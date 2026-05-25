"""Sensor agent registration, telemetry ingestion, and timeline query endpoints."""
from __future__ import annotations
import json
import os
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify

from ..models.sensor import SensorAgent, SensorTelemetry
from ..services import sensor_service

SENSOR_API_KEY = os.environ.get('SENSOR_API_KEY', '')


def _auth_check():
    """Return (response, status) if unauthorized, else None."""
    if not SENSOR_API_KEY:
        return None  # dev mode: no key configured
    if request.headers.get('X-Sensor-Key', '') != SENSOR_API_KEY:
        return jsonify({'error': 'unauthorized'}), 401
    return None


def create_sensor_blueprint(db):
    bp = Blueprint('sensor', __name__)

    # ------------------------------------------------------------------
    # POST /api/sensor/register
    # ------------------------------------------------------------------
    @bp.route('/sensor/register', methods=['POST'])
    def register_agent():
        denied = _auth_check()
        if denied:
            return denied

        payload = request.get_json(silent=True) or {}
        agent_id = payload.get('agent_id', '').strip()
        if not agent_id:
            return jsonify({'error': 'agent_id required'}), 400

        try:
            existing = SensorAgent.query.filter_by(agent_id=agent_id).first()
            if existing:
                # Idempotent update — allow IP/version changes (e.g. DHCP)
                existing.hostname = payload.get('hostname', existing.hostname)
                existing.host_ip = payload.get('host_ip', existing.host_ip)
                existing.role = payload.get('role', existing.role)
                existing.agent_version = payload.get('agent_version', existing.agent_version)
                existing.tags = json.dumps(payload.get('tags', json.loads(existing.tags or '[]')))
                existing.last_seen_at = datetime.utcnow()
                db.session.commit()
                return jsonify({'status': 'updated', 'agent_id': agent_id})

            agent = SensorAgent(
                agent_id=agent_id,
                hostname=payload.get('hostname'),
                host_ip=payload.get('host_ip'),
                role=payload.get('role', 'linux-server'),
                agent_version=payload.get('agent_version'),
                last_seen_at=datetime.utcnow(),
                tags=json.dumps(payload.get('tags', [])),
            )
            db.session.add(agent)
            db.session.commit()
            return jsonify({'status': 'registered', 'agent_id': agent_id}), 201

        except Exception as e:
            db.session.rollback()
            print(f'[DEBUG] sensor register error: {e}')
            return jsonify({'error': str(e)}), 500

    # ------------------------------------------------------------------
    # POST /api/sensor/ingest
    # ------------------------------------------------------------------
    @bp.route('/sensor/ingest', methods=['POST'])
    def ingest_telemetry():
        denied = _auth_check()
        if denied:
            return denied

        payload = request.get_json(silent=True) or {}
        agent_id = payload.get('agent_id', '').strip()
        if not agent_id:
            return jsonify({'error': 'agent_id required'}), 400

        agent = SensorAgent.query.filter_by(agent_id=agent_id).first()
        if not agent:
            return jsonify({'error': 'agent not registered'}), 404

        try:
            ts_str = payload.get('ts', '')
            try:
                collected_at = datetime.fromisoformat(ts_str.replace('Z', '+00:00')).replace(tzinfo=None)
            except (ValueError, AttributeError):
                collected_at = datetime.utcnow()

            collectors = payload.get('collectors', {})
            system = collectors.get('system', {})

            row = SensorTelemetry(
                agent_id=agent_id,
                collected_at=collected_at,
                cpu_pct=system.get('cpu_pct'),
                mem_pct=system.get('mem_pct'),
                load_avg_1m=(system.get('load_avg') or [None])[0],
                collectors_json=json.dumps(collectors),
            )
            db.session.add(row)

            agent.last_seen_at = datetime.utcnow()
            # Update host_ip and hostname if they changed
            if payload.get('host_ip'):
                agent.host_ip = payload['host_ip']
            if payload.get('hostname'):
                agent.hostname = payload['hostname']
            if payload.get('agent_version'):
                agent.agent_version = payload['agent_version']

            db.session.commit()
            return jsonify({'status': 'accepted', 'telemetry_id': row.id}), 202

        except Exception as e:
            db.session.rollback()
            print(f'[DEBUG] sensor ingest error: {e}')
            return jsonify({'error': str(e)}), 500

    # ------------------------------------------------------------------
    # GET /api/sensor/agents
    # ------------------------------------------------------------------
    @bp.route('/sensor/agents', methods=['GET'])
    def list_agents():
        agents = SensorAgent.query.order_by(SensorAgent.last_seen_at.desc()).all()
        result = []
        for a in agents:
            d = a.as_dict()
            d['status'] = sensor_service.compute_agent_status(a)
            result.append(d)
        return jsonify({'agents': result, 'count': len(result)})

    # ------------------------------------------------------------------
    # GET /api/sensor/agents/<agent_id>
    # ------------------------------------------------------------------
    @bp.route('/sensor/agents/<agent_id>', methods=['GET'])
    def get_agent(agent_id):
        agent = SensorAgent.query.filter_by(agent_id=agent_id).first()
        if not agent:
            return jsonify({'error': 'not found'}), 404

        recent = (
            SensorTelemetry.query
            .filter_by(agent_id=agent_id)
            .order_by(SensorTelemetry.collected_at.desc())
            .limit(10)
            .all()
        )
        d = agent.as_dict()
        d['status'] = sensor_service.compute_agent_status(agent)
        d['recent_telemetry'] = [r.as_dict(include_collectors=False) for r in recent]
        return jsonify(d)

    # ------------------------------------------------------------------
    # GET /api/sensor/latest/<agent_id>
    # ------------------------------------------------------------------
    @bp.route('/sensor/latest/<agent_id>', methods=['GET'])
    def get_latest(agent_id):
        agent = SensorAgent.query.filter_by(agent_id=agent_id).first()
        if not agent:
            return jsonify({'error': 'not found'}), 404

        row = (
            SensorTelemetry.query
            .filter_by(agent_id=agent_id)
            .order_by(SensorTelemetry.collected_at.desc())
            .first()
        )
        if not row:
            return jsonify({'error': 'no telemetry yet'}), 404

        return jsonify(row.as_dict(include_collectors=True))

    # ------------------------------------------------------------------
    # GET /api/sensor/timeline
    # Params: ip=<host_ip>, minutes=<int>, collectors=<comma-list>
    # ------------------------------------------------------------------
    @bp.route('/sensor/timeline', methods=['GET'])
    def get_timeline():
        ip = request.args.get('ip', '').strip()
        if not ip:
            return jsonify({'error': 'ip parameter required'}), 400

        minutes = min(int(request.args.get('minutes', 120)), 1440)
        collector_filter = request.args.get('collectors', '')
        wanted = set(collector_filter.split(',')) if collector_filter else set()

        agent = SensorAgent.query.filter_by(host_ip=ip).first()
        if not agent:
            return jsonify({'error': 'no agent for that ip'}), 404

        rows = sensor_service.get_timeline(db, agent.agent_id, minutes)
        entries = []
        for row in rows:
            d = row.as_dict(include_collectors=True)
            if wanted and 'collectors' in d:
                d['collectors'] = {k: v for k, v in d['collectors'].items() if k in wanted}
            entries.append(d)

        window_start = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
        window_end = datetime.utcnow().isoformat()
        return jsonify({
            'agent_id': agent.agent_id,
            'hostname': agent.hostname,
            'ip': ip,
            'window_start': window_start,
            'window_end': window_end,
            'entries': entries,
            'entry_count': len(entries),
        })

    # ------------------------------------------------------------------
    # GET /api/sensor/timeline/process-events
    # Params: ip=<host_ip>, minutes=<int>, process_name=<str>
    # ------------------------------------------------------------------
    @bp.route('/sensor/timeline/process-events', methods=['GET'])
    def get_process_events():
        ip = request.args.get('ip', '').strip()
        if not ip:
            return jsonify({'error': 'ip parameter required'}), 400

        minutes = min(int(request.args.get('minutes', 120)), 1440)
        process_name = request.args.get('process_name', '').strip() or None

        agent = SensorAgent.query.filter_by(host_ip=ip).first()
        if not agent:
            return jsonify({'error': 'no agent for that ip'}), 404

        events = sensor_service.get_process_events(db, agent.agent_id, minutes, process_name)
        return jsonify({
            'agent_id': agent.agent_id,
            'ip': ip,
            'minutes': minutes,
            'process_filter': process_name,
            'events': events,
            'event_count': len(events),
        })

    # ------------------------------------------------------------------
    # DELETE /api/sensor/agents/<agent_id>
    # ------------------------------------------------------------------
    @bp.route('/sensor/agents/<agent_id>', methods=['DELETE'])
    def delete_agent(agent_id):
        denied = _auth_check()
        if denied:
            return denied

        agent = SensorAgent.query.filter_by(agent_id=agent_id).first()
        if not agent:
            return jsonify({'error': 'not found'}), 404

        try:
            db.session.delete(agent)
            db.session.commit()
            return jsonify({'status': 'deleted', 'agent_id': agent_id})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    return bp
