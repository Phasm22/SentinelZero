#!/usr/bin/env python3
"""
sentinel-opnsense — OPNsense gateway sensor for SentinelZero.

Runs on the SentinelZero host. Polls the OPNsense REST API on a configurable
interval and ships gateway/network context to the SentinelZero ingest endpoint.

Auth: HTTP Basic Auth — key:secret from OPNsense user manager (System > Access > Users).
The key/secret pair must have at minimum read access to the API modules used here.

Collected data:
  system_info       firmware version, product metadata
  gateway_status    WAN/LAN gateway health, loss, latency
  interface_stats   per-interface byte/packet counters and errors
  traffic           live throughput snapshot per interface
  arp_table         all ARP entries — IP, MAC, hostname, manufacturer, interface
  dhcp_leases       full DHCP lease table — hostname, IP, MAC, online status
  ids_alerts        Suricata IDS alert log (most recent N entries)
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
log = logging.getLogger('sentinel-opnsense')

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_IDS_CAP  = 100   # max IDS alerts to ship per cycle
_ARP_CAP  = 500   # max ARP entries
_DHCP_CAP = 500   # max DHCP leases


# ── OPNsense API client ────────────────────────────────────────────────────────

class OPNsenseClient:
    """
    Thin client for the OPNsense REST API.

    Authentication: HTTP Basic Auth (key:secret). All endpoints return JSON.
    Base URL: https://<host>/api/<module>/<controller>/<action>
    """

    def __init__(self, base_url: str, key: str, secret: str,
                 timeout: int = 10, verify_ssl: bool = False):
        self._base    = base_url.rstrip('/')
        self._timeout = timeout
        self._verify  = verify_ssl
        self._auth    = (key, secret)
        self._s = requests.Session()
        self._s.headers['Accept'] = 'application/json'

    def _get(self, path: str, params: dict | None = None) -> dict | list | None:
        try:
            r = self._s.get(
                f'{self._base}{path}',
                params=params,
                auth=self._auth,
                timeout=self._timeout,
                verify=self._verify,
            )
            r.raise_for_status()
            return r.json() if r.text.strip() else None
        except requests.RequestException as exc:
            log.warning('GET %s failed: %s', path, exc)
            return None

    def _post(self, path: str, body: dict | None = None) -> dict | list | None:
        try:
            r = self._s.post(
                f'{self._base}{path}',
                json=body or {},
                auth=self._auth,
                timeout=self._timeout,
                verify=self._verify,
            )
            r.raise_for_status()
            return r.json() if r.text.strip() else None
        except requests.RequestException as exc:
            log.warning('POST %s failed: %s', path, exc)
            return None

    def ping(self) -> bool:
        r = self._get('/api/core/firmware/status')
        return isinstance(r, dict) and 'product' in r

    # ── Endpoints ──────────────────────────────────────────────────────────────

    def firmware_status(self) -> dict | None:
        return self._get('/api/core/firmware/status')

    def gateway_status(self) -> dict | None:
        return self._get('/api/routes/gateway/status')

    def interface_statistics(self) -> dict | None:
        return self._get('/api/diagnostics/interface/getInterfaceStatistics')

    def traffic_interface(self) -> dict | None:
        return self._get('/api/diagnostics/traffic/interface')

    def arp_table(self) -> list | None:
        return self._get('/api/diagnostics/interface/getArp')

    def dhcp_leases(self, row_count: int = _DHCP_CAP) -> dict | None:
        return self._post('/api/dhcpv4/leases/searchLease', {
            'current':      1,
            'rowCount':     row_count,
            'sort':         {},
            'searchPhrase': '',
        })

    def ids_alerts(self, row_count: int = _IDS_CAP) -> dict | None:
        return self._post('/api/ids/service/queryAlerts', {
            'current':      1,
            'rowCount':     row_count,
            'sort':         {},
            'searchPhrase': '',
        })


# ── Collectors ─────────────────────────────────────────────────────────────────

def collect_system_info(client: OPNsenseClient) -> dict:
    raw = client.firmware_status()
    if not raw:
        return {}
    p = raw.get('product', {})
    return {
        'version':     p.get('CORE_PKGVERSION'),
        'product':     p.get('CORE_PRODUCT'),
        'nickname':    p.get('CORE_NICKNAME'),
        'arch':        p.get('CORE_ARCH'),
        'abi':         p.get('CORE_ABI'),
        'next_version':p.get('CORE_NEXT'),
    }


def collect_gateway_status(client: OPNsenseClient) -> list:
    raw = client.gateway_status()
    if not raw:
        return []
    items = raw.get('items', raw) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []
    return [
        {
            'name':    gw.get('name'),
            'address': gw.get('address'),
            'monitor': gw.get('monitor'),
            'status':  gw.get('status_translated') or gw.get('status'),
            'loss':    gw.get('loss'),
            'delay_ms':gw.get('delay'),
            'stddev':  gw.get('stddev'),
        }
        for gw in items
        if isinstance(gw, dict)
    ]


def collect_interface_stats(client: OPNsenseClient) -> list:
    raw = client.interface_statistics()
    if not raw:
        return []
    stats = raw.get('statistics', raw) if isinstance(raw, dict) else raw
    if not isinstance(stats, dict):
        return []

    # Collapse per-address rows into per-interface rows, keeping IP-addressed entries
    seen: set[str] = set()
    results = []
    for label, data in stats.items():
        if not isinstance(data, dict):
            continue
        name    = data.get('name') or label
        network = data.get('network', '')
        address = data.get('address', '')

        # Skip link-layer rows (MAC address entries); keep IP-addressed rows
        if ':' in address and '.' not in address:
            continue
        key = f"{name}:{network}"
        if key in seen:
            continue
        seen.add(key)

        results.append({
            'interface':      name,
            'network':        network,
            'address':        address,
            'rx_bytes':       data.get('received-bytes'),
            'tx_bytes':       data.get('sent-bytes'),
            'rx_packets':     data.get('received-packets'),
            'tx_packets':     data.get('sent-packets'),
            'rx_errors':      data.get('received-errors', 0),
            'tx_errors':      data.get('send-errors', 0),
            'dropped_packets':data.get('dropped-packets', 0),
            'collisions':     data.get('collisions', 0),
        })
    return results


def collect_traffic(client: OPNsenseClient) -> list:
    raw = client.traffic_interface()
    if not raw:
        return []
    interfaces = raw.get('interfaces', raw) if isinstance(raw, dict) else {}
    if not isinstance(interfaces, dict):
        return []

    results = []
    for iface_name, data in interfaces.items():
        if not isinstance(data, dict):
            continue
        results.append({
            'interface':  iface_name,
            'device':     data.get('device'),
            'rx_bytes':   data.get('bytes received'),
            'tx_bytes':   data.get('bytes transmitted'),
            'rx_packets': data.get('packets received'),
            'tx_packets': data.get('packets transmitted'),
            'rx_errors':  data.get('input errors', 0),
            'tx_errors':  data.get('output errors', 0),
            'mtu':        data.get('mtu'),
            'line_rate':  data.get('line rate'),
        })
    return results


def collect_arp_table(client: OPNsenseClient) -> list:
    raw = client.arp_table()
    if not isinstance(raw, list):
        return []

    results = []
    for entry in raw[:_ARP_CAP]:
        if not isinstance(entry, dict):
            continue
        results.append({
            'ip':           entry.get('ip'),
            'mac':          entry.get('mac'),
            'hostname':     entry.get('hostname') or '',
            'manufacturer': entry.get('manufacturer') or '',
            'interface':    entry.get('intf'),
            'network':      entry.get('intf_description') or '',
            'expired':      entry.get('expired', False),
            'expires_sec':  entry.get('expires'),
            'permanent':    entry.get('permanent', False),
        })
    return results


def collect_dhcp_leases(client: OPNsenseClient) -> list:
    raw = client.dhcp_leases()
    if not raw:
        return []
    rows = raw.get('rows', raw) if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        return []

    results = []
    for lease in rows[:_DHCP_CAP]:
        if not isinstance(lease, dict):
            continue
        results.append({
            'ip':           lease.get('address'),
            'mac':          lease.get('mac'),
            'hostname':     lease.get('hostname') or '',
            'description':  lease.get('descr') or '',
            'manufacturer': lease.get('man') or '',
            'network':      lease.get('if_descr') or '',
            'type':         lease.get('type'),       # static / dynamic
            'status':       lease.get('status'),     # online / offline
            'starts':       lease.get('starts') or None,
            'ends':         lease.get('ends') or None,
        })
    return results


def collect_ids_alerts(client: OPNsenseClient) -> list:
    raw = client.ids_alerts()
    if not raw:
        return []
    rows = raw.get('rows', raw) if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        return []

    results = []
    for alert in rows[:_IDS_CAP]:
        if not isinstance(alert, dict):
            continue
        results.append({
            'timestamp':  alert.get('timestamp'),
            'interface':  alert.get('in_iface'),
            'src_ip':     alert.get('src_ip'),
            'src_port':   alert.get('src_port'),
            'dest_ip':    alert.get('dest_ip'),
            'dest_port':  alert.get('dest_port'),
            'proto':      alert.get('proto'),
            'alert':      alert.get('alert'),
            'sid':        alert.get('alert_sid'),
            'action':     alert.get('alert_action'),
            'direction':  alert.get('direction'),
            'flow':       alert.get('flow'),
        })
    return results


from sensor_reporter import Reporter


# ── Main loop ──────────────────────────────────────────────────────────────────

def _load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def run(config_path: str) -> None:
    cfg = _load_config(config_path)

    level = getattr(logging, cfg.get('log_level', 'INFO').upper(), logging.INFO)
    logging.basicConfig(level=level, format='%(asctime)s %(name)s %(levelname)s %(message)s')

    agent_id      = cfg['agent_id']
    api_url       = cfg['api_url']
    api_key       = cfg.get('api_key', '')
    interval      = int(cfg.get('interval', 60))
    role          = cfg.get('role', 'network-sensor')
    tags          = cfg.get('tags', ['category:network', 'source:opnsense'])
    host_ip       = cfg.get('host_ip', '172.16.0.1')
    hostname      = cfg.get('hostname', 'opnsense')

    opnsense_url  = cfg['opnsense_url']
    opnsense_key  = cfg.get('opnsense_key') or os.environ.get('OPNSENSE_KEY', '')
    opnsense_sec  = cfg.get('opnsense_secret') or os.environ.get('OPNSENSE_SECRET', '')
    verify_ssl    = cfg.get('verify_ssl', False)

    client = OPNsenseClient(opnsense_url, opnsense_key, opnsense_sec, verify_ssl=verify_ssl)

    if not client.ping():
        log.error('[sensor] OPNsense unreachable at %s — check opnsense_url and credentials', opnsense_url)
    else:
        log.info('[sensor] OPNsense reachable at %s (OPNsense 25.x)', opnsense_url)

    reporter = Reporter(api_url, api_key)
    reporter.register(agent_id, hostname, host_ip, role, tags, version=__version__)

    stop = False

    def _handle_signal(sig, _frame):
        nonlocal stop
        log.info('[sensor] signal %d — stopping', sig)
        stop = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    collector_cfg = cfg.get('collectors', {})

    _collectors = [
        ('system_info',     collect_system_info,     (client,),          True),
        ('gateway_status',  collect_gateway_status,  (client,),          True),
        ('interface_stats', collect_interface_stats, (client,),          True),
        ('traffic',         collect_traffic,         (client,),          True),
        ('arp_table',       collect_arp_table,       (client,),          True),
        ('dhcp_leases',     collect_dhcp_leases,     (client,),          True),
        ('ids_alerts',      collect_ids_alerts,      (client,),          True),
    ]

    log.info('[sensor] starting — agent_id=%s opnsense=%s interval=%ds',
             agent_id, opnsense_url, interval)

    cycle = 0
    while not stop:
        cycle += 1
        reporter.maybe_reregister(cycle)
        ts = datetime.now(tz=timezone.utc).isoformat()

        collectors: dict = {}
        for name, fn, args, default_on in _collectors:
            if not collector_cfg.get(name, default_on):
                continue
            try:
                collectors[name] = fn(*args)
            except Exception as exc:
                log.warning('[sensor] collector %s failed: %s', name, exc)
                collectors[name] = {'error': str(exc)}

        # Log summary
        ids = collectors.get('ids_alerts', [])
        arp = collectors.get('arp_table', [])
        gws = collectors.get('gateway_status', [])
        down_gw = [g['name'] for g in gws if isinstance(g, dict) and 'offline' in (g.get('status') or '').lower()]
        log.info('[sensor] cycle %d: %d arp entries, %d ids alerts%s',
                 cycle, len(arp) if isinstance(arp, list) else 0,
                 len(ids) if isinstance(ids, list) else 0,
                 f', GATEWAYS DOWN: {down_gw}' if down_gw else '')

        ok = reporter.ingest({
            'agent_id':      agent_id,
            'host_ip':       host_ip,
            'hostname':      hostname,
            'role':          role,
            'ts':            ts,
            'agent_version': __version__,
            'collectors':    collectors,
        })
        if not ok:
            log.error('[sensor] cycle %d: ingest failed', cycle)

        for _ in range(interval):
            if stop:
                break
            time.sleep(1)

    log.info('[sensor] stopped')


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description='SentinelZero OPNsense sensor')
    p.add_argument('--config', '-c', default=None)
    args = p.parse_args()

    search = [
        args.config,
        '/etc/sentinel-opnsense/config.yaml',
        str(Path(__file__).parent / 'config-opnsense.yaml'),
    ]
    config_path = next((p for p in search if p and os.path.exists(p)), None)
    if not config_path:
        print('ERROR: no config found. Checked:', [p for p in search if p])
        raise SystemExit(1)
    run(config_path)


if __name__ == '__main__':
    main()
