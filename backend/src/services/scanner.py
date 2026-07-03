"""
Network scanning service
"""
import os
import re
import time
import json
import queue
import threading
import subprocess
import shutil
from collections import deque
from datetime import datetime
import xml.etree.ElementTree as ET

from ..models import Scan
from ..config.database import db
from .insights import generate_and_store_insights


def _target_is_on_link(target_network):
    """True if the target CIDR is directly reachable (ARP-capable) on a local interface,
    False if it must be routed through a gateway.

    ARP host-discovery (-PR) and ICMP address-mask (-PM) only work on the local L2
    segment; across a router they elicit nothing and just burn a probe round per host.
    This host has a single real NIC on the Lab net (172.16.0.0/22) and reaches the Home
    net (192.168.68.0/22) routed via the gateway, so Home scans must drop those probes.
    """
    import ipaddress
    try:
        target = ipaddress.ip_network(target_network, strict=False)
    except Exception:
        return True  # unknown target -> preserve legacy ARP behavior
    try:
        import socket
        import psutil
        for addrs in psutil.net_if_addrs().values():
            for a in addrs:
                if a.family != socket.AF_INET or not a.netmask:
                    continue
                try:
                    iface_net = ipaddress.ip_network(f"{a.address}/{a.netmask}", strict=False)
                except Exception:
                    continue
                if iface_net.prefixlen == 32:
                    continue  # /32 service VIPs (e.g. dummy0) are not a real L2 segment
                if target.subnet_of(iface_net):
                    return True
        return False
    except Exception:
        # psutil unavailable: fall back to known topology (Home is routed, Lab on-link).
        try:
            from .scan_scope import is_home_network
            return not is_home_network(target_network)
        except Exception:
            return True


def _host_discovery_probes(on_link):
    """Host-discovery probe set tuned to whether the target is on-link or routed."""
    if on_link:
        # Local segment: ARP is fastest/most reliable; ICMP echo/timestamp/netmask back it up.
        return ['-PE', '-PP', '-PM', '-PR', '-PS22,80,443,3389,8080', '-PA80,443']
    # Routed: ARP (-PR) and address-mask (-PM) can't cross the gateway. Lean on routable
    # ICMP echo/timestamp plus TCP SYN/ACK probes that actually traverse the firewall.
    return ['-PE', '-PP', '-PS22,80,443,3389,8080', '-PA80,443']


def _parse_timeout_env(name, default):
    raw_value = os.environ.get(name, str(default))
    try:
        timeout_value = int(raw_value)
    except (TypeError, ValueError):
        timeout_value = default
    return max(timeout_value, 5)


def _get_scan_timeout_seconds(scan_type_normalized=None, target_network=None, on_link=True):
    """Watchdog budget: routed/home and IoT scans need more time than on-link lab scans."""
    from .scan_scope import is_home_network

    if scan_type_normalized == 'vuln scripts':
        # Vuln scripts run NSE against every open service; allow much longer than port sweeps.
        return _parse_timeout_env('SCAN_TIMEOUT_VULN_SECONDS', 10800)

    net = target_network or ''
    home = is_home_network(net) or not on_link
    if scan_type_normalized == 'iot scan' and home:
        return _parse_timeout_env('SCAN_TIMEOUT_IOT_HOME_SECONDS', 7200)
    if home:
        return _parse_timeout_env('SCAN_TIMEOUT_HOME_SECONDS', 5400)
    return _parse_timeout_env('SCAN_TIMEOUT_SECONDS', 1800)


# Port sweep used by Full TCP and as vuln-script fallback when no recent scan exists.
_FULL_TCP_PORT_SPEC = (
    'T:1-2048,3306,3389,5000,5353,5432,8006,8080,8443,8581,9000,1194,51820'
)


def _get_open_ports_from_recent_full_tcp(target_network):
    """Return sorted open TCP ports from the latest completed Full TCP scan on this network."""
    from .scan_scope import normalize_cidr

    net = normalize_cidr(target_network) or target_network
    recent = (
        Scan.query
        .filter(Scan.scan_type.ilike('%full tcp%'))
        .filter(Scan.status == 'complete')
        .filter(Scan.target_network == net)
        .order_by(Scan.completed_at.desc())
        .first()
    )
    if not recent or not recent.hosts_json:
        return None
    try:
        hosts = json.loads(recent.hosts_json)
    except (TypeError, ValueError):
        return None
    ports = set()
    for host in hosts:
        for port in host.get('ports', []):
            proto = str(port.get('protocol') or 'tcp').lower()
            if proto not in ('tcp', ''):
                continue
            try:
                ports.add(int(port['port']))
            except (TypeError, ValueError, KeyError):
                continue
    return sorted(ports) if ports else None


