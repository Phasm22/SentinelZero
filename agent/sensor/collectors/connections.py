"""Active network connection collector with process-name resolution."""
import psutil

_KEEP_STATES = {'LISTEN', 'ESTABLISHED'}
_CAP = 500


def collect_connections() -> list:
    # Build pid->name cache first (one pass)
    pid_names: dict = {}
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                pid_names[proc.info['pid']] = proc.info['name']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass

    results = []
    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.status not in _KEEP_STATES:
                continue

            laddr = f'{conn.laddr.ip}:{conn.laddr.port}' if conn.laddr else None
            raddr = f'{conn.raddr.ip}:{conn.raddr.port}' if conn.raddr else None

            results.append({
                'local_addr': laddr,
                'remote_addr': raddr,
                'state': conn.status,
                'pid': conn.pid,
                'process': pid_names.get(conn.pid, 'unknown') if conn.pid else 'unknown',
            })

            if len(results) >= _CAP:
                break
    except (psutil.AccessDenied, PermissionError):
        pass

    return results
