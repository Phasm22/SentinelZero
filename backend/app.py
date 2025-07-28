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
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
import json as pyjson
import sys
import psutil

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
    socketio.emit('scan_log', {'msg': '404 Not Found'})
    if is_api_request():
        return jsonify({'error': 'Not found', 'code': 404}), 404
    return render_template('error.html', code=404, message='Page not found'), 404

@app.errorhandler(400)
def bad_request_error(error):
    socketio.emit('scan_log', {'msg': '400 Bad Request - Unicode error from nmap probes'})
    if is_api_request():
        return jsonify({'error': 'Bad request', 'code': 400}), 400
    return render_template('error.html', code=400, message='Bad request - Unicode error from nmap probes'), 400

@app.errorhandler(500)
def internal_error(error):
    socketio.emit('scan_log', {'msg': '500 Internal Server Error'})
    if is_api_request():
        return jsonify({'error': 'Internal server error', 'code': 500}), 500
    return render_template('error.html', code=500, message='Internal server error'), 500

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
                settings['network'] = json.load(f)
        else:
            settings['network'] = {
                'target_network': '172.16.0.0/22',
                'max_hosts': 1000,
                'scan_timeout': 300
            }
        
        # Load notification settings
        if os.path.exists('notification_settings.json'):
            with open('notification_settings.json', 'r') as f:
                settings['notifications'] = json.load(f)
        else:
            settings['notifications'] = {
                'pushover_enabled': bool(PUSHOVER_API_TOKEN and PUSHOVER_USER_KEY),
                'pushover_token': PUSHOVER_API_TOKEN or '',
                'pushover_user_key': PUSHOVER_USER_KEY or ''
            }
        # Always set pushoverConfigured based on env
        settings['notifications']['pushoverConfigured'] = bool(os.environ.get('PUSHOVER_API_TOKEN') and os.environ.get('PUSHOVER_USER_KEY'))
        
        # Load security settings
        if os.path.exists('security_settings.json'):
            with open('security_settings.json', 'r') as f:
                settings['security'] = json.load(f)
        else:
            settings['security'] = {
                'vuln_scanning_enabled': True,
                'os_detection_enabled': True,
                'service_detection_enabled': True
            }
        
        # Load scheduled scan settings
        if os.path.exists('scheduled_scans_settings.json'):
            with open('scheduled_scans_settings.json', 'r') as f:
                settings['scheduledScans'] = json.load(f)
        else:
            settings['scheduledScans'] = load_schedule_config()
        
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
            with open('network_settings.json', 'w') as f:
                json.dump(data['network'], f)
        
        # Update notification settings
        if 'notifications' in data:
            with open('notification_settings.json', 'w') as f:
                json.dump(data['notifications'], f)
        
        # Update security settings
        if 'security' in data:
            with open('security_settings.json', 'w') as f:
                json.dump(data['security'], f)
        
        # Update scheduled scan settings
        if 'scheduledScans' in data:
            with open('scheduled_scans_settings.json', 'w') as f:
                json.dump(data['scheduledScans'], f)
        
        return jsonify({'status': 'ok'})
    except Exception as e:
        print(f'Error saving settings: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/network-interfaces', methods=['GET'])