def _vuln_scripts_port_spec(target_network):
    """Pick ports for vuln-script scans: known opens from Full TCP, else the standard sweep."""
    known_ports = _get_open_ports_from_recent_full_tcp(target_network)
    if known_ports:
        return ','.join(str(p) for p in known_ports), f'{len(known_ports)} open ports from latest Full TCP scan'
    return _FULL_TCP_PORT_SPEC, 'standard Full TCP port range (no recent Full TCP scan for this network)'


def _should_run_pre_discovery(scan_type_normalized, target_network, on_link, pre_discovery_requested):
    """Pre-discover live hosts before heavy port scans on routed or large subnets."""
    if scan_type_normalized in ('discovery scan',):
        return False
    if pre_discovery_requested:
        return True
    if scan_type_normalized not in ('iot scan', 'full tcp', 'vuln scripts'):
        return False
    if not on_link:
        return True
    try:
        import ipaddress
        net = ipaddress.ip_network(target_network, strict=False)
        return net.num_addresses > 512
    except Exception:
        return False


def _get_xml_parse_retry_policy():
    raw_attempts = os.environ.get('SCAN_XML_PARSE_RETRIES', '3')
    raw_delay = os.environ.get('SCAN_XML_PARSE_RETRY_DELAY_SECONDS', '1')
    try:
        attempts = int(raw_attempts)
    except (TypeError, ValueError):
        attempts = 3
    try:
        delay = float(raw_delay)
    except (TypeError, ValueError):
        delay = 1.0
    return max(attempts, 1), max(delay, 0.0)


def _is_reportable_port_state(protocol, state):
    """Scanner keeps TCP strict while preserving IoT-relevant UDP open|filtered."""
    proto = str(protocol or '').lower()
    state_value = str(state or '').lower()
    return state_value == 'open' or (proto == 'udp' and state_value == 'open|filtered')


def _terminate_process(proc):
    try:
        proc.terminate()
    except Exception:
        pass
    try:
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _stream_process_output(proc, output_queue):
    try:
        stdout = proc.stdout
        if hasattr(stdout, 'readline'):
            iterator = iter(stdout.readline, '')
        else:
            iterator = iter(stdout)
        for line in iterator:
            output_queue.put(line)
    except Exception:
        pass
    finally:
        output_queue.put(None)

def should_include_vulnerability(vuln_id, score, has_exploit):
    """Filter out false positives and low-value vulnerabilities"""
    
    # Skip very low scores unless they have active exploits
    if score < 4.0 and not has_exploit:
        return False
    
    # Skip common false positives
    false_positive_patterns = [
        'PACKETSTORM:140261',  # Common SSH false positive
        'CVE-2025-32728',      # Future CVEs (likely false)
        'CVE-2025-26465',      # Future CVEs (likely false)
    ]
    
    for pattern in false_positive_patterns:
        if pattern in vuln_id:
            return False
    
    # Skip GitHub exploit entries with very generic IDs (often false positives)
    if len(vuln_id) > 30 and '-' in vuln_id and vuln_id.count('-') >= 4:
        return False
    
    return True

def parse_vulners_output(host_ip, cpe, output):
    """Parse vulnerability scanner output"""
    vulns = []
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    for line in lines:
        # Example: CVE-2017-14493 9.8 https://vulners.com/cve/CVE-2017-14493
        m = re.match(r'^([A-Z0-9\-:]+)\s+(\d+\.\d+)\s+(https?://\S+)(.*)$', line)
        if m:
            id_ = m.group(1)
            score = float(m.group(2))
            url = m.group(3)
            rest = m.group(4)
            exploit = '*EXPLOIT*' in rest
            
            # Filter out false positives and low-quality vulnerabilities
            if should_include_vulnerability(id_, score, exploit):
                vulns.append({
                    'host': host_ip,
                    'cpe': cpe,
                    'id': id_,
                    'score': score,
                    'url': url,
                    'exploit': exploit
                })
    return vulns

