"""Nmap scheduled-scan config load/migrate/hydrate helpers."""
from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, List, Optional

SCHEDULE_SETTINGS_FILE = 'scheduled_scans_settings.json'
SCHEDULED_JOB_PREFIX = 'scheduled_scan_'

MAINTENANCE_JOB_IDS = {
    'xml_cleanup',
    'sensor_telemetry_cleanup',
    'sensor_telemetry_vacuum',
    'whats_up_snapshot_refresh',
    'hunter_baseline_snapshot',
    'wal_checkpoint',
}


def schedule_settings_path() -> str:
    return os.path.abspath(SCHEDULE_SETTINGS_FILE)


def _frequency_to_cron(frequency: str, time_str: str) -> Dict[str, str]:
    hour, minute = '2', '0'
    if time_str and ':' in time_str:
        parts = time_str.split(':')
        hour = str(int(parts[0]))
        minute = str(int(parts[1])) if len(parts) > 1 else '0'

    freq = (frequency or 'daily').lower()
    if freq == 'hourly':
        return {'minute': minute, 'hour': '*', 'day': '*', 'month': '*', 'dayOfWeek': '*'}
    if freq == 'weekly':
        return {'minute': minute, 'hour': hour, 'day': '*', 'month': '*', 'dayOfWeek': '0'}
    if freq == 'monthly':
        return {'minute': minute, 'hour': hour, 'day': '1', 'month': '*', 'dayOfWeek': '*'}
    return {'minute': minute, 'hour': hour, 'day': '*', 'month': '*', 'dayOfWeek': '*'}


def normalize_job(job: Dict[str, Any], fallback_index: int = 0) -> Dict[str, Any]:
    job_id = job.get('id') or f'nmap_{fallback_index}_{uuid.uuid4().hex[:8]}'
    return {
        'id': str(job_id),
        'enabled': bool(job.get('enabled', False)),
        'scanType': job.get('scanType') or job.get('scan_type') or 'Full TCP',
        'targetNetwork': (
            job.get('targetNetwork')
            or job.get('target_network')
            or '172.16.0.0/22'
        ),
        'minute': str(job.get('minute', '0')),
        'hour': str(job.get('hour', '0')),
        'day': str(job.get('day', '*')),
        'month': str(job.get('month', '*')),
        'dayOfWeek': str(job.get('dayOfWeek', job.get('day_of_week', '*'))),
    }


def migrate_legacy_settings(raw: Any) -> List[Dict[str, Any]]:
    """Normalize stored schedule settings to a list of cron job configs."""
    if raw is None:
        return []

    if isinstance(raw, list):
        return [
            normalize_job(item, fallback_index=i)
            for i, item in enumerate(raw)
            if isinstance(item, dict)
        ]

    if not isinstance(raw, dict):
        return []

    if 'scanType' not in raw and 'scan_type' not in raw:
        return []

    if 'minute' in raw or 'hour' in raw:
        return [normalize_job(raw, fallback_index=0)]

    if not raw.get('enabled', False):
        return []

    cron = _frequency_to_cron(raw.get('frequency', 'daily'), raw.get('time', '02:00'))
    return [normalize_job({
        'enabled': True,
        'scanType': raw.get('scanType') or raw.get('scan_type') or 'Full TCP',
        'targetNetwork': raw.get('targetNetwork') or raw.get('target_network') or '172.16.0.0/22',
        **cron,
    }, fallback_index=0)]


def load_scheduled_jobs(path: Optional[str] = None) -> List[Dict[str, Any]]:
    path = path or schedule_settings_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        return migrate_legacy_settings(raw)
    except Exception as e:
        print(f'[WARN] Failed to load scheduled scans from {path}: {e}')
        return []


def save_scheduled_jobs(jobs: List[Dict[str, Any]], path: Optional[str] = None) -> List[Dict[str, Any]]:
    path = path or schedule_settings_path()
    normalized = [normalize_job(j, fallback_index=i) for i, j in enumerate(jobs)]
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(normalized, f, indent=4)
    return normalized


def clear_nmap_jobs(scheduler) -> None:
    if not scheduler:
        return
    for job in list(scheduler.get_jobs()):
        if job.id.startswith(SCHEDULED_JOB_PREFIX):
            try:
                scheduler.remove_job(job.id)
            except Exception:
                pass


