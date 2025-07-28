"""
Alert model for storing notifications and alerts
"""
from datetime import datetime
from ..config.database import db

class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    title = db.Column(db.String(128))
    message = db.Column(db.String(256))
    severity = db.Column(db.String(16), default='info')  # info, warning, error
    read = db.Column(db.Boolean, default=False)
    scan_id = db.Column(db.Integer, db.ForeignKey('scan.id'), nullable=True)
