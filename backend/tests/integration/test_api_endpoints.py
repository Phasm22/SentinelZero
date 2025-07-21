import sys
import os
import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from backend.app import app, db

def test_dashboard_stats():
    with app.app_context():
        db.create_all()
        client = app.test_client()
        response = client.get('/api/dashboard-stats')
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        assert 'hosts_count' in data
        assert 'vulns_count' in data
        assert 'total_scans' in data 