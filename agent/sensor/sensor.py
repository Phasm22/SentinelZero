#!/usr/bin/env python3
"""
sentinel-sensor — endpoint telemetry daemon for SentinelZero.

Collects process, connection, auth, service, and system data every N seconds
and ships it to the central SentinelZero API.
"""
from __future__ import annotations
import argparse
import logging
import os
import signal
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import yaml

from reporter import Reporter

__version__ = '0.1.0'

log = logging.getLogger('sentinel-sensor')

COLLECTOR_MAP: dict[str, Callable] = {}


def _load_collectors():
    from collectors.base import collect_system
    from collectors.connections import collect_connections
    from collectors.processes import collect_processes
    from collectors.auth import collect_auth
    from collectors.services import collect_services
    COLLECTOR_MAP['system'] = collect_system
    COLLECTOR_MAP['connections'] = collect_connections
    COLLECTOR_MAP['processes'] = collect_processes
    COLLECTOR_MAP['auth'] = collect_auth
    COLLECTOR_MAP['services'] = collect_services
    try:
        from role_modules.proxmox import collect_proxmox
        COLLECTOR_MAP['proxmox'] = collect_proxmox
    except ImportError:
        pass


def _load_config(path: str) -> dict:
    with open(path) as f:
        cfg = yaml.safe_load(f) or {}
    return cfg


def _resolve_host_ip(api_url: str) -> str:
    try:
        import urllib.parse
        host = urllib.parse.urlparse(api_url).hostname or '8.8.8.8'
        port = urllib.parse.urlparse(api_url).port or 80
        with socket.create_connection((host, port), timeout=3) as s:
            return s.getsockname()[0]
    except Exception:
        return socket.gethostbyname(socket.gethostname())


def run(config_path: str) -> None:
    cfg = _load_config(config_path)

    level = getattr(logging, cfg.get('log_level', 'INFO').upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format='%(asctime)s %(name)s %(levelname)s %(message)s',
    )

    _load_collectors()

    agent_id = cfg['agent_id']
    api_url = cfg['api_url']
    api_key = cfg.get('api_key', '')
    interval = int(cfg.get('interval', 60))
    role = cfg.get('role', 'linux-server')
    host_ip = cfg.get('host_ip') or _resolve_host_ip(api_url)
    hostname = cfg.get('hostname') or socket.getfqdn()
    auth_log = cfg.get('auth_log_path', '/var/log/auth.log')
    enabled: dict = cfg.get('collectors', {})

    reporter = Reporter(api_url, api_key)
    reporter.register_agent(agent_id, hostname, host_ip, role, __version__,
                            tags=cfg.get('tags', []))

    stop = False

    def _handle_signal(sig, frame):
        nonlocal stop
        log.info('[sensor] signal %d received — stopping', sig)
        stop = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    log.info('[sensor] starting — agent_id=%s ip=%s role=%s interval=%ds',
             agent_id, host_ip, role, interval)

    cycle = 0
    while not stop:
        cycle += 1
        ts = datetime.now(tz=timezone.utc).isoformat()
        payload: dict = {
            'agent_id': agent_id,
            'host_ip': host_ip,
            'hostname': hostname,
            'role': role,
            'ts': ts,
            'agent_version': __version__,
            'collectors': {},
        }

        for name, fn in COLLECTOR_MAP.items():
            if not enabled.get(name, True):
                continue
            # auth collector needs log_path kwarg
            try:
                if name == 'auth':
                    payload['collectors'][name] = fn(log_path=auth_log)
                else:
                    payload['collectors'][name] = fn()
            except Exception as exc:
                log.warning('[sensor] collector %s failed: %s', name, exc)
                payload['collectors'][name] = {'error': str(exc)}

        ok = reporter.post_telemetry(payload)
        log.info('[sensor] cycle %d: %d collectors, POST %s',
                 cycle, len(payload['collectors']), 'ok' if ok else 'FAILED')

        # Sleep in short chunks so SIGTERM is handled promptly
        for _ in range(interval):
            if stop:
                break
            time.sleep(1)

    log.info('[sensor] stopped')


def main():
    parser = argparse.ArgumentParser(description='SentinelZero sensor daemon')
    parser.add_argument(
        '--config', '-c',
        default=None,
        help='Path to config.yaml',
    )
    args = parser.parse_args()

    search = [
        args.config,
        '/etc/sentinel-sensor/config.yaml',
        str(Path(__file__).parent / 'config.yaml'),
    ]
    config_path = next((p for p in search if p and os.path.exists(p)), None)
    if not config_path:
        print('ERROR: no config.yaml found. Checked:', [p for p in search if p])
        raise SystemExit(1)

    run(config_path)


if __name__ == '__main__':
    main()
