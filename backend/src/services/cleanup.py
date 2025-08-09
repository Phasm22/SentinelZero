"""Utility for cleaning up old scan XML files and orphaned records."""
import os
from datetime import datetime, timedelta
from ..models import Scan
from ..config.database import db
from flask import current_app

DEFAULT_RETENTION_DAYS = 14

def cleanup_old_scan_files(retention_days: int | None = None, scans_dir: str = 'scans'):
    """Delete XML files older than retention_days and remove DB records with missing files.

    Args:
        retention_days: Days to retain XML files. Defaults to DEFAULT_RETENTION_DAYS.
        scans_dir: Directory where scan XML files are stored (relative to backend root).
    """
    retention = retention_days or DEFAULT_RETENTION_DAYS
    cutoff = datetime.utcnow() - timedelta(days=retention)
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
    target_dir = os.path.join(base_dir, scans_dir)
    if not os.path.isdir(target_dir):
        return {'removed_files': 0, 'removed_records': 0}

    removed_files = 0
    # Remove old files
    for fname in os.listdir(target_dir):
        if not fname.endswith('.xml'):
            continue
        fpath = os.path.join(target_dir, fname)
        try:
            mtime = datetime.utcfromtimestamp(os.path.getmtime(fpath))
            if mtime < cutoff:
                os.remove(fpath)
                removed_files += 1
        except Exception:
            continue

    # Remove scan records pointing to missing files (optional light cleanup)
    removed_records = 0
    try:
        scans = Scan.query.all()
        for s in scans:
            if s.raw_xml_path and not os.path.exists(s.raw_xml_path):
                # Only prune if completed > retention ago
                if s.completed_at and s.completed_at < cutoff:
                    db.session.delete(s)
                    removed_records += 1
        if removed_records:
            db.session.commit()
    except Exception:
        db.session.rollback()

    return {'removed_files': removed_files, 'removed_records': removed_records}

def scheduled_cleanup_job():
    """Scheduled job entrypoint (uses current_app)."""
    app = current_app
    if app:
        with app.app_context():
            result = cleanup_old_scan_files()
            print(f"[CLEANUP] Removed {result['removed_files']} files, {result['removed_records']} records")
