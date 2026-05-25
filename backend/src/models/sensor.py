"""
Models for sentinel sensor agents and their telemetry.
"""
import json
from datetime import datetime
from ..config.database import db


class SensorAgent(db.Model):
    """Registry of enrolled sensor agents — one row per remote node."""
    __tablename__ = 'sensor_agent'

    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    hostname = db.Column(db.String(128))
    host_ip = db.Column(db.String(45), index=True)
    role = db.Column(db.String(32))           # proxmox-node | linux-vm | linux-server
    agent_version = db.Column(db.String(16))
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen_at = db.Column(db.DateTime)
    tags = db.Column(db.Text)                 # JSON array, e.g. '["proxmox","cluster"]'

    telemetry = db.relationship(
        'SensorTelemetry',
        backref='agent',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )

    def as_dict(self):
        return {
            'id': self.id,
            'agent_id': self.agent_id,
            'hostname': self.hostname,
            'host_ip': self.host_ip,
            'role': self.role,
            'agent_version': self.agent_version,
            'registered_at': self.registered_at.isoformat() if self.registered_at else None,
            'last_seen_at': self.last_seen_at.isoformat() if self.last_seen_at else None,
            'tags': json.loads(self.tags) if self.tags else [],
        }


class SensorTelemetry(db.Model):
    """Time-series telemetry — one row per 60-second collection cycle per agent."""
    __tablename__ = 'sensor_telemetry'

    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(
        db.String(64),
        db.ForeignKey('sensor_agent.agent_id'),
        nullable=False,
        index=True,
    )
    collected_at = db.Column(db.DateTime, nullable=False, index=True)
    received_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Denormalized scalars for fast timeline queries without JSON parsing
    cpu_pct = db.Column(db.Float)
    mem_pct = db.Column(db.Float)
    load_avg_1m = db.Column(db.Float)

    # Full collector payload as JSON blob
    collectors_json = db.Column(db.Text)

    def as_dict(self, include_collectors=True):
        d = {
            'id': self.id,
            'agent_id': self.agent_id,
            'collected_at': self.collected_at.isoformat() if self.collected_at else None,
            'received_at': self.received_at.isoformat() if self.received_at else None,
            'cpu_pct': self.cpu_pct,
            'mem_pct': self.mem_pct,
            'load_avg_1m': self.load_avg_1m,
        }
        if include_collectors:
            d['collectors'] = json.loads(self.collectors_json) if self.collectors_json else {}
        return d
