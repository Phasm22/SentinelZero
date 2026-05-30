import sys
import os
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from backend.app import app, db
from src.models.incident import IncidentEmbedding
from src.services import incident_memory


@pytest.fixture
def test_app():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_store_and_search_ranks_by_cosine(test_app):
    with test_app.app_context():
        incident_memory.store_incident(
            db, ip='10.0.0.1', port=22, scan_id=1,
            vector=[1.0, 0.0, 0.0], summary='ssh on .1', embedding_model='m')
        incident_memory.store_incident(
            db, ip='10.0.0.2', port=443, scan_id=1,
            vector=[0.0, 1.0, 0.0], summary='https on .2', embedding_model='m')

        matches = incident_memory.search_similar(db, vector=[0.9, 0.1, 0.0], top_k=5)
        assert len(matches) == 2
        # The .1 incident (aligned with query) ranks first.
        assert matches[0]['ip'] == '10.0.0.1'
        assert matches[0]['score'] > matches[1]['score']


def test_store_is_idempotent_per_scan_ip_port(test_app):
    with test_app.app_context():
        r1 = incident_memory.store_incident(
            db, ip='10.0.0.5', port=8080, scan_id=7,
            vector=[1.0, 0.0], summary='first', embedding_model='m')
        r2 = incident_memory.store_incident(
            db, ip='10.0.0.5', port=8080, scan_id=7,
            vector=[0.0, 1.0], summary='second', embedding_model='m')
        assert r1['status'] == 'stored'
        assert r2['status'] == 'updated'
        rows = IncidentEmbedding.query.filter_by(scan_id=7, ip='10.0.0.5', port=8080).all()
        assert len(rows) == 1
        assert rows[0].summary == 'second'


def test_search_respects_days_window(test_app):
    with test_app.app_context():
        old = IncidentEmbedding(ip='10.0.0.9', port=23, scan_id=2, source='verdict',
                                summary='old', vector_json='[1.0, 0.0]',
                                created_at=datetime.utcnow() - timedelta(days=200))
        db.session.add(old)
        db.session.commit()
        assert incident_memory.search_similar(db, vector=[1.0, 0.0], days=90) == []
        assert len(incident_memory.search_similar(db, vector=[1.0, 0.0], days=365)) == 1


def test_search_excludes_scan_id(test_app):
    with test_app.app_context():
        incident_memory.store_incident(
            db, ip='10.0.0.1', port=22, scan_id=42,
            vector=[1.0, 0.0], summary='self', embedding_model='m')
        matches = incident_memory.search_similar(db, vector=[1.0, 0.0], exclude_scan_id=42)
        assert matches == []
