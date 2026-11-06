#!/usr/bin/env python3
"""
sentinel-wifi — passive RF summary sensor for SentinelZero (Hermes wireless/RF).

Posts Wi-Fi *summaries* via the shared Reporter envelope. Does not capture
packets, invoke wifi-mon/tshark, change radio mode, or transmit.

Hard rules (R1–R7):
  R1  Passive receive only — no deauth/injection/active probing from this process.
  R2  Own/authorized ESS summaries; neighbor APs are occupancy counts only.
  R3  No cracking / handshake / PMKID material in envelopes.
  R4  Never expose wifi-mon as a forge primitive from this sensor.
  R5  Never touch uplink iface wlp58s0. If a sniff iface is named, it is only
      wlx54c9ff02d309 (hardware capture itself is a deferred PoC).
  R6  Never print secrets / PSKs / SENSOR_API_KEY values (header name only).
  R7  Payload-free summaries — management/control metadata only.

Live monitor-mode capture and t470s-rf-mcp on the laptop are deferred; this
module reads optional local summary JSON (produced later by a capture daemon)
or ships an empty heartbeat so registration + ingest paths stay warm.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sensor_reporter import Reporter

__version__ = '0.1.0'
log = logging.getLogger('sentinel-wifi')

# Defaults match Hermes wireless/RF spec §6 (T470s core sense).
DEFAULT_AGENT_ID = 't470s-rf'
DEFAULT_HOSTNAME = 'phasm-T470s'
DEFAULT_HOST_IP = '192.168.68.111'
DEFAULT_ROLE = 'wireless'
DEFAULT_TAGS = ['rf', 'passive']
DEFAULT_INTERVAL = 60
WIFI_MAX_BYTES = 5 * 1024
# Named only as a comment/default constant — this process never configures it.
SNIFF_IFACE = 'wlx54c9ff02d309'
UPLINK_IFACE = 'wlp58s0'  # refused; never operated on

_SECRET_KEYS = frozenset({
    'psk', 'password', 'passphrase', 'api_key', 'sensor_api_key',
    'token', 'secret', 'wpa_psk', 'pmkid', 'handshake',
})


def _strip_secrets(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: _strip_secrets(v)
            for k, v in obj.items()
            if not is_secret(k)
        }
    if isinstance(obj, list):
        return [_strip_secrets(x) for x in obj]
    return obj


def is_secret(key: str) -> bool:
    return str(key).lower() in _SECRET_KEYS


def enforce_wifi_budget(wifi: dict, max_bytes: int = WIFI_MAX_BYTES) -> dict:
    """Ensure collectors.wifi JSON is ≤ max_bytes (summaries only)."""
    if not isinstance(wifi, dict):
        return empty_wifi_summary(reason='invalid_wifi_block')

    cleaned = _strip_secrets(wifi)
    normalized = {
        'aps': cleaned.get('aps') if isinstance(cleaned.get('aps'), list) else [],
        'clients_summary': (
            cleaned.get('clients_summary')
            if isinstance(cleaned.get('clients_summary'), dict)
            else {}
        ),
        'channels': cleaned.get('channels') if isinstance(cleaned.get('channels'), list) else [],
        'events': cleaned.get('events') if isinstance(cleaned.get('events'), list) else [],
    }
    for key, value in cleaned.items():
        if key not in normalized:
            normalized[key] = value

    def _size(payload: dict) -> int:
        return len(json.dumps(payload, separators=(',', ':'), default=str).encode('utf-8'))

    if _size(normalized) <= max_bytes:
        return normalized

    for field in ('events', 'aps', 'channels'):
        items = list(normalized.get(field) or [])
        while items and _size(normalized) > max_bytes:
            items = items[:-1]
            normalized[field] = items
        if _size(normalized) <= max_bytes:
            return normalized

    cs = normalized.get('clients_summary') or {}
    return {
        'aps': [],
        'clients_summary': {
            k: cs.get(k)
            for k in ('associated', 'probe_noise_count', 'unresolved')
            if k in cs
        },
        'channels': [],
        'events': [],
        'truncated': True,
    }


def empty_wifi_summary(*, reason: str = 'no_local_summary') -> dict:
    """Heartbeat-shaped wifi block when capture/summary DB is not available yet."""
    return {
        'aps': [],
        'clients_summary': {
            'associated': 0,
            'probe_noise_count': 0,
            'unresolved': 0,
        },
        'channels': [],
        'events': [],
        'sensor': {
            'status': 'deferred',
            'reason': reason,
            # Document intent only — no iface bring-up from this process.
            'sniff_iface_expected': SNIFF_IFACE,
            'uplink_iface_refused': UPLINK_IFACE,
            'capture': 'deferred_hardware_poc',
            'mcp': 't470s-rf-mcp deferred',
        },
    }


def load_summary_file(path: str | Path | None) -> dict | None:
    """Load a local RF summary JSON produced by a future capture daemon.

    Expected shape: {aps, clients_summary, channels, events, ...}. Returns None
    if path is missing/unreadable. Never invokes wifi-mon, tshark, or sudo.
    """
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        log.warning('[wifi] summary file unreadable (%s): %s', p, exc)
        return None
    if not isinstance(data, dict):
        return None
    # Allow either a bare wifi block or {wifi: {...}} / {collectors:{wifi:...}}.
    if 'wifi' in data and isinstance(data['wifi'], dict):
        return data['wifi']
    collectors = data.get('collectors')
    if isinstance(collectors, dict) and isinstance(collectors.get('wifi'), dict):
        return collectors['wifi']
    return data


def collect_system() -> dict:
    """Lightweight host vitals for the shared envelope (no secrets)."""
    load_avg: list[float] | list[None]
    try:
        load_avg = list(os.getloadavg())
    except (AttributeError, OSError):
        load_avg = [None, None, None]

    mem_pct = None
    try:
        # /proc/meminfo — portable enough for the T470s Linux target.
        info: dict[str, int] = {}
        with open('/proc/meminfo', encoding='utf-8') as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 2 and parts[0].endswith(':'):
                    info[parts[0][:-1]] = int(parts[1])
        total = info.get('MemTotal') or 0
        avail = info.get('MemAvailable') or info.get('MemFree') or 0
        if total > 0:
            mem_pct = round(100.0 * (1.0 - (avail / total)), 2)
    except (OSError, ValueError):
        mem_pct = None

    return {
        'cpu_pct': None,  # optional; backend accepts null scalars
        'mem_pct': mem_pct,
        'load_avg': load_avg,
    }


def build_ingest_payload(
    *,
    agent_id: str = DEFAULT_AGENT_ID,
    hostname: str = DEFAULT_HOSTNAME,
    host_ip: str = DEFAULT_HOST_IP,
    role: str = DEFAULT_ROLE,
    wifi: dict | None = None,
    system: dict | None = None,
    ts: str | None = None,
) -> dict:
    """Build the register/ingest envelope with collectors.system + collectors.wifi."""
    wifi_block = enforce_wifi_budget(wifi if wifi is not None else empty_wifi_summary())
    payload = {
        'agent_id': agent_id,
        'hostname': hostname,
        'host_ip': host_ip,
        'role': role,
        'ts': ts or datetime.now(tz=timezone.utc).isoformat(),
        'agent_version': __version__,
        'collectors': {
            'system': system if system is not None else collect_system(),
            'wifi': wifi_block,
        },
    }
    # Whole-envelope soft check: wifi alone must stay ≤5 KB.
    wifi_bytes = len(json.dumps(wifi_block, separators=(',', ':'), default=str).encode('utf-8'))
    if wifi_bytes > WIFI_MAX_BYTES:
        payload['collectors']['wifi'] = empty_wifi_summary(reason='budget_exceeded')
    return payload


def registration_identity(
    *,
    agent_id: str = DEFAULT_AGENT_ID,
    hostname: str = DEFAULT_HOSTNAME,
    host_ip: str = DEFAULT_HOST_IP,
    role: str = DEFAULT_ROLE,
    tags: list | None = None,
) -> dict:
    return {
        'agent_id': agent_id,
        'hostname': hostname,
        'host_ip': host_ip,
        'role': role,
        'tags': list(tags if tags is not None else DEFAULT_TAGS),
    }


def _load_config(path: str) -> dict:
    import yaml

    with open(path, encoding='utf-8') as fh:
        return yaml.safe_load(fh) or {}


def run(config_path: str) -> None:
    cfg = _load_config(config_path)

    level = getattr(logging, str(cfg.get('log_level', 'INFO')).upper(), logging.INFO)
    logging.basicConfig(level=level, format='%(asctime)s %(name)s %(levelname)s %(message)s')

    identity = registration_identity(
        agent_id=cfg.get('agent_id', DEFAULT_AGENT_ID),
        hostname=cfg.get('hostname', DEFAULT_HOSTNAME),
        host_ip=cfg.get('host_ip', DEFAULT_HOST_IP),
        role=cfg.get('role', DEFAULT_ROLE),
        tags=cfg.get('tags', DEFAULT_TAGS),
    )
    api_url = cfg['api_url']
    # Prefer env SENSOR_API_KEY; never log the value — header name is X-Sensor-Key.
    api_key = cfg.get('api_key') or os.environ.get('SENSOR_API_KEY', '')
    interval = int(cfg.get('interval', DEFAULT_INTERVAL))
    summary_path = cfg.get('summary_path') or os.environ.get('WIFI_SUMMARY_PATH', '')

    reporter = Reporter(api_url, api_key)
    reporter.register(
        identity['agent_id'],
        identity['hostname'],
        identity['host_ip'],
        identity['role'],
        identity['tags'],
        version=__version__,
    )

    stop = False

    def _handle_signal(sig, _frame):
        nonlocal stop
        log.info('[wifi] signal %d — stopping', sig)
        stop = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    log.info(
        '[wifi] starting — agent_id=%s host=%s interval=%ds summary_path=%s '
        '(live capture / t470s-rf-mcp deferred; never operating %s)',
        identity['agent_id'], identity['host_ip'], interval,
        summary_path or '(none)', UPLINK_IFACE,
    )

    cycle = 0
    while not stop:
        cycle += 1
        reporter.maybe_reregister(cycle)

        raw = load_summary_file(summary_path)
        wifi = enforce_wifi_budget(raw) if raw else empty_wifi_summary()
        payload = build_ingest_payload(
            agent_id=identity['agent_id'],
            hostname=identity['hostname'],
            host_ip=identity['host_ip'],
            role=identity['role'],
            wifi=wifi,
        )
        ok = reporter.ingest(payload)
        wifi_bytes = len(
            json.dumps(payload['collectors']['wifi'], separators=(',', ':'), default=str).encode('utf-8')
        )
        log.info(
            '[wifi] cycle %d: wifi=%dB aps=%d events=%d POST %s',
            cycle,
            wifi_bytes,
            len(payload['collectors']['wifi'].get('aps') or []),
            len(payload['collectors']['wifi'].get('events') or []),
            'ok' if ok else 'FAILED',
        )

        for _ in range(interval):
            if stop:
                break
            time.sleep(1)

    log.info('[wifi] stopped')


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description='SentinelZero passive Wi-Fi / RF summary sensor')
    parser.add_argument('--config', '-c', default=None)
    args = parser.parse_args()

    search = [
        args.config,
        '/etc/sentinel-wifi/config.yaml',
        str(Path(__file__).parent / 'config-wifi.yaml'),
    ]
    config_path = next((p for p in search if p and os.path.exists(p)), None)
    if not config_path:
        print('ERROR: no config found. Checked:', [p for p in search if p])
        raise SystemExit(1)
    run(config_path)


if __name__ == '__main__':
    main()
