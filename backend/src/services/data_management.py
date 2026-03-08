"""Data deletion and cleanup helpers."""
import os
from typing import Dict, Any

from ..models import Scan, Alert
from ..services.scan_runtime import ACTIVE_SCAN_STATUSES


def _safe_remove_file(path: str, base_dir: str) -> bool:
    if not path:
        return False
    full_path = path if os.path.isabs(path) else os.path.join(base_dir, path)
    full_path = os.path.normpath(full_path)
    if not full_path.startswith(os.path.normpath(base_dir)):
        return False
    if not os.path.isfile(full_path):
        return False
    try:
        os.remove(full_path)
        return True
    except Exception:
        return False


def delete_data(db, scope: str = 'scans', delete_files: bool = False, prune_orphan_files: bool = False) -> Dict[str, Any]:
    """Delete scan/all data with optional filesystem cleanup."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
    scans_dir = os.path.join(base_dir, 'scans')

    cancelled_running = 0
    for running in Scan.query.filter(Scan.status.in_(ACTIVE_SCAN_STATUSES)).all():
        running.status = 'cancelled'
        cancelled_running += 1

    scans = Scan.query.all()
    deleted_files = 0
    deleted_orphan_files = 0
    deleted_scans = len(scans)

    if delete_files:
        for scan in scans:
            if _safe_remove_file(scan.raw_xml_path, base_dir):
                deleted_files += 1

    for scan in scans:
        db.session.delete(scan)

    deleted_alerts = 0
    if scope == 'all':
        alerts = Alert.query.all()
        deleted_alerts = len(alerts)
        for alert in alerts:
            db.session.delete(alert)

    db.session.commit()

    if delete_files and prune_orphan_files and os.path.isdir(scans_dir):
        for filename in os.listdir(scans_dir):
            if not filename.endswith('.xml'):
                continue
            file_path = os.path.join(scans_dir, filename)
            try:
                os.remove(file_path)
                deleted_orphan_files += 1
            except Exception:
                continue

    return {
        'scope': scope,
        'deleted_scans': deleted_scans,
        'deleted_alerts': deleted_alerts,
        'cancelled_running_scans': cancelled_running,
        'deleted_scan_files': deleted_files,
        'deleted_orphan_scan_files': deleted_orphan_files,
    }