def run_nmap_scan(scan_id, scan_type, security_settings=None, socketio=None, app=None, target_network='172.16.0.0/22', _priv_fallback=False, pre_discovery=False):
    """
    Run an nmap scan with the specified parameters
    
    Args:
        scan_type: Type of scan to run
        security_settings: Security configuration options
        socketio: SocketIO instance for real-time updates
        app: Flask app instance for database context
        target_network: Network range to scan (e.g., '172.16.0.0/22')
    """
    if security_settings is None:
        security_settings = {
            'vuln_scanning_enabled': True,
            'os_detection_enabled': True,
            'service_detection_enabled': True,
            'aggressive_scanning': False
        }
    
    with app.app_context():
        runtime = app.extensions['scan_runtime']
        scan = runtime.get_scan(scan_id)
        if not scan:
            raise LookupError(f'Scan {scan_id} not found')

        from ..services.scan_scope import normalize_cidr
        from ..config.database import db as _db

        net = normalize_cidr(target_network)
        if net:
            scan.target_network = net
            _db.session.commit()

        try:
            def emit_stage(status, message):
                try:
                    nonlocal scan
                    scan = runtime.set_state(
                        scan_id,
                        status,
                        message,
                        execution_mode='degraded' if _priv_fallback else 'normal',
                    )
                except Exception as db_error:
                    print(f"Database error in emit_progress: {db_error}")
                    db.session.rollback()

            on_link = _target_is_on_link(net or target_network)
            runtime.append_log(
                scan_id,
                f'Host discovery mode: {"on-link (ARP)" if on_link else "routed (TCP/ICMP, ARP skipped)"} '
                f'for {net or target_network}',
            )

            emit_stage('running', f'Started {scan_type} on {net or target_network}')
            msg = (
                f'Thread started for scan: {scan_type} target={net or target_network} '
                f'(scheduled={threading.current_thread().name.startswith("APScheduler")})'
            )
            runtime.append_log(scan_id, msg)
            print(msg)
            
            now = datetime.now().strftime('%Y-%m-%d_%H%M')
            # Normalize scan_type for robust matching
            scan_type_normalized = scan_type.strip().lower()
            try:
                print(f"[DEBUG] Normalized scan_type='{scan_type_normalized}' (original='{scan_type}')")
            except Exception:
                pass

            # Accept common aliases for discovery scans
            if scan_type_normalized in ('discovery', 'discover', 'host discovery'):
                scan_type_normalized = 'discovery scan'
            xml_path = f'scans/{scan_type_normalized.replace(" ", "_")}_{now}.xml'
            # Ensure scans directory exists to avoid silent file write issues
            try:
                os.makedirs(os.path.dirname(xml_path), exist_ok=True)
            except Exception as _e:
                print(f'[WARN] Could not ensure scans directory: {_e}')
            
            # Optional pre-discovery phase for heavy scans (not for explicit discovery scan)
            discovered_hosts = []
            use_pre_discovery = _should_run_pre_discovery(
                scan_type_normalized,
                net or target_network,
                on_link,
                pre_discovery,
            )
            if use_pre_discovery and not pre_discovery:
                runtime.append_log(
                    scan_id,
                    'Auto pre-discovery enabled (routed or large target for heavy scan type)',
                )
            if use_pre_discovery and scan_type_normalized not in ('discovery scan',):
                try:
                    emit_stage('running', 'Pre-discovery: enumerating live hosts...')
                    pre_xml = f'scans/pre_discovery_{now}.xml'
                    pre_cmd = [
                        'nmap', '-sn',
                        *_host_discovery_probes(on_link),
                        '-n', '--max-retries', '2', '-T4',
                        target_network, '-oX', pre_xml,
                    ]
                    runtime.append_log(scan_id, f'Pre-discovery command: {" ".join(pre_cmd)}')
                    pre_proc = subprocess.run(pre_cmd, capture_output=True, text=True)
                    if pre_proc.returncode == 0 and os.path.exists(pre_xml):
                        try:
                            pre_tree = ET.parse(pre_xml)
                            pre_root = pre_tree.getroot()
                            for host in pre_root.findall('host'):
                                status = host.find('status')
                                if status is not None and status.attrib.get('state') == 'up':
                                    addr = host.find('address[@addrtype="ipv4"]')
                                    if addr is not None:
                                        ip = addr.attrib.get('addr')
                                        if ip:
                                            discovered_hosts.append(ip)
                        except Exception as _e:
                            print(f'[WARN] Pre-discovery parse failed: {_e}')
                    if discovered_hosts:
                        emit_stage('running', f'Pre-discovery found {len(discovered_hosts)} hosts – targeting only live hosts')
                        runtime.append_log(scan_id, f'Pre-discovery found {len(discovered_hosts)} live hosts')
                    else:
                        emit_stage('running', 'Pre-discovery (ICMP/ARP) found no hosts — retrying with -Pn')
                        runtime.append_log(scan_id, 'Pre-discovery retry: -Pn -sn')
                        pre_cmd_pn = [
                            'nmap', '-sn', '-Pn',
                            '-PE', '-PP', '-PS22,80,443,3389,8080', '-PA80,443',
                            '-n', '--max-retries', '2', '-T4',
                            target_network, '-oX', pre_xml,
                        ]
                        pre_proc2 = subprocess.run(pre_cmd_pn, capture_output=True, text=True)
                        if pre_proc2.returncode == 0 and os.path.exists(pre_xml):
                            try:
                                pre_tree = ET.parse(pre_xml)
                                for host in pre_tree.getroot().findall('host'):
                                    status = host.find('status')
                                    if status is not None and status.attrib.get('state') == 'up':
                                        addr = host.find('address[@addrtype="ipv4"]')
                                        if addr is not None:
                                            ip = addr.attrib.get('addr')
                                            if ip:
                                                discovered_hosts.append(ip)
                            except Exception as _e2:
                                print(f'[WARN] Pre-discovery -Pn parse failed: {_e2}')
                        if discovered_hosts:
                            emit_stage(
                                'running',
                                f'Pre-discovery (-Pn) found {len(discovered_hosts)} hosts',
                            )
                        else:
                            emit_stage('running', 'Pre-discovery found no hosts (falling back to full range)')
                except Exception as _e:
                    print(f'[WARN] Pre-discovery step failed: {_e}')
            # Build nmap command (user-facing prior to privilege adjustments)
            # NOTE: We intentionally omit -Pn for discovery scans so nmap actually performs host discovery.
            # When pre-discovery yields a live host list, skip -Pn — probing 1024 addresses with -Pn is
            # what caused home IoT scans to stall in service detection until the watchdog fired.
            if scan_type_normalized == 'discovery scan':
                cmd = ['nmap', '-v', '-T4']  # no -Pn here; allow ARP/ICMP
            elif discovered_hosts:
                cmd = ['nmap', '-v', '-T4']
            else:
                cmd = ['nmap', '-v', '-T4', '-Pn']
            if scan_type_normalized == 'full tcp':
                # Balanced deep scan: broader ports + service/OS without full -p- (T2-class) sweep
                port_spec = _FULL_TCP_PORT_SPEC
                if _priv_fallback:
                    cmd += [
                        '-sT', '-p', port_spec, '--open',
                        '-T3', '--max-retries', '2', '--host-timeout', '8m',
                    ]
                else:
                    cmd += [
                        '-sS', '-p', port_spec, '--open',
                        '-T3', '--max-retries', '2', '--host-timeout', '8m',
                        '--min-rate', '150', '--max-rate', '600',
                    ]
            elif scan_type_normalized == 'iot scan':
                iot_ports = '53,67,68,80,443,1900,5353,554,8080'
                if _priv_fallback:
                    # Fallback removes UDP requirement (switch to TCP connect scan)
                    cmd += ['-sT', '-p', iot_ports]
                else:
                    cmd += ['-sU', '-p', iot_ports]
                # Routed home IoT: cap per-host work so -sV across the /22 cannot run for hours.
                if not on_link or discovered_hosts:
                    cmd += ['--max-retries', '2', '--host-timeout', '4m']
            elif scan_type_normalized == 'discovery scan':
                # Fast host discovery (-sn, no port scan). Probes adapt to on-link vs routed
                # below; ARP is used on-link only (needs privs), TCP/ICMP fallback when routed.
                cmd += ['-sn']  # host discovery only
                # Probe set adapts to on-link (ARP) vs routed (TCP/ICMP) targets
                cmd += _host_discovery_probes(on_link)
                cmd += ['-n']  # disable DNS for speed / consistency
                # Speed: reduce retries
                cmd += ['--max-retries', '1', '-T4']
            elif scan_type_normalized == 'vuln scripts':
                port_spec, port_source = _vuln_scripts_port_spec(net or target_network)
                runtime.append_log(scan_id, f'Vuln scan port list: {port_source}')
                vuln_scan_flags = [
                    '-p', port_spec, '--open',
                    '-T3', '--max-retries', '2', '--host-timeout', '15m',
                ]
                if _priv_fallback:
                    cmd += ['-sT', *vuln_scan_flags]
                else:
                    cmd += ['-sS', *vuln_scan_flags]
            else:
                runtime.fail_scan(scan_id, f'Unknown scan type: {scan_type}', error_code='unknown_scan_type')
                msg = f'Unknown scan type: {scan_type}'
                runtime.append_log(scan_id, msg)
                print(msg)
                return
            
            # Apply security settings
            # Discovery scan does not use OS/service/vuln phases to stay lightweight
            skip_os = (
                scan_type_normalized == 'iot scan'
                and not on_link
                and security_settings.get('os_detection_enabled')
            )
            if skip_os:
                runtime.append_log(
                    scan_id,
                    'Skipping OS detection for routed IoT scan (slow/unreliable across gateway)',
                )
            if (
                scan_type_normalized != 'discovery scan'
                and security_settings.get('os_detection_enabled')
                and not skip_os
            ):
                cmd.append('-O')
            if scan_type_normalized != 'discovery scan' and security_settings.get('service_detection_enabled'):
                cmd.append('-sV')
                if scan_type_normalized == 'full tcp':
                    cmd.extend(['--version-intensity', '5'])
                elif scan_type_normalized == 'iot scan':
                    cmd.extend(['--version-intensity', '3'])
            if scan_type_normalized == 'vuln scripts':
                # Only run vulnerability scripts for explicit vulnerability scans
                cmd.append('--script=vuln')
            elif scan_type_normalized not in ('discovery scan',) and security_settings.get('vuln_scanning_enabled'):
                # Use more targeted vulnerability scripts for regular scans
                cmd.append('--script=ssl-cert,ssl-enum-ciphers,http-title,ssh-hostkey')
            if scan_type_normalized != 'discovery scan' and security_settings.get('aggressive_scanning'):
                cmd.append('-A')
            
            # Target specification: if we have a discovered hosts list, enumerate them directly
            if discovered_hosts:
                cmd += discovered_hosts
            else:
                cmd += [target_network]
            cmd += ['-oX', xml_path]

            user_facing_cmd = list(cmd)
            exec_cmd = list(cmd)
            try:
                nmap_path = shutil.which('nmap') or 'nmap'
                exec_cmd[0] = nmap_path
            except Exception:
                pass
            try:
                is_root = (os.geteuid() == 0)
            except Exception:
                is_root = False
            needs_raw = any(flag in exec_cmd for flag in ('-sU', '-O', '-sS'))
            if needs_raw and not is_root and '--privileged' not in exec_cmd:
                exec_cmd.insert(1, '--privileged')

            msg = f'Nmap command: {" ".join(user_facing_cmd)}'
            runtime.append_log(scan_id, msg)
            if scan_type_normalized == 'discovery scan':
                runtime.append_log(scan_id, '[Discovery] Fast host discovery started (no port scan)')
            print(msg)
            if exec_cmd != user_facing_cmd:
                adj_msg = f'Executing adjusted command: {" ".join(exec_cmd)}'
                runtime.append_log(scan_id, adj_msg)
                print(adj_msg)
            
            # Execute nmap
            proc = subprocess.Popen(exec_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)
            
            # Store process ID for proper termination
            scan = runtime.update_scan(scan_id, process_id=proc.pid)
            
            msg = f'Nmap process started (PID: {proc.pid})...'
            runtime.append_log(scan_id, msg)
            print(msg)
            scan_timeout_seconds = _get_scan_timeout_seconds(
                scan_type_normalized,
                net or target_network,
                on_link,
            )
            runtime.append_log(scan_id, f'Watchdog timeout set to {scan_timeout_seconds}s')
            
            # Cleanup function for interrupted scans
            def cleanup_interrupted_scan():
                try:
                    # Mark scan as cancelled if it's still running
                    if scan.status in ['running', 'parsing', 'saving', 'postprocessing']:
                        scan.status = 'cancelled'
                        db.session.commit()
                        print(f'[DEBUG] Marked interrupted scan {scan_id} as cancelled')
                    
                    # Remove the XML file if it exists and is small (incomplete)
                    if os.path.exists(xml_path):
                        try:
                            file_size = os.path.getsize(xml_path)
                            if file_size < 1000:  # Less than 1KB indicates incomplete scan
                                os.remove(xml_path)
                                print(f'[DEBUG] Removed incomplete XML file: {xml_path}')
                        except Exception as e:
                            print(f'[WARN] Could not remove incomplete XML file: {e}')
                except Exception as e:
                    print(f'[WARN] Error during scan cleanup: {e}')
            
            timed_out = False
            started_at = time.monotonic()
            recent_lines = deque(maxlen=40)
            output_queue = queue.Queue()
            reader = threading.Thread(
                target=_stream_process_output,
                args=(proc, output_queue),
                daemon=True,
            )
            reader.start()

            while True:
                # Check for cancellation
                scan_check = db.session.get(Scan, scan_id)
                if scan_check and scan_check.status == 'cancelled':
                    try:
                        # Kill the process and its children
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)  # Give it 5 seconds to terminate gracefully
                        except subprocess.TimeoutExpired:
                            proc.kill()  # Force kill if it doesn't terminate
                        # Also try to kill any child processes
                        try:
                            import psutil
                            parent = psutil.Process(proc.pid)
                            children = parent.children(recursive=True)
                            for child in children:
                                child.terminate()
                            # Wait for children to terminate
                            psutil.wait_procs(children, timeout=5)
                            # Force kill any remaining children
                            for child in children:
                                if child.is_running():
                                    child.kill()
                        except Exception as e:
                            print(f'[WARN] Could not kill child processes: {e}')
                    except Exception as e:
                        print(f'[WARN] Could not kill process: {e}')
                    scan = runtime.cancel_scan(scan_id, 'Scan cancelled by user')
                    msg = 'Scan cancelled by user.'
                    runtime.append_log(scan_id, msg)
                    print(msg)
                    # Clean up incomplete scan files
                    try:
                        cleanup_interrupted_scan()
                    except Exception:
                        pass
                    return

                try:
                    line = output_queue.get(timeout=1.0)
                except queue.Empty:
                    if proc.poll() is not None:
                        break
                    if (time.monotonic() - started_at) > scan_timeout_seconds:
                        timed_out = True
                        _terminate_process(proc)
                        runtime.append_log(
                            scan_id,
                            f'Scan watchdog timeout reached after {scan_timeout_seconds}s',
                        )
                        break
                    continue

                if line is None:
                    break

                runtime.append_log(scan_id, line.rstrip())
                recent_lines.append(line.rstrip())
                
                match = re.search(r'About ([0-9.]+)% done', line)
                if match:
                    runtime.append_log(scan_id, f'nmap reported progress: {match.group(1)}%')
            
            proc.wait()
            if timed_out:
                runtime.fail_scan(
                    scan_id,
                    f'Scan timed out after {scan_timeout_seconds}s',
                    error_code='scan_timeout',
                )
                return
            # Handle failure before parsing
            if proc.returncode != 0:
                output_tail = '\n'.join(recent_lines)
                lowered = output_tail.lower()
                privilege_issue = any(k in lowered for k in ['requires root', 'cap_net_raw', 'dnet'])
                if privilege_issue and not _priv_fallback:
                    emit_stage('running', 'Raw socket access denied: retrying with TCP connect scan (degraded mode)...')
                    runtime.append_log(scan_id, 'Retrying in degraded mode: using TCP connect scan instead of SYN scan')
                    degraded_security = dict(security_settings or {})
                    degraded_security['os_detection_enabled'] = False
                    try:
                        run_nmap_scan(scan_id, scan_type, degraded_security, socketio, app, target_network, _priv_fallback=True)
                    except Exception as e:
                        runtime.fail_scan(scan_id, f'Fallback failed: {e}', error_code='degraded_retry_failed')
                    return
                guidance = ''
                if privilege_issue:
                    guidance = ' (Hint: grant CAP_NET_RAW/CAP_NET_ADMIN to nmap or run with sudo)'
                runtime.fail_scan(
                    scan_id,
                    f'nmap exited with code {proc.returncode}{guidance}',
                    error_code='nmap_exit_code',
                )
                runtime.append_log(scan_id, '--- Nmap last output (truncated) ---')
                for l in list(recent_lines)[-10:]:
                    runtime.append_log(scan_id, l)
                print(f'[ERROR] nmap failed (code {proc.returncode}). Last lines:\n{output_tail}')
                return

            # Validate XML output before parsing
            for i in range(5):
                if os.path.exists(xml_path) and os.path.getsize(xml_path) > 100:
                    break
                time.sleep(1)
            if not os.path.exists(xml_path) or os.path.getsize(xml_path) < 100:
                runtime.fail_scan(scan_id, 'XML file not found or too small (no results)', error_code='missing_xml')
                return

            emit_stage('parsing', 'Parsing scan results...')
            
            # Parse XML results
            emit_stage('parsing', 'Parsing XML results...')
            hosts = []
            vulns = []
            
            try:
                parse_attempts, parse_delay = _get_xml_parse_retry_policy()
                tree = None
                parse_error = None
                for attempt in range(1, parse_attempts + 1):
                    try:
                        tree = ET.parse(xml_path)
                        parse_error = None
                        break
                    except ET.ParseError as e:
                        parse_error = e
                        if attempt < parse_attempts:
                            runtime.append_log(
                                scan_id,
                                f'XML parse retry {attempt}/{parse_attempts - 1} after error: {e}',
                            )
                            time.sleep(parse_delay)
                if parse_error is not None:
                    raise parse_error
                root = tree.getroot()
                total_open_ports = 0
                for host in root.findall('host'):
                    status = host.find('status')
                    if status is None or status.attrib.get('state') != 'up':
                        continue
                    host_obj = {}
                    addr = host.find('address[@addrtype="ipv4"]')
                    if addr is not None:
                        host_obj['ip'] = addr.attrib.get('addr')
                    # Hostnames
                    hostnames_el = host.find('hostnames')
                    if hostnames_el is not None:
                        host_obj['hostnames'] = [hn.attrib.get('name') for hn in hostnames_el.findall('hostname') if hn.attrib.get('name')]
                    # MAC / vendor (if layer2 present)
                    mac_addr = host.find('address[@addrtype="mac"]')
                    if mac_addr is not None:
                        host_obj['mac'] = mac_addr.attrib.get('addr')
                        if mac_addr.attrib.get('vendor'):
                            host_obj['vendor'] = mac_addr.attrib.get('vendor')
                    # OS detection (simplified: first osmatch)
                    os_el = host.find('os')
                    if os_el is not None:
                        osmatch = os_el.find('osmatch')
                        if osmatch is not None:
                            host_obj['os'] = {
                                'name': osmatch.attrib.get('name'),
                                'accuracy': osmatch.attrib.get('accuracy')
                            }
                    # Uptime
                    uptime_el = host.find('uptime')
                    if uptime_el is not None:
                        host_obj['uptime'] = {
                            'seconds': int(uptime_el.attrib.get('seconds', '0') or 0),
                            'lastboot': uptime_el.attrib.get('lastboot')
                        }
                    # Distance
                    distance_el = host.find('distance')
                    if distance_el is not None and distance_el.attrib.get('value'):
                        host_obj['distance'] = int(distance_el.attrib.get('value'))
                    # Ports
                    ports_block = host.find('ports')
                    open_ports = []
                    if ports_block is not None:
                        for port_el in ports_block.findall('port'):
                            state_el = port_el.find('state')
                            if state_el is None:
                                continue
                            state_value = state_el.attrib.get('state')
                            proto = port_el.attrib.get('protocol')
                            if not _is_reportable_port_state(proto, state_value):
                                continue
                            portid = port_el.attrib.get('portid')
                            service_el = port_el.find('service')
                            service_name = service_el.attrib.get('name') if service_el is not None else None
                            product = service_el.attrib.get('product') if service_el is not None and service_el.attrib.get('product') else None
                            version = service_el.attrib.get('version') if service_el is not None and service_el.attrib.get('version') else None
                            extrainfo = (
                                service_el.attrib.get('extrainfo')
                                if service_el is not None and service_el.attrib.get('extrainfo')
                                else None
                            )
                            try:
                                p_int = int(portid)
                            except Exception:
                                p_int = None
                            
                            # Use common port mapping for better service identification
                            from ..utils.port_mapping import get_service_name
                            final_service_name = get_service_name(p_int or int(portid) if portid.isdigit() else 0, service_name)
                            
                            port_entry = {
                                'port': p_int or portid,
                                'protocol': proto,
                                'service': final_service_name,
                                'product': product,
                                'version': version,
                            }
                            if extrainfo:
                                port_entry['extrainfo'] = extrainfo
                            open_ports.append(port_entry)

                            for script_el in port_el.findall('script'):
                                script_id = script_el.attrib.get('id', '')
                                if 'vuln' not in script_id:
                                    continue
                                if script_id == 'vulners' and script_el.attrib.get('output'):
                                    host_ip = host_obj.get('ip')
                                    cpe = None
                                    cpe_match = re.search(
                                        r'(cpe:/[\w:.-]+)', script_el.attrib['output'],
                                    )
                                    if cpe_match:
                                        cpe = cpe_match.group(1)
                                    vulns.extend(
                                        parse_vulners_output(
                                            host_ip, cpe, script_el.attrib['output'],
                                        )
                                    )
                                else:
                                    vulns.append({
                                        'id': script_id,
                                        'output': script_el.attrib.get('output', ''),
                                        'host': host_obj.get('ip'),
                                        'port': p_int or portid,
                                        'protocol': proto,
                                    })
                    if open_ports:
                        open_ports.sort(key=lambda x: (x.get('port') or 0, x.get('protocol') or ''))
                        total_open_ports += len(open_ports)
                        host_obj['ports'] = open_ports

                    host_ip = host_obj.get('ip')
                    if host_ip:
                        for script_el in host.findall('.//script'):
                            script_id = script_el.attrib.get('id', '')
                            if 'vuln' not in script_id:
                                continue
                            if script_id == 'vulners' and script_el.attrib.get('output'):
                                cpe = None
                                cpe_match = re.search(
                                    r'(cpe:/[\w:.-]+)', script_el.attrib['output'],
                                )
                                if cpe_match:
                                    cpe = cpe_match.group(1)
                                vulns.extend(
                                    parse_vulners_output(
                                        host_ip, cpe, script_el.attrib['output'],
                                    )
                                )
                            elif script_id not in {v.get('id') for v in vulns if v.get('host') == host_ip}:
                                vulns.append({
                                    'id': script_id,
                                    'output': script_el.attrib.get('output', ''),
                                    'host': host_ip,
                                    'port': None,
                                    'protocol': None,
                                })

                    hosts.append(host_obj)
                # Update aggregate port counts on scan
                try:
                    scan.total_ports = total_open_ports
                    scan.open_ports = total_open_ports
                except Exception:
                    pass
                # If discovery scan, filter out network/broadcast addresses that can appear as 'up' when -Pn was previously used
                if scan_type_normalized == 'discovery scan':
                    try:
                        import ipaddress as _ip
                        net = _ip.ip_network(target_network, strict=False)
                        filtered = []
                        for h in hosts:
                            ip = h.get('ip')
                            try:
                                ip_obj = _ip.ip_address(ip)
                                if ip_obj == net.network_address or ip_obj == net.broadcast_address:
                                    continue
                            except Exception:
                                pass
                            filtered.append(h)
                        if len(filtered) != len(hosts):
                            print(f"[DEBUG] Discovery filtering removed {len(hosts)-len(filtered)} network/broadcast entries")
                        hosts = filtered
                    except Exception as _e:
                        print(f"[WARN] Discovery filtering failed: {_e}")
                # Update host counters (especially important for discovery scan accuracy)
                try:
                    scan.total_hosts = len(hosts)
                    scan.hosts_up = len(hosts)
                    db.session.commit()
                except Exception as _e:
                    print(f'[WARN] Failed updating host counters: {_e}')
                
                msg = f'Parsed {len(hosts)} hosts, {len(vulns)} vulns.'
                runtime.append_log(scan_id, msg)
                print(msg)
                
            except Exception as e:
                runtime.fail_scan(scan_id, f'XML parse error: {str(e)}', error_code='xml_parse_error')
                return
            
            # Save results
            emit_stage('saving', 'Saving scan results to database...')
            scan.hosts_json = json.dumps(hosts)
            scan.vulns_json = json.dumps(vulns)
            scan.raw_xml_path = xml_path
            # Do not mark complete until after insights
            db.session.commit()
            
            # Generate insights unless discovery-only
            if scan_type_normalized == 'discovery scan':
                emit_stage('postprocessing', 'Discovery complete – skipping insights...')
                try:
                    from . import scan_analysis
                    scan_analysis.record_insights_generation(
                        scan_id,
                        count=0,
                        skipped_reason='Discovery scan — insights not generated',
                    )
                except Exception:
                    pass
            else:
                emit_stage('postprocessing', 'Generating insights...')
                try:
                    insights = generate_and_store_insights(scan_id)
                    print(f'Generated {len(insights) if insights else 0} insights for scan {scan_id}')
                    # Spawn verdict agent in background — never blocks scan completion
                    try:
                        from . import agent_service
                        threading.Thread(
                            target=agent_service.run_ai_pipeline,
                            args=(scan_id, app, socketio),
                            daemon=True,
                        ).start()
                        print(f'Spawned AI pipeline thread for scan {scan_id}')
                    except Exception as _agent_err:
                        print(f'Failed to spawn verdict agent: {_agent_err}')
                except Exception as e:
                    print(f'Error generating insights: {str(e)}')
            # Finalize
            scan = runtime.complete_scan(scan_id, 'Scan complete!')
            runtime.append_log(scan_id, f'Scan complete: {scan_type}')
            
        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
            runtime.fail_scan(scan_id, f'Error: {str(e)}', error_code='scanner_exception')
            print(f'Scan error: {str(e)}')
            try:
                scan = runtime.get_scan(scan_id)
                if scan and scan.completed_at is None:
                    runtime.update_scan(scan_id, completed_at=datetime.utcnow())
            except Exception:
                pass
            # Clean up incomplete scan files
            try:
                cleanup_interrupted_scan()
            except Exception:
                pass
