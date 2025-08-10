"""
Network scanning service
"""
import os
import re
import time
import json
import threading
import subprocess
import shutil
from collections import deque
from datetime import datetime
import xml.etree.ElementTree as ET

from ..models import Scan
from ..config.database import db
from .insights import generate_and_store_insights

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

def run_nmap_scan(scan_type, security_settings=None, socketio=None, app=None, target_network='172.16.0.0/22', _priv_fallback=False, pre_discovery=False):
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
        # Store original label (human-friendly) but allow internal alias normalization later
        scan = Scan(scan_type=scan_type, status='running', percent=0.0)
        db.session.add(scan)
        db.session.commit()
        scan_id = scan.id
        
        try:
            def emit_progress(status, percent, message):
                scan.status = status
                scan.percent = percent
                db.session.commit()
                if socketio:
                    socketio.emit('scan_progress', {
                        'scan_id': scan_id,
                        'status': status,
                        'percent': percent,
                        'message': message
                    })

            emit_progress('running', 0, f'Started scan: {scan_type}')
            msg = f'Thread started for scan: {scan_type} (scheduled={threading.current_thread().name.startswith("APScheduler")})'
            
            if socketio:
                try:
                    socketio.emit('scan_log', {'msg': msg})
                except Exception as e:
                    print(f'[DEBUG] Could not emit to socketio: {e}')
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
            
            # Optional pre-discovery phase for heavy scans (not for explicit discovery scan or fallback retries)
            discovered_hosts = []
            if pre_discovery and scan_type_normalized not in ('discovery scan',) and not _priv_fallback:
                try:
                    emit_progress('running', 1, 'Pre-discovery: enumerating live hosts...')
                    pre_xml = f'scans/pre_discovery_{now}.xml'
                    pre_cmd = ['nmap', '-sn', '-PE', '-PP', '-PM', '-PR', '-n', '--max-retries', '1', '-T4', target_network, '-oX', pre_xml]
                    if socketio:
                        try:
                            socketio.emit('scan_log', {'msg': f'Pre-discovery command: {" ".join(pre_cmd)}'})
                        except Exception:
                            pass
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
                        emit_progress('running', 2, f'Pre-discovery found {len(discovered_hosts)} hosts – targeting only live hosts')
                        if socketio:
                            try:
                                socketio.emit('scan_log', {'msg': f'Pre-discovery found {len(discovered_hosts)} live hosts'})
                            except Exception:
                                pass
                    else:
                        emit_progress('running', 2, 'Pre-discovery found no hosts (falling back to full range)')
                except Exception as _e:
                    print(f'[WARN] Pre-discovery step failed: {_e}')
            # Build nmap command (user-facing prior to privilege adjustments)
            # NOTE: We intentionally omit -Pn for discovery scans so nmap actually performs host discovery
            if scan_type_normalized == 'discovery scan':
                cmd = ['nmap', '-v', '-T4']  # no -Pn here; allow ARP/ICMP
            else:
                cmd = ['nmap', '-v', '-T4', '-Pn']  # retain -Pn for other scan types to skip unreliable ping on some Wi-Fi setups
            if scan_type_normalized == 'full tcp':
                cmd += ['-sS', '-p-', '--open']
            elif scan_type_normalized == 'iot scan':
                if _priv_fallback:
                    # Fallback removes UDP requirement (switch to TCP SYN limited ports)
                    cmd += ['-sS', '-p', '53,67,68,80,443,1900,5353,554,8080']
                else:
                    cmd += ['-sU', '-p', '53,67,68,80,443,1900,5353,554,8080']
            elif scan_type_normalized == 'discovery scan':
                # Fast host discovery: prefer ARP (-PR) + skip port scan (-sn). If not root later, will still work (ARP needs privs, ping fallback).
                cmd += ['-sn']  # host discovery only
                # Add multiple host discovery probes for better coverage
                cmd += ['-PE', '-PP', '-PM', '-PR']  # ICMP echo, timestamp, netmask, ARP
                cmd += ['-n']  # disable DNS for speed / consistency
                # Speed: reduce retries
                cmd += ['--max-retries', '1', '-T4']
            elif scan_type_normalized == 'vuln scripts':
                cmd += ['-sS', '-p-', '--open']
            else:
                emit_progress('error', 0, f'Unknown scan type: {scan_type}')
                msg = f'Unknown scan type: {scan_type}'
                if socketio:
                    try:
                        socketio.emit('scan_log', {'msg': msg})
                    except Exception as e:
                        print(f'[DEBUG] Could not emit to socketio: {e}')
                print(msg)
                return
            
            # Apply security settings
            # Discovery scan does not use OS/service/vuln phases to stay lightweight
            if scan_type_normalized != 'discovery scan' and security_settings.get('os_detection_enabled'):
                cmd.append('-O')
            if scan_type_normalized != 'discovery scan' and security_settings.get('service_detection_enabled'):
                cmd.append('-sV')
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
            if socketio:
                try:
                    socketio.emit('scan_log', {'msg': msg})
                    if scan_type_normalized == 'discovery scan':
                        socketio.emit('scan_log', {'msg': '[Discovery] Fast host discovery started (no port scan)'})
                except Exception as e:
                    print(f'[DEBUG] Could not emit to socketio: {e}')
            print(msg)
            if exec_cmd != user_facing_cmd:
                adj_msg = f'Executing adjusted command: {" ".join(exec_cmd)}'
                if socketio:
                    try:
                        socketio.emit('scan_log', {'msg': adj_msg})
                    except Exception:
                        pass
                print(adj_msg)
            
            # Execute nmap
            proc = subprocess.Popen(exec_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)
            msg = 'Nmap process started...'
            if socketio:
                try:
                    socketio.emit('scan_log', {'msg': msg})
                except Exception as e:
                    print(f'[DEBUG] Could not emit to socketio: {e}')
            print(msg)
            
            percent = 0
            recent_lines = deque(maxlen=40)
            for line in proc.stdout:
                # Check for cancellation
                scan_check = Scan.query.get(scan_id)
                if scan_check and scan_check.status == 'cancelled':
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    emit_progress('cancelled', percent, 'Scan cancelled by user')
                    msg = 'Scan cancelled by user.'
                    if socketio:
                        try:
                            socketio.emit('scan_log', {'msg': msg})
                        except Exception as e:
                            print(f'[DEBUG] Could not emit to socketio: {e}')
                    print(msg)
                    return
                
                if socketio:
                    try:
                        socketio.emit('scan_log', {'msg': line.rstrip()})
                    except Exception as e:
                        print(f'[DEBUG] Could not emit to socketio: {e}')
                recent_lines.append(line.rstrip())
                
                match = re.search(r'About ([0-9.]+)% done', line)
                if match:
                    percent = float(match.group(1))
                    emit_progress('running', percent, f'Scanning: {percent:.1f}%')
            
            proc.wait()
            # Handle failure before parsing
            if proc.returncode != 0:
                output_tail = '\n'.join(recent_lines)
                lowered = output_tail.lower()
                privilege_issue = any(k in lowered for k in ['requires root', 'cap_net_raw', 'dnet'])
                if privilege_issue and scan_type_normalized == 'iot scan' and not _priv_fallback:
                    emit_progress('running', percent, 'Privilege issue: retrying IoT scan without -sU/-O (degraded TCP mode)...')
                    if socketio:
                        try:
                            socketio.emit('scan_log', {'msg': 'Retrying in degraded mode: removed -sU and -O'})
                        except Exception:
                            pass
                    degraded_security = dict(security_settings or {})
                    degraded_security['os_detection_enabled'] = False
                    try:
                        run_nmap_scan(scan_type, degraded_security, socketio, app, target_network, _priv_fallback=True)
                    except Exception as e:
                        emit_progress('error', percent, f'Fallback failed: {e}')
                    return
                guidance = ''
                if privilege_issue:
                    guidance = ' (Hint: grant CAP_NET_RAW/CAP_NET_ADMIN to nmap or run with sudo)'
                emit_progress('error', percent, f'nmap exited with code {proc.returncode}{guidance}')
                if socketio:
                    try:
                        socketio.emit('scan_log', {'msg': '--- Nmap last output (truncated) ---'})
                        for l in list(recent_lines)[-10:]:
                            socketio.emit('scan_log', {'msg': l})
                    except Exception:
                        pass
                print(f'[ERROR] nmap failed (code {proc.returncode}). Last lines:\n{output_tail}')
                return

            # Validate XML output before parsing
            for i in range(5):
                if os.path.exists(xml_path) and os.path.getsize(xml_path) > 100:
                    break
                time.sleep(1)
            if not os.path.exists(xml_path) or os.path.getsize(xml_path) < 100:
                emit_progress('error', percent, 'XML file not found or too small (no results)')
                return

            emit_progress('parsing', 90, 'Parsing scan results...')
            
            # Parse XML results
            emit_progress('parsing', 95, 'Parsing XML results...')
            hosts = []
            vulns = []
            
            try:
                tree = ET.parse(xml_path)
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
                            if state_el is None or state_el.attrib.get('state') != 'open':
                                continue
                            portid = port_el.attrib.get('portid')
                            proto = port_el.attrib.get('protocol')
                            service_el = port_el.find('service')
                            service_name = service_el.attrib.get('name') if service_el is not None else None
                            product = service_el.attrib.get('product') if service_el is not None and service_el.attrib.get('product') else None
                            version = service_el.attrib.get('version') if service_el is not None and service_el.attrib.get('version') else None
                            try:
                                p_int = int(portid)
                            except Exception:
                                p_int = None
                            open_ports.append({
                                'port': p_int or portid,
                                'protocol': proto,
                                'service': service_name,
                                'product': product,
                                'version': version
                            })
                    if open_ports:
                        open_ports.sort(key=lambda x: (x.get('port') or 0, x.get('protocol') or ''))
                        total_open_ports += len(open_ports)
                        host_obj['ports'] = open_ports
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
                if socketio:
                    try:
                        socketio.emit('scan_log', {'msg': msg})
                    except Exception as e:
                        print(f'[DEBUG] Could not emit to socketio: {e}')
                print(msg)
                
            except Exception as e:
                emit_progress('error', 95, f'XML parse error: {str(e)}')
                return
            
            # Save results
            emit_progress('saving', 98, 'Saving scan results to database...')
            scan.hosts_json = json.dumps(hosts)
            scan.vulns_json = json.dumps(vulns)
            scan.raw_xml_path = xml_path
            # Do not mark complete until after insights
            scan.percent = 99.0
            db.session.commit()
            
            # Generate insights unless discovery-only
            if scan_type_normalized == 'discovery scan':
                emit_progress('postprocessing', 99, 'Discovery complete – skipping insights...')
            else:
                emit_progress('postprocessing', 99, 'Generating insights...')
                try:
                    insights = generate_and_store_insights(scan_id)
                    if insights is not None:
                        try:
                            scan.insights_json = json.dumps(insights)
                        except Exception:
                            pass
                    print(f'Generated {len(insights) if insights else 0} insights for scan {scan_id}')
                except Exception as e:
                    print(f'Error generating insights: {str(e)}')
            # Finalize
            from datetime import datetime as _dt
            scan.status = 'complete'
            scan.percent = 100.0
            scan.completed_at = _dt.utcnow()
            db.session.commit()
            emit_progress('complete', 100, 'Scan complete!')
            if socketio:
                socketio.emit('scan_complete', {'msg': f'Scan complete: {scan_type}', 'scan_id': scan_id})
            
        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
            emit_progress('error', 0, f'Error: {str(e)}')
            print(f'Scan error: {str(e)}')
            try:
                from datetime import datetime as _dt
                scan.completed_at = _dt.utcnow()
                db.session.commit()
            except Exception:
                pass
