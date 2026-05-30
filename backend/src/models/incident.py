"""Incident memory — embeddings of past escalate verdicts / IDS alerts for similarity recall."""
import json
from datetime import datetime
from ..config.database import db


class IncidentEmbedding(db.Model):
    """One row per remembered incident (escalate verdict, IDS alert, analyst narrative)."""
    __tablename__ = 'incident_embedding'

    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(45), index=True)
    port = db.Column(db.Integer, index=True, nullable=True)
    scan_id = db.Column(db.Integer, index=True, nullable=True)
    source = db.Column(db.String(32), default='verdict')   # verdict | ids | narrative
    summary = db.Column(db.Text)                            # human-readable incident text
    embedding_model = db.Column(db.String(64))
    vector_json = db.Column(db.Text)                        # JSON array of floats
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def vector(self) -> list:
        return json.loads(self.vector_json) if self.vector_json else []

    def as_dict(self, include_vector=False):
        d = {
            'id': self.id,
            'ip': self.ip,
            'port': self.port,
            'scan_id': self.scan_id,
            'source': self.source,
            'summary': self.summary,
            'embedding_model': self.embedding_model,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_vector:
            d['vector'] = self.vector()
        return d
