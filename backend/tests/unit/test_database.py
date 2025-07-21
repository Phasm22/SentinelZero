import sys
import os
import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from backend.app import app, db, Scan

@pytest.fixture
def test_app():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

def test_scan_model(test_app):
    with test_app.app_context():
        scan = Scan(scan_type='Full TCP', hosts_json='[]', diff_from_previous='{}', vulns_json='[]', raw_xml_path='test.xml')
        db.session.add(scan)
        db.session.commit()
        assert scan.id is not None 