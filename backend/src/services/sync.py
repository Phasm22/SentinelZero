"""
Scan synchronization utility to rebuild database records from filesystem XML files
"""
import os
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Any, Optional
from ..models.scan import Scan
from ..config.database import db
from .scanner import parse_vulners_output


def parse_xml_file(xml_path: str) -> Dict[str, Any]:
    """
    Parse an nmap XML file and extract scan data
    
    Args:
        xml_path: Path to the XML file
        
    Returns:
        Dictionary containing parsed scan data
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # Extract basic scan info
        scan_info = {
            'scan_type': 'Unknown',
            'hosts': [],
            'vulns': [],
            'total_hosts': 0,
            'hosts_up': 0,
            'total_ports': 0,
            'open_ports': 0,
            'start_time': None,
            'end_time': None
        }
        
        # Get scan start/end times
        if 'start' in root.attrib:
            try:
                scan_info['start_time'] = datetime.fromtimestamp(int(root.attrib['start']))
            except (ValueError, TypeError):
                pass
                
        if 'end' in root.attrib:
            try:
                scan_info['end_time'] = datetime.fromtimestamp(int(root.attrib['end']))
            except (ValueError, TypeError):
                pass
        
        # Determine scan type from filename
        filename = os.path.basename(xml_path)
        if 'discovery' in filename.lower():
            scan_info['scan_type'] = 'Discovery Scan'
        elif 'full_tcp' in filename.lower():
            scan_info['scan_type'] = 'Full TCP'
        elif 'iot' in filename.lower():
            scan_info['scan_type'] = 'IoT Scan'
        elif 'vuln' in filename.lower():
            scan_info['scan_type'] = 'Vuln Scripts'
        elif 'uploaded' in filename.lower():
            scan_info['scan_type'] = 'Uploaded Scan'
        elif 'pre_discovery' in filename.lower():
            scan_info['scan_type'] = 'Pre-Discovery'
        
        # Parse hosts
        hosts = []
        vulns = []
        total_ports = 0
        open_ports = 0
        
        for host in root.findall('host'):
            host_data = {
                'ip': host.find('address').get('addr') if host.find('address') is not None else 'unknown',
                'hostname': '',
                'state': 'down',
                'ports': [],
                'os': {},
                'uptime': {}
            }
            
            # Get hostname
            hostnames = host.find('hostnames')
            if hostnames is not None and hostnames.find('hostname') is not None:
                host_data['hostname'] = hostnames.find('hostname').get('name', '')
            
            # Get host state
            status = host.find('status')
            if status is not None:
                host_data['state'] = status.get('state', 'down')
            
            # Parse ports
            ports = host.find('ports')
            if ports is not None:
                for port in ports.findall('port'):
                    port_data = {
                        'port': int(port.get('portid', 0)),
                        'protocol': port.get('protocol', 'tcp'),
                        'state': 'closed',
                        'service': {},
                        'scripts': []
                    }
                    
                    # Get port state
                    state = port.find('state')
                    if state is not None:
                        port_data['state'] = state.get('state', 'closed')
                        if port_data['state'] == 'open':
                            open_ports += 1
                    
                    # Get service info
                    service = port.find('service')
                    if service is not None:
                        port_data['service'] = {
                            'name': service.get('name', ''),
                            'product': service.get('product', ''),
                            'version': service.get('version', ''),
                            'extrainfo': service.get('extrainfo', '')
                        }
                    
                    # Parse scripts (vulnerabilities)
                    scripts = port.find('script')
                    if scripts is not None:
                        for script in scripts.findall('script'):
                            script_data = {
                                'id': script.get('id', ''),
                                'output': script.get('output', ''),
                                'tables': []
                            }
                            
                            # Parse script tables
                            for table in script.findall('table'):
                                table_data = {
                                    'key': table.get('key', ''),
                                    'elements': []
                                }
                                for elem in table.findall('elem'):
                                    table_data['elements'].append(elem.text or '')
                                script_data['tables'].append(table_data)
                            
                            port_data['scripts'].append(script_data)
                            
                            # Extract vulnerabilities from vuln scripts
                            if 'vuln' in script_data['id'].lower():
                                try:
                                    vuln_data = parse_vulners_output(
                                        host_data['ip'], 
                                        port_data['service'].get('product', ''), 
                                        script_data['output']
                                    )
                                    vulns.extend(vuln_data)
                                except Exception as e:
                                    print(f"[WARN] Failed to parse vuln script {script_data['id']}: {e}")
                    
                    host_data['ports'].append(port_data)
                    total_ports += 1
            
            # Get OS info
            os_info = host.find('os')
            if os_info is not None:
                osmatch = os_info.find('osmatch')
                if osmatch is not None:
                    host_data['os'] = {
                        'name': osmatch.get('name', ''),
                        'accuracy': osmatch.get('accuracy', ''),
                        'line': osmatch.get('line', '')
                    }
            
            # Get uptime info
            uptime = host.find('uptime')
            if uptime is not None:
                host_data['uptime'] = {
                    'seconds': uptime.get('seconds', ''),
                    'lastboot': uptime.get('lastboot', '')
                }
            
            hosts.append(host_data)
        
        scan_info['hosts'] = hosts
        scan_info['vulns'] = vulns
        scan_info['total_hosts'] = len(hosts)
        scan_info['hosts_up'] = len([h for h in hosts if h['state'] == 'up'])
        scan_info['total_ports'] = total_ports
        scan_info['open_ports'] = open_ports
        
        return scan_info
        
    except Exception as e:
        print(f"[ERROR] Failed to parse XML file {xml_path}: {e}")
        return None


def sync_scans_from_filesystem(scans_dir: str = 'scans') -> Dict[str, Any]:
    """
    Synchronize database with filesystem XML files
    
    Args:
        scans_dir: Directory containing XML files
        
    Returns:
        Dictionary with sync results
    """
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
    target_dir = os.path.join(base_dir, scans_dir)
    
    if not os.path.isdir(target_dir):
        return {'error': f'Scans directory not found: {target_dir}'}
    
    # Get existing database scans
    existing_scans = {scan.raw_xml_path: scan for scan in Scan.query.all()}
    
    # Get filesystem XML files
    xml_files = [f for f in os.listdir(target_dir) if f.endswith('.xml')]
    
    synced_count = 0
    skipped_count = 0
    error_count = 0
    errors = []
    
    for xml_file in sorted(xml_files):
        xml_path = os.path.join(target_dir, xml_file)
        
        # Skip if already in database
        if xml_path in existing_scans:
            skipped_count += 1
            continue
        
        try:
            # Parse XML file
            scan_data = parse_xml_file(xml_path)
            if not scan_data:
                error_count += 1
                errors.append(f'Failed to parse {xml_file}')
                continue
            
            # Create scan record
            scan = Scan(
                scan_type=scan_data['scan_type'],
                status='complete',
                percent=100.0,
                total_hosts=scan_data['total_hosts'],
                hosts_up=scan_data['hosts_up'],
                total_ports=scan_data['total_ports'],
                open_ports=scan_data['open_ports'],
                hosts_json=json.dumps(scan_data['hosts']),
                vulns_json=json.dumps(scan_data['vulns']),
                raw_xml_path=xml_path,
                created_at=scan_data['start_time'] or datetime.utcnow(),
                completed_at=scan_data['end_time'] or datetime.utcnow()
            )
            
            db.session.add(scan)
            db.session.commit()
            
            synced_count += 1
            print(f"[SYNC] Synced {xml_file} -> Scan ID {scan.id}")
            
        except Exception as e:
            error_count += 1
            error_msg = f'Failed to sync {xml_file}: {str(e)}'
            errors.append(error_msg)
            print(f"[ERROR] {error_msg}")
            db.session.rollback()
    
    return {
        'synced_count': synced_count,
        'skipped_count': skipped_count,
        'error_count': error_count,
        'total_files': len(xml_files),
        'errors': errors
    }


def get_sync_status(scans_dir: str = 'scans') -> Dict[str, Any]:
    """
    Get synchronization status between database and filesystem
    
    Args:
        scans_dir: Directory containing XML files
        
    Returns:
        Dictionary with sync status information
    """
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
    target_dir = os.path.join(base_dir, scans_dir)
    
    if not os.path.isdir(target_dir):
        return {'error': f'Scans directory not found: {target_dir}'}
    
    # Get database scans
    db_scans = Scan.query.all()
    db_paths = {scan.raw_xml_path for scan in db_scans if scan.raw_xml_path}
    
    # Get filesystem files
    fs_files = {os.path.join(target_dir, f) for f in os.listdir(target_dir) if f.endswith('.xml')}
    
    # Find missing in database
    missing_in_db = fs_files - db_paths
    
    # Find missing in filesystem
    missing_in_fs = db_paths - fs_files
    
    return {
        'database_scans': len(db_scans),
        'filesystem_files': len(fs_files),
        'missing_in_database': len(missing_in_db),
        'missing_in_filesystem': len(missing_in_fs),
        'missing_in_db_files': list(missing_in_db),
        'missing_in_fs_files': list(missing_in_fs),
        'in_sync': len(missing_in_db) == 0 and len(missing_in_fs) == 0
    }
