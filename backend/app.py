import eventlet
eventlet.monkey_patch()
import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, Response
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

app = Flask(__name__)
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
    def as_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'scan_type': self.scan_type,
            'hosts_json': self.hosts_json,
            'diff_from_previous': self.diff_from_previous,
            'vulns_json': self.vulns_json,
            'raw_xml_path': self.raw_xml_path,
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

def run_nmap_scan(scan_type):
    with app.app_context():
        try:
            msg = f'Thread started for scan: {scan_type} (scheduled={threading.current_thread().name.startswith("APScheduler")})'
            try:
                socketio.emit('scan_log', {'msg': msg})
            except Exception as e:
                print(f'[DEBUG] Could not emit to socketio: {e}')
            print(msg)
            now = datetime.now().strftime('%Y-%m-%d_%H%M')
            if scan_type == 'Full TCP':
                xml_path = f'scans/full_tcp_{now}.xml'
                cmd = [
                    'nmap', '-v', '-sS', '-T4', '-p-', '--open', '-O', '-sV',
                    '172.16.0.0/22', '-oX', xml_path
                ]
            elif scan_type == 'IoT Scan':
                xml_path = f'scans/iot_scan_{now}.xml'
                cmd = [
                    'nmap', '-v', '-sU', '-T4', '-p', '53,67,68,80,443,1900,5353,554,8080',
                    '172.16.0.0/22', '-oX', xml_path
                ]
            elif scan_type == 'Vuln Scripts':
                xml_path = f'scans/vuln_scripts_{now}.xml'
                cmd = [
                    'nmap', '-v', '-sS', '-T4', '-p-', '--open', '-sV', '--script=vuln',
                    '172.16.0.0/22', '-oX', xml_path
                ]
            else:
                msg = f'Unknown scan type: {scan_type}'
                try:
                    socketio.emit('scan_log', {'msg': msg})
                except Exception as e:
                    print(f'[DEBUG] Could not emit to socketio: {e}')
                print(msg)
                return
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
                try:
                    socketio.emit('scan_log', {'msg': line.rstrip()})
                except Exception as e:
                    print(f'[DEBUG] Could not emit to socketio: {e}')
                match = re.search(r'About ([0-9.]+)% done', line)
                if match:
                    percent = float(match.group(1))
                    try:
                        socketio.emit('scan_progress', {'percent': percent})
                    except Exception as e:
                        print(f'[DEBUG] Could not emit scan_progress: {e}')
            proc.wait()
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
                msg = f'nmap error: {proc.returncode}'
                try:
                    socketio.emit('scan_log', {'msg': msg})
                except Exception as e:
                    print(f'[DEBUG] Could not emit to socketio: {e}')
                print(msg)
                send_pushover_alert(f'Scan failed: {scan_type}', 'danger')
                return
            msg = 'Parsing XML results...'
            try:
                socketio.emit('scan_log', {'msg': msg})
            except Exception as e:
                print(f'[DEBUG] Could not emit to socketio: {e}')
            print(msg)
            hosts = []
            vulns = []
            try:
                tree = ET.parse(xml_path)
                root = tree.getroot()
                for host in root.findall('host'):
                    status = host.find('status')
                    if status is not None and status.attrib.get('state') == 'up':
                        addr = host.find('address')
                        if addr is not None:
                            hosts.append(addr.attrib.get('addr'))
                    for script in host.findall('.//script'):
                        if 'vuln' in script.attrib.get('id', ''):
                            vulns.append(script.attrib.get('output', ''))
                msg = f'Parsed {len(hosts)} hosts, {len(vulns)} vulns.'
                try:
                    socketio.emit('scan_log', {'msg': msg})
                except Exception as e:
                    print(f'[DEBUG] Could not emit to socketio: {e}')
                print(msg)
            except Exception as e:
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
            msg = 'Saving scan results to database...'
            try:
                socketio.emit('scan_log', {'msg': msg})
            except Exception as e:
                print(f'[DEBUG] Could not emit to socketio: {e}')
            print(msg)
            scan = Scan(
                scan_type=scan_type,
                hosts_json=json.dumps(hosts),
                diff_from_previous='{}',
                vulns_json=json.dumps(vulns),
                raw_xml_path=xml_path
            )
            db.session.add(scan)
            db.session.commit()
            msg = 'Scan results saved.'
            try:
                socketio.emit('scan_log', {'msg': msg})
            except Exception as e:
                print(f'[DEBUG] Could not emit to socketio: {e}')
            print(msg)
            socketio.emit('scan_complete', {'msg': f'Scan complete: {scan_type}'})
            send_pushover_alert(f'Scan complete: {scan_type}', 'info', scan.id)
        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
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

@app.errorhandler(404)
def not_found_error(error):
    socketio.emit('scan_log', {'msg': '404 Not Found'})
    return render_template('error.html', code=404, message='Page not found'), 404

@app.errorhandler(400)
def bad_request_error(error):
    socketio.emit('scan_log', {'msg': '400 Bad Request - Unicode error from nmap probes'})
    return render_template('error.html', code=400, message='Bad request - Unicode error from nmap probes'), 400

@app.errorhandler(500)
def internal_error(error):
    socketio.emit('scan_log', {'msg': '500 Internal Server Error'})
    return render_template('error.html', code=500, message='Internal server error'), 500

@app.errorhandler(Exception)
def handle_exception(e):
    print("=== Uncaught Exception ===", file=sys.stderr)
    import traceback
    traceback.print_exc()
    return jsonify({'error': str(e)}), 500

@app.route('/scan', methods=['POST'])
def trigger_scan():
    scan_type = request.form.get('scan_type', 'Full TCP')
    threading.Thread(target=run_nmap_scan, args=(scan_type,), daemon=True).start()
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
    emit('scan_log', {'msg': 'Connected to SentinelZero'})

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
        settings['notifications'] = {
            'pushover_enabled': bool(PUSHOVER_API_TOKEN and PUSHOVER_USER_KEY),
            'pushover_token': PUSHOVER_API_TOKEN or '',
            'pushover_user_key': PUSHOVER_USER_KEY or ''
        }
        
        # Load security settings
        settings['security'] = {
            'vuln_scanning_enabled': True,
            'os_detection_enabled': True,
            'service_detection_enabled': True
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
            with open('network_settings.json', 'w') as f:
                json.dump(data['network'], f)
        
        # Update notification settings (environment variables)
        if 'notifications' in data:
            # Note: In a real app, you'd want to persist these securely
            # For now, we'll just acknowledge the update
            pass
        
        # Update security settings
        if 'security' in data:
            # Note: In a real app, you'd want to persist these
            pass
        
        return jsonify({'status': 'ok'})
    except Exception as e:
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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, host='0.0.0.0', port=5000) 