import eventlet
eventlet.monkey_patch()
import os
# Add dotenv support
from dotenv import load_dotenv
load_dotenv()
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, Response, make_response, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
import logging
import requests
import pytz
import threading
import subprocess
import xml.etree.ElementTree as ET
import time
import re
import socket
import asyncio
import concurrent.futures
import traceback
import warnings
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
import json as pyjson
import sys
import psutil

# Suppress SSL warnings for internal network monitoring
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

print("=== Flask app.py started ===")

SCHEDULE_CONFIG_PATH = 'schedule_config.json'

LAST_RUN_PATH = 'last_run.txt'

def load_schedule_config():
    if os.path.exists(SCHEDULE_CONFIG_PATH):
        with open(SCHEDULE_CONFIG_PATH, 'r') as f:
            return pyjson.load(f)
    return {
        'enabled': False,
        'scan_type': 'Full TCP',
        'frequency': 'daily',
        'time': '03:00',
    }

def save_schedule_config(config):
    with open(SCHEDULE_CONFIG_PATH, 'w') as f:
        pyjson.dump(config, f)

def save_last_run(status):
    with open(LAST_RUN_PATH, 'w') as f:
        f.write(f'{datetime.now().isoformat()}|{status}')

def load_last_run():
    if os.path.exists(LAST_RUN_PATH):
        with open(LAST_RUN_PATH, 'r') as f:
            val = f.read().strip()
            if '|' in val:
                t, s = val.split('|', 1)
                # Convert to Denver timezone for display
                try:
                    dt = datetime.fromisoformat(t)
                    denver = pytz.timezone('America/Denver')
                    t_local = dt.astimezone(denver).isoformat()
                except Exception:
                    t_local = t
                return {'time': t_local, 'status': s}
    return {'time': None, 'status': '--'}

def get_next_run():
    job = scheduler.get_job('scheduled_scan')
    if job and job.next_run_time:
        denver = pytz.timezone('America/Denver')
        return job.next_run_time.astimezone(denver).isoformat()
    return None

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-to-a-random-secret')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sentinelzero.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins='*')

# Database Models
class Scan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    scan_type = db.Column(db.String(32))
    hosts_json = db.Column(db.Text)
    diff_from_previous = db.Column(db.Text)
    vulns_json = db.Column(db.Text)
    raw_xml_path = db.Column(db.String(256))
    status = db.Column(db.String(32), default='pending')  # new: pending, running, parsing, saving, complete, error
    percent = db.Column(db.Float, default=0.0)            # new: progress percent
    def as_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'scan_type': self.scan_type,
            'hosts_json': self.hosts_json,
            'diff_from_previous': self.diff_from_previous,
            'vulns_json': self.vulns_json,
            'raw_xml_path': self.raw_xml_path,
            'status': self.status,
            'percent': self.percent,
        }

class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    message = db.Column(db.String(256))
    level = db.Column(db.String(16))
    scan_id = db.Column(db.Integer, db.ForeignKey('scan.id'))

PUSHOVER_API_TOKEN = os.environ.get('PUSHOVER_API_TOKEN')
PUSHOVER_USER_KEY = os.environ.get('PUSHOVER_USER_KEY')

# Helper to send Pushover alert and log to DB
def send_pushover_alert(message, level='info', scan_id=None):
    try:
        resp = requests.post('https://api.pushover.net/1/messages.json', data={
            'token': PUSHOVER_API_TOKEN,
            'user': PUSHOVER_USER_KEY,
            'message': message,
            'priority': 1 if level == 'danger' else 0,
            'title': 'SentinelZero',
        })
        if resp.status_code == 200:
            socketio.emit('scan_log', {'msg': f'Pushover alert sent: {message}'})
        else:
            socketio.emit('scan_log', {'msg': f'Pushover failed: {resp.text}'})
        alert = Alert(message=message, level=level, scan_id=scan_id)
        db.session.add(alert)
        db.session.commit()
    except Exception as e:
        socketio.emit('scan_log', {'msg': f'Pushover error: {str(e)}'})

scheduler = BackgroundScheduler(jobstores={
    'default': SQLAlchemyJobStore(url=app.config['SQLALCHEMY_DATABASE_URI'])
})
if not scheduler.running:
    scheduler.start()

def parse_vulners_output(host_ip, cpe, output):
    import re
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

def run_nmap_scan(scan_type, security_settings=None):
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
                socketio.emit('scan_progress', {
                    'scan_id': scan_id,
                    'status': status,
                    'percent': percent,
                    'message': message
                })

            emit_progress('running', 0, f'Started scan: {scan_type}')
            msg = f'Thread started for scan: {scan_type} (scheduled={threading.current_thread().name.startswith("APScheduler")})'
            try:
                socketio.emit('scan_log', {'msg': msg})
            except Exception as e:
                print(f'[DEBUG] Could not emit to socketio: {e}')
            print(msg)
            now = datetime.now().strftime('%Y-%m-%d_%H%M')
            # Normalize scan_type for robust matching
            scan_type_normalized = scan_type.strip().lower()
            xml_path = f'scans/{scan_type_normalized.replace(" ", "_")}_{now}.xml'
            cmd = ['nmap', '-v', '-T4']
            if scan_type_normalized == 'full tcp':
                cmd += ['-sS', '-p-', '--open']
            elif scan_type_normalized == 'iot scan':
                cmd += ['-sU', '-p', '53,67,68,80,443,1900,5353,554,8080']
            elif scan_type_normalized == 'vuln scripts':
                cmd += ['-sS', '-p-', '--open']
            else:
                emit_progress('error', 0, f'Unknown scan type: {scan_type}')
                msg = f'Unknown scan type: {scan_type}'
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
            cmd += ['172.16.0.0/22', '-oX', xml_path]
            msg = f'Nmap command: {" ".join(cmd)}'
            try:
                socketio.emit('scan_log', {'msg': msg})
            except Exception as e:
                print(f'[DEBUG] Could not emit to socketio: {e}')
            print(msg)
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)
            msg = 'Nmap process started...'
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
                    try:
                        socketio.emit('scan_log', {'msg': msg})
                    except Exception as e:
                        print(f'[DEBUG] Could not emit to socketio: {e}')
                    print(msg)
                    return
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
            msg = 'Nmap process finished.'
            try:
                socketio.emit('scan_log', {'msg': msg})
            except Exception as e:
                print(f'[DEBUG] Could not emit to socketio: {e}')
            print(msg)
            for i in range(5):
                if os.path.exists(xml_path) and os.path.getsize(xml_path) > 100:
                    break
                time.sleep(1)
            if not os.path.exists(xml_path) or os.path.getsize(xml_path) < 100:
                emit_progress('error', percent, 'XML file not found or too small')
                msg = f'XML file not found or too small: {xml_path}'
                try:
                    socketio.emit('scan_log', {'msg': msg})
                except Exception as e:
                    print(f'[DEBUG] Could not emit to socketio: {e}')
                print(msg)
                send_pushover_alert(f'Scan failed: {scan_type} (no XML output)', 'danger')
                return
            msg = f'XML file size: {os.path.getsize(xml_path)} bytes'
            try:
                socketio.emit('scan_log', {'msg': msg})
            except Exception as e:
                print(f'[DEBUG] Could not emit to socketio: {e}')
            print(msg)
            if proc.returncode != 0:
                emit_progress('error', percent, f'nmap error: {proc.returncode}')
                msg = f'nmap error: {proc.returncode}'
                try:
                    socketio.emit('scan_log', {'msg': msg})
                except Exception as e:
                    print(f'[DEBUG] Could not emit to socketio: {e}')
                print(msg)
                send_pushover_alert(f'Scan failed: {scan_type}', 'danger')
                return
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
                        mac = host.find('address[@addrtype="mac"]')
                        if mac is not None:
                            host_obj['mac'] = mac.attrib.get('addr')
                            if 'vendor' in mac.attrib:
                                host_obj['vendor'] = mac.attrib['vendor']
                        # Hostnames
                        hostnames = host.find('hostnames')
                        if hostnames is not None:
                            host_obj['hostnames'] = [hn.attrib.get('name') for hn in hostnames.findall('hostname') if hn.attrib.get('name')]
                        # Distance
                        distance = host.find('distance')
                        if distance is not None:
                            host_obj['distance'] = distance.attrib.get('value')
                        # OS
                        os_elem = host.find('os/osmatch')
                        if os_elem is not None:
                            host_obj['os'] = {
                                'name': os_elem.attrib.get('name'),
                                'accuracy': os_elem.attrib.get('accuracy')
                            }
                        # Uptime
                        uptime = host.find('uptime')
                        if uptime is not None:
                            host_obj['uptime'] = {
                                'seconds': int(uptime.attrib.get('seconds', 0)),
                                'lastboot': uptime.attrib.get('lastboot')
                            }
                        # Ports
                        ports_elem = host.find('ports')
                        ports = []
                        if ports_elem is not None:
                            for port in ports_elem.findall('port'):
                                state = port.find('state')
                                if state is not None and state.attrib.get('state') == 'open':
                                    port_obj = {
                                        'port': int(port.attrib.get('portid')),
                                        'protocol': port.attrib.get('protocol'),
                                        'service': None,
                                        'product': None,
                                        'version': None
                                    }
                                    service = port.find('service')
                                    if service is not None:
                                        port_obj['service'] = service.attrib.get('name')
                                        port_obj['product'] = service.attrib.get('product') if 'product' in service.attrib else None
                                        port_obj['version'] = service.attrib.get('version') if 'version' in service.attrib else None
                                    ports.append(port_obj)
                                    # Vulnerability scripts on this port
                                    for script in port.findall('script'):
                                        if 'vuln' in script.attrib.get('id', ''):
                                            vuln_obj = {
                                                'id': script.attrib.get('id'),
                                                'output': script.attrib.get('output'),
                                                'host': host_obj.get('ip'),
                                                'port': port_obj['port'],
                                                'protocol': port_obj['protocol']
                                            }
                                            vulns.append(vuln_obj)
                        host_obj['ports'] = ports
                        # Vulnerability scripts at host level
                    for script in host.findall('.//script'):
                        if 'vuln' in script.attrib.get('id', ''):
                                # Special handling for vulners output
                                if script.attrib.get('id') == 'vulners' and script.attrib.get('output'):
                                    cpe = None
                                    # Try to extract CPE from output
                                    cpe_match = re.search(r'(cpe:/[\w:.-]+)', script.attrib['output'])
                                    if cpe_match:
                                        cpe = cpe_match.group(1)
                                    vulns += parse_vulners_output(host_obj.get('ip'), cpe, script.attrib['output'])
                                else:
                                    vuln_obj = {
                                        'id': script.attrib.get('id'),
                                        'output': script.attrib.get('output'),
                                        'host': host_obj.get('ip'),
                                        'port': None,
                                        'protocol': None
                                    }
                                    vulns.append(vuln_obj)
                        hosts.append(host_obj)
                msg = f'Parsed {len(hosts)} hosts, {len(vulns)} vulns.'
                try:
                    socketio.emit('scan_log', {'msg': msg})
                except Exception as e:
                    print(f'[DEBUG] Could not emit to socketio: {e}')
                print(msg)
            except Exception as e:
                emit_progress('error', 95, f'XML parse error: {str(e)}')
                msg = f'XML parse error: {str(e)}'
                try:
                    socketio.emit('scan_log', {'msg': msg})
                except Exception as emit_e:
                    print(f'[DEBUG] Could not emit to socketio: {emit_e}')
                print(msg)
                msg = f'First 500 bytes of XML: ' + open(xml_path).read(500)
                try:
                    socketio.emit('scan_log', {'msg': msg})
                except Exception as emit_e:
                    print(f'[DEBUG] Could not emit to socketio: {emit_e}')
                print(msg)
                send_pushover_alert(f'Scan failed: {scan_type} (XML parse error)', 'danger')
                return
            emit_progress('saving', 98, 'Saving scan results to database...')
            scan.hosts_json = json.dumps(hosts)
            scan.vulns_json = json.dumps(vulns)
            scan.raw_xml_path = xml_path
            scan.status = 'complete'
            scan.percent = 100.0
            db.session.commit()
            emit_progress('complete', 100, 'Scan complete!')
            msg = 'Scan results saved.'
            try:
                socketio.emit('scan_log', {'msg': msg})
            except Exception as e:
                print(f'[DEBUG] Could not emit to socketio: {e}')
            print(msg)
            socketio.emit('scan_complete', {'msg': f'Scan complete: {scan_type}', 'scan_id': scan_id})
            send_pushover_alert(f'Scan complete: {scan_type}', 'info', scan.id)
        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
            emit_progress('error', 0, f'Error: {str(e)}')
            logging.exception('Scan trigger failed')
            msg = f'Error: {str(e)}'
            try:
                socketio.emit('scan_log', {'msg': msg})
            except Exception as emit_e:
                print(f'[DEBUG] Could not emit error to socketio: {emit_e}')
            print(msg)
            try:
                send_pushover_alert(f'Scan failed: {str(e)}', 'danger')
            except Exception:
                pass

