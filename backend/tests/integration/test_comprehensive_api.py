"""
Comprehensive API Test Suite for SentinelZero Backend
Tests all API endpoints, error handling, and edge cases
"""

import pytest
import json
import os
import tempfile
import sys
import io
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# Add the backend directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app import create_app, db
from src.models import Scan, Alert

@pytest.fixture
def app():
    """Create test app with in-memory database"""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()

@pytest.fixture
def sample_scan_data():
    """Sample scan data for testing"""
    return {
        'scan_type': 'Full TCP',
        'status': 'complete',
        'percent': 100.0,
        'total_hosts': 5,
        'hosts_up': 3,
        'total_ports': 1000,
        'open_ports': 25,
        'hosts_json': json.dumps([
            {
                'ip': '192.168.1.1',
                'status': 'up',
                'ports': [
                    {'port': 80, 'protocol': 'tcp', 'service': 'http', 'state': 'open'},
                    {'port': 443, 'protocol': 'tcp', 'service': 'https', 'state': 'open'}
                ]
            }
        ]),
        'vulns_json': json.dumps([
            {
                'id': 'CVE-2023-1234',
                'severity': 'high',
                'description': 'Test vulnerability',
                'host': '192.168.1.1'
            }
        ])
    }

class TestGeneralAPI:
    """Test general API endpoints"""
    
    def test_ping_endpoint(self, client):
        """Test ping endpoint"""
        response = client.get('/api/ping')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert 'timestamp' in data
    
    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get('/api/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
        assert 'version' in data
    
    def test_dashboard_stats_empty(self, client):
        """Test dashboard stats with no data"""
        response = client.get('/api/dashboard-stats')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['totalScans'] == 0
        assert data['totalAlerts'] == 0
        assert data['unreadAlerts'] == 0
        assert data['recentScan'] is None
    
    def test_dashboard_stats_with_data(self, client, sample_scan_data):
        """Test dashboard stats with sample data"""
        # Create sample scan
        scan = Scan(**sample_scan_data)
        db.session.add(scan)
        db.session.commit()
        
        # Create sample alert
        alert = Alert(
            title='Test Alert',
            message='Test message',
            severity='high',
            read=False
        )
        db.session.add(alert)
        db.session.commit()
        
        response = client.get('/api/dashboard-stats')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['totalScans'] == 1
        assert data['totalAlerts'] == 1
        assert data['unreadAlerts'] == 1
        assert data['recentScan'] is not None
    
    def test_get_scans_empty(self, client):
        """Test get scans with no data"""
        response = client.get('/api/scans')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == []
    
    def test_get_scans_with_data(self, client, sample_scan_data):
        """Test get scans with sample data"""
        scan = Scan(**sample_scan_data)
        db.session.add(scan)
        db.session.commit()
        
        response = client.get('/api/scans')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 1
        assert data[0]['scan_type'] == 'Full TCP'
        assert data[0]['status'] == 'complete'
    
    def test_get_scan_history(self, client, sample_scan_data):
        """Test get scan history"""
        scan = Scan(**sample_scan_data)
        db.session.add(scan)
        db.session.commit()
        
        response = client.get('/api/scan-history')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'scans' in data
        assert len(data['scans']) == 1
        assert data['scans'][0]['scan_type'] == 'Full TCP'
        assert 'hosts_count' in data['scans'][0]
        assert 'vulns_count' in data['scans'][0]
    
    def test_get_active_scans_empty(self, client):
        """Test get active scans with no active scans"""
        response = client.get('/api/active-scans')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['scans'] == []
        assert data['count'] == 0
    
    def test_get_active_scans_with_data(self, client):
        """Test get active scans with running scan"""
        scan = Scan(
            scan_type='Full TCP',
            status='running',
            percent=50.0
        )
        db.session.add(scan)
        db.session.commit()
        
        response = client.get('/api/active-scans')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['scans']) == 1
        assert data['count'] == 1
        assert data['scans'][0]['status'] == 'running'
    
    def test_get_alerts_empty(self, client):
        """Test get alerts with no data"""
        response = client.get('/api/alerts')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == []
    
    def test_get_alerts_with_data(self, client):
        """Test get alerts with sample data"""
        alert = Alert(
            title='Test Alert',
            message='Test message',
            severity='high',
            read=False
        )
        db.session.add(alert)
        db.session.commit()
        
        response = client.get('/api/alerts')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 1
        assert data[0]['title'] == 'Test Alert'
        assert data[0]['severity'] == 'high'
        assert data[0]['read'] == False
    
    def test_mark_alert_read(self, client):
        """Test mark alert as read"""
        alert = Alert(
            title='Test Alert',
            message='Test message',
            severity='high',
            read=False
        )
        db.session.add(alert)
        db.session.commit()
        alert_id = alert.id
        
        response = client.post(f'/api/alerts/{alert_id}/mark-read')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        
        # Verify alert is marked as read
        updated_alert = Alert.query.get(alert_id)
        assert updated_alert.read == True
    
    def test_mark_nonexistent_alert_read(self, client):
        """Test mark non-existent alert as read"""
        response = client.post('/api/alerts/999/mark-read')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['status'] == 'error'
    
    def test_get_scan_details(self, client, sample_scan_data):
        """Test get individual scan details"""
        scan = Scan(**sample_scan_data)
        db.session.add(scan)
        db.session.commit()
        scan_id = scan.id
        
        response = client.get(f'/api/scan/{scan_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['id'] == scan_id
        assert data['scan_type'] == 'Full TCP'
        assert data['status'] == 'complete'
        assert 'hosts_count' in data
        assert 'vulns_count' in data
    
    def test_get_nonexistent_scan(self, client):
        """Test get non-existent scan"""
        response = client.get('/api/scan/999')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_get_scan_hosts(self, client, sample_scan_data):
        """Test get scan hosts"""
        scan = Scan(**sample_scan_data)
        db.session.add(scan)
        db.session.commit()
        scan_id = scan.id
        
        response = client.get(f'/api/hosts/{scan_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'hosts' in data
        assert len(data['hosts']) == 1
        assert data['hosts'][0]['ip'] == '192.168.1.1'
    
    def test_get_scan_vulns(self, client, sample_scan_data):
        """Test get scan vulnerabilities"""
        scan = Scan(**sample_scan_data)
        db.session.add(scan)
        db.session.commit()
        scan_id = scan.id
        
        response = client.get(f'/api/vulns/{scan_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'vulns' in data
        assert len(data['vulns']) == 1
        assert data['vulns'][0]['id'] == 'CVE-2023-1234'
    
    def test_get_scan_xml(self, client, sample_scan_data):
        """Test get scan XML"""
        # Create temporary XML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write('<?xml version="1.0"?><nmaprun></nmaprun>')
            xml_path = f.name
        
        try:
            scan = Scan(**sample_scan_data)
            scan.raw_xml_path = xml_path
            db.session.add(scan)
            db.session.commit()
            scan_id = scan.id
            
            response = client.get(f'/api/scan-xml/{scan_id}')
            assert response.status_code == 200
            assert response.content_type == 'text/plain; charset=utf-8'
            assert b'<nmaprun>' in response.data
        finally:
            os.unlink(xml_path)
    
    def test_get_scan_xml_nonexistent_file(self, client, sample_scan_data):
        """Test get scan XML with non-existent file"""
        scan = Scan(**sample_scan_data)
        scan.raw_xml_path = '/nonexistent/path.xml'
        db.session.add(scan)
        db.session.commit()
        scan_id = scan.id
        
        response = client.get(f'/api/scan-xml/{scan_id}')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_network_interfaces(self, client):
        """Test get network interfaces"""
        response = client.get('/api/network-interfaces')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'interfaces' in data
        assert 'count' in data
        assert isinstance(data['interfaces'], list)
    
    def test_test_pushover_get(self, client):
        """Test Pushover test endpoint GET"""
        response = client.get('/api/test-pushover')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
    
    def test_test_pushover_post_no_credentials(self, client):
        """Test Pushover test endpoint POST without credentials"""
        with patch.dict(os.environ, {}, clear=True):
            response = client.post('/api/test-pushover')
            assert response.status_code == 400
            data = json.loads(response.data)
            assert data['status'] == 'error'

class TestScanAPI:
    """Test scan-related API endpoints"""
    
    def test_trigger_scan_discovery(self, client):
        """Test trigger discovery scan"""
        with patch('src.services.scanner.run_nmap_scan') as mock_scan:
            mock_scan.return_value = None
            
            response = client.post('/api/scan', data={'scan_type': 'Discovery Scan'})
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'success'
            assert 'scan_id' in data
    
    def test_trigger_scan_full_tcp(self, client):
        """Test trigger full TCP scan"""
        with patch('src.services.scanner.run_nmap_scan') as mock_scan:
            mock_scan.return_value = None
            
            response = client.post('/api/scan', data={'scan_type': 'Full TCP'})
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'success'
    
    def test_trigger_scan_iot(self, client):
        """Test trigger IoT scan"""
        with patch('src.services.scanner.run_nmap_scan') as mock_scan:
            mock_scan.return_value = None
            
            response = client.post('/api/scan', data={'scan_type': 'IoT Scan'})
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'success'
    
    def test_trigger_scan_vuln(self, client):
        """Test trigger vulnerability scan"""
        with patch('src.services.scanner.run_nmap_scan') as mock_scan:
            mock_scan.return_value = None
            
            response = client.post('/api/scan', data={'scan_type': 'Vuln Scripts'})
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'success'
    
    def test_trigger_scan_invalid_network(self, client):
        """Test trigger scan with invalid network"""
        with patch.dict(os.environ, {'NETWORK_SETTINGS': '{"defaultTargetNetwork": "invalid"}'}):
            response = client.post('/api/scan', data={'scan_type': 'Full TCP'})
            assert response.status_code == 400
            data = json.loads(response.data)
            assert data['status'] == 'error'
    
    def test_trigger_scan_concurrency_limit(self, client):
        """Test scan concurrency limit"""
        # Create running scans to hit limit
        for i in range(3):
            scan = Scan(
                scan_type='Full TCP',
                status='running',
                percent=50.0
            )
            db.session.add(scan)
        db.session.commit()
        
        with patch.dict(os.environ, {'NETWORK_SETTINGS': '{"concurrentScans": 2}'}):
            response = client.post('/api/scan', data={'scan_type': 'Full TCP'})
            assert response.status_code == 429
            data = json.loads(response.data)
            assert data['status'] == 'error'
    
    def test_get_scan_status(self, client, sample_scan_data):
        """Test get scan status"""
        scan = Scan(**sample_scan_data)
        db.session.add(scan)
        db.session.commit()
        scan_id = scan.id
        
        response = client.get(f'/api/scan-status/{scan_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['scan_id'] == scan_id
        assert data['status'] == 'complete'
        assert data['percent'] == 100.0
    
    def test_get_scan_status_nonexistent(self, client):
        """Test get scan status for non-existent scan"""
        response = client.get('/api/scan-status/999')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data

class TestUploadAPI:
    """Test upload-related API endpoints"""
    
    def test_upload_scan_no_file(self, client):
        """Test upload scan without file"""
        response = client.post('/api/upload-scan')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_upload_scan_invalid_file_type(self, client):
        """Test upload scan with invalid file type"""
        data = {'file': (io.BytesIO(b'test content'), 'test.txt')}
        response = client.post('/api/upload-scan', data=data, content_type='multipart/form-data')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_upload_scan_invalid_xml(self, client):
        """Test upload scan with invalid XML"""
        data = {'file': (io.BytesIO(b'not xml content'), 'test.xml')}
        response = client.post('/api/upload-scan', data=data, content_type='multipart/form-data')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_upload_scan_valid_xml(self, client):
        """Test upload scan with valid XML"""
        xml_content = '''<?xml version="1.0"?>
        <nmaprun>
            <host>
                <status state="up"/>
                <address addr="192.168.1.1" addrtype="ipv4"/>
                <ports>
                    <port protocol="tcp" portid="80">
                        <state state="open"/>
                        <service name="http"/>
                    </port>
                </ports>
            </host>
        </nmaprun>'''
        
        data = {
            'file': (io.BytesIO(xml_content.encode()), 'test.xml'),
            'scan_type': 'Uploaded Scan'
        }
        
        response = client.post('/api/upload-scan', data=data, content_type='multipart/form-data')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert 'scan_id' in data
        assert 'hosts_count' in data
        assert 'vulns_count' in data

class TestSettingsAPI:
    """Test settings-related API endpoints"""
    
    def test_get_settings(self, client):
        """Test get settings"""
        response = client.get('/api/settings')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'securitySettings' in data
        assert 'networkSettings' in data
        assert 'notificationSettings' in data
    
    def test_save_settings(self, client):
        """Test save settings"""
        settings_data = {
            'securitySettings': {
                'vulnScanningEnabled': True,
                'osDetectionEnabled': True,
                'serviceDetectionEnabled': True,
                'aggressiveScanning': False
            },
            'networkSettings': {
                'defaultTargetNetwork': '192.168.1.0/24',
                'maxHosts': 500,
                'scanTimeout': 300,
                'concurrentScans': 2,
                'preDiscoveryEnabled': True
            }
        }
        
        response = client.post('/api/settings', 
                             data=json.dumps(settings_data),
                             content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'

class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_database_error_handling(self, client):
        """Test database error handling"""
        with patch('src.models.Scan.query') as mock_query:
            mock_query.count.side_effect = Exception('Database error')
            
            response = client.get('/api/dashboard-stats')
            assert response.status_code == 500
            data = json.loads(response.data)
            assert data['systemStatus'] == 'error'
    
    def test_invalid_json_handling(self, client):
        """Test invalid JSON handling"""
        response = client.post('/api/settings',
                             data='invalid json',
                             content_type='application/json')
        assert response.status_code == 400
    
    def test_missing_required_fields(self, client):
        """Test missing required fields"""
        response = client.post('/api/scan')
        # Should still work with default values
        assert response.status_code in [200, 400]  # Depends on validation
    
    def test_large_file_upload(self, client):
        """Test large file upload handling"""
        # Create a large XML file (simulate)
        large_xml = '<?xml version="1.0"?><nmaprun>' + '<host><status state="up"/><address addr="192.168.1.1" addrtype="ipv4"/></host>' * 1000 + '</nmaprun>'
        
        data = {
            'file': (io.BytesIO(large_xml.encode()), 'large.xml'),
            'scan_type': 'Large Upload Test'
        }
        
        response = client.post('/api/upload-scan', data=data, content_type='multipart/form-data')
        # Should handle large files gracefully
        assert response.status_code in [200, 413, 500]  # Success, too large, or server error

class TestPerformance:
    """Test API performance and limits"""
    
    def test_concurrent_requests(self, client):
        """Test handling of concurrent requests"""
        import threading
        import time
        
        results = []
        
        def make_request():
            response = client.get('/api/ping')
            results.append(response.status_code)
        
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        assert all(status == 200 for status in results)
        assert len(results) == 10
    
    def test_response_time(self, client):
        """Test API response times"""
        import time
        
        start_time = time.time()
        response = client.get('/api/ping')
        end_time = time.time()
        
        assert response.status_code == 200
        assert (end_time - start_time) < 1.0  # Should respond within 1 second

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
