import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from ..models.scan import Scan
from ..services.scanner import parse_vulners_output, should_include_vulnerability

def create_upload_blueprint(db, socketio):
    bp = Blueprint('upload', __name__)

    @bp.route('/upload-scan', methods=['POST'])
    def upload_scan():
        """Upload and parse an nmap XML file"""
        try:
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            # Check file extension
            if not file.filename.lower().endswith('.xml'):
                return jsonify({'error': 'File must be an XML file'}), 400
            
            # Get scan metadata from form
            scan_type = request.form.get('scan_type', 'Uploaded Scan')
            
            # Read and validate XML content
            xml_content = file.read().decode('utf-8')
            
            # Validate it's an nmap XML file
            if 'nmaprun' not in xml_content:
                return jsonify({'error': 'File does not appear to be an nmap XML file'}), 400
            
            # Create scan record
            scan = Scan(
                scan_type=scan_type,
                status='parsing',
                percent=0.0,
                timestamp=datetime.utcnow()
            )
            db.session.add(scan)
            db.session.commit()
            scan_id = scan.id
            
            # Save XML file
            now = datetime.now().strftime('%Y-%m-%d_%H%M')
            safe_filename = secure_filename(f'uploaded_{scan_type.lower().replace(" ", "_")}_{now}.xml')
            xml_path = f'scans/{safe_filename}'
            
            os.makedirs('scans', exist_ok=True)
            with open(xml_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            
            # Parse XML
            hosts, vulns = parse_nmap_xml(xml_content, scan_id)
            
            # Update scan with results
            scan.hosts_json = json.dumps(hosts)
            scan.vulns_json = json.dumps(vulns)
            scan.raw_xml_path = xml_path
            scan.status = 'complete'
            scan.percent = 100.0
            scan.hosts_count = len(hosts)
            scan.vulns_count = len(vulns)
            scan.completed_at = datetime.utcnow()
            
            db.session.commit()
            
            # Emit completion event via socketio
            if socketio:
                try:
                    socketio.emit('scan_progress', {
                        'scan_id': scan_id,
                        'status': 'complete',
                        'percent': 100,
                        'message': f'Upload complete: {len(hosts)} hosts, {len(vulns)} vulnerabilities'
                    })
                except Exception as e:
                    print(f'[DEBUG] Could not emit to socketio: {e}')
            
            return jsonify({
                'status': 'success',
                'message': f'Scan uploaded successfully',
                'scan_id': scan_id,
                'hosts_count': len(hosts),
                'vulns_count': len(vulns)
            })
            
        except ET.ParseError as e:
            return jsonify({'error': f'Invalid XML format: {str(e)}'}), 400
        except Exception as e:
            print(f'[DEBUG] Upload error: {e}')
            return jsonify({'error': f'Upload failed: {str(e)}'}), 500

    return bp

def parse_nmap_xml(xml_content, scan_id):
    """Parse nmap XML content and extract hosts and vulnerabilities"""
    hosts = []
    vulns = []
    
    try:
        root = ET.fromstring(xml_content)
        
        for host in root.findall('host'):
            status = host.find('status')
            if status is not None and status.attrib.get('state') == 'up':
                host_obj = {}
                
                # Get IP address
                addr = host.find('address[@addrtype="ipv4"]')
                if addr is not None:
                    host_obj['ip'] = addr.attrib.get('addr')
                
                # Get MAC address and vendor
                mac = host.find('address[@addrtype="mac"]')
                if mac is not None:
                    host_obj['mac'] = mac.attrib.get('addr')
                    if 'vendor' in mac.attrib:
                        host_obj['vendor'] = mac.attrib['vendor']
                
                # Get hostnames
                hostnames = host.find('hostnames')
                if hostnames is not None:
                    host_obj['hostnames'] = [hn.attrib.get('name') for hn in hostnames.findall('hostname') if hn.attrib.get('name')]
                
                # Get distance
                distance = host.find('distance')
                if distance is not None:
                    host_obj['distance'] = distance.attrib.get('value')
                
                # Get OS information
                os_elem = host.find('os/osmatch')
                if os_elem is not None:
                    host_obj['os'] = {
                        'name': os_elem.attrib.get('name'),
                        'accuracy': os_elem.attrib.get('accuracy')
                    }
                
                # Get uptime
                uptime = host.find('uptime')
                if uptime is not None:
                    host_obj['uptime'] = {
                        'seconds': int(uptime.attrib.get('seconds', 0)),
                        'lastboot': uptime.attrib.get('lastboot')
                    }
                
                # Get ports
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
                            
                            # Check for vulnerability scripts on this port
                            for script in port.findall('script'):
                                script_id = script.attrib.get('id', '')
                                if 'vuln' in script_id:
                                    vuln_obj = {
                                        'id': script_id,
                                        'output': script.attrib.get('output', ''),
                                        'host': host_obj.get('ip'),
                                        'port': port_obj['port'],
                                        'protocol': port_obj['protocol']
                                    }
                                    vulns.append(vuln_obj)
                
                host_obj['ports'] = ports
                
                # Check for host-level vulnerability scripts
                for script in host.findall('.//script'):
                    script_id = script.attrib.get('id', '')
                    if 'vuln' in script_id:
                        # Special handling for vulners output
                        if script_id == 'vulners' and script.attrib.get('output'):
                            cpe = None
                            # Try to extract CPE from output
                            import re
                            cpe_match = re.search(r'(cpe:/[\w:.-]+)', script.attrib['output'])
                            if cpe_match:
                                cpe = cpe_match.group(1)
                            vulns += parse_vulners_output(host_obj.get('ip'), cpe, script.attrib['output'])
                        else:
                            vuln_obj = {
                                'id': script_id,
                                'output': script.attrib.get('output', ''),
                                'host': host_obj.get('ip'),
                                'port': None,
                                'protocol': None
                            }
                            vulns.append(vuln_obj)
                
                # Only add host if we have an IP address
                if 'ip' in host_obj:
                    hosts.append(host_obj)
        
        print(f'[UPLOAD] Parsed {len(hosts)} hosts, {len(vulns)} vulnerabilities')
        
    except Exception as e:
        print(f'[UPLOAD] XML parse error: {str(e)}')
        raise
    
    return hosts, vulns
