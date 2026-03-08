"""Deterministic network health monitoring service."""
import socket
import threading
import time
from datetime import datetime
from typing import Iterable, Optional

import requests

LOOPBACKS = [
    {"name": "LAN Gateway", "ip": "172.16.0.1", "description": "Network gateway health", "interface": "enp6s18"},
    {"name": "LAN Sentinel", "ip": "172.16.0.254", "description": "LAN health probe (172.16.0.0/22)", "interface": "dummy0"},
    {"name": "Home Sentinel", "ip": "192.168.68.254", "description": "Home network probe via dummy interface", "interface": "dummy0"},
    {"name": "Localhost", "ip": "127.0.0.1", "description": "SentinelZero health probe", "interface": "lo"},
]

SERVICES = [
    {"name": "Primary DNS", "ip": "172.16.0.13", "port": 53, "type": "dns", "query": "google.com"},
    {"name": "Cloudflare DNS", "ip": "1.1.1.1", "port": 53, "type": "dns", "query": "google.com"},
    {"name": "Google DNS", "ip": "8.8.8.8", "port": 53, "type": "dns", "query": "google.com"},
    {"name": "Internet Test", "ip": "8.8.8.8", "port": 53, "type": "ping", "path": "/"},
    {"name": "Network Gateway", "ip": "172.16.0.1", "port": 80, "type": "ping", "path": "/"},
]

INFRASTRUCTURE = [
    {"name": "Network Gateway", "ip": "172.16.0.1", "type": "ping"},
    {"name": "Primary DNS", "ip": "172.16.0.13", "port": 53, "type": "dns", "query": "google.com"},
    {"name": "Cloudflare DNS", "ip": "1.1.1.1", "port": 53, "type": "dns", "query": "google.com"},
    {"name": "Google DNS", "ip": "8.8.8.8", "port": 53, "type": "dns", "query": "google.com"},
    {"name": "Internet Connectivity", "ip": "8.8.8.8", "type": "ping"},
    {"name": "Proxmox Node (proxBig.prox)", "ip": "172.16.0.10", "type": "ping"},
    {"name": "Proxmox Cluster (yin.prox)", "ip": "172.16.0.11", "type": "ping"},
    {"name": "Proxmox Cluster (yang.prox)", "ip": "172.16.0.12", "type": "ping"},
    {"name": "Homebridge", "ip": "192.168.68.79", "type": "ping"},
    {"name": "Ubuntu Server", "ip": "192.168.71.30", "type": "ping"},
    {"name": "Home Net DNS", "ip": "192.168.71.25", "type": "ping"},
    {"name": "Backup Home DNS", "ip": "192.168.71.30", "type": "ping"},
    {"name": "Code Server (code-server.prox)", "ip": "172.16.0.106", "type": "ping"},
    {"name": "VPN to Home Network", "ip": "192.168.71.40", "type": "ping"},
    {"name": "Main Lab Windows VM (winvm.prox)", "ip": "172.16.0.100", "type": "ping"},
]

DEFAULT_CONNECTIVITY_PORTS = (22, 80, 443, 53, 3389, 8080, 8443)
DEFAULT_MONITOR_INTERVAL = 30


class NetworkProbe:
    """Small probe interface for network checks."""

    def ping(self, host: str, timeout: float = 0.5, ports: Optional[Iterable[int]] = None):
        started = time.perf_counter()
        if host == '127.0.0.1':
            return {
                'success': True,
                'method': 'localhost',
                'response_time': 0.0,
                'error': None,
            }

        probe_ports = tuple(ports or DEFAULT_CONNECTIVITY_PORTS)
        last_error = 'no connectivity'
        for port in probe_ports:
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    return {
                        'success': True,
                        'method': f'tcp:{port}',
                        'response_time': round((time.perf_counter() - started) * 1000, 2),
                        'error': None,
                    }
            except OSError as exc:
                last_error = str(exc)

        return {
            'success': False,
            'method': 'tcp',
            'response_time': None,
            'error': last_error,
        }

    def tcp_connect(self, host: str, port: int, timeout: float = 1.0):
        started = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return {
                    'success': True,
                    'method': f'tcp:{port}',
                    'response_time': round((time.perf_counter() - started) * 1000, 2),
                    'error': None,
                }
        except OSError as exc:
            return {
                'success': False,
                'method': f'tcp:{port}',
                'response_time': None,
                'error': str(exc),
            }

    def resolve(self, host: str):
        try:
            return socket.gethostbyname(host)
        except OSError:
            return None

    def http_check(self, host: str, port: int, path: str = '/', use_https: bool = False, timeout: float = 2.0):
        scheme = 'https' if use_https else 'http'
        url = f'{scheme}://{host}:{port}{path}'
        started = time.perf_counter()
        try:
            response = requests.get(url, timeout=timeout, verify=False)
            return {
                'success': response.status_code < 500,
                'status_code': response.status_code,
                'response_time': round((time.perf_counter() - started) * 1000, 2),
                'error': None,
            }
        except requests.RequestException as exc:
            return {
                'success': False,
                'status_code': None,
                'response_time': None,
                'error': str(exc),
            }


