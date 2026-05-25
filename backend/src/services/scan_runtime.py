"""Runtime helpers for scan lifecycle state and realtime delivery."""
import json
from datetime import datetime

from flask import request
from flask_socketio import emit, join_room, leave_room

from ..models import Scan
from .observability import log_event

ACTIVE_SCAN_STATUSES = (
    'queued',
    'running',
    'parsing',
    'saving',
    'postprocessing',
    'starting',
    'in_progress',
)


class ScanRuntime:
    """Persist scan state transitions and emit room-scoped events."""

    def __init__(self, db, socketio):
        self.db = db
        self.socketio = socketio

    @staticmethod
    def scan_room(scan_id):
        return f'scan:{scan_id}'

    @staticmethod
    def serialize_scan(scan, include_results=False):
        payload = {
            'scan_id': scan.id,
            'id': scan.id,
            'scan_type': scan.scan_type,
            'target_network': getattr(scan, 'target_network', None),
            'source': getattr(scan, 'source', 'manual') or 'manual',
            'initiated_by': getattr(scan, 'initiated_by', 'api') or 'api',
            'correlation_id': getattr(scan, 'correlation_id', None),
            'state': scan.status,
            'status': scan.status,
            'message': getattr(scan, 'status_message', None) or f'Status: {scan.status}',
            'execution_mode': getattr(scan, 'execution_mode', None) or 'normal',
            'error_code': getattr(scan, 'error_code', None),
            'error_detail': getattr(scan, 'error_detail', None),
            'process_id': scan.process_id,
            'created_at': scan.created_at.isoformat() if scan.created_at else None,
            'started_at': scan.created_at.isoformat() if scan.created_at else None,
            'completed_at': scan.completed_at.isoformat() if scan.completed_at else None,
            'total_hosts': scan.total_hosts or 0,
            'hosts_up': scan.hosts_up or 0,
            'total_ports': scan.total_ports or 0,
            'open_ports': scan.open_ports or 0,
        }
        if include_results:
            try:
                payload['hosts'] = json.loads(scan.hosts_json) if scan.hosts_json else []
            except Exception:
                payload['hosts'] = []
            try:
                payload['vulns'] = json.loads(scan.vulns_json) if scan.vulns_json else []
            except Exception:
                payload['vulns'] = []
            payload['hosts_count'] = len(payload['hosts'])
            payload['vulns_count'] = len(payload['vulns'])
        return payload

    def get_scan(self, scan_id):
        return self.db.session.get(Scan, scan_id)

    def create_scan(
        self,
        scan_type,
        source='manual',
        initiated_by='api',
        state='queued',
        message='Queued scan request',
        execution_mode='normal',
        correlation_id=None,
        target_network=None,
    ):
        scan = Scan(
            scan_type=scan_type,
            target_network=target_network,
            status=state,
            status_message=message,
            execution_mode=execution_mode,
            source=source,
            initiated_by=initiated_by,
            correlation_id=correlation_id,
        )
        self.db.session.add(scan)
        self.db.session.commit()
        log_event(
            'scan.created',
            scan_id=scan.id,
            scan_type=scan.scan_type,
            source=scan.source,
            initiated_by=scan.initiated_by,
            correlation_id=scan.correlation_id,
            state=scan.status,
        )
        return scan

    def update_scan(self, scan_id, **changes):
        scan = self.get_scan(scan_id)
        if not scan:
            raise LookupError(f'Scan {scan_id} not found')

        for field, value in changes.items():
            setattr(scan, field, value)

        self.db.session.commit()
        return scan

    def emit_scan_event(self, event_name, scan, extra=None, include_results=False):
        payload = self.serialize_scan(scan, include_results=include_results)
        if extra:
            payload.update(extra)
        room = self.scan_room(scan.id)
        self.socketio.emit(event_name, payload, room=room)

        return payload

    def emit_snapshot(self, scan, include_results=False):
        return self.emit_scan_event('scan.snapshot', scan, include_results=include_results)

    def append_log(self, scan_id, message):
        scan = self.get_scan(scan_id)
        if not scan:
            return None
        return self.emit_scan_event('scan.log', scan, extra={
            'msg': message,
            'timestamp': datetime.utcnow().isoformat(),
        })

    def set_state(self, scan_id, state, message, emit_event=True, event_name='scan.progress', **extra_updates):
        scan = self.update_scan(
            scan_id,
            status=state,
            status_message=message,
            **extra_updates,
        )
        if emit_event:
            self.emit_scan_event(event_name, scan)
        return scan

    def fail_scan(self, scan_id, message, error_code='scan_failed'):
        scan = self.update_scan(
            scan_id,
            status='failed',
            status_message=message,
            error_code=error_code,
            error_detail=message,
            completed_at=datetime.utcnow(),
        )
        self.emit_scan_event('scan.failed', scan)
        log_event(
            'scan.failed',
            scan_id=scan.id,
            error_code=scan.error_code,
            execution_mode=scan.execution_mode,
            correlation_id=getattr(scan, 'correlation_id', None),
        )
        return scan

    def complete_scan(self, scan_id, message='Scan complete!'):
        scan = self.update_scan(
            scan_id,
            status='complete',
            status_message=message,
            completed_at=datetime.utcnow(),
            error_code=None,
            error_detail=None,
        )
        self.emit_scan_event('scan.completed', scan)
        duration_ms = None
        if scan.created_at and scan.completed_at:
            duration_ms = round((scan.completed_at - scan.created_at).total_seconds() * 1000, 2)
        log_event(
            'scan.completed',
            scan_id=scan.id,
            execution_mode=scan.execution_mode,
            duration_ms=duration_ms,
            correlation_id=getattr(scan, 'correlation_id', None),
        )
        return scan

    def cancel_scan(self, scan_id, message='Scan cancelled by user'):
        scan = self.update_scan(
            scan_id,
            status='cancelled',
            status_message=message,
            completed_at=datetime.utcnow(),
        )
        self.emit_scan_event('scan.cancelled', scan)
        return scan



def register_socket_handlers(socketio, runtime):
    """Attach room-based Socket.IO handlers."""

    @socketio.on('connect')
    def handle_connect():
        join_room(request.sid)
        emit('socket.ready', {
            'sid': request.sid,
            'message': 'Connected to SentinelZero',
        }, to=request.sid)

    @socketio.on('disconnect')
    def handle_disconnect():
        try:
            leave_room(request.sid)
        except Exception:
            pass

    @socketio.on('ping')
    def handle_ping(data=None):
        emit('pong', {'message': 'Server received ping', 'echo': data}, to=request.sid)

    @socketio.on('scan.subscribe')
    def handle_scan_subscribe(data):
        scan_id = None
        if isinstance(data, dict):
            scan_id = data.get('scan_id')
        if scan_id is None:
            emit('scan.subscription_error', {'message': 'scan_id is required'}, to=request.sid)
            return
        room = runtime.scan_room(scan_id)
        join_room(room)
        scan = runtime.get_scan(scan_id)
        emit('scan.subscribed', {'scan_id': scan_id}, to=request.sid)
        if scan:
            emit('scan.snapshot', runtime.serialize_scan(scan, include_results=False), to=request.sid)

    @socketio.on('scan.unsubscribe')
    def handle_scan_unsubscribe(data):
        scan_id = None
        if isinstance(data, dict):
            scan_id = data.get('scan_id')
        if scan_id is None:
            return
        leave_room(runtime.scan_room(scan_id))
        emit('scan.unsubscribed', {'scan_id': scan_id}, to=request.sid)
