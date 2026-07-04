#!/usr/bin/env python3
"""Start SentinelZero for Playwright e2e tests (mock scanner, no background probes)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
os.chdir(BACKEND_ROOT)

tmpdir = tempfile.mkdtemp(prefix="sentinelzero-e2e-")
os.environ.setdefault("SENTINEL_MOCK_SCANNER", "1")
os.environ.setdefault("SENTINEL_WHATSUP_CONFIG", "whatsup_config.ci.json")
os.environ.setdefault("SENTINEL_BIND_HOST", "127.0.0.1")
os.environ.setdefault("SENTINEL_BIND_PORT", "5099")
os.environ.setdefault("SENTINEL_ALLOWED_ORIGINS", "http://127.0.0.1:5099")
os.environ["SENTINEL_SCANS_DIR"] = str(Path(tmpdir) / "scans")
Path(os.environ["SENTINEL_SCANS_DIR"]).mkdir(parents=True, exist_ok=True)

from app import create_app, db, socketio  # noqa: E402
from src.models import Scan  # noqa: E402


def seed_database(application):
    with application.app_context():
        db.create_all()
        if Scan.query.count() > 0:
            return

        sample_hosts = [
            {
                "ip": "172.16.0.1",
                "status": "up",
                "ports": [{"port": 443, "protocol": "tcp", "service": "https", "state": "open"}],
            },
            {
                "ip": "172.16.0.10",
                "status": "up",
                "ports": [{"port": 22, "protocol": "tcp", "service": "ssh", "state": "open"}],
            },
        ]
        scan = Scan(
            scan_type="Full TCP",
            status="complete",
            status_message="E2E seed scan",
            target_network="172.16.0.0/22",
            total_hosts=2,
            hosts_up=2,
            total_ports=2,
            open_ports=2,
            hosts_json=json.dumps(sample_hosts),
            vulns_json=json.dumps([]),
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            source="manual",
            initiated_by="e2e-seed",
        )
        db.session.add(scan)
        db.session.commit()
        print(f"[E2E] Seeded scan id={scan.id}")


def main():
    application = create_app(
        {
            "TESTING": False,
            "ENABLE_BACKGROUND_SERVICES": False,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmpdir}/e2e.db",
        }
    )
    seed_database(application)
    host = os.environ.get("SENTINEL_BIND_HOST", "127.0.0.1")
    port = int(os.environ.get("SENTINEL_BIND_PORT", "5000"))
    print(f"[E2E] Starting mock-mode server at http://{host}:{port}")
    socketio.run(application, host=host, port=port, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()
