"""
Incremental auth log parser.

Tracks inode + byte offset across cycles (Wazuh-style) so only new lines
are parsed each run. State is stored at /var/lib/sentinel-sensor/auth_state.json.
On first run, positions at EOF — historical events are not replayed.
"""
from __future__ import annotations
import json
import os
import re
from datetime import datetime
from pathlib import Path

STATE_FILE = Path('/var/lib/sentinel-sensor/auth_state.json')
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

_PATTERNS = [
    # Accepted login
    (re.compile(r'sshd.*Accepted (\w+) for (\S+) from ([\d.]+)'),
     lambda m: {'event': 'ssh_login_ok', 'method': m.group(1), 'user': m.group(2), 'source': m.group(3)}),
    # Failed login
    (re.compile(r'sshd.*Failed (\w+) for (?:invalid user )?(\S+) from ([\d.]+)'),
     lambda m: {'event': 'ssh_login_fail', 'method': m.group(1), 'user': m.group(2), 'source': m.group(3)}),
    # Session opened
    (re.compile(r'sshd.*session opened for user (\S+)'),
     lambda m: {'event': 'session_opened', 'user': m.group(1), 'source': None}),
    # Sudo command
    (re.compile(r'sudo:\s+(\S+)\s*:.*COMMAND=(.+)$'),
     lambda m: {'event': 'sudo_command', 'user': m.group(1), 'command': m.group(2).strip()[:200]}),
    # User add/del
    (re.compile(r'(useradd|userdel|usermod).*user (\S+)'),
     lambda m: {'event': 'user_change', 'action': m.group(1), 'user': m.group(2)}),
]

_TS_RE = re.compile(r'^(\w{3}\s+\d+\s+[\d:]+)')
_CAP = 50


def _parse_ts(line: str) -> str:
    m = _TS_RE.match(line)
    return m.group(1) if m else ''


def _parse_line(line: str) -> dict | None:
    for pattern, builder in _PATTERNS:
        m = pattern.search(line)
        if m:
            result = builder(m)
            result['ts'] = _parse_ts(line)
            return result
    return None


def collect_auth(log_path: str = '/var/log/auth.log') -> list:
    if not os.path.exists(log_path):
        return []

    try:
        current_inode = os.stat(log_path).st_ino
    except OSError:
        return []

    state: dict = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            state = {}

    # Detect log rotation by inode change
    if state.get('inode') != current_inode:
        state = {'inode': current_inode, 'offset': None}

    events = []
    try:
        with open(log_path, 'r', errors='replace') as f:
            if state.get('offset') is None:
                # First run — seek to end, don't replay history
                f.seek(0, 2)
            else:
                f.seek(state['offset'])

            for line in f:
                evt = _parse_line(line)
                if evt:
                    events.append(evt)

            new_offset = f.tell()
    except OSError:
        return []

    STATE_FILE.write_text(json.dumps({'inode': current_inode, 'offset': new_offset}))
    return events[-_CAP:]
