"""Hunter systemd timer management."""
from __future__ import annotations

import os
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple

HUNTER_TIMERS: Dict[str, Dict[str, str]] = {
    'lab_inventory': {
        'unit': 'sentinel-hunter@lab_inventory.timer',
        'label': 'Lab Inventory',
        'description': 'Daily lab network inventory hunt',
    },
    'home_inventory': {
        'unit': 'sentinel-hunter@home_inventory.timer',
        'label': 'Home Inventory',
        'description': 'Daily home network inventory hunt',
    },
    'home_assess': {
        'unit': 'sentinel-hunter@home_assess.timer',
        'label': 'Home Assess',
        'description': 'Daily home assessment hunt',
    },
}

_ONCALENDAR_RE = re.compile(r'^OnCalendar\s*=\s*(.+)$', re.MULTILINE | re.IGNORECASE)
_TIME_FROM_CAL_RE = re.compile(r'(\d{1,2}):(\d{2})(?::\d{2})?')


def _run_systemctl(args: List[str], timeout: int = 15) -> Tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ['systemctl', *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, (proc.stdout or '').strip(), (proc.stderr or '').strip()
    except FileNotFoundError:
        return 127, '', 'systemctl not found'
    except subprocess.TimeoutExpired:
        return 124, '', 'systemctl timed out'


def _unit_file_candidates(unit: str) -> List[str]:
    repo_timer = os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        '..',
        '..',
        '..',
        'agent',
        'hunter',
        unit,
    ))
    return [
        f'/etc/systemd/system/{unit}',
        f'/lib/systemd/system/{unit}',
        f'/usr/lib/systemd/system/{unit}',
        repo_timer,
    ]


def _find_unit_file(unit: str) -> Optional[str]:
    for path in _unit_file_candidates(unit):
        if os.path.isfile(path):
            return path
    return None


def _parse_oncalendar(text: str) -> Optional[str]:
    match = _ONCALENDAR_RE.search(text or '')
    return match.group(1).strip() if match else None


def _time_from_oncalendar(oncalendar: Optional[str]) -> Optional[str]:
    if not oncalendar:
        return None
    match = _TIME_FROM_CAL_RE.search(oncalendar)
    if not match:
        return None
    return f'{int(match.group(1)):02d}:{match.group(2)}'


def _oncalendar_daily(hour: int, minute: int) -> str:
    return f'*-*-* {hour:02d}:{minute:02d}:00'


def get_timer_status(name: str) -> Dict[str, Any]:
    meta = HUNTER_TIMERS.get(name)
    if not meta:
        return {'error': f'Unknown timer: {name}'}

    unit = meta['unit']
    _, out_active, _ = _run_systemctl(['is-active', unit])
    _, out_enabled, _ = _run_systemctl(['is-enabled', unit])
    rc_show, out_show, err_show = _run_systemctl([
        'show',
        unit,
        '--property=ActiveState,UnitFileState,NextElapseUSecRealtime,LastTriggerUSec,TimersCalendar',
    ])

    props: Dict[str, str] = {}
    if rc_show == 0:
        for line in out_show.splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                props[key.strip()] = value.strip()

    unit_path = _find_unit_file(unit)
    oncalendar = None
    if unit_path:
        try:
            with open(unit_path, 'r', encoding='utf-8') as f:
                oncalendar = _parse_oncalendar(f.read())
        except OSError:
            oncalendar = None
    if not oncalendar and props.get('TimersCalendar'):
        oncalendar = props['TimersCalendar']

    privilege_ok = (
        rc_show != 127
        and 'Access denied' not in err_show
        and 'Permission denied' not in err_show
    )

    return {
        'name': name,
        'unit': unit,
        'label': meta['label'],
        'description': meta['description'],
        'active': out_active == 'active',
        'activeState': out_active or props.get('ActiveState') or 'unknown',
        'enabled': out_enabled in ('enabled', 'enabled-runtime', 'static'),
        'unitFileState': out_enabled or props.get('UnitFileState') or 'unknown',
        'onCalendar': oncalendar,
        'time': _time_from_oncalendar(oncalendar),
        'nextElapse': props.get('NextElapseUSecRealtime') or None,
        'lastTrigger': props.get('LastTriggerUSec') or None,
        'unitFilePath': unit_path,
        'privilegeOk': privilege_ok,
        'schedulable': True,
        'manualOnly': False,
    }