def register_nmap_jobs(scheduler, app, socketio, jobs: List[Dict[str, Any]]) -> int:
    """Register enabled nmap schedule jobs. Returns count registered."""
    if not scheduler:
        return 0

    from apscheduler.triggers.cron import CronTrigger
    from .scanner import run_nmap_scan

    clear_nmap_jobs(scheduler)
    runtime = app.extensions.get('scan_runtime')
    if runtime is None:
        print('[WARN] scan_runtime missing; skipping nmap schedule registration')
        return 0

    registered = 0
    for i, scan_config in enumerate(jobs):
        if not scan_config.get('enabled', False):
            continue

        job_id = f'{SCHEDULED_JOB_PREFIX}{scan_config.get("id") or i}'
        trigger = CronTrigger(
            minute=scan_config.get('minute', '0'),
            hour=scan_config.get('hour', '0'),
            day=scan_config.get('day', '*'),
            month=scan_config.get('month', '*'),
            day_of_week=scan_config.get('dayOfWeek', '*'),
        )
        scan_type = scan_config['scanType']
        scheduled_network = scan_config.get('targetNetwork') or '172.16.0.0/22'

        def scheduled_scan_wrapper(scan_type=scan_type, scheduled_network=scheduled_network):
            with app.app_context():
                security_settings = {
                    'vuln_scanning_enabled': True,
                    'os_detection_enabled': True,
                    'service_detection_enabled': True,
                    'aggressive_scanning': False,
                }
                try:
                    if os.path.exists('security_settings.json'):
                        with open('security_settings.json', 'r', encoding='utf-8') as f:
                            security_settings.update(json.load(f))
                except Exception as e:
                    print(f'[DEBUG] Could not load security settings for scheduled scan: {e}')

                scan = runtime.create_scan(
                    scan_type=scan_type,
                    target_network=scheduled_network,
                    source='scheduled',
                    initiated_by='scheduler',
                    correlation_id=str(uuid.uuid4()),
                    state='queued',
                    message=f'Queued scheduled {scan_type} on {scheduled_network}',
                )
                runtime.emit_scan_event('scan.started', scan)
                runtime.emit_snapshot(scan)
                run_nmap_scan(scan.id, scan_type, security_settings, socketio, app, scheduled_network)

        scheduler.add_job(
            func=scheduled_scan_wrapper,
            trigger=trigger,
            id=job_id,
            name=f'Scheduled {scan_type} Scan',
            replace_existing=True,
        )
        registered += 1
        print(f'[DEBUG] Scheduled scan job created: {job_id}')

    return registered


def hydrate_scheduled_scans(scheduler, app, socketio) -> int:
    """Load JSON config and register APScheduler jobs at startup."""
    jobs = load_scheduled_jobs()
    path = schedule_settings_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                save_scheduled_jobs(jobs, path)
        except Exception:
            pass
    return register_nmap_jobs(scheduler, app, socketio, jobs)


def enrich_jobs_with_next_run(scheduler, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    job_map = {}
    if scheduler:
        try:
            job_map = {job.id: job for job in scheduler.get_jobs()}
        except Exception:
            job_map = {}

    enriched = []
    for i, job in enumerate(jobs):
        item = dict(job)
        aps_id = f'{SCHEDULED_JOB_PREFIX}{job.get("id") or i}'
        aps_job = job_map.get(aps_id)
        item['apschedulerJobId'] = aps_id
        item['nextRunTime'] = (
            aps_job.next_run_time.isoformat()
            if aps_job is not None and getattr(aps_job, 'next_run_time', None)
            else None
        )
        enriched.append(item)
    return enriched


def list_maintenance_jobs(scheduler) -> List[Dict[str, Any]]:
    if not scheduler:
        return []
    try:
        return [
            {
                'id': job.id,
                'name': job.name or job.id,
                'nextRunTime': job.next_run_time.isoformat()
                if getattr(job, 'next_run_time', None)
                else None,
                'trigger': str(job.trigger) if getattr(job, 'trigger', None) else None,
            }
            for job in scheduler.get_jobs()
            if job.id in MAINTENANCE_JOB_IDS
        ]
    except Exception as e:
        print(f'[WARN] list_maintenance_jobs: {e}')
        return []
