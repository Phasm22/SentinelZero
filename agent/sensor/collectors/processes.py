"""Process list collector with process→port correlation."""
from datetime import datetime

import psutil

_CAP = 200


def collect_processes() -> list:
    # Build pid->listening_ports map from connections (one pass, then reuse)
    pid_ports: dict = {}
    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.status == 'LISTEN' and conn.pid and conn.laddr:
                pid_ports.setdefault(conn.pid, []).append(
                    f'{conn.laddr.ip}:{conn.laddr.port}'
                )
    except (psutil.AccessDenied, PermissionError):
        pass

    procs = []
    try:
        all_procs = list(psutil.process_iter(
            ['pid', 'name', 'username', 'memory_percent', 'cpu_percent', 'create_time', 'status']
        ))
        # Sort by cpu_percent descending so we keep the most active under the cap
        all_procs.sort(key=lambda p: p.info.get('cpu_percent') or 0, reverse=True)

        for proc in all_procs[:_CAP]:
            try:
                info = proc.info
                started = datetime.fromtimestamp(info['create_time']).strftime('%H:%M:%S') \
                    if info.get('create_time') else None
                procs.append({
                    'pid': info['pid'],
                    'name': info['name'],
                    'user': info.get('username'),
                    'mem_pct': round(info.get('memory_percent') or 0, 2),
                    'cpu_pct': round(info.get('cpu_percent') or 0, 2),
                    'status': info.get('status'),
                    'started_at': started,
                    'listening_ports': pid_ports.get(info['pid'], []),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass

    return procs
