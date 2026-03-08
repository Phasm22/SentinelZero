import sys
import os
import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from backend.app import create_app, db

@pytest.fixture
def app():
    """Create test app with in-memory database"""
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'ENABLE_BACKGROUND_SERVICES': False,
    })
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()

def test_dashboard_stats(client):
    response = client.get('/api/dashboard-stats')
    assert response.status_code == 200
    assert response.is_json
    data = response.get_json()
    assert 'totalScans' in data
    assert 'totalAlerts' in data
    assert 'systemStatus' in data 
