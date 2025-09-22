"""
Common port number to service name mapping utility
"""
from typing import Dict, Optional

# Common port mappings for well-known services
COMMON_PORTS: Dict[int, str] = {
    # SSH
    22: 'ssh',
    
    # HTTP/HTTPS
    80: 'http',
    443: 'https',
    8080: 'http',
    8443: 'https',
    8000: 'http',
    8008: 'http',
    8888: 'http',
    9000: 'http',
    9443: 'https',
    
    # DNS
    53: 'dns',
    
    # FTP
    21: 'ftp',
    20: 'ftp-data',
    
    # SMTP
    25: 'smtp',
    587: 'smtp',
    465: 'smtps',
    
    # POP3
    110: 'pop3',
    995: 'pop3s',
    
    # IMAP
    143: 'imap',
    993: 'imaps',
    
    # Telnet
    23: 'telnet',
    
    # RDP
    3389: 'rdp',
    
    # VNC
    5900: 'vnc',
    5901: 'vnc',
    5902: 'vnc',
    5903: 'vnc',
    
    # MySQL
    3306: 'mysql',
    
    # PostgreSQL
    5432: 'postgresql',
    
    # Redis
    6379: 'redis',
    
    # MongoDB
    27017: 'mongodb',
    
    # Elasticsearch
    9200: 'elasticsearch',
    9300: 'elasticsearch',
    
    # RabbitMQ
    5672: 'amqp',
    15672: 'rabbitmq',
    
    # Memcached
    11211: 'memcached',
    
    # NTP
    123: 'ntp',
    
    # SNMP
    161: 'snmp',
    162: 'snmptrap',
    
    # LDAP
    389: 'ldap',
    636: 'ldaps',
    
    # Kerberos
    88: 'kerberos',
    464: 'kpasswd',
    
    # SMB/CIFS
    139: 'netbios-ssn',
    445: 'microsoft-ds',
    
    # RPC
    111: 'rpcbind',
    
    # NFS
    2049: 'nfs',
    
    # Syslog
    514: 'syslog',
    
    # DHCP
    67: 'dhcps',
    68: 'dhcpc',
    
    # TFTP
    69: 'tftp',
    
    # HTTP Alternative
    3000: 'http',
    3001: 'http',
    5000: 'http',
    5001: 'http',
    
    # Database
    1521: 'oracle',
    1433: 'mssql',
    1527: 'oracle',
    
    # Web Services
    8081: 'http',
    8082: 'http',
    8083: 'http',
    8084: 'http',
    8085: 'http',
    8086: 'http',
    8087: 'http',
    8088: 'http',
    8089: 'http',
    8090: 'http',
    
    # Custom/Common
    3128: 'http-proxy',
    4786: 'cisco-vp',
    5353: 'mdns',
    8444: 'https',
    9090: 'http',
    9091: 'http',
    9092: 'http',
    9093: 'http',
    9094: 'http',
    9095: 'http',
    9096: 'http',
    9097: 'http',
    9098: 'http',
    9099: 'http',
    9100: 'http',
}

def get_service_name(port: int, detected_service: Optional[str] = None) -> str:
    """
    Get the appropriate service name for a port.
    
    Args:
        port: Port number
        detected_service: Service name detected by nmap (if any)
    
    Returns:
        Service name to use
    """
    # If nmap detected a specific service and it's not tcpwrapped, use it
    if detected_service and detected_service != 'tcpwrapped':
        return detected_service
    
    # Otherwise, use common port mapping
    return COMMON_PORTS.get(port, 'unknown')

def is_common_port(port: int) -> bool:
    """Check if a port is in the common ports mapping."""
    return port in COMMON_PORTS
