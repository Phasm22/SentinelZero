"""Unit tests for mock scanner mode."""
import os
from unittest.mock import patch

import pytest

from src.services.mock_scanner import build_mock_nmap_xml, mock_scanner_enabled


def test_mock_scanner_enabled_truthy_values(monkeypatch):
    for value in ("1", "true", "TRUE", "yes"):
        monkeypatch.setenv("SENTINEL_MOCK_SCANNER", value)
        assert mock_scanner_enabled() is True


def test_mock_scanner_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SENTINEL_MOCK_SCANNER", raising=False)
    assert mock_scanner_enabled() is False


def test_build_mock_nmap_xml_contains_hosts():
    xml = build_mock_nmap_xml("172.16.0.0/22", "discovery scan")
    assert "<nmaprun" in xml
    assert "172.16.0.1" in xml
    assert "172.16.0.10" in xml


def test_run_mock_nmap_execution_completes_scan(app, monkeypatch):
    monkeypatch.setenv("SENTINEL_MOCK_SCANNER", "1")

    with app.app_context():
        runtime = app.extensions["scan_runtime"]
        scan = runtime.create_scan(
            scan_type="Discovery Scan",
            source="manual",
            initiated_by="test",
            state="queued",
            message="queued",
        )
        scan_id = scan.id

        def emit_stage(status, message):
            runtime.set_state(scan_id, status, message)

        from src.config.paths import make_scan_xml_path
        stored, absolute = make_scan_xml_path("discovery scan", "2026-01-01_1200")

        from src.services.mock_scanner import run_mock_nmap_execution

        with patch("src.services.scanner.generate_and_store_insights", return_value=[]):
            run_mock_nmap_execution(
                scan_id,
                "Discovery Scan",
                "discovery scan",
                "172.16.0.0/22",
                stored,
                str(absolute),
                runtime,
                app,
                None,
                {},
                emit_stage,
            )

        refreshed = runtime.get_scan(scan_id)
        assert refreshed.status == "complete"
        assert refreshed.total_hosts >= 1
        assert absolute.exists()
