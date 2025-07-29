"""
Network scanning service
"""
import os
import re
import time
import json
import threading
import subprocess
from datetime import datetime
import xml.etree.ElementTree as ET

from ..models import Scan
from ..config.database import db

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

def run_nmap_scan(scan_type, security_settings=None, socketio=None, app=None, target_network='172.16.0.0/22'):
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
            xml_path = f'scans/{scan_type_normalized.replace(" ", "_")}_{now}.xml'
            
            # Build nmap command
            cmd = ['nmap', '-v', '-T4', '-Pn']  # -Pn bypasses host discovery for macOS Wi-Fi compatibility
            if scan_type_normalized == 'full tcp':
                cmd += ['-sS', '-p-', '--open']
            elif scan_type_normalized == 'iot scan':
                cmd += ['-sU', '-p', '53,67,68,80,443,1900,5353,554,8080']
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
            if security_settings.get('os_detection_enabled'):
                cmd.append('-O')
            if security_settings.get('service_detection_enabled'):
                cmd.append('-sV')
            if scan_type_normalized == 'vuln scripts':
                # Only run vulnerability scripts for explicit vulnerability scans
                cmd.append('--script=vuln')
            elif security_settings.get('vuln_scanning_enabled'):
                # Use more targeted vulnerability scripts for regular scans
                cmd.append('--script=ssl-cert,ssl-enum-ciphers,http-title,ssh-hostkey')
            if security_settings.get('aggressive_scanning'):
                cmd.append('-A')
            
            # Target network
            cmd += [target_network, '-oX', xml_path]
            
            msg = f'Nmap command: {" ".join(cmd)}'
            if socketio:
                try:
                    socketio.emit('scan_log', {'msg': msg})
                except Exception as e:
                    print(f'[DEBUG] Could not emit to socketio: {e}')
            print(msg)
            
            # Execute nmap
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)
            msg = 'Nmap process started...'
            if socketio:
                try:
                    socketio.emit('scan_log', {'msg': msg})
                except Exception as e:
                    print(f'[DEBUG] Could not emit to socketio: {e}')
            print(msg)
            
            percent = 0
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
                
                match = re.search(r'About ([0-9.]+)% done', line)
                if match:
                    percent = float(match.group(1))
                    emit_progress('running', percent, f'Scanning: {percent:.1f}%')
            
            proc.wait()
            emit_progress('parsing', 90, 'Parsing scan results...')
            
            # Validate XML output
            for i in range(5):
                if os.path.exists(xml_path) and os.path.getsize(xml_path) > 100:
                    break
                time.sleep(1)
            
            if not os.path.exists(xml_path) or os.path.getsize(xml_path) < 100:
                emit_progress('error', percent, 'XML file not found or too small')
                return
            
            if proc.returncode != 0:
                emit_progress('error', percent, f'nmap error: {proc.returncode}')
                return
            
            # Parse XML results
            emit_progress('parsing', 95, 'Parsing XML results...')
            hosts = []
            vulns = []
            
            try:
                tree = ET.parse(xml_path)
                root = tree.getroot()
                for host in root.findall('host'):
                    status = host.find('status')
                    if status is not None and status.attrib.get('state') == 'up':
                        host_obj = {}
                        addr = host.find('address[@addrtype="ipv4"]')
                        if addr is not None:
                            host_obj['ip'] = addr.attrib.get('addr')
                        
                        # Parse ports, OS, services, etc.
                        # (Detailed parsing logic would go here)
                        hosts.append(host_obj)
                
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
            scan.status = 'complete'
            scan.percent = 100.0
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