def list_timers() -> List[Dict[str, Any]]:
    return [get_timer_status(name) for name in HUNTER_TIMERS]


def set_timer_enabled(name: str, enabled: bool) -> Dict[str, Any]:
    meta = HUNTER_TIMERS.get(name)
    if not meta:
        return {'status': 'error', 'message': f'Unknown timer: {name}'}

    unit = meta['unit']
    rc, out, err = _run_systemctl(['enable' if enabled else 'disable', '--now', unit])
    if rc != 0:
        return {
            'status': 'error',
            'message': err or out or f'systemctl failed (exit {rc})',
            'hint': 'Backend user needs permission to manage hunter timers (polkit/sudoers).',
        }
    return {'status': 'success', 'timer': get_timer_status(name)}


def set_timer_schedule(name: str, time_str: str) -> Dict[str, Any]:
    """Update OnCalendar to daily at HH:MM and reload the timer."""
    meta = HUNTER_TIMERS.get(name)
    if not meta:
        return {'status': 'error', 'message': f'Unknown timer: {name}'}
    if not time_str or ':' not in time_str:
        return {'status': 'error', 'message': 'time must be HH:MM'}

    try:
        hour_s, minute_s = time_str.strip().split(':', 1)
        hour, minute = int(hour_s), int(minute_s)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError('out of range')
    except ValueError:
        return {'status': 'error', 'message': 'Invalid time; expected HH:MM'}

    unit = meta['unit']
    unit_path = _find_unit_file(unit)
    if not unit_path:
        return {'status': 'error', 'message': f'Unit file not found for {unit}'}

    etc_path = f'/etc/systemd/system/{unit}'
    try:
        with open(unit_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except OSError as e:
        return {'status': 'error', 'message': f'Cannot read unit file: {e}'}

    new_cal = _oncalendar_daily(hour, minute)
    if _ONCALENDAR_RE.search(content):
        new_content = _ONCALENDAR_RE.sub(f'OnCalendar={new_cal}', content, count=1)
    elif '[Timer]' in content:
        new_content = content.replace('[Timer]', f'[Timer]\nOnCalendar={new_cal}', 1)
    else:
        new_content = content + f'\n[Timer]\nOnCalendar={new_cal}\n'

    try:
        with open(etc_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
    except OSError as e:
        return {
            'status': 'error',
            'message': f'Cannot write {etc_path}: {e}',
            'hint': 'Backend user needs write access to /etc/systemd/system and systemctl reload.',
        }

    rc_reload, out_reload, err_reload = _run_systemctl(['daemon-reload'])
    if rc_reload != 0:
        return {'status': 'error', 'message': err_reload or out_reload or 'daemon-reload failed'}

    rc_restart, out_restart, err_restart = _run_systemctl(['restart', unit])
    if rc_restart != 0:
        return {
            'status': 'error',
            'message': err_restart or out_restart or f'restart {unit} failed',
        }

    return {'status': 'success', 'timer': get_timer_status(name)}


def patch_timer(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if name not in HUNTER_TIMERS:
        return {'status': 'error', 'message': f'Unknown timer: {name}'}

    result: Dict[str, Any] = {'status': 'success'}
    if 'enabled' in payload:
        result = set_timer_enabled(name, bool(payload['enabled']))
        if result.get('status') != 'success':
            return result

    if 'time' in payload and payload['time']:
        result = set_timer_schedule(name, str(payload['time']))
        if result.get('status') != 'success':
            return result

    if 'timer' not in result:
        result['timer'] = get_timer_status(name)
    return result