class WhatsUpMonitor:
    """Collect and emit lab-health snapshots."""

    def __init__(self, probe=None, loopbacks=None, services=None, infrastructure=None):
        self.probe = probe or NetworkProbe()
        self.loopbacks = list(LOOPBACKS if loopbacks is None else loopbacks)
        self.services = list(SERVICES if services is None else services)
        self.infrastructure = list(INFRASTRUCTURE if infrastructure is None else infrastructure)
        self._last_snapshot = None
        self._lock = threading.Lock()

    def collect_snapshot(self):
        loopbacks = self._collect_loopbacks()
        services = self._collect_services()
        infrastructure = self._collect_infrastructure()
        snapshot = self._build_snapshot(loopbacks, services, infrastructure)
        with self._lock:
            self._last_snapshot = snapshot
        return snapshot

    def get_snapshot(self, refresh=False):
        with self._lock:
            if self._last_snapshot is not None and not refresh:
                return self._last_snapshot
        return self.collect_snapshot()

    def emit_snapshot(self, socketio, snapshot=None):
        payload = snapshot or self.get_snapshot(refresh=True)
        socketio.emit('whats_up.snapshot', payload)
        socketio.emit('whats_up_update', payload)
        socketio.emit('health_update', payload)
        return payload

    def _collect_loopbacks(self):
        results = []
        for loopback in self.loopbacks:
            probe_result = self.probe.ping(loopback['ip'], timeout=0.5)
            results.append({
                'name': loopback['name'],
                'ip': loopback['ip'],
                'description': loopback.get('description', ''),
                'interface': loopback.get('interface', 'unknown'),
                'status': 'up' if probe_result['success'] else 'down',
                'response_time': probe_result.get('response_time'),
                'method': probe_result.get('method', 'unknown'),
                'error': None if probe_result['success'] else probe_result.get('error'),
                'checked_at': datetime.utcnow().isoformat(),
            })
        return results

    def _collect_services(self):
        results = []
        for service in self.services:
            target_host = service.get('domain') or service['ip']
            target_ip = self.probe.resolve(target_host) if service.get('domain') else service.get('ip')
            port = service.get('port', 80)
            service_type = service.get('type', 'ping')
            checked_at = datetime.utcnow().isoformat()

            dns_info = {
                'success': target_ip is not None,
                'ip': target_ip,
                'error': None if target_ip is not None else 'DNS resolution failed',
            }

            if target_ip is None and not service.get('domain'):
                dns_info = {'success': True, 'ip': target_host, 'error': None}
                target_ip = target_host

            ping_info = self.probe.ping(target_ip, timeout=0.5, ports=[port] if port else None) if target_ip else {
                'success': False,
                'method': 'unresolved',
                'response_time': None,
                'error': 'DNS resolution failed',
            }

            if target_ip and service_type in ('http', 'https'):
                service_info = self.probe.http_check(
                    target_host,
                    port,
                    path=service.get('path', '/'),
                    use_https=(service_type == 'https'),
                    timeout=2.0,
                )
            elif target_ip:
                service_info = self.probe.tcp_connect(target_ip, port, timeout=1.0)
            else:
                service_info = {
                    'success': False,
                    'method': f'tcp:{port}',
                    'response_time': None,
                    'error': 'DNS resolution failed',
                }

            overall_success = dns_info['success'] and service_info['success']
            results.append({
                'name': service['name'],
                'domain': service.get('domain'),
                'ip': service.get('ip'),
                'port': port,
                'type': service_type,
                'path': service.get('path', '/'),
                'checked_at': checked_at,
                'dns': dns_info,
                'ping': {
                    'success': ping_info['success'],
                    'ip': target_ip,
                    'method': ping_info.get('method'),
                    'response_time_ms': ping_info.get('response_time'),
                    'attempts': 1,
                    'error': None if ping_info['success'] else ping_info.get('error'),
                },
                'service': service_info,
                'status': 'up' if overall_success else 'down',
                'overall_status': 'up' if overall_success else 'down',
            })
        return results

    def _collect_infrastructure(self):
        results = []
        for infra in self.infrastructure:
            port = infra.get('port')
            infra_type = infra.get('type', 'ping')
            checked_at = datetime.utcnow().isoformat()

            if infra_type in ('http', 'https') and port:
                probe_result = self.probe.http_check(
                    infra['ip'],
                    port,
                    path=infra.get('path', '/'),
                    use_https=(infra_type == 'https'),
                    timeout=2.0,
                )
            elif port:
                probe_result = self.probe.tcp_connect(infra['ip'], port, timeout=1.0)
            else:
                probe_result = self.probe.ping(infra['ip'], timeout=0.5)

            results.append({
                'name': infra['name'],
                'ip': infra['ip'],
                'port': port,
                'type': infra_type,
                'status': 'up' if probe_result['success'] else 'down',
                'error': None if probe_result['success'] else probe_result.get('error'),
                'response_time': probe_result.get('response_time'),
                'method': probe_result.get('method', infra_type),
                'checked_at': checked_at,
            })
        return results

    @staticmethod
    def _build_snapshot(loopbacks, services, infrastructure):
        all_items = list(loopbacks) + list(services) + list(infrastructure)
        total_items = len(all_items)
        up_items = sum(1 for item in all_items if item.get('status') == 'up' or item.get('overall_status') == 'up')
        health_percentage = round((up_items / total_items) * 100, 1) if total_items else 0.0
        if health_percentage >= 80:
            overall_status = 'healthy'
        elif health_percentage >= 50:
            overall_status = 'degraded'
        elif total_items:
            overall_status = 'critical'
        else:
            overall_status = 'unknown'

        return {
            'overall_status': overall_status,
            'health_percentage': health_percentage,
            'total_items': total_items,
            'up_items': up_items,
            'down_items': total_items - up_items,
            'total_up': up_items,
            'total_checks': total_items,
            'timestamp': datetime.utcnow().isoformat(),
            'last_update': datetime.utcnow().isoformat(),
            'layers': {
                'loopbacks': {'total': len(loopbacks), 'up': sum(1 for item in loopbacks if item['status'] == 'up')},
                'services': {'total': len(services), 'up': sum(1 for item in services if item['overall_status'] == 'up')},
                'infrastructure': {'total': len(infrastructure), 'up': sum(1 for item in infrastructure if item['status'] == 'up')},
            },
            'categories': {
                'loopbacks': {
                    'total': len(loopbacks),
                    'up': sum(1 for item in loopbacks if item['status'] == 'up'),
                    'items': loopbacks,
                },
                'services': {
                    'total': len(services),
                    'up': sum(1 for item in services if item['overall_status'] == 'up'),
                    'items': services,
                },
                'infrastructure': {
                    'total': len(infrastructure),
                    'up': sum(1 for item in infrastructure if item['status'] == 'up'),
                    'items': infrastructure,
                },
            },
            'loopbacks': loopbacks,
            'services': services,
            'infrastructure': infrastructure,
        }


