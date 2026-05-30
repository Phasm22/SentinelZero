#!/usr/bin/env python3
"""
sentinel-pihole — DNS telemetry sensor for SentinelZero.

Polls Pi-hole v6 REST API and ships DNS context to the SentinelZero
ingest endpoint. Runs on the SentinelZero host; one process per Pi-hole.

Collected data:
  summary       total queries, blocked %, unique domains, query type breakdown
  top_domains   top queried domains (what hosts are resolving)
  top_blocked   top blocked domains (malware/ad signal)
  top_clients   top clients by query count (who's chatty)
"""
from __future__ import annotations
import logging
import os
import signal
import time
import urllib3
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

__version__ = '0.1.0'
log = logging.getLogger('sentinel-pihole')

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_TOP_N = 20


class PiholeClient:
    """Pi-hole v6 REST API client with automatic session management."""

    def __init__(self, base_url: str, password: str,
                 timeout: int = 10, verify_ssl: bool = False):
        self._base = base_url.rstrip('/')
        self._password = password
        self._timeout = timeout
        self._verify = verify_ssl
        self._sid: str = ''
        self._s = requests.Session()
        self._s.headers['Content-Type'] = 'application/json'

    def login(self) -> bool:
        try:
            r = self._s.post(
                f'{self._base}/api/auth',
                json={'password': self._password},
                timeout=self._timeout, verify=self._verify,
            )
            r.raise_for_status()
            data = r.json()
            session = data.get('session', {})
            if not session.get('valid'):
                log.error('pihole login rejected — check pihole_password in config')
                return False
            self._sid = session['sid']
            self._s.headers['X-FTL-SID'] = self._sid
            log.info('[auth] pihole session established (validity=%ss)', session.get('validity'))
            return True
        except requests.RequestException as exc:
            log.error('pihole login failed: %s', exc)
            return False

    def logout(self) -> None:
        if not self._sid:
            return
        try:
            self._s.delete(f'{self._base}/api/auth',
                           timeout=self._timeout, verify=self._verify)
        except requests.RequestException:
            pass
        self._sid = ''

    def _get(self, path: str, params: dict | None = None, _retry: bool = True) -> dict | None:
        try:
            r = self._s.get(
                f'{self._base}{path}', params=params,
                timeout=self._timeout, verify=self._verify,
            )
        except requests.RequestException as exc:
            log.warning('pihole request failed %s: %s', path, exc)
            return None

        if r.status_code == 401 and _retry:
            log.info('[auth] session expired — re-authenticating')
            if self.login():
                return self._get(path, params, _retry=False)
            return None

        if not r.ok:
            log.warning('pihole HTTP %s for %s', r.status_code, path)
            return None

        try:
            return r.json()
        except ValueError:
            log.warning('pihole non-JSON response for %s', path)
            return None

    def ping(self) -> bool:
        try:
            r = self._s.get(f'{self._base}/api/info/version',
                            timeout=self._timeout, verify=self._verify)
            return r.status_code in (200, 401)
        except requests.RequestException:
            return False


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------

def collect_summary(client: PiholeClient) -> dict | None:
    data = client._get('/api/stats/summary')
    if not data:
        return None
    q = data.get('queries', {})
    return {
        'total': q.get('total'),
        'blocked': q.get('blocked'),
        'percent_blocked': round(q.get('percent_blocked', 0), 2),
        'unique_domains': q.get('unique_domains'),
        'forwarded': q.get('forwarded'),
        'cached': q.get('cached'),
        'query_types': {k: v for k, v in (q.get('types') or {}).items() if v},
    }


def collect_top_domains(client: PiholeClient) -> list[dict]:
    data = client._get('/api/stats/top_domains',
                       params={'blocked': 'false', 'count': _TOP_N})
    if not data:
        return []
    return data.get('domains', [])


def collect_top_blocked(client: PiholeClient) -> list[dict]:
    data = client._get('/api/stats/top_domains',
                       params={'blocked': 'true', 'count': _TOP_N})
    if not data:
        return []
    return data.get('domains', [])


def collect_top_clients(client: PiholeClient) -> list[dict]:
    data = client._get('/api/stats/top_clients',
                       params={'blocked': 'false', 'count': _TOP_N})
    if not data:
        return []
    return data.get('clients', [])


from sensor_reporter import Reporter


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run(config_path: str) -> None:
    with open(config_path) as f:
        cfg = yaml.safe_load(f) or {}

    level = getattr(logging, cfg.get('log_level', 'INFO').upper(), logging.INFO)
    logging.basicConfig(level=level, format='%(asctime)s %(name)s %(levelname)s %(message)s')

    agent_id       = cfg['agent_id']
    api_url        = cfg['api_url']
    api_key        = cfg.get('api_key', '')
    interval       = int(cfg.get('interval', 60))
    role           = cfg.get('role', 'network-sensor')
    tags           = cfg.get('tags', ['category:network', 'source:pihole'])
    host_ip        = cfg['host_ip']
    hostname       = cfg.get('hostname', host_ip)
    pihole_url     = cfg['pihole_url']
    pihole_password = cfg.get('pihole_password', '')
    verify_ssl     = cfg.get('verify_ssl', False)

    client   = PiholeClient(pihole_url, pihole_password, verify_ssl=verify_ssl)
    reporter = Reporter(api_url, api_key)

    if not client.ping():
        log.error('[sensor] pihole unreachable at %s', pihole_url)
    else:
        if not client.login():
            log.error('[sensor] auth failed — will retry each cycle')

    reporter.register(agent_id, hostname, host_ip, role, tags, version=__version__)

    stop = False

    def _handle_signal(sig, _frame):
        nonlocal stop
        log.info('[sensor] signal %d — stopping', sig)
        stop = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    log.info('[sensor] starting — agent_id=%s pihole=%s interval=%ds',
             agent_id, pihole_url, interval)

    cycle = 0
    while not stop:
        cycle += 1
        reporter.maybe_reregister(cycle)
        ts = datetime.now(tz=timezone.utc).isoformat()

        collectors: dict = {}
        for name, fn in [
            ('summary',     lambda: collect_summary(client)),
            ('top_domains', lambda: collect_top_domains(client)),
            ('top_blocked', lambda: collect_top_blocked(client)),
            ('top_clients', lambda: collect_top_clients(client)),
        ]:
            if not cfg.get('collectors', {}).get(name, True):
                continue
            try:
                collectors[name] = fn()
            except Exception as exc:
                log.warning('[sensor] collector %s failed: %s', name, exc)
                collectors[name] = {'error': str(exc)}

        payload = {
            'agent_id': agent_id, 'host_ip': host_ip, 'hostname': hostname,
            'role': role, 'ts': ts, 'agent_version': __version__,
            'collectors': collectors,
        }

        ok = reporter.ingest(payload)
        log.info('[sensor] cycle %d: %d collectors, POST %s',
                 cycle, len(collectors), 'ok' if ok else 'FAILED')

        for _ in range(interval):
            if stop:
                break
            time.sleep(1)

    client.logout()
    log.info('[sensor] stopped')


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description='SentinelZero pihole sensor')
    parser.add_argument('--config', '-c', default=None)
    args = parser.parse_args()

    search = [args.config, str(Path(__file__).parent / 'config.yaml')]
    config_path = next((p for p in search if p and os.path.exists(p)), None)
    if not config_path:
        print('ERROR: no config.yaml found')
        raise SystemExit(1)
    run(config_path)


if __name__ == '__main__':
    main()