def scheduled_scan_job(scan_type='Full TCP'):
    print(f"[SCHEDULER] Triggering scheduled scan: {scan_type}")
    save_last_run('Started')
    def run_and_record():
        try:
            run_nmap_scan(scan_type)
            save_last_run('Success')
        except Exception as e:
            save_last_run(f'Error: {str(e)}')
    threading.Thread(target=run_and_record, daemon=True, name="APScheduler-Scan").start()

@app.route('/')
def index():
    # In production with Docker, serve the React app
    if os.path.exists(os.path.join(app.static_folder, 'index.html')):
        return send_from_directory(app.static_folder, 'index.html')
    else:
        # Fallback to original template-based approach for development
        scans = Scan.query.order_by(Scan.timestamp.desc()).limit(5).all()
        denver = pytz.timezone('America/Denver')
        scans_dicts = []
        for scan in scans:
            d = scan.as_dict()
            if d['timestamp']:
                d['timestamp'] = d['timestamp'].astimezone(denver)
            try:
                d['hosts'] = json.loads(d['hosts_json']) if d['hosts_json'] else []
            except Exception:
                d['hosts'] = []
            try:
                d['vulns'] = json.loads(d['vulns_json']) if d['vulns_json'] else []
            except Exception:
                d['vulns'] = []
            scans_dicts.append(d)
        latest_scan = scans_dicts[0] if scans_dicts else None
        return render_template('index.html', scans=scans_dicts, latest_scan=latest_scan)

@app.route('/scans-table')
def scans_table():
    scans = Scan.query.order_by(Scan.timestamp.desc()).limit(5).all()
    denver = pytz.timezone('America/Denver')
    scans_dicts = []
    for scan in scans:
        d = scan.as_dict()
        if d['timestamp']:
            d['timestamp'] = d['timestamp'].astimezone(denver)
        try:
            d['hosts'] = json.loads(d['hosts_json']) if d['hosts_json'] else []
        except Exception:
            d['hosts'] = []
        try:
            d['vulns'] = json.loads(d['vulns_json']) if d['vulns_json'] else []
        except Exception:
            d['vulns'] = []
        scans_dicts.append(d)
    return render_template('scans_table.html', scans=scans_dicts)

# Helper to determine if request is for API

def is_api_request():
    return request.path.startswith('/api/')

@app.errorhandler(404)
def not_found_error(error):
    try:
        socketio.emit('scan_log', {'msg': '404 Not Found'})
    except Exception:
        pass
    if is_api_request():
        return jsonify({'error': 'Not found', 'code': 404}), 404
    # For non-API requests (like static files), serve the React app index.html
    if os.path.exists(os.path.join(app.static_folder, 'index.html')):
        return send_from_directory(app.static_folder, 'index.html')
    return jsonify({'error': 'Not found', 'code': 404}), 404

@app.errorhandler(400)
def bad_request_error(error):
    try:
        socketio.emit('scan_log', {'msg': '400 Bad Request - Unicode error from nmap probes'})
    except Exception:
        pass
    return jsonify({'error': 'Bad request - Unicode error from nmap probes', 'code': 400}), 400