def whats_up_monitor(socketio, app, interval=DEFAULT_MONITOR_INTERVAL, stop_event=None):
    """Background loop for lab-health snapshots."""
    print("[INFO] What's Up monitoring started")
    monitor = app.extensions.get('whats_up_monitor')
    if monitor is None:
        monitor = DEFAULT_MONITOR
        app.extensions['whats_up_monitor'] = monitor

    while True:
        try:
            with app.app_context():
                snapshot = monitor.collect_snapshot()
                monitor.emit_snapshot(socketio, snapshot)
                print(
                    f"[INFO] What's Up Health: {snapshot['health_percentage']:.1f}% "
                    f"({snapshot['up_items']}/{snapshot['total_items']}) - {snapshot['overall_status']}"
                )
        except Exception as exc:
            print(f"[ERROR] What's Up monitoring error: {exc}")

        if stop_event is not None and stop_event.wait(interval):
            break
        if stop_event is None:
            time.sleep(interval)


def get_monitor():
    return DEFAULT_MONITOR


def get_loopbacks_data(refresh=True):
    snapshot = DEFAULT_MONITOR.get_snapshot(refresh=refresh)
    return snapshot['categories']['loopbacks']['items']


def get_services_data(refresh=True):
    snapshot = DEFAULT_MONITOR.get_snapshot(refresh=refresh)
    return snapshot['categories']['services']['items']


def get_infrastructure_data(refresh=True):
    snapshot = DEFAULT_MONITOR.get_snapshot(refresh=refresh)
    return snapshot['categories']['infrastructure']['items']


def get_summary_data(refresh=True):
    return DEFAULT_MONITOR.get_snapshot(refresh=refresh)


DEFAULT_MONITOR = WhatsUpMonitor()
