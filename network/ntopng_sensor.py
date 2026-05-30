#!/usr/bin/env python3
"""
sentinel-ntopng — network telemetry sensor for SentinelZero.

Runs on the SentinelZero host. Polls ntopng REST API on a configurable
interval and ships network context to the SentinelZero ingest endpoint
for correlation with nmap scan diffs.

Collected data (all non-low-value):
  interface_stats   throughput, flow/host counts, TCP health, anomaly counts
  l7_stats          top protocols by bytes (application-layer breakdown)
  l4_counters       TCP / UDP / ICMP / other distribution
  alerts            currently engaged security alerts
  active_hosts      count + flagged hosts (score > 0 or alerted)
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
log = logging.getLogger('sentinel-ntopng')

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_ALERT_CAP       = 50
_L7_TOP_N        = 25
_FLAGGED_HOST_CAP = 20


# ---------------------------------------------------------------------------
# ntopng API client
# ---------------------------------------------------------------------------

class NtopngClient:
    """Thin wrapper around ntopng REST v2 API.

    Auth: session-based (preferred) — POSTs credentials to /authorize.html,
    maintains a session cookie. Re-authenticates automatically on 302 redirect
    back to login. Falls back to ?token= query param if ntopng_user is unset.
    """

    def __init__(self, base_url: str, token: str = '', user: str = '',
                 password: str = '', timeout: int = 10, verify_ssl: bool = False):
        self._base = base_url.rstrip('/')
        self._token = token
        self._user = user
        self._password = password
        self._timeout = timeout
        self._verify = verify_ssl
        self._s = requests.Session()
        self._s.headers['Accept'] = 'application/json'

    def _login(self) -> bool:
        """POST credentials to /authorize.html to obtain a session cookie."""
        try:
            r = self._s.post(
                f'{self._base}/authorize.html',
                # JS removes _username name attr before submit; only user/password/referer are sent
                data={'user': self._user, 'password': self._password, 'referer': ''},
                allow_redirects=True,
                timeout=self._timeout, verify=self._verify,
            )
            # Success: ntopng sets a session cookie and redirects to dashboard
            # Failure: redirects back to /lua/login.lua
            if 'login' in r.url.lower():
                log.error('ntopng login failed — check ntopng_user/ntopng_password in config.yaml')
                return False
            log.info('[auth] ntopng session established')
            return True
        except requests.RequestException as exc:
            log.error('ntopng login request failed: %s', exc)
            return False

    def _get(self, path: str, params: dict | None = None, _retry: bool = True) -> dict | list | None:
        p = dict(params or {})
        if self._token and not self._user:
            p['token'] = self._token
        try:
            r = self._s.get(
                f'{self._base}{path}', params=p,
                timeout=self._timeout, verify=self._verify,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            log.warning('ntopng request failed %s: %s', path, exc)
            return None

        # 302 to login means session expired or auth failed — re-authenticate once
        if r.status_code == 302 and _retry and self._user:
            if self._login():
                return self._get(path, params, _retry=False)
            return None

        try:
            r.raise_for_status()
        except requests.RequestException as exc:
            log.warning('ntopng HTTP error %s: %s', path, exc)
            return None

        if not r.text or not r.text.strip():
            return None

        try:
            data = r.json()
        except ValueError:
            log.warning('ntopng non-JSON response for %s (status=%s, body=%.80s)',
                        path, r.status_code, r.text)
            return None

        if data.get('rc', 0) not in (0, None):
            log.debug('ntopng rc=%s for %s: %s', data.get('rc'), path, data.get('rc_str'))
            return None
        return data.get('rsp')

    def ping(self) -> bool:
        """Check ntopng reachability without auth (version endpoint is public)."""
        try:
            r = self._s.get(f'{self._base}/lua/rest/version.lua',
                            timeout=self._timeout, verify=self._verify)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def interfaces(self) -> list[dict]:
        rsp = self._get('/lua/rest/v2/get/ntopng/interfaces.lua')
        if not rsp:
            return [{'ifid': 1, 'name': 'default'}]
        if isinstance(rsp, dict):
            out = []
            for k, v in rsp.items():
                try:
                    ifid = int(k)
                except (ValueError, TypeError):
                    continue
                name = v.get('name', k) if isinstance(v, dict) else str(v)
                out.append({'ifid': ifid, 'name': name})
            return out or [{'ifid': 1, 'name': 'default'}]
        if isinstance(rsp, list):
            return rsp
        return [{'ifid': 1, 'name': 'default'}]

    def interface_data(self, ifid: int) -> dict | None:
        return self._get('/lua/rest/v2/get/interface/data.lua', {'ifid': ifid})

    def l7_stats(self, ifid: int) -> dict | None:
        return self._get('/lua/rest/v2/get/interface/l7/stats.lua', {
            'ifid': ifid,
            'ndpistats_mode': 'count',
        })

    def l4_counters(self, ifid: int) -> dict | None:
        return self._get('/lua/rest/v2/get/flow/l4/counters.lua', {'ifid': ifid})

    def alerts(self, ifid: int) -> list:
        rsp = self._get('/lua/rest/v2/get/alert/data.lua', {
            'ifid': ifid,
            'status': 'engaged',
            'perPage': _ALERT_CAP,
            'currentPage': 1,
        })
        if rsp is None:
            return []
        if isinstance(rsp, dict):
            return rsp.get('data', []) or []
        return rsp if isinstance(rsp, list) else []

    def active_hosts(self, ifid: int) -> dict | None:
        return self._get('/lua/rest/v2/get/host/active.lua', {
            'ifid': ifid,
            'currentPage': 1,
            'perPage': 200,
            'sortColumn': 'score',
            'sortOrder': 'desc',
        })


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------

def collect_interface_stats(client: NtopngClient, ifids: list[int]) -> list[dict]:
    results = []
    for ifid in ifids:
        raw = client.interface_data(ifid)
        if not raw:
            continue
        tcp = raw.get('tcpPacketStats', {})
        tput = raw.get('throughput', {})
        results.append({
            'ifid': ifid,
            'num_flows': raw.get('num_flows'),
            'throughput_bps': raw.get('throughput_bps'),
            'upload_bps': tput.get('upload', {}).get('bps'),
            'download_bps': tput.get('download', {}).get('bps'),
            'bytes_upload_since_reset': raw.get('bytes_upload_since_reset'),
            'bytes_download_since_reset': raw.get('bytes_download_since_reset'),
            'num_local_hosts_anomalies': raw.get('num_local_hosts_anomalies'),
            'alerted_flows_error': raw.get('alerted_flows_error', 0),
            'alerted_flows_notice': raw.get('alerted_flows_notice', 0),
            'flow_dropped_alerts': raw.get('flow_dropped_alerts', 0),
            'tcp_retransmissions': tcp.get('retransmissions'),
            'tcp_lost': tcp.get('lost'),
            'tcp_ooo': tcp.get('out_of_order'),
        })
    return results


def collect_l7_stats(client: NtopngClient, ifids: list[int]) -> list[dict]:
    """Top protocols by flow count across all interfaces."""
    results = []
    for ifid in ifids:
        raw = client.l7_stats(ifid)
        if not raw:
            continue
        # Response: {labels: ["TLS","DNS",...], series: [42,23,...], ...}
        labels = raw.get('labels', [])
        series = raw.get('series', [])
        if not labels or not series:
            continue
        protos = [
            {'protocol': label, 'flows': count}
            for label, count in zip(labels, series)
            if label and count
        ]
        protos.sort(key=lambda x: x['flows'], reverse=True)
        results.append({'ifid': ifid, 'top_protocols': protos[:_L7_TOP_N]})
    return results


def collect_l4_counters(client: NtopngClient, ifids: list[int]) -> list[dict]:
    results = []
    for ifid in ifids:
        raw = client.l4_counters(ifid)
        if raw is None:
            continue
        results.append({'ifid': ifid, 'counters': raw})
    return results


def collect_alerts(client: NtopngClient, ifids: list[int]) -> list[dict]:
    all_alerts = []
    for ifid in ifids:
        for alert in client.alerts(ifid):
            if not isinstance(alert, dict):
                continue
            all_alerts.append({
                'ifid': ifid,
                'alert_type': alert.get('alert_type_label') or alert.get('alert_type'),
                'severity': alert.get('alert_severity_label') or alert.get('alert_severity'),
                'entity': alert.get('alert_entity_val') or alert.get('entity_val'),
                'description': alert.get('alert_description') or alert.get('msg'),
                'first_seen': alert.get('tstamp') or alert.get('first_seen'),
                'last_seen': alert.get('tstamp_end') or alert.get('last_seen'),
                'score': alert.get('score'),
            })
    return all_alerts[:_ALERT_CAP]


def collect_active_hosts(client: NtopngClient, ifids: list[int]) -> dict:
    total = 0
    flagged = []
    for ifid in ifids:
        raw = client.active_hosts(ifid)
        if not raw:
            continue
        hosts = raw.get('data', raw) if isinstance(raw, dict) else raw
        if not isinstance(hosts, list):
            continue
        total += len(hosts)
        for h in hosts:
            if not isinstance(h, dict):
                continue
            raw_score = h.get('score', 0) or 0
            # score may be a dict {total, as_client, as_server} or a plain int
            score_total = raw_score.get('total', 0) if isinstance(raw_score, dict) else int(raw_score or 0)
            num_alerts = h.get('num_alerts', 0) or 0
            if score_total > 0 or num_alerts > 0:
                flagged.append({
                    'ip': h.get('ip') or h.get('host'),
                    'name': h.get('name') or h.get('hostname'),
                    'score': score_total,
                    'num_alerts': num_alerts,
                    'bytes_sent': (h.get('bytes') or {}).get('sent') or h.get('bytes_sent'),
                    'bytes_rcvd': (h.get('bytes') or {}).get('recvd') or h.get('bytes_rcvd'),
                })
    flagged.sort(key=lambda x: x.get('score', 0), reverse=True)
    return {'total_active': total, 'flagged': flagged[:_FLAGGED_HOST_CAP]}


from sensor_reporter import Reporter

def _load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def run(config_path: str) -> None:
    cfg = _load_config(config_path)

    level = getattr(logging, cfg.get('log_level', 'INFO').upper(), logging.INFO)
    logging.basicConfig(level=level, format='%(asctime)s %(name)s %(levelname)s %(message)s')

    agent_id  = cfg['agent_id']
    api_url   = cfg['api_url']
    api_key   = cfg.get('api_key', '')
    interval  = int(cfg.get('interval', 60))
    role      = cfg.get('role', 'network-sensor')
    tags      = cfg.get('tags', ['category:network', 'source:ntopng'])
    host_ip   = cfg.get('host_ip', '172.16.0.1')
    hostname  = cfg.get('hostname', 'opnsense')

    ntopng_url      = cfg['ntopng_url']
    ntopng_token    = cfg.get('ntopng_token') or os.environ.get('NTOPNG_TOKEN', '')
    ntopng_user     = cfg.get('ntopng_user', '')
    ntopng_password = cfg.get('ntopng_password') or os.environ.get('NTOPNG_PASSWORD', '')
    verify_ssl      = cfg.get('verify_ssl', False)
    ifids           = cfg.get('interface_ids', [1])

    client = NtopngClient(
        ntopng_url, token=ntopng_token,
        user=ntopng_user, password=ntopng_password,
        verify_ssl=verify_ssl,
    )

    if not client.ping():
        log.error('[sensor] ntopng unreachable at %s — check ntopng_url and network', ntopng_url)
    else:
        log.info('[sensor] ntopng reachable at %s', ntopng_url)
        if ntopng_user:
            client._login()

    reporter = Reporter(api_url, api_key)
    reporter.register(agent_id, hostname, host_ip, role, tags, version=__version__)

    stop = False

    def _handle_signal(sig, _frame):
        nonlocal stop
        log.info('[sensor] signal %d — stopping', sig)
        stop = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    log.info('[sensor] starting — agent_id=%s ntopng=%s ifids=%s interval=%ds',
             agent_id, ntopng_url, ifids, interval)

    cycle = 0
    while not stop:
        cycle += 1
        reporter.maybe_reregister(cycle)
        ts = datetime.now(tz=timezone.utc).isoformat()

        collectors: dict = {}
        for name, fn, args in [
            ('interface_stats', collect_interface_stats, (client, ifids)),
            ('l7_stats',        collect_l7_stats,        (client, ifids)),
            ('l4_counters',     collect_l4_counters,     (client, ifids)),
            ('alerts',          collect_alerts,          (client, ifids)),
            ('active_hosts',    collect_active_hosts,    (client, ifids)),
        ]:
            if not cfg.get('collectors', {}).get(name, True):
                continue
            try:
                collectors[name] = fn(*args)
            except Exception as exc:
                log.warning('[sensor] collector %s failed: %s', name, exc)
                collectors[name] = {'error': str(exc)}

        payload = {
            'agent_id': agent_id,
            'host_ip':  host_ip,
            'hostname': hostname,
            'role':     role,
            'ts':       ts,
            'agent_version': __version__,
            'collectors': collectors,
        }

        ok = reporter.ingest(payload)
        log.info('[sensor] cycle %d: %d collectors, POST %s',
                 cycle, len(collectors), 'ok' if ok else 'FAILED')

        for _ in range(interval):
            if stop:
                break
            time.sleep(1)

    log.info('[sensor] stopped')


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description='SentinelZero ntopng sensor')
    parser.add_argument('--config', '-c', default=None)
    args = parser.parse_args()

    search = [
        args.config,
        '/etc/sentinel-ntopng/config.yaml',
        str(Path(__file__).parent / 'config.yaml'),
    ]
    config_path = next((p for p in search if p and os.path.exists(p)), None)
    if not config_path:
        print('ERROR: no config.yaml found. Checked:', [p for p in search if p])
        raise SystemExit(1)
    run(config_path)


if __name__ == '__main__':
    main()
