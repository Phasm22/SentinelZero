"""
Scan synchronization utility to rebuild database records from filesystem XML files
"""
import os
import json
import re
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Any
from ..models.scan import Scan
from ..config.database import db
from .scanner import parse_vulners_output


def _normalize_path(path: str, base_dir: str) -> str:
    """Normalize db/file paths to absolute canonical filesystem paths."""
    if not path:
        return ''
    if os.path.isabs(path):
        return os.path.normpath(path)
    return os.path.normpath(os.path.join(base_dir, path))


def _is_sync_artifact(filename: str) -> bool:
    """Internal scan artifacts that should not be imported as user scans."""
    lower = filename.lower()
    return lower.startswith('pre_discovery_') and lower.endswith('.xml')


def _scan_type_from_filename(filename: str) -> str:
    lower = filename.lower()
    if 'pre_discovery' in lower:
        return 'Pre-Discovery'
    if 'full_tcp' in lower:
        return 'Full TCP'
    if 'iot' in lower:
        return 'IoT Scan'
    if 'vuln' in lower:
        return 'Vuln Scripts'
    if 'uploaded' in lower:
        return 'Uploaded Scan'
    if 'discovery' in lower:
        return 'Discovery Scan'
    return 'Unknown'


_FILENAME_TS_RE = re.compile(r'(\d{4}-\d{2}-\d{2}_\d{4})')


def _timestamp_from_filename(filename: str):
    match = _FILENAME_TS_RE.search(filename)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), '%Y-%m-%d_%H%M')
    except ValueError:
        return None


def _timestamp_from_mtime(xml_path: str):
    try:
        return datetime.fromtimestamp(os.path.getmtime(xml_path))
    except OSError:
        return None


def _resolve_scan_timestamps(xml_path: str, scan_info: Dict[str, Any]):
    """Resolve created_at/completed_at from XML, filename, or file mtime."""
    filename = os.path.basename(xml_path)
    fallback = _timestamp_from_filename(filename) or _timestamp_from_mtime(xml_path)
    start = scan_info.get('start_time') or fallback
    end = scan_info.get('end_time') or start or fallback
    return start, end


def _to_relative_path(path: str, base_dir: str) -> str:
    """Store paths relative to backend root for portability."""
    try:
        rel = os.path.relpath(path, base_dir)
        return rel if rel and rel != '.' else path
    except Exception:
        return path


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
        scan_info['scan_type'] = _scan_type_from_filename(filename)
        
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


