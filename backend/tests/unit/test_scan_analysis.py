import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app import create_app, db
from src.models import Scan
from src.services import scan_analysis


@pytest.fixture
def app():
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'ENABLE_BACKGROUND_SERVICES': False,
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_record_verdict_agent_persists_raw_response(app):
    with app.app_context():
        scan = Scan(scan_type='Full TCP', status='complete', hosts_json='[]')
        db.session.add(scan)
        db.session.commit()

        scan_analysis.record_verdict_agent(
            scan.id,
            status='success',
            actionable_count=2,
            patched_count=2,
            raw_response={'verdicts': [{'insight_id': 'x', 'verdict': 'explain'}]},
        )

        loaded = scan_analysis.load_analysis(db.session.get(Scan, scan.id))
        assert loaded['verdict_agent']['status'] == 'success'
        assert loaded['verdict_agent']['raw_response']['verdicts'][0]['verdict'] == 'explain'
