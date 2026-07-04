"""Shared pytest fixtures for SentinelZero backend tests."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db


@pytest.fixture
def scans_dir(tmp_path):
    directory = tmp_path / "scans"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


@pytest.fixture
def app(scans_dir, monkeypatch):
    """Create test app with in-memory database and isolated scans directory."""
    monkeypatch.setenv("SENTINEL_SCANS_DIR", str(scans_dir))
    monkeypatch.setenv("SENTINEL_WHATSUP_CONFIG", "whatsup_config.ci.json")
    monkeypatch.delenv("SENSOR_API_KEY", raising=False)

    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "ENABLE_BACKGROUND_SERVICES": False,
        }
    )

    with application.app_context():
        db.create_all()
        yield application
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
