"""
Scan model for storing network scan results
"""
from datetime import datetime
from ..config.database import db

class Scan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    scan_type = db.Column(db.String(32))
    hosts_json = db.Column(db.Text)
    diff_from_previous = db.Column(db.Text)
    vulns_json = db.Column(db.Text)
    raw_xml_path = db.Column(db.String(256))
    status = db.Column(db.String(32), default='pending')
    status_message = db.Column(db.Text, default='Pending')
    execution_mode = db.Column(db.String(32), default='normal')
    error_code = db.Column(db.String(64), nullable=True)
    error_detail = db.Column(db.Text, nullable=True)
    source = db.Column(db.String(32), default='manual')
    initiated_by = db.Column(db.String(64), default='api')
    correlation_id = db.Column(db.String(64), nullable=True)
    total_hosts = db.Column(db.Integer, default=0)
    hosts_up = db.Column(db.Integer, default=0)
    total_ports = db.Column(db.Integer, default=0)
    open_ports = db.Column(db.Integer, default=0)
    insights_json = db.Column(db.Text)
    process_id = db.Column(db.Integer, nullable=True)
    
    def as_dict(self):
        """Convert scan instance to dictionary"""
        return {
            'id': self.id,
            'created_at': self.created_at,
            'completed_at': self.completed_at,
            'scan_type': self.scan_type,
            'hosts_json': self.hosts_json,
            'diff_from_previous': self.diff_from_previous,
            'vulns_json': self.vulns_json,
            'raw_xml_path': self.raw_xml_path,
            'status': self.status,
            'status_message': self.status_message,
            'execution_mode': self.execution_mode,
            'error_code': self.error_code,
            'error_detail': self.error_detail,
            'source': self.source,
            'initiated_by': self.initiated_by,
            'correlation_id': self.correlation_id,
            'process_id': self.process_id,
            'total_hosts': self.total_hosts,
            'hosts_up': self.hosts_up,
            'total_ports': self.total_ports,
            'open_ports': self.open_ports,
            'insights_json': self.insights_json
        }