@app.errorhandler(500)
def internal_error(error):
    try:
        socketio.emit('scan_log', {'msg': '500 Internal Server Error'})
    except Exception:
        pass
    return jsonify({'error': 'Internal server error', 'code': 500}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    print("=== Uncaught Exception ===", file=sys.stderr)
    import traceback
    traceback.print_exc()
    if is_api_request():
        return jsonify({'error': str(e), 'code': 500}), 500
    return jsonify({'error': str(e)}), 500

@app.route('/scan', methods=['POST'])
def trigger_scan():
    scan_type = request.form.get('scan_type', 'Full TCP')
    # Load security settings
    security_settings = {
        'vuln_scanning_enabled': True,
        'os_detection_enabled': True,
        'service_detection_enabled': True,
        'aggressive_scanning': False
    }
    try:
        if os.path.exists('security_settings.json'):
            with open('security_settings.json', 'r') as f:
                security_settings.update(json.load(f))
    except Exception as e:
        print(f'[DEBUG] Could not load security settings: {e}')
    threading.Thread(target=run_nmap_scan, args=(scan_type, security_settings), daemon=True).start()
    return jsonify({'status': 'success', 'message': f'{scan_type} scan started'})

@app.route('/clear-scan/<int:scan_id>', methods=['POST'])
def clear_scan(scan_id):
    try:
        scan = Scan.query.get(scan_id)
        if scan:
            db.session.delete(scan)
            db.session.commit()
            print(f'[DEBUG] Scan {scan_id} deleted.')
            return jsonify({'status': 'success', 'message': 'Scan cleared'})
        else:
            print(f'[DEBUG] Scan {scan_id} not found for deletion.')
            return jsonify({'status': 'error', 'message': 'Scan not found'}), 404
    except Exception as e:
        db.session.rollback()
        print(f'[DEBUG] Error deleting scan {scan_id}: {e}')
        return jsonify({'status': 'error', 'message': f'Error clearing scan: {str(e)}'}), 500

@app.route('/test-log')
def test_log():
    socketio.emit('scan_log', {'msg': 'Test log message from /test-log route'})
    return 'Test log emitted', 200

@socketio.on('connect')
def handle_connect():
    print('[Socket.IO] Client connected:', request.sid)
    emit('scan_log', {'msg': 'Connected to SentinelZero'})

@socketio.on('disconnect')
def handle_disconnect():
    print('[Socket.IO] Client disconnected:', request.sid)

@app.template_filter('host_count')
def host_count_filter(hosts_json):
    try:
        hosts = json.loads(hosts_json)
        return len(hosts)
    except Exception:
        return 0

@app.route('/api/schedule', methods=['GET'])
def get_schedule():
    config = load_schedule_config()
    next_run = get_next_run()
    last_run = load_last_run()
    return jsonify({**config, 'next_run': next_run, 'last_run': last_run})

@app.route('/api/schedule', methods=['POST'])
def update_schedule():
    data = request.json
    config = load_schedule_config()
    config.update({
        'enabled': data.get('enabled', config['enabled']),
        'scan_type': data.get('scan_type', config['scan_type']),
        'frequency': data.get('frequency', config['frequency']),
        'time': data.get('time', config['time']),
    })
    save_schedule_config(config)
    # Remove existing job if any
    if scheduler.get_job('scheduled_scan'):
        scheduler.remove_job('scheduled_scan')
    # Add job if enabled
    if config['enabled']:
        hour, minute = map(int, config['time'].split(':'))
        if config['frequency'] == 'daily':
            scheduler.add_job(
                scheduled_scan_job,
                'cron',
                id='scheduled_scan',
                hour=hour,
                minute=minute,
                args=[config['scan_type']],
                replace_existing=True
            )
        elif config['frequency'] == 'weekly':
            scheduler.add_job(
                scheduled_scan_job,
                'cron',
                id='scheduled_scan',
                day_of_week='mon',
                hour=hour,
                minute=minute,
                args=[config['scan_type']],
                replace_existing=True
            )
        # Add more frequencies as needed
    logging.info(f"[SCHEDULE] Schedule updated: {config}")
    next_run = get_next_run()
    last_run = load_last_run()
    return jsonify({'status': 'ok', 'config': config, 'next_run': next_run, 'last_run': last_run})

@app.route('/api/schedules', methods=['GET'])
def list_schedules():
    jobs = scheduler.get_jobs()
    denver = pytz.timezone('America/Denver')
    result = []
    for job in jobs:
        job_args = job.args if hasattr(job, 'args') else []
        scan_type = job_args[0] if job_args else 'Full TCP'
        freq = 'custom'
        if hasattr(job.trigger, 'fields'):
            fields = {f.name: f for f in job.trigger.fields}
            if 'day_of_week' in fields:
                freq = 'weekly'
            elif 'day' not in fields and 'day_of_week' not in fields:
                freq = 'daily'
        next_run = job.next_run_time.astimezone(denver).isoformat() if job.next_run_time else None
        last_run = load_last_run() if job.id == 'scheduled_scan' else {'time': None, 'status': '--'}
        result.append({
            'id': job.id,
            'scan_type': scan_type,
            'frequency': freq,
            'time': job.trigger.fields[2].__getattribute__('expressions')[0] if hasattr(job.trigger, 'fields') and len(job.trigger.fields) > 2 else '',
            'next_run': next_run,
            'last_run': last_run
        })
    return jsonify(result)

@app.route('/api/schedules/<job_id>', methods=['DELETE'])
def delete_schedule(job_id):
    try:
        scheduler.remove_job(job_id)
        logging.info(f"[SCHEDULE] Deleted schedule: {job_id}")
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 400

@app.route('/scan-history')
def scan_history():
    scans = Scan.query.order_by(Scan.timestamp.desc()).all()
    denver = pytz.timezone('America/Denver')
    scans_dicts = []
    for scan in scans:
        d = scan.as_dict()
        if d['timestamp']:
            d['timestamp'] = d['timestamp'].astimezone(denver)
        try:
            d['hosts'] = json.loads(d['hosts_json']) if d['hosts_json'] else []
        except Exception:
            d['hosts'] = []
        try:
            d['vulns'] = json.loads(d['vulns_json']) if d['vulns_json'] else []
        except Exception:
            d['vulns'] = []
        scans_dicts.append(d)
    return render_template('scan_history.html', scans=scans_dicts)

print("=== Registering /api/scan-history ===")
@app.route('/api/scan-history')
def api_scan_history():
    print('HIT /api/scan-history')
    try:
        scans = Scan.query.order_by(Scan.timestamp.desc()).all()
        denver = pytz.timezone('America/Denver')
        scans_dicts = []
        for scan in scans:
            d = scan.as_dict()
            if d['timestamp']:
                d['timestamp'] = d['timestamp'].astimezone(denver)
            try:
                d['hosts'] = json.loads(d['hosts_json']) if d['hosts_json'] else []
                d['hosts_count'] = len(d['hosts'])
            except Exception as e:
                print('Error parsing hosts_json:', e)
                d['hosts'] = []
                d['hosts_count'] = 0
            try:
                d['vulns'] = json.loads(d['vulns_json']) if d['vulns_json'] else []
                d['vulns_count'] = len(d['vulns'])
            except Exception as e:
                print('Error parsing vulns_json:', e)
                d['vulns'] = []
                d['vulns_count'] = 0
            scans_dicts.append(d)
        print('Returning scans:', len(scans_dicts))
        return jsonify({'scans': scans_dicts})
    except Exception as e:
        print('Exception in /api/scan-history:', e)
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/active-scans')
def api_active_scans():
    active_statuses = ['pending', 'running', 'parsing', 'saving']
    scans = Scan.query.filter(Scan.status.in_(active_statuses)).order_by(Scan.timestamp.desc()).all()
    denver = pytz.timezone('America/Denver')
    scans_dicts = []
    for scan in scans:
        d = scan.as_dict()
        if d['timestamp']:
            d['timestamp'] = d['timestamp'].astimezone(denver)
        try:
            d['hosts'] = json.loads(d['hosts_json']) if d['hosts_json'] else []
        except Exception:
            d['hosts'] = []
        try:
            d['vulns'] = json.loads(d['vulns_json']) if d['vulns_json'] else []
        except Exception:
            d['vulns'] = []
        scans_dicts.append(d)
    return jsonify({'scans': scans_dicts})

@app.route('/api/scan/<int:scan_id>', methods=['GET'])
def get_scan(scan_id):
    scan = Scan.query.get(scan_id)
    if not scan:
        return jsonify({'error': 'Scan not found'}), 404
    return jsonify(scan.as_dict())

@app.route('/api/scan-xml/<int:scan_id>')
def get_scan_xml(scan_id):
    """Get raw XML data for a scan"""
    scan = Scan.query.get_or_404(scan_id)
    if not scan.raw_xml_path:
        return jsonify({'error': 'No XML file path recorded for this scan'}), 404
    
    if not os.path.exists(scan.raw_xml_path):
        return jsonify({'error': f'XML file not found at path: {scan.raw_xml_path}'}), 404
    
    try:
        with open(scan.raw_xml_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()
        
        # Set proper headers for XML download
        response = Response(xml_content, mimetype='application/xml')
        response.headers['Content-Disposition'] = f'attachment; filename=scan_{scan_id}.xml'
        return response
    except Exception as e:
        return jsonify({'error': f'Error reading XML file: {str(e)}'}), 500

@app.route('/settings')
def settings():
    return render_template('settings.html')

@app.route('/api/hosts/<int:scan_id>')
def get_scan_hosts(scan_id):
    scan = Scan.query.get_or_404(scan_id)
    if scan.hosts_json:
        hosts = json.loads(scan.hosts_json)
        return jsonify({'hosts': hosts})
    return jsonify({'hosts': []})

@app.route('/api/vulns/<int:scan_id>')
def get_scan_vulns(scan_id):
    scan = Scan.query.get_or_404(scan_id)
    if scan.vulns_json:
        vulns = json.loads(scan.vulns_json)
        return jsonify({'vulns': vulns})
    return jsonify({'vulns': []})

@app.route('/api/hosts/latest')
def get_latest_hosts():
    latest_scan = Scan.query.order_by(Scan.timestamp.desc()).first()
    if latest_scan and latest_scan.hosts_json:
        hosts = json.loads(latest_scan.hosts_json)
        return jsonify({'hosts': hosts})
    return jsonify({'hosts': []})

@app.route('/api/vulns/latest')
def get_latest_vulns():
    latest_scan = Scan.query.order_by(Scan.timestamp.desc()).first()
    if latest_scan and latest_scan.vulns_json:
        vulns = json.loads(latest_scan.vulns_json)
        return jsonify({'vulns': vulns})
    return jsonify({'vulns': []})

print("=== Registering /api/dashboard-stats ===")
@app.route('/api/dashboard-stats')
def dashboard_stats():
    print('HIT /api/dashboard-stats')
    try:
        latest_scan = Scan.query.order_by(Scan.timestamp.desc()).first()
        total_scans = Scan.query.count()
        total_hosts = 0
        total_vulns = 0
        if latest_scan:
            if latest_scan.hosts_json:
                total_hosts = len(json.loads(latest_scan.hosts_json))
            if latest_scan.vulns_json:
                total_vulns = len(json.loads(latest_scan.vulns_json))
        print('Returning dashboard stats:', total_scans, total_hosts, total_vulns)
        return jsonify({
            'hosts_count': total_hosts,
            'vulns_count': total_vulns,
            'total_scans': total_scans,
            'latest_scan_time': latest_scan.timestamp.isoformat() if latest_scan else None
        })
    except Exception as e:
        print('Exception in /api/dashboard-stats:', e)
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get all application settings"""
    settings = {}
    try:
        # Load network settings
        if os.path.exists('network_settings.json'):
            with open('network_settings.json', 'r') as f:
                network_data = json.load(f)
        else:
            network_data = {
                'defaultTargetNetwork': '172.16.0.0/22',
                'maxHosts': 1000,
                'scanTimeout': 300,
                'concurrentScans': 1
            }
        
        # Normalize network settings to frontend format
        settings['network'] = {
            'defaultTargetNetwork': network_data.get('defaultTargetNetwork', network_data.get('target_network', '172.16.0.0/22')),
            'maxHosts': network_data.get('maxHosts', network_data.get('max_hosts', 1000)),
            'scanTimeout': network_data.get('scanTimeout', network_data.get('scan_timeout', 300)),
            'concurrentScans': network_data.get('concurrentScans', 1)
        }
        
        # Load notification settings
        if os.path.exists('notification_settings.json'):
            with open('notification_settings.json', 'r') as f:
                notification_data = json.load(f)
        else:
            notification_data = {}
        
        # Normalize notification settings to frontend format
        settings['notifications'] = {
            'pushoverEnabled': notification_data.get('pushoverEnabled', notification_data.get('pushover_enabled', bool(PUSHOVER_API_TOKEN and PUSHOVER_USER_KEY))),
            'pushoverConfigured': bool(os.environ.get('PUSHOVER_API_TOKEN') and os.environ.get('PUSHOVER_USER_KEY')),
            'scanComplete': notification_data.get('scanComplete', True),
            'vulnerabilityFound': notification_data.get('vulnerabilityFound', True),
            'newHostFound': notification_data.get('newHostFound', False)
        }
        
        # Load security settings
        if os.path.exists('security_settings.json'):
            with open('security_settings.json', 'r') as f:
                security_data = json.load(f)
        else:
            security_data = {}
        
        # Normalize security settings to frontend format
        settings['security'] = {
            'vulnScanningEnabled': security_data.get('vulnScanningEnabled', security_data.get('vuln_scanning_enabled', True)),
            'osDetectionEnabled': security_data.get('osDetectionEnabled', security_data.get('os_detection_enabled', True)),
            'serviceDetectionEnabled': security_data.get('serviceDetectionEnabled', security_data.get('service_detection_enabled', True)),
            'aggressiveScanning': security_data.get('aggressiveScanning', security_data.get('aggressive_scanning', False))
        }
        
        # Load scheduled scan settings
        if os.path.exists('scheduled_scans_settings.json'):
            with open('scheduled_scans_settings.json', 'r') as f:
                scheduled_data = json.load(f)
        else:
            scheduled_data = load_schedule_config()
        
        # Normalize scheduled scan settings to frontend format
        settings['scheduledScans'] = {
            'enabled': scheduled_data.get('enabled', False),
            'frequency': scheduled_data.get('frequency', 'daily'),
            'time': scheduled_data.get('time', '02:00'),
            'scanType': scheduled_data.get('scanType', scheduled_data.get('scan_type', 'Full TCP')),
            'targetNetwork': scheduled_data.get('targetNetwork', scheduled_data.get('target_network', '172.16.0.0/22'))
        }
        
    except Exception as e:
        print(f'Error loading settings: {e}')
    
    return jsonify(settings)

@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Update application settings"""
    data = request.json
    try:
        # Update network settings
        if 'network' in data:
            # Convert frontend format to backend storage format
            network_settings = {
                'defaultTargetNetwork': data['network'].get('defaultTargetNetwork'),
                'maxHosts': data['network'].get('maxHosts'),
                'scanTimeout': data['network'].get('scanTimeout'),
                'concurrentScans': data['network'].get('concurrentScans', 1)
            }
            with open('network_settings.json', 'w') as f:
                json.dump(network_settings, f)
        
        # Update notification settings
        if 'notifications' in data:
            # Convert frontend format to backend storage format
            notification_settings = {
                'pushoverEnabled': data['notifications'].get('pushoverEnabled'),
                'scanComplete': data['notifications'].get('scanComplete', True),
                'vulnerabilityFound': data['notifications'].get('vulnerabilityFound', True),
                'newHostFound': data['notifications'].get('newHostFound', False)
            }
            with open('notification_settings.json', 'w') as f:
                json.dump(notification_settings, f)
        
        # Update security settings
        if 'security' in data:
            # Convert frontend format to backend storage format
            security_settings = {
                'vulnScanningEnabled': data['security'].get('vulnScanningEnabled'),
                'osDetectionEnabled': data['security'].get('osDetectionEnabled'),
                'serviceDetectionEnabled': data['security'].get('serviceDetectionEnabled'),
                'aggressiveScanning': data['security'].get('aggressiveScanning', False)
            }
            with open('security_settings.json', 'w') as f:
                json.dump(security_settings, f)
        
        # Update scheduled scan settings
        if 'scheduledScans' in data:
            # Convert frontend format to backend storage format
            scheduled_settings = {
                'enabled': data['scheduledScans'].get('enabled', False),
                'frequency': data['scheduledScans'].get('frequency', 'daily'),
                'time': data['scheduledScans'].get('time', '02:00'),
                'scanType': data['scheduledScans'].get('scanType', 'Full TCP'),
                'targetNetwork': data['scheduledScans'].get('targetNetwork', '172.16.0.0/22')
            }
            with open('scheduled_scans_settings.json', 'w') as f:
                json.dump(scheduled_settings, f)
        
        return jsonify({'status': 'ok'})
    except Exception as e:
        print(f'Error saving settings: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/network-interfaces', methods=['GET'])
def get_network_interfaces():
    """Get available network interfaces and their subnets"""
    try:
        import netifaces
        import ipaddress
        
        interfaces = []
        for interface in netifaces.interfaces():
            try:
                addrs = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addrs:
                    for addr_info in addrs[netifaces.AF_INET]:
                        ip = addr_info['addr']
                        netmask = addr_info['netmask']
                        
                        # Skip loopback and invalid addresses
                        if ip.startswith('127.') or ip.startswith('169.254.'):
                            continue
                            
                        # Calculate CIDR notation and network address
                        if ip and netmask:
                            try:
                                # Convert netmask to CIDR
                                netmask_bits = sum([bin(int(x)).count('1') for x in netmask.split('.')])
                                
                                # Calculate network address
                                network = ipaddress.IPv4Network(f"{ip}/{netmask_bits}", strict=False)
                                network_addr = str(network.network_address)
                                cidr = f"{network_addr}/{netmask_bits}"
                                
                                # Calculate number of hosts
                                hosts = network.num_addresses - 2  # Subtract network and broadcast
                                
                                interfaces.append({
                                    'interface': interface,
                                    'ip': ip,
                                    'netmask': netmask,
                                    'network': network_addr,
                                    'cidr': cidr,
                                    'broadcast': str(network.broadcast_address),
                                    'hosts': hosts,
                                    'display': f"{interface} - {cidr} ({hosts} hosts)"
                                })
                            except ValueError as e:
                                print(f"Error calculating network for {interface} {ip}/{netmask}: {e}")
                                continue
            except Exception as e:
                print(f"Error processing interface {interface}: {e}")
                continue
        
        # Sort interfaces by preference (en0, eth0 first, then others)
        def interface_priority(iface):
            name = iface['interface']
            if name == 'en0':
                return 0
            elif name.startswith('en'):
                return 1
            elif name.startswith('eth'):
                return 2
            elif name.startswith('bridge'):
                return 3
            else:
                return 4
        
        interfaces.sort(key=interface_priority)
        
        return jsonify({
            'interfaces': interfaces,
            'detected_count': len(interfaces)
        })
    except ImportError:
        # Fallback: Use ifconfig command (macOS/Linux compatible)
        try:
            import subprocess
            import re
            import ipaddress
            
            result = subprocess.run(['ifconfig'], capture_output=True, text=True, timeout=10)
            interfaces = []
            
            # Parse ifconfig output
            current_interface = None
            current_ip = None
            current_netmask = None
            
            for line in result.stdout.split('\n'):
                # Interface line (starts with interface name)
                if re.match(r'^[a-zA-Z]', line):
                    # Save previous interface if it had IP
                    if current_interface and current_ip and current_netmask:
                        try:
                            if not current_ip.startswith('127.') and not current_ip.startswith('169.254.'):
                                netmask_bits = sum([bin(int(x)).count('1') for x in current_netmask.split('.')])
                                network = ipaddress.IPv4Network(f"{current_ip}/{netmask_bits}", strict=False)
                                network_addr = str(network.network_address)
                                cidr = f"{network_addr}/{netmask_bits}"
                                hosts = network.num_addresses - 2
                                
                                interfaces.append({
                                    'interface': current_interface,
                                    'ip': current_ip,
                                    'netmask': current_netmask,
                                    'network': network_addr,
                                    'cidr': cidr,
                                    'broadcast': str(network.broadcast_address),
                                    'hosts': hosts,
                                    'display': f"{current_interface} - {cidr} ({hosts} hosts)"
                                })
                        except Exception as e:
                            print(f"Error processing ifconfig interface {current_interface}: {e}")
                    
                    # Start new interface
                    current_interface = line.split(':')[0]
                    current_ip = None
                    current_netmask = None
                
                # Look for inet line
                elif 'inet ' in line and 'netmask' in line:
                    parts = line.strip().split()
                    for i, part in enumerate(parts):
                        if part == 'inet' and i + 1 < len(parts):
                            current_ip = parts[i + 1]
                        elif part == 'netmask' and i + 1 < len(parts):
                            # Convert hex netmask to dotted decimal
                            hex_mask = parts[i + 1]
                            if hex_mask.startswith('0x'):
                                mask_int = int(hex_mask, 16)
                                current_netmask = '.'.join([str((mask_int >> (8 * (3 - i))) & 0xFF) for i in range(4)])
            
            # Don't forget the last interface
            if current_interface and current_ip and current_netmask:
                try:
                    if not current_ip.startswith('127.') and not current_ip.startswith('169.254.'):
                        netmask_bits = sum([bin(int(x)).count('1') for x in current_netmask.split('.')])
                        network = ipaddress.IPv4Network(f"{current_ip}/{netmask_bits}", strict=False)
                        network_addr = str(network.network_address)
                        cidr = f"{network_addr}/{netmask_bits}"
                        hosts = network.num_addresses - 2
                        
                        interfaces.append({
                            'interface': current_interface,
                            'ip': current_ip,
                            'netmask': current_netmask,
                            'network': network_addr,
                            'cidr': cidr,
                            'broadcast': str(network.broadcast_address),
                            'hosts': hosts,
                            'display': f"{current_interface} - {cidr} ({hosts} hosts)"
                        })
                except Exception as e:
                    print(f"Error processing final ifconfig interface {current_interface}: {e}")
            
            return jsonify({
                'interfaces': interfaces,
                'detected_count': len(interfaces),
                'method': 'ifconfig_fallback'
            })
        except Exception as e:
            print(f'Fallback ifconfig failed: {e}')
            # Ultimate fallback: return common networks
            return jsonify({
                'interfaces': [
                    {'interface': 'en0', 'ip': '192.168.1.1', 'netmask': '255.255.255.0', 'network': '192.168.1.0', 'cidr': '192.168.1.0/24', 'broadcast': '192.168.1.255', 'hosts': 254, 'display': 'en0 - 192.168.1.0/24 (254 hosts)'},
                    {'interface': 'eth0', 'ip': '172.16.0.1', 'netmask': '255.255.252.0', 'network': '172.16.0.0', 'cidr': '172.16.0.0/22', 'broadcast': '172.16.3.255', 'hosts': 1022, 'display': 'eth0 - 172.16.0.0/22 (1022 hosts)'},
                ],
                'detected_count': 2,
                'method': 'static_fallback'
            })
    except Exception as e:
        print(f'Error getting network interfaces: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/clear-all-data', methods=['POST'])
def clear_all_data():
    """Clear all scan data"""
    try:
        Scan.query.delete()
        Alert.query.delete()
        db.session.commit()
        return jsonify({'status': 'ok'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete-all-scans', methods=['POST'])
def delete_all_scans():
    try:
        num_deleted = Scan.query.delete()
        db.session.commit()
        return jsonify({'status': 'ok', 'deleted': num_deleted})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/test-pushover', methods=['POST', 'GET', 'OPTIONS'])
def test_pushover():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response, 204
    if request.method == 'GET':
        return jsonify({'status': 'ok', 'message': 'GET method works. Use POST to send a test notification.'})
    try:
        import requests
        import logging
        PUSHOVER_API_TOKEN = os.environ.get('PUSHOVER_API_TOKEN')
        PUSHOVER_USER_KEY = os.environ.get('PUSHOVER_USER_KEY')
        message = 'Test notification from SentinelZero!'
        resp = requests.post('https://api.pushover.net/1/messages.json', data={
            'token': PUSHOVER_API_TOKEN,
            'user': PUSHOVER_USER_KEY,
            'message': message,
            'priority': 0,
            'title': 'SentinelZero',
        })
        logging.info(f"[PUSHOVER TEST] Status: {resp.status_code}, Response: {resp.text}")
        if resp.status_code == 200:
            return jsonify({'status': 'ok', 'message': 'Pushover test sent.'})
        else:
            return jsonify({'status': 'error', 'message': f'Pushover failed: {resp.text}', 'code': resp.status_code}), 500
    except Exception as e:
        import logging
        logging.exception('[PUSHOVER TEST] Exception:')
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/scan-status/<int:scan_id>', methods=['GET'])
def get_scan_status(scan_id):
    scan = Scan.query.get(scan_id)
    if not scan:
        return jsonify({'error': 'Scan not found'}), 404
    return jsonify({
        'scan_id': scan.id,
        'status': scan.status,
        'percent': scan.percent,
        'message': f'Status: {scan.status}, {scan.percent:.1f}%',
    })

@app.route('/api/ping', methods=['GET'])
def ping():
    return jsonify({'status': 'ok', 'message': 'pong'})

@socketio.on('ping')
def handle_ping():
    print('[Socket.IO] Received ping from:', request.sid)
    emit('pong', {'message': 'pong'})

@app.route('/api/kill-all-scans', methods=['POST'])
def kill_all_scans():
    # Kill all running nmap processes
    killed_pids = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'nmap' in proc.info['name'] or (proc.info['cmdline'] and any('nmap' in arg for arg in proc.info['cmdline'])):
                proc.kill()
                killed_pids.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    # Update all active scans in DB
    active_statuses = ['pending', 'running', 'parsing', 'saving']
    scans = Scan.query.filter(Scan.status.in_(active_statuses)).all()
    for scan in scans:
        scan.status = 'cancelled'
        scan.percent = 0
    db.session.commit()
    return jsonify({
        'status': 'ok',
        'killed_pids': killed_pids,
        'cancelled_scans': [scan.id for scan in scans]
    })

# === WHAT'S UP STATUS MONITORING ===
# 3-Layer Status Architecture: Loopbacks → DNS/Services → Health Checks

# Layer 1: Host-Level Status (Loopback sentinels)
LOOPBACKS = [
    {"name": "LAN", "ip": "172.16.0.254", "description": "LAN health probe (172.16.0.0/22)", "interface": "eth0"},
    {"name": "VPN", "ip": "192.168.68.254", "description": "VPN tunnel probe (192.168.68.0/22)", "interface": "eth1"},
    {"name": "Localhost", "ip": "127.0.0.1", "description": "SentinelZero health probe", "interface": "lo"},
]

# Layer 2: DNS/Service Reachability  
SERVICES = [
    {"name": "Windows VM", "domain": "windowsVM.prox", "port": 3389, "type": "ping", "path": "/"},
    {"name": "Code Server", "domain": "code-server.prox", "port": 8080, "type": "http", "path": "/"},
    {"name": "Kali Linux", "domain": "kali.prox", "port": 22, "type": "ping", "path": "/"},
    {"name": "TJ Server", "ip": "192.168.71.30", "port": 22, "type": "ping", "path": "/"},
    {"name": "Homebridge", "ip": "192.168.68.79", "port": 22, "type": "ping", "path": "/"},
    {"name": "AI Market Bot", "domain": "aiMarketBot.prox", "port": 22, "type": "ping", "path": "/"},
]

# Layer 3: Critical Infrastructure
INFRASTRUCTURE = [
    # Proxmox Cluster
    {"name": "Proxmox Yin", "domain": "yin.prox", "type": "ping"},
    {"name": "Proxmox Yang", "domain": "yang.prox", "type": "ping"},
    {"name": "Proxmox Big", "domain": "proxBig.prox", "type": "ping"},
    # Network Infrastructure
    {"name": "OPNsense Firewall", "domain": "opnsense.prox", "type": "ping"},
    {"name": "Pi-hole Lab DNS", "ip": "192.168.71.25", "type": "dns", "query": "google.com"},
    {"name": "Home VPN", "ip": "192.168.71.40", "type": "ping"},
    {"name": "WireGuard VPN", "ip": "10.16.0.1", "type": "ping"},
    {"name": "Home Router", "ip": "192.168.68.1", "type": "ping"},
    {"name": "Home DNS Primary", "ip": "192.168.71.25", "type": "http", "port": 443, "path": "/admin/login", "use_https": True},
    {"name": "Home DNS Backup", "ip": "192.168.71.30", "type": "dns", "query": "windowsVM.prox"},
    # External DNS for comparison
    {"name": "Cloudflare DNS", "ip": "1.1.1.1", "type": "dns", "query": "google.com"},
    {"name": "Google DNS", "ip": "8.8.8.8", "type": "dns", "query": "google.com"},
]

def ping_ip(ip, timeout=1, retries=2, log_results=True):
    """Smart connectivity check with retries, detailed logging, and parallel execution support"""
    from datetime import datetime
    
    # Special case for localhost
    if ip == '127.0.0.1':
        return {"success": True, "method": "localhost", "response_time": 0, "attempts": 1}
    
    def log_ping_result(ip, result):
        """Log ping results with timestamp for debugging and monitoring"""
        if not log_results:
            return
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "ip": ip,
                "success": result["success"],
                "method": result.get("method", "unknown"),
                "response_time": result.get("response_time", None),
                "attempts": result.get("attempts", 1),
                "error": result.get("error", None)
            }
            
            # Append to daily log file
            log_file = f"logs/ping_{datetime.now().strftime('%Y-%m-%d')}.log"
            os.makedirs("logs", exist_ok=True)
            with open(log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            print(f"[DEBUG] Failed to log ping result: {e}")
    
    def try_icmp_ping(ip, timeout):
        """Try ICMP ping with structured error handling - macOS compatible"""
        import platform
        
        try:
            start_time = time.time()
            
            # On macOS, ping doesn't require sudo for basic ICMP
            if platform.system() == "Darwin":  # macOS
                result = subprocess.run(["ping", "-c1", "-W", str(int(timeout * 1000)), ip], 
                                      capture_output=True, text=True, timeout=timeout+2)
            else:  # Linux/other - may require sudo in some environments
                result = subprocess.run(["sudo", "ping", "-c1", f"-W{timeout}", ip], 
                                      capture_output=True, text=True, timeout=timeout+2)
            
            response_time = (time.time() - start_time) * 1000
            
            if result.returncode == 0:
                return {"success": True, "method": "icmp", "response_time": response_time, "error": None}
            else:
                # Parse ping error for better debugging
                error_msg = result.stderr.strip() or result.stdout.strip()
                return {"success": False, "method": "icmp", "response_time": None, 
                       "error": f"ICMP failed: {error_msg[:100]}"}
        except subprocess.TimeoutExpired:
            return {"success": False, "method": "icmp", "response_time": None, "error": "ICMP timeout"}
        except Exception as e:
            return {"success": False, "method": "icmp", "response_time": None, "error": f"ICMP error: {str(e)}"}
    
    def try_tcp_ports(ip, timeout):
        """Try TCP connectivity on common ports with detailed results"""
        common_ports = [22, 80, 443, 3389, 8080, 8581, 5353, 53]
        
        for port in common_ports:
            try:
                start_time = time.time()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                result = sock.connect_ex((ip, port))
                response_time = (time.time() - start_time) * 1000
                sock.close()
                
                if result == 0:
                    return {"success": True, "method": f"tcp:{port}", "response_time": response_time, "error": None}
            except Exception as e:
                continue
        
        return {"success": False, "method": "tcp", "response_time": None, "error": "No TCP ports responding"}
    
    def try_udp_ping(ip, timeout):
        """Try UDP ping to DNS port as last resort"""
        try:
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            sock.sendto(b'\x12\x34', (ip, 53))  # Simple DNS-like packet
            response_time = (time.time() - start_time) * 1000
            sock.close()
            return {"success": True, "method": "udp:53", "response_time": response_time, "error": None}
        except Exception as e:
            return {"success": False, "method": "udp", "response_time": None, "error": f"UDP error: {str(e)}"}
    
    # Retry logic with exponential backoff
    for attempt in range(retries + 1):
        if attempt > 0:
            time.sleep(0.1 * (2 ** (attempt - 1)))  # Exponential backoff: 0.1s, 0.2s, 0.4s...
        
        # Try methods in order of preference
        for method_func in [try_icmp_ping, try_tcp_ports, try_udp_ping]:
            result = method_func(ip, timeout)
            if result["success"]:
                result["attempts"] = attempt + 1
                log_ping_result(ip, result)
                return result
    
    # All methods failed after retries
    final_result = {"success": False, "method": "all_failed", "response_time": None, 
                   "attempts": retries + 1, "error": "All ping methods failed after retries"}
    log_ping_result(ip, final_result)
    return final_result

async def ping_multiple_ips_async(ip_list, timeout=1, retries=2):
    """Async parallel ping for multiple IPs - much faster for large lists"""
    
    async def ping_single_async(ip):
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, ping_ip, ip, timeout, retries, False)
            return ip, result
    
    tasks = [ping_single_async(ip) for ip in ip_list]
    results = await asyncio.gather(*tasks)
    return dict(results)

def resolve_domain(domain):
    """Resolve domain to IP with error handling"""
    try:
        ip = socket.gethostbyname(domain)
        return {"success": True, "ip": ip, "error": None}
    except socket.gaierror as e:
        return {"success": False, "ip": None, "error": str(e)}
    except Exception as e:
        return {"success": False, "ip": None, "error": f"Unknown error: {str(e)}"}

def check_http_service(domain, port, path="/", use_https=False, timeout=3):
    """Check HTTP/HTTPS service health"""
    try:
        protocol = "https" if use_https else "http"
        url = f"{protocol}://{domain}:{port}{path}"
        
        response = requests.get(url, timeout=timeout, verify=False)  # Ignore SSL for internal services
        return {
            "success": True,
            "status_code": response.status_code,
            "response_time": response.elapsed.total_seconds(),
            "error": None
        }
    except requests.exceptions.Timeout:
        return {"success": False, "status_code": None, "response_time": None, "error": "Timeout"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "status_code": None, "response_time": None, "error": "Connection refused"}
    except Exception as e:
        return {"success": False, "status_code": None, "response_time": None, "error": str(e)}

def check_dns_query(dns_server, query_domain, timeout=2):
    """Check DNS resolution capability"""
    try:
        result = subprocess.run(
            ["dig", "+short", f"@{dns_server}", query_domain],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0 and result.stdout.strip():
            return {"success": True, "result": result.stdout.strip(), "error": None}
        else:
            return {"success": False, "result": None, "error": "No response or query failed"}
    except subprocess.TimeoutExpired:
        return {"success": False, "result": None, "error": "DNS query timeout"}
    except Exception as e:
        return {"success": False, "result": None, "error": str(e)}

def get_loopbacks_data():
    """Core logic for checking loopbacks - returns raw data"""
    results = []
    for lb in LOOPBACKS:
        start_time = time.time()
        ping_result = ping_ip(lb["ip"], timeout=2, retries=1)  # Longer timeout for loopbacks
        total_time = (time.time() - start_time) * 1000
        
        results.append({
            "name": lb["name"],
            "ip": lb["ip"],
            "description": lb.get("description", ""),
            "interface": lb.get("interface", "unknown"),
            "status": "up" if ping_result["success"] else "down",
            "response_time_ms": ping_result.get("response_time", total_time) if ping_result["success"] else None,
            "method": ping_result.get("method", "unknown"),
            "attempts": ping_result.get("attempts", 1),
            "error": ping_result.get("error", None) if not ping_result["success"] else None
        })
    return results

@app.route('/api/whatsup/loopbacks')
def check_loopbacks():
    """Layer 1: Check loopback sentinels for network health"""
    return jsonify({"loopbacks": get_loopbacks_data()})

def check_specific_port_hping(ip, port, timeout=2):
    """Use hping3/nping for precise TCP port testing - with macOS compatibility"""
    import platform
    
    try:
        start_time = time.time()
        
        # Detect platform and choose appropriate tool
        if platform.system() == "Darwin":  # macOS
            # Use nping instead of hping3 on macOS - no sudo needed for non-privileged mode
            cmd = ['/opt/homebrew/bin/nping', '--tcp', '-p', str(port), '-c', '1', ip]
            tool_name = "nping"
        else:
            # Linux/other - use hping3 with sudo
            cmd = ['sudo', '/usr/sbin/hping3', '-S', '-p', str(port), '-c', '1', ip]
            tool_name = "hping3"
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 2)
        response_time = (time.time() - start_time) * 1000
        
        # Parse output for different response types
        output = result.stdout + result.stderr
        
        if tool_name == "nping":
            # Parse nping output (different format than hping3)
            if ("1 packets captured" in output or "RCVD" in output):
                return {"success": True, "response_time": response_time, "error": None, "method": "nping", "detail": "port_open"}
            elif ("0 packets captured" in output or result.returncode != 0):
                return {"success": False, "response_time": None, "error": f"Port {port} filtered/closed", "method": "nping", "detail": "port_closed"}
        else:
            # Parse hping3 output (original logic)
            if ("1 packets transmitted, 1 packets received" in output or 
                "flags=SA" in output or "flags=18" in output):
                return {"success": True, "response_time": response_time, "error": None, "method": "hping3", "detail": "port_open"}
            elif ("flags=RA" in output or "flags=4" in output or "ICMP Port Unreachable" in output):
                return {"success": False, "response_time": response_time, "error": f"Port {port} closed (RST)", "method": "hping3", "detail": "port_closed"}
            elif ("100% packet loss" in output or "0 packets received" in output or result.returncode != 0):
                return {"success": False, "response_time": None, "error": f"Port {port} filtered/firewalled", "method": "hping3", "detail": "port_filtered"}
        
        # Fallback for unexpected responses
        return {"success": False, "response_time": None, "error": f"Port {port} unknown response: {output[:50]}", "method": tool_name, "detail": "unknown"}
            
    except subprocess.TimeoutExpired:
        return {"success": False, "response_time": None, "error": f"Port {port} timeout", "method": tool_name, "detail": "timeout"}
    except FileNotFoundError:
        # Tool not found, fallback to socket
        print(f"[DEBUG] {tool_name if 'tool_name' in locals() else 'network tool'} not found, falling back to socket for {ip}:{port}")
        return check_specific_port_socket(ip, port, timeout)
    except Exception as e:
        # Any other error, fallback to socket method
        print(f"[DEBUG] {tool_name if 'tool_name' in locals() else 'network tool'} error for {ip}:{port}: {e}, falling back to socket")
        return check_specific_port_socket(ip, port, timeout)

def check_specific_port_socket(ip, port, timeout=2):
    """Fallback socket-based port checking with better error classification"""
    try:
        start_time = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        response_time = (time.time() - start_time) * 1000
        sock.close()
        
        if result == 0:
            return {"success": True, "response_time": response_time, "error": None, "method": "socket", "detail": "port_open"}
        elif result == 61:  # Connection refused (port closed, host up)
            return {"success": False, "response_time": response_time, "error": f"Port {port} closed (connection refused)", "method": "socket", "detail": "port_closed"}
        elif result == 60:  # Timeout (filtered/firewalled)
            return {"success": False, "response_time": None, "error": f"Port {port} filtered (timeout)", "method": "socket", "detail": "port_filtered"}
        else:
            return {"success": False, "response_time": None, "error": f"Port {port} error (code {result})", "method": "socket", "detail": "error"}
    except socket.timeout:
        return {"success": False, "response_time": None, "error": f"Port {port} timeout", "method": "socket", "detail": "timeout"}
    except Exception as e:
        return {"success": False, "response_time": None, "error": f"Port {port} error: {str(e)}", "method": "socket", "detail": "error"}

def verify_hping3_availability():
    """Check if hping3/nping is available and working"""
    import platform
    
    if platform.system() == "Darwin":  # macOS
        try:
            result = subprocess.run(['/opt/homebrew/bin/nping', '--version'], 
                                  capture_output=True, text=True, timeout=2)
            return True
        except:
            try:
                # Try alternative path for nping
                result = subprocess.run(['nping', '--version'], 
                                      capture_output=True, text=True, timeout=2)
                return True
            except:
                return False
    else:  # Linux/other
        try:
            result = subprocess.run(['/usr/sbin/hping3', '--version'], 
                                  capture_output=True, text=True, timeout=2)
            return True
        except:
            try:
                # Try alternative path
                result = subprocess.run(['hping3', '--version'], 
                                      capture_output=True, text=True, timeout=2)
                return True
            except:
                return False

def get_services_data():
    """Core logic for checking services - returns raw data with fast hping3-based testing"""
    results = []
    for service in SERVICES:
        result = {
            "name": service["name"],
            "port": service["port"],
            "type": service["type"],
            "path": service.get("path", "/"),
        }
        
        # Handle both domain-based and IP-based services
        if "domain" in service:
            # Domain-based service
            result["domain"] = service["domain"]
            
            # Step 1: DNS Resolution (fast timeout)
            dns_result = resolve_domain(service["domain"])
            result["dns"] = dns_result
            
            if dns_result["success"]:
                target_ip = dns_result["ip"]
                target_host = service["domain"]
            else:
                target_ip = None
                target_host = service["domain"]
        else:
            # IP-based service
            result["ip"] = service["ip"]
            target_ip = service["ip"]
            target_host = service["ip"]
            result["dns"] = {"success": True, "ip": target_ip, "error": None}  # Skip DNS for IP-based
        
        if target_ip:
            # Step 2: Basic ICMP connectivity check (short timeout)
            try:
                start_time = time.time()
                icmp_result = subprocess.run(["ping", "-c1", "-W1", target_ip], 
                                           capture_output=True, text=True, timeout=2)
                icmp_time = (time.time() - start_time) * 1000
                icmp_success = icmp_result.returncode == 0
            except:
                icmp_success = False
                icmp_time = None
            
            result["ping"] = {
                "success": icmp_success, 
                "ip": target_ip,
                "method": "icmp",
                "response_time_ms": icmp_time if icmp_success else None,
                "attempts": 1,
                "error": "ICMP timeout/failed" if not icmp_success else None
            }
            
            # Step 3: Service-Specific Port Check (the critical part)
            if service["type"] in ["http", "https"]:
                use_https = service["type"] == "https"
                service_result = check_http_service(
                    target_host, 
                    service["port"], 
                    service.get("path", "/"),
                    use_https,
                    timeout=3  # Short timeout for HTTP
                )
                result["service"] = service_result
                dns_ok = result["dns"]["success"]
                result["overall_status"] = "up" if (dns_ok and service_result["success"]) else "down"
            else:
                # Use hping3 for precise port testing
                port_result = check_specific_port_hping(target_ip, service["port"], timeout=2)
                result["service"] = {
                    "success": port_result["success"],
                    "response_time": port_result.get("response_time"),
                    "error": port_result.get("error") if not port_result["success"] else None,
                    "method": port_result.get("method", "unknown")
                }
                dns_ok = result["dns"]["success"]
                # Service is up only if DNS works AND the specific port is accessible
                result["overall_status"] = "up" if (dns_ok and port_result["success"]) else "down"
        else:
            result["ping"] = {"success": False, "ip": None}
            result["service"] = {"success": False, "error": "DNS resolution failed"}
            result["overall_status"] = "down"
            
        results.append(result)
    
    return results

@app.route('/api/whatsup/services')
def check_services():
    """Layer 2: Check DNS resolution and service reachability"""
    return jsonify({"services": get_services_data()})

def get_infrastructure_data():
    """Core logic for checking infrastructure - returns raw data"""
    results = []
    for infra in INFRASTRUCTURE:
        result = {
            "name": infra["name"],
            "type": infra["type"],
        }
        
        # Handle both domain-based and IP-based infrastructure
        if "domain" in infra:
            result["domain"] = infra["domain"]
            # Resolve domain to IP first
            if infra["type"] == "ping":
                dns_result = resolve_domain(infra["domain"])
                if dns_result["success"]:
                    target_ip = dns_result["ip"]
                    start_time = time.time()
                    ping_result = ping_ip(target_ip, timeout=2, retries=1)
                    total_time = (time.time() - start_time) * 1000
                    
                    result["status"] = "up" if ping_result["success"] else "down"
                    result["response_time_ms"] = ping_result.get("response_time", total_time) if ping_result["success"] else None
                    result["method"] = ping_result.get("method", "unknown")
                    result["attempts"] = ping_result.get("attempts", 1)
                    result["ip"] = target_ip
                    result["details"] = ping_result.get("error") if not ping_result["success"] else None
                else:
                    result["status"] = "down"
                    result["details"] = f"DNS resolution failed: {dns_result['error']}"
            elif infra["type"] == "dns":
                # For DNS queries against domains, we need to resolve the domain first
                dns_result = resolve_domain(infra["domain"])
                if dns_result["success"]:
                    dns_query_result = check_dns_query(dns_result["ip"], infra["query"])
                    result["status"] = "up" if dns_query_result["success"] else "down"
                    result["details"] = dns_query_result["result"] if dns_query_result["success"] else dns_query_result["error"]
                    result["query"] = infra["query"]
                    result["ip"] = dns_result["ip"]
                else:
                    result["status"] = "down"
                    result["details"] = f"DNS server resolution failed: {dns_result['error']}"
                    result["query"] = infra["query"]
        else:
            # IP-based infrastructure
            result["ip"] = infra["ip"]
            
            if infra["type"] == "ping":
                start_time = time.time()
                ping_result = ping_ip(infra["ip"], timeout=2, retries=1)
                total_time = (time.time() - start_time) * 1000
                
                result["status"] = "up" if ping_result["success"] else "down"
                result["response_time_ms"] = ping_result.get("response_time", total_time) if ping_result["success"] else None
                result["method"] = ping_result.get("method", "unknown")
                result["attempts"] = ping_result.get("attempts", 1)
                result["details"] = ping_result.get("error") if not ping_result["success"] else None
                
            elif infra["type"] == "dns":
                dns_result = check_dns_query(infra["ip"], infra["query"])
                result["status"] = "up" if dns_result["success"] else "down"
                result["details"] = dns_result["result"] if dns_result["success"] else dns_result["error"]
                result["query"] = infra["query"]
                
            elif infra["type"] == "http":
                # HTTP check for infrastructure (like Pi-hole admin interface)
                port = infra.get("port", 80)
                path = infra.get("path", "/")
                use_https = infra.get("use_https", False)
                
                http_result = check_http_service(infra["ip"], port, path, use_https)
                result["status"] = "up" if http_result["success"] else "down"
                result["details"] = f"HTTP {http_result['status_code']}" if http_result["status_code"] else http_result["error"]
                result["port"] = port
                result["path"] = path
                result["response_time_ms"] = round(http_result["response_time"] * 1000, 1) if http_result["response_time"] else None
            
        results.append(result)
    
    return results

@app.route('/api/whatsup/infrastructure')
def check_infrastructure():
    """Layer 3: Check critical infrastructure components"""
    return jsonify({"infrastructure": get_infrastructure_data()})

@app.route('/api/whatsup/summary')
def whatsup_summary():
    """Consolidated status summary for dashboard"""
    try:
        # Get all layer results by calling the logic functions directly
        loopbacks_result = get_loopbacks_data()
        services_result = get_services_data()
        infrastructure_result = get_infrastructure_data()
        
        # Calculate summary stats
        loopback_up = sum(1 for lb in loopbacks_result if lb["status"] == "up")
        services_up = sum(1 for svc in services_result if svc["overall_status"] == "up")
        infra_up = sum(1 for inf in infrastructure_result if inf["status"] == "up")
        
        total_checks = len(loopbacks_result) + len(services_result) + len(infrastructure_result)
        total_up = loopback_up + services_up + infra_up
        
        overall_health = "healthy" if total_up == total_checks else "degraded" if total_up > total_checks * 0.7 else "critical"
        
        return jsonify({
            "overall_health": overall_health,
            "total_checks": total_checks,
            "total_up": total_up,
            "layers": {
                "loopbacks": {"up": loopback_up, "total": len(loopbacks_result)},
                "services": {"up": services_up, "total": len(services_result)},
                "infrastructure": {"up": infra_up, "total": len(infrastructure_result)}
            },
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/whatsup/bulk-ping', methods=['POST'])
def bulk_ping():
    """Parallel ping multiple IPs for faster bulk monitoring"""
    
    data = request.json
    ip_list = data.get('ips', [])
    timeout = data.get('timeout', 2)
    retries = data.get('retries', 1)
    
    if not ip_list:
        return jsonify({"error": "No IPs provided"}), 400
    
    # Run async ping for all IPs
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(
            ping_multiple_ips_async(ip_list, timeout, retries)
        )
        loop.close()
        
        return jsonify({
            "results": results,
            "summary": {
                "total": len(ip_list),
                "up": sum(1 for r in results.values() if r["success"]),
                "down": sum(1 for r in results.values() if not r["success"])
            }
        })
    except Exception as e:
        return jsonify({"error": f"Bulk ping failed: {str(e)}"}), 500

@app.route('/api/whatsup/ping-logs')
def get_ping_logs():
    """Get recent ping logs for debugging and monitoring trends"""
    from datetime import datetime, timedelta
    
    try:
        logs = []
        # Get logs from last 7 days
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            log_file = f"logs/ping_{date}.log"
            
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    for line in f:
                        try:
                            log_entry = json.loads(line.strip())
                            logs.append(log_entry)
                        except:
                            continue
        
        # Sort by timestamp, most recent first
        logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Limit to last 1000 entries to avoid overwhelming the client
        logs = logs[:1000]
        
        return jsonify({
            "logs": logs,
            "summary": {
                "total_entries": len(logs),
                "failed_pings": len([l for l in logs if not l.get('success', True)]),
                "unique_ips": len(set(l.get('ip') for l in logs if l.get('ip')))
            }
        })
    except Exception as e:
        return jsonify({"error": f"Failed to load ping logs: {str(e)}"}), 500

@app.route('/api/whatsup/network-topology')
def check_network_topology():
    """Check network topology and interface health before services"""
    
    try:
        # Check our own interfaces first
        interface_status = {}
        for loopback in LOOPBACKS:
            interface = loopback.get("interface", "unknown")
            if interface != "unknown":
                try:
                    # Check if interface is up
                    result = subprocess.run(["ip", "link", "show", interface], 
                                          capture_output=True, text=True, timeout=5)
                    interface_up = "state UP" in result.stdout
                    interface_status[interface] = {
                        "name": interface,
                        "status": "up" if interface_up else "down", 
                        "sentinel_ip": loopback["ip"],
                        "description": loopback["description"]
                    }
                except Exception as e:
                    interface_status[interface] = {
                        "name": interface,
                        "status": "error",
                        "error": str(e),
                        "sentinel_ip": loopback["ip"]
                    }
        
        # Check routing table for default routes
        try:
            route_result = subprocess.run(["ip", "route", "show", "default"], 
                                        capture_output=True, text=True, timeout=5)
            default_routes = len(route_result.stdout.strip().split('\n')) if route_result.stdout.strip() else 0
        except Exception:
            default_routes = 0
        
        return jsonify({
            "interfaces": interface_status,
            "routing": {
                "default_routes": default_routes,
                "status": "ok" if default_routes > 0 else "no_default_route"
            },
            "recommendation": "Check interfaces before services" if any(
                iface["status"] != "up" for iface in interface_status.values()
            ) else "All interfaces healthy"
        })
    except Exception as e:
        return jsonify({"error": f"Network topology check failed: {str(e)}"}), 500

@app.route('/api/whatsup/config', methods=['GET'])
def get_whatsup_config():
    """Get current What's Up configuration"""
    try:
        if os.path.exists('whatsup_config.json'):
            with open('whatsup_config.json', 'r') as f:
                custom_config = json.load(f)
                return jsonify(custom_config)
        else:
            # Return default configuration
            return jsonify({
                "loopbacks": LOOPBACKS,
                "services": SERVICES,
                "infrastructure": INFRASTRUCTURE
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/whatsup/config', methods=['POST'])
def update_whatsup_config():
    """Update What's Up configuration"""
    try:
        data = request.json
        
        # Validate the structure
        required_keys = ['loopbacks', 'services', 'infrastructure']
        for key in required_keys:
            if key not in data:
                return jsonify({"error": f"Missing required key: {key}"}), 400
        
        # Save to file
        with open('whatsup_config.json', 'w') as f:
            json.dump(data, f, indent=2)
        
        # Update global variables (for this session)
        global LOOPBACKS, SERVICES, INFRASTRUCTURE
        LOOPBACKS = data['loopbacks']
        SERVICES = data['services'] 
        INFRASTRUCTURE = data['infrastructure']
        
        return jsonify({"status": "ok", "message": "Configuration updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/whatsup/test/<test_type>')
def test_individual_component(test_type):
    """Test individual components for troubleshooting"""
    test_ip = request.args.get('ip')
    test_domain = request.args.get('domain')
    test_port = request.args.get('port', type=int)
    
    if test_type == 'ping' and test_ip:
        result = ping_ip(test_ip)
        return jsonify({"test": "ping", "target": test_ip, "success": result})
    
    elif test_type == 'dns' and test_domain:
        result = resolve_domain(test_domain)
        return jsonify({"test": "dns", "target": test_domain, "result": result})
    
    elif test_type == 'http' and test_domain and test_port:
        use_https = request.args.get('https', 'false').lower() == 'true'
        path = request.args.get('path', '/')
        result = check_http_service(test_domain, test_port, path, use_https)
        return jsonify({"test": "http", "target": f"{test_domain}:{test_port}{path}", "result": result})
    
    else:
        return jsonify({"error": "Invalid test type or missing parameters"}), 400

# Catch-all route for React Router (must be last)
@app.route('/<path:path>')
def catch_all(path):
    # Don't serve index.html for API routes
    if path.startswith('api/'):
        return jsonify({'error': 'API endpoint not found'}), 404
    
    # Serve static files if they exist
    if os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    
    # For all other routes, serve the React app
    if os.path.exists(os.path.join(app.static_folder, 'index.html')):
        return send_from_directory(app.static_folder, 'index.html')
    
    return "React app not found", 404

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, host='0.0.0.0', port=5000)