def get_network_interfaces():
    """Get available network interfaces and their subnets"""
    try:
        import netifaces
        
        interfaces = []
        for interface in netifaces.interfaces():
            try:
                addrs = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addrs:
                    for addr_info in addrs[netifaces.AF_INET]:
                        ip = addr_info['addr']
                        netmask = addr_info['netmask']
                        
                        # Calculate CIDR notation
                        if ip and netmask:
                            # Convert netmask to CIDR
                            netmask_bits = sum([bin(int(x)).count('1') for x in netmask.split('.')])
                            cidr = f"{ip}/{netmask_bits}"
                            
                            interfaces.append({
                                'name': interface,
                                'ip': ip,
                                'netmask': netmask,
                                'cidr': cidr,
                                'display': f"{interface} ({cidr})"
                            })
            except Exception as e:
                print(f"Error processing interface {interface}: {e}")
                continue
        
        # Add some common network ranges
        common_networks = [
            {'name': 'Localhost', 'ip': '127.0.0.1', 'netmask': '255.255.255.0', 'cidr': '127.0.0.0/24', 'display': 'Localhost (127.0.0.0/24)'},
            {'name': 'Private Class A', 'ip': '10.0.0.1', 'netmask': '255.0.0.0', 'cidr': '10.0.0.0/8', 'display': 'Private Class A (10.0.0.0/8)'},
            {'name': 'Private Class B', 'ip': '172.16.0.1', 'netmask': '255.240.0.0', 'cidr': '172.16.0.0/12', 'display': 'Private Class B (172.16.0.0/12)'},
            {'name': 'Private Class C', 'ip': '192.168.0.1', 'netmask': '255.255.0.0', 'cidr': '192.168.0.0/16', 'display': 'Private Class C (192.168.0.0/16)'},
        ]
        
        return jsonify({
            'interfaces': interfaces,
            'common_networks': common_networks
        })
    except ImportError:
        # If netifaces is not available, return common networks only
        return jsonify({
            'interfaces': [],
            'common_networks': [
                {'name': 'Localhost', 'ip': '127.0.0.1', 'netmask': '255.255.255.0', 'cidr': '127.0.0.0/24', 'display': 'Localhost (127.0.0.0/24)'},
                {'name': 'Private Class A', 'ip': '10.0.0.1', 'netmask': '255.0.0.0', 'cidr': '10.0.0.0/8', 'display': 'Private Class A (10.0.0.0/8)'},
                {'name': 'Private Class B', 'ip': '172.16.0.1', 'netmask': '255.240.0.0', 'cidr': '172.16.0.0/12', 'display': 'Private Class B (172.16.0.0/12)'},
                {'name': 'Private Class C', 'ip': '192.168.0.1', 'netmask': '255.255.0.0', 'cidr': '192.168.0.0/16', 'display': 'Private Class C (192.168.0.0/16)'},
            ]
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

def ping_ip(ip, timeout=1):
    """Fast connectivity check with timeout - uses TCP socket for compatibility"""
    import subprocess
    import socket
    
    # Special case for localhost
    if ip == '127.0.0.1':
        return True
    
    try:
        # First try ICMP ping (will work if privileges allow)
        result = subprocess.run(["ping", "-c1", f"-W1", ip], 
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
        if result.returncode == 0:
            return True
    except Exception:
        pass
    
    # Fallback to TCP connectivity check for common ports
    try:
        # Test a broader range of common ports for better coverage
        common_ports = [22, 80, 443, 3389, 8080, 8581, 5353, 53]
        
        for port in common_ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.0)  # Slightly longer timeout for reliability
                result = sock.connect_ex((ip, port))
                sock.close()
                if result == 0:
                    return True
            except:
                continue
        
        # If no TCP ports respond, try a UDP ping to port 53 (DNS)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(1.0)
            sock.sendto(b'\x00', (ip, 53))
            sock.close()
            return True
        except:
            pass
        
        return False
        
    except Exception:
        return False

def resolve_domain(domain):
    """Resolve domain to IP with error handling"""
    import socket
    try:
        ip = socket.gethostbyname(domain)
        return {"success": True, "ip": ip, "error": None}
    except socket.gaierror as e:
        return {"success": False, "ip": None, "error": str(e)}
    except Exception as e:
        return {"success": False, "ip": None, "error": f"Unknown error: {str(e)}"}

def check_http_service(domain, port, path="/", use_https=False, timeout=3):
    """Check HTTP/HTTPS service health"""
    import requests
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
    import subprocess
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

@app.route('/api/whatsup/loopbacks')
def check_loopbacks():
    """Layer 1: Check loopback sentinels for network health"""
    results = []
    for lb in LOOPBACKS:
        start_time = time.time()
        is_up = ping_ip(lb["ip"])
        response_time = (time.time() - start_time) * 1000  # Convert to ms
        
        results.append({
            "name": lb["name"],
            "ip": lb["ip"],
            "description": lb.get("description", ""),
            "interface": lb.get("interface", "unknown"),
            "status": "up" if is_up else "down",
            "response_time_ms": round(response_time, 1) if is_up else None
        })
    return jsonify({"loopbacks": results})

@app.route('/api/whatsup/services')
def check_services():
    """Layer 2: Check DNS resolution and service reachability"""
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
            
            # Step 1: DNS Resolution
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
            # Step 2: Ping IP
            ping_result = ping_ip(target_ip)
            result["ping"] = {"success": ping_result, "ip": target_ip}
            
            # Step 3: Service Health Check
            if service["type"] in ["http", "https"]:
                use_https = service["type"] == "https"
                http_result = check_http_service(
                    target_host, 
                    service["port"], 
                    service.get("path", "/"),
                    use_https
                )
                result["service"] = http_result
                dns_ok = result["dns"]["success"]
                result["overall_status"] = "up" if (dns_ok and ping_result and http_result["success"]) else "down"
            else:
                result["service"] = {"success": ping_result, "error": None if ping_result else "Service unreachable"}
                dns_ok = result["dns"]["success"]
                result["overall_status"] = "up" if (dns_ok and ping_result) else "down"
        else:
            result["ping"] = {"success": False, "ip": None}
            result["service"] = {"success": False, "error": "DNS resolution failed"}
            result["overall_status"] = "down"
            
        results.append(result)
    
    return jsonify({"services": results})

@app.route('/api/whatsup/infrastructure')
def check_infrastructure():
    """Layer 3: Check critical infrastructure components"""
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
                    is_up = ping_ip(target_ip)
                    response_time = (time.time() - start_time) * 1000
                    
                    result["status"] = "up" if is_up else "down"
                    result["response_time_ms"] = round(response_time, 1) if is_up else None
                    result["ip"] = target_ip
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
                is_up = ping_ip(infra["ip"])
                response_time = (time.time() - start_time) * 1000
                
                result["status"] = "up" if is_up else "down"
                result["response_time_ms"] = round(response_time, 1) if is_up else None
                result["details"] = None
                
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
    
    return jsonify({"infrastructure": results})

@app.route('/api/whatsup/summary')
def whatsup_summary():
    """Consolidated status summary for dashboard"""
    try:
        # Get all layer results
        from flask import current_app
        with current_app.test_request_context():
            loopbacks = check_loopbacks().get_json()["loopbacks"]
            services = check_services().get_json()["services"] 
            infrastructure = check_infrastructure().get_json()["infrastructure"]
        
        # Calculate summary stats
        loopback_up = sum(1 for lb in loopbacks if lb["status"] == "up")
        services_up = sum(1 for svc in services if svc["overall_status"] == "up")
        infra_up = sum(1 for inf in infrastructure if inf["status"] == "up")
        
        total_checks = len(loopbacks) + len(services) + len(infrastructure)
        total_up = loopback_up + services_up + infra_up
        
        overall_health = "healthy" if total_up == total_checks else "degraded" if total_up > total_checks * 0.7 else "critical"
        
        return jsonify({
            "overall_health": overall_health,
            "total_checks": total_checks,
            "total_up": total_up,
            "layers": {
                "loopbacks": {"up": loopback_up, "total": len(loopbacks)},
                "services": {"up": services_up, "total": len(services)},
                "infrastructure": {"up": infra_up, "total": len(infrastructure)}
            },
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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