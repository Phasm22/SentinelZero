"""
What's Up monitoring service for network health checks
"""
import time
import socket
import subprocess
import threading
import platform
import json
import os
import requests
from datetime import datetime

# Layer 1: Host-Level Status (Loopback sentinels)
LOOPBACKS = [
    {"name": "LAN Gateway", "ip": "172.16.0.1", "description": "Network gateway health", "interface": "enp6s18"},
    {"name": "LAN Sentinel", "ip": "172.16.0.254", "description": "LAN health probe (172.16.0.0/22)", "interface": "dummy0"},
    {"name": "Home Sentinel", "ip": "192.168.68.254", "description": "Home network probe via dummy interface", "interface": "dummy0"},
    {"name": "Localhost", "ip": "127.0.0.1", "description": "SentinelZero health probe", "interface": "lo"},
]

# Layer 2: DNS/Service Reachability  
SERVICES = [
    {"name": "Primary DNS", "ip": "172.16.0.13", "port": 53, "type": "dns", "query": "google.com"},
    {"name": "Cloudflare DNS", "ip": "1.1.1.1", "port": 53, "type": "dns", "query": "google.com"},
    {"name": "Google DNS", "ip": "8.8.8.8", "port": 53, "type": "dns", "query": "google.com"},
    {"name": "Internet Test", "ip": "8.8.8.8", "port": 53, "type": "ping", "path": "/"},
    {"name": "Network Gateway", "ip": "172.16.0.1", "port": 80, "type": "ping", "path": "/"},
]

# Layer 3: Infrastructure Status
INFRASTRUCTURE = [
    {"name": "Network Gateway", "ip": "172.16.0.1", "type": "ping"},
    {"name": "Primary DNS", "ip": "172.16.0.13", "port": 53, "type": "dns", "query": "google.com"},
    {"name": "Cloudflare DNS", "ip": "1.1.1.1", "port": 53, "type": "dns", "query": "google.com"},
    {"name": "Google DNS", "ip": "8.8.8.8", "port": 53, "type": "dns", "query": "google.com"},
    {"name": "Internet Connectivity", "ip": "8.8.8.8", "type": "ping"},
    # Lab Infrastructure
    {"name": "Proxmox Node (proxBig.prox)", "ip": "172.16.0.10", "type": "ping"},
    {"name": "Proxmox Cluster (yin.prox)", "ip": "172.16.0.11", "type": "ping"},
    {"name": "Proxmox Cluster (yang.prox)", "ip": "172.16.0.12", "type": "ping"},
    {"name": "Homebridge", "ip": "192.168.68.79", "type": "ping"},
    {"name": "Ubuntu Server", "ip": "192.168.71.30", "type": "ping"},
    {"name": "Home Net DNS", "ip": "192.168.71.25", "type": "ping"},
    {"name": "Backup Home DNS", "ip": "192.168.71.30", "type": "ping"},
    {"name": "Code Server (code-server.prox)", "ip": "172.16.0.106", "type": "ping"},
    {"name": "VPN to Home Network", "ip": "192.168.71.40", "type": "ping"},
    {"name": "Main Lab Windows VM (winvm.prox)", "ip": "172.16.0.100", "type": "ping"},
]

def ping_ip(ip, timeout=0.5, retries=1, log_results=True):
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
                # For external IPs, use default routing; for internal IPs, try specific interface
                if ip.startswith(('1.1.1.', '8.8.8.', '208.67.')) or ip in ['1.1.1.1', '8.8.8.8', '208.67.222.222']:
                    # External services - use default routing
                    result = subprocess.run(["ping", "-c1", f"-W{timeout}", ip], 
                                          capture_output=True, text=True, timeout=timeout+2)
                else:
                    # Internal services - try with sudo
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
        
        # For external services, try alternative methods
        if ip.startswith(('1.1.1.', '8.8.8.', '208.67.')) or ip in ['1.1.1.1', '8.8.8.8', '208.67.222.222']:
            # Try with curl as fallback for external services
            try:
                import requests
                start_time = time.time()
                response = requests.get(f"http://{ip}", timeout=timeout)
                response_time = (time.time() - start_time) * 1000
                if response.status_code < 500:  # Any response is good
                    result = {"success": True, "method": "http", "response_time": response_time, "error": None}
                    result["attempts"] = attempt + 1
                    log_ping_result(ip, result)
                    return result
            except Exception:
                pass
    
    # All methods failed after retries
    final_result = {"success": False, "method": "all_failed", "response_time": None, 
                   "attempts": retries + 1, "error": "All ping methods failed after retries"}
    log_ping_result(ip, final_result)
    return final_result

def resolve_domain(domain):
    """Resolve domain to IP with error handling"""
    try:
        import socket
        return socket.gethostbyname(domain)
    except Exception as e:
        return None

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

def ping_host(ip, timeout=3):
    """Ping a host and return success status"""
    result = ping_ip(ip, timeout, retries=1, log_results=False)
    return result["success"]

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
    
    # Handle domain-based services
    if 'domain' in service:
        target_host = service['domain']
        target_ip = resolve_domain(target_host)
        if not target_ip and service_type != 'ping':
            return False
    else:
        target_host = service['ip']
        target_ip = service['ip']
    
    port = service.get('port', 80)
    
    if service_type == 'ping':
        return ping_host(target_ip if target_ip else target_host)
    elif service_type == 'dns':
        # For DNS, check both port and resolution
        if target_ip:
            port_ok = check_port(target_ip, port)
            query_domain = service.get('query', 'google.com')
            if port_ok:
                dns_result = check_dns_query(target_ip, query_domain)
                return dns_result['success']
        return False
    elif service_type in ['http', 'https']:
        if 'domain' in service:
            return check_http_service(
                target_host, 
                port, 
                service.get('path', '/'),
                service_type == 'https'
            )['success']
        else:
            return check_port(target_ip, port)
    else:
        return ping_host(target_ip if target_ip else target_host)

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
                        'ip': service.get('ip', service.get('domain', 'N/A')),
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

def get_loopbacks_data():
    """Core logic for checking loopbacks - returns raw data"""
    import signal
    
    def timeout_handler(signum, frame):
        raise TimeoutError("Loopbacks check timed out")
    
    # Set a 5-second timeout for the entire function
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(5)
    
    try:
        results = []
        for loopback in LOOPBACKS:
            result = ping_ip(loopback["ip"], timeout=2, retries=1)
            results.append({
                "name": loopback["name"],
                "ip": loopback["ip"],
                "description": loopback.get("description", ""),
                "interface": loopback.get("interface", "unknown"),
                "status": "up" if result["success"] else "down",
                "response_time": result.get("response_time"),
                "method": result.get("method", "unknown"),
                "error": result.get("error") if not result["success"] else None,
                "checked_at": datetime.now().isoformat()
            })
        return results
    finally:
        signal.alarm(0)  # Cancel the alarm

def get_services_data():
    """Core logic for checking services - returns raw data with fast hping3-based testing"""
    import signal
    
    def timeout_handler(signum, frame):
        raise TimeoutError("Services check timed out")
    
    # Set a 8-second timeout for the entire function
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(8)
    
    try:
        results = []
        for service in SERVICES:
            result = {
                "name": service["name"],
                "domain": service.get("domain"),
                "ip": service.get("ip"),
                "port": service.get("port"),
                "type": service.get("type", "ping"),
                "path": service.get("path", "/"),
                "checked_at": datetime.now().isoformat()
            }
            
            # Determine target host and resolve if needed
            if 'domain' in service:
                target_host = service['domain']
                target_ip = resolve_domain(target_host)
            else:
                target_host = service['ip']
                target_ip = service['ip']
            
            # Step 1: DNS Resolution (if domain-based)
            if 'domain' in service:
                if target_ip:
                    result["dns"] = {"success": True, "ip": target_ip, "error": None}
                else:
                    result["dns"] = {"success": False, "ip": None, "error": "DNS resolution failed"}
            else:
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
                    # Use socket check for other services
                    port_result = {"success": check_port(target_ip, service["port"], timeout=2)}
                    result["service"] = {
                        "success": port_result["success"],
                        "response_time": None,
                        "error": None if port_result["success"] else f"Port {service['port']} not accessible",
                        "method": "socket"
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
    finally:
        signal.alarm(0)  # Cancel the alarm

def get_infrastructure_data():
    """Core logic for checking infrastructure - returns raw data with parallel processing"""
    import signal
    import time
    import concurrent.futures
    import threading
    
    def timeout_handler(signum, frame):
        raise TimeoutError("Infrastructure check timed out")
    
    def check_single_infra(infra):
        """Check a single infrastructure item"""
        try:
            result = {
                "name": infra["name"],
                "ip": infra["ip"],
                "port": infra.get("port"),
                "type": infra.get("type", "ping"),
                "checked_at": datetime.now().isoformat()
            }
            
            # Check based on type
            if infra["type"] == "dns":
                query_domain = infra.get("query", "google.com")
                dns_result = check_dns_query(infra["ip"], query_domain, timeout=0.5)
                result["status"] = "up" if dns_result["success"] else "down"
                result["error"] = dns_result.get("error") if not dns_result["success"] else None
                result["response"] = dns_result.get("result")
            elif infra["type"] in ["http", "https"]:
                path = infra.get("path", "/")
                http_result = check_http_service(
                    infra["ip"], 
                    infra["port"], 
                    path, 
                    infra["type"] == "https",
                    timeout=1
                )
                result["status"] = "up" if http_result["success"] else "down"
                result["error"] = http_result.get("error") if not http_result["success"] else None
                result["status_code"] = http_result.get("status_code")
                result["response_time"] = http_result.get("response_time")
            else:
                # Basic ping with shorter timeout
                ping_result = ping_ip(infra["ip"], timeout=0.2, retries=1)
                result["status"] = "up" if ping_result["success"] else "down"
                result["error"] = ping_result.get("error") if not ping_result["success"] else None
                result["response_time"] = ping_result.get("response_time")
                result["method"] = ping_result.get("method")
            
            return result
        except Exception as e:
            return {
                "name": infra["name"],
                "ip": infra["ip"],
                "port": infra.get("port"),
                "type": infra.get("type", "ping"),
                "status": "down",
                "error": str(e),
                "checked_at": datetime.now().isoformat()
            }
    
    # Set a 10-second timeout for the entire function
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(10)
    
    try:
        print(f"[DEBUG] Starting parallel infrastructure check for {len(INFRASTRUCTURE)} items")
        start_time = time.time()
        
        # Use ThreadPoolExecutor for parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            # Submit all tasks
            future_to_infra = {executor.submit(check_single_infra, infra): infra for infra in INFRASTRUCTURE}
            
            # Collect results as they complete
            results = []
            for future in concurrent.futures.as_completed(future_to_infra, timeout=8):
                try:
                    result = future.result()
                    results.append(result)
                    print(f"[DEBUG] Completed {result['name']}: {result['status']}")
                except Exception as e:
                    infra = future_to_infra[future]
                    print(f"[DEBUG] Failed {infra['name']}: {e}")
                    results.append({
                        "name": infra["name"],
                        "ip": infra["ip"],
                        "port": infra.get("port"),
                        "type": infra.get("type", "ping"),
                        "status": "down",
                        "error": str(e),
                        "checked_at": datetime.now().isoformat()
                    })
        
        elapsed = time.time() - start_time
        print(f"[DEBUG] Infrastructure check completed in {elapsed:.2f}s. Found {len(results)} results")
        return results
    finally:
        signal.alarm(0)  # Cancel the alarm