def sync_scans_from_filesystem(scans_dir: str = 'scans', prune_missing_in_filesystem: bool = False) -> Dict[str, Any]:
    """
    Synchronize database with filesystem XML files
    
    Args:
        scans_dir: Directory containing XML files
        
    Returns:
        Dictionary with sync results
    """
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
    target_dir = _ensure_scans_dir(scans_dir)
    
    # Get existing database scans and normalize paths so relative/absolute don't duplicate
    scans_with_paths = [scan for scan in Scan.query.all() if scan.raw_xml_path]
    existing_scans_by_path = {
        _normalize_path(scan.raw_xml_path, base_dir): scan
        for scan in scans_with_paths
    }
    
    # Get filesystem XML files
    xml_files = [f for f in os.listdir(target_dir) if f.endswith('.xml')]
    
    synced_count = 0
    skipped_count = 0
    skipped_artifacts = 0
    pruned_count = 0
    error_count = 0
    errors = []
    
    for xml_file in sorted(xml_files):
        xml_path = os.path.normpath(os.path.join(target_dir, xml_file))

        if _is_sync_artifact(xml_file):
            skipped_artifacts += 1
            continue
        
        # Skip if already in database
        if xml_path in existing_scans_by_path:
            skipped_count += 1
            continue
        
        try:
            # Parse XML file
            scan_data = parse_xml_file(xml_path)
            if not scan_data:
                error_count += 1
                errors.append(f'Failed to parse {xml_file}')
                continue

            created_at, completed_at = _resolve_scan_timestamps(xml_path, scan_data)
            
            # Create scan record
            scan = Scan(
                scan_type=scan_data['scan_type'],
                status='complete',
                total_hosts=scan_data['total_hosts'],
                hosts_up=scan_data['hosts_up'],
                total_ports=scan_data['total_ports'],
                open_ports=scan_data['open_ports'],
                hosts_json=json.dumps(scan_data['hosts']),
                vulns_json=json.dumps(scan_data['vulns']),
                raw_xml_path=_to_relative_path(xml_path, base_dir),
                created_at=created_at or datetime.utcnow(),
                completed_at=completed_at or datetime.utcnow()
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

    if prune_missing_in_filesystem:
        fs_files = {
            os.path.normpath(os.path.join(target_dir, name))
            for name in os.listdir(target_dir)
            if name.endswith('.xml')
        }
        stale_scans = [
            scan for scan in scans_with_paths
            if _normalize_path(scan.raw_xml_path, base_dir) not in fs_files
        ]
        for stale in stale_scans:
            db.session.delete(stale)
            pruned_count += 1
        if stale_scans:
            db.session.commit()

    _invalidate_sync_status_cache()
    
    return {
        'synced_count': synced_count,
        'skipped_count': skipped_count,
        'skipped_artifacts': skipped_artifacts,
        'pruned_count': pruned_count,
        'error_count': error_count,
        'total_files': len(xml_files),
        'errors': errors
    }


def _ensure_scans_dir(scans_dir: str = 'scans') -> str:
    """Return absolute scans directory path, creating it if missing."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
    target_dir = os.path.join(base_dir, scans_dir)
    os.makedirs(target_dir, exist_ok=True)
    return target_dir


_SYNC_STATUS_TTL_SECONDS = 15
_sync_status_cache: Dict[str, Any] = {}
_sync_status_cache_at: float = 0.0
_sync_status_lock = threading.Lock()


def _invalidate_sync_status_cache():
    global _sync_status_cache, _sync_status_cache_at
    with _sync_status_lock:
        _sync_status_cache = {}
        _sync_status_cache_at = 0.0


def _compute_sync_status(scans_dir: str = 'scans') -> Dict[str, Any]:
    """Compute DB/filesystem sync status (uncached)."""
    target_dir = _ensure_scans_dir(scans_dir)
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))

    # Only the raw_xml_path column is needed — avoid loading full Scan rows
    # (which include large JSON blobs) just to diff filenames.
    raw_paths = db.session.query(Scan.raw_xml_path).all()
    db_count = len(raw_paths)
    db_paths = {
        _normalize_path(p, base_dir)
        for (p,) in raw_paths
        if p
    }

    # Get filesystem files (exclude internal artifacts from sync status)
    fs_files = {
        os.path.normpath(os.path.join(target_dir, f))
        for f in os.listdir(target_dir)
        if f.endswith('.xml') and not _is_sync_artifact(f)
    }
    artifact_files = [
        f for f in os.listdir(target_dir)
        if f.endswith('.xml') and _is_sync_artifact(f)
    ]

    # Find missing in database
    missing_in_db = fs_files - db_paths

    # Find missing in filesystem
    missing_in_fs = db_paths - fs_files

    return {
        'database_scans': db_count,
        'filesystem_files': len(fs_files),
        'missing_in_database': len(missing_in_db),
        'missing_in_filesystem': len(missing_in_fs),
        'missing_in_db_files': sorted(list(missing_in_db)),
        'missing_in_fs_files': sorted(list(missing_in_fs)),
        'skipped_artifact_files': len(artifact_files),
        'in_sync': len(missing_in_db) == 0 and len(missing_in_fs) == 0
    }


def get_sync_status(scans_dir: str = 'scans', refresh: bool = False) -> Dict[str, Any]:
    """
    Get synchronization status between database and filesystem.

    Result is cached in-memory for a short TTL because the UI polls this
    frequently and the DB/filesystem delta does not change between rapid polls.
    Pass refresh=True to force recomputation.

    Args:
        scans_dir: Directory containing XML files
        refresh: Bypass the cache and recompute

    Returns:
        Dictionary with sync status information
    """
    global _sync_status_cache, _sync_status_cache_at
    now = time.time()
    if not refresh:
        with _sync_status_lock:
            if _sync_status_cache and (now - _sync_status_cache_at) < _SYNC_STATUS_TTL_SECONDS:
                return _sync_status_cache

    result = _compute_sync_status(scans_dir)
    with _sync_status_lock:
        _sync_status_cache = result
        _sync_status_cache_at = time.time()
    return result
