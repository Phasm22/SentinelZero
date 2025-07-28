"""
What's Up monitoring service for network health checks
"""
import time
import socket
import subprocess
import threading
from datetime import datetime

# What's Up monitoring configuration
LOOPBACKS = [
    {'name': 'Local Loopback', 'ip': '127.0.0.1'},
    {'name': 'Gateway', 'ip': '192.168.1.1'},  # Adjust to your network
]

SERVICES = [
    {'name': 'DNS Primary', 'ip': '8.8.8.8', 'port': 53, 'type': 'dns'},
    {'name': 'DNS Secondary', 'ip': '1.1.1.1', 'port': 53, 'type': 'dns'},
    {'name': 'Web Test', 'ip': 'google.com', 'port': 80, 'type': 'http'},
]

INFRASTRUCTURE = [
    {'name': 'Router', 'ip': '192.168.1.1', 'port': 80, 'type': 'http'},
    {'name': 'Internal DNS', 'ip': '192.168.1.1', 'port': 53, 'type': 'dns'},
]

def ping_host(ip, timeout=3):
    """Ping a host and return success status"""
    try:
        # Use ping command based on OS
        import platform
        if platform.system().lower() == 'windows':
            cmd = ['ping', '-n', '1', '-w', str(timeout * 1000), ip]
        else:
            cmd = ['ping', '-c', '1', '-W', str(timeout), ip]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 1)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return False

def check_port(ip, port, timeout=3):
    """Check if a TCP port is open"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except Exception:
        return False

def dns_lookup(hostname, timeout=3):
    """Check DNS resolution"""
    try:
        socket.setdefaulttimeout(timeout)
        socket.gethostbyname(hostname)
        return True
    except Exception:
        return False

def check_service(service):
    """Check a service based on its type"""
    service_type = service.get('type', 'ping')
    ip = service['ip']
    port = service.get('port', 80)
    
    if service_type == 'ping':
        return ping_host(ip)
    elif service_type == 'dns':
        # For DNS, check both port and resolution
        port_ok = check_port(ip, port)
        if port_ok and ip not in ['8.8.8.8', '1.1.1.1']:  # Skip resolution test for public DNS
            return dns_lookup('google.com')  # Test resolution
        return port_ok
    elif service_type == 'http':
        return check_port(ip, port)
    else:
        return ping_host(ip)

def whats_up_monitor(socketio, app):
    """Main What's Up monitoring loop"""
    print('[INFO] What\'s Up monitoring started')
    
    while True:
        try:
            with app.app_context():
                # Check all categories
                loopback_results = []
                service_results = []
                infrastructure_results = []
                
                # Check loopbacks
                for loopback in LOOPBACKS:
                    status = ping_host(loopback['ip'])
                    loopback_results.append({
                        'name': loopback['name'],
                        'ip': loopback['ip'],
                        'status': 'up' if status else 'down',
                        'checked_at': datetime.utcnow().isoformat()
                    })
                
                # Check services
                for service in SERVICES:
                    status = check_service(service)
                    service_results.append({
                        'name': service['name'],
                        'ip': service['ip'],
                        'port': service.get('port', 'N/A'),
                        'type': service.get('type', 'ping'),
                        'status': 'up' if status else 'down',
                        'checked_at': datetime.utcnow().isoformat()
                    })
                
                # Check infrastructure
                for infra in INFRASTRUCTURE:
                    status = check_service(infra)
                    infrastructure_results.append({
                        'name': infra['name'],
                        'ip': infra['ip'],
                        'port': infra.get('port', 'N/A'),
                        'type': infra.get('type', 'ping'),
                        'status': 'up' if status else 'down',
                        'checked_at': datetime.utcnow().isoformat()
                    })
                
                # Emit results via WebSocket
                whats_up_data = {
                    'loopbacks': loopback_results,
                    'services': service_results,
                    'infrastructure': infrastructure_results,
                    'last_update': datetime.utcnow().isoformat()
                }
                
                try:
                    socketio.emit('whats_up_update', whats_up_data)
                except Exception as e:
                    print(f'[DEBUG] Error emitting What\'s Up update: {e}')
                
                # Calculate overall status
                all_items = loopback_results + service_results + infrastructure_results
                total_items = len(all_items)
                up_items = len([item for item in all_items if item['status'] == 'up'])
                
                if total_items > 0:
                    health_percentage = (up_items / total_items) * 100
                    overall_status = 'healthy' if health_percentage >= 80 else 'degraded' if health_percentage >= 50 else 'critical'
                else:
                    health_percentage = 0
                    overall_status = 'unknown'
                
                print(f'[INFO] What\'s Up Health: {health_percentage:.1f}% ({up_items}/{total_items}) - {overall_status}')
                
        except Exception as e:
            print(f'[ERROR] What\'s Up monitoring error: {e}')
        
        # Wait before next check (30 seconds)
        time.sleep(30)
