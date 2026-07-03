"""Unit tests for scan filesystem sync helpers."""
import os
import sys
import tempfile
from datetime import datetime

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.services import sync as sync_module


def test_scan_type_pre_discovery_before_discovery():
    assert sync_module._scan_type_from_filename('pre_discovery_2026-01-01_1200.xml') == 'Pre-Discovery'
    assert sync_module._scan_type_from_filename('discovery_scan_2026-01-01_1200.xml') == 'Discovery Scan'


def test_is_sync_artifact():
    assert sync_module._is_sync_artifact('pre_discovery_2026-01-01_1200.xml') is True
    assert sync_module._is_sync_artifact('discovery_scan_2026-01-01_1200.xml') is False


def test_timestamp_from_filename():
    ts = sync_module._timestamp_from_filename('full_tcp_2026-03-15_1430.xml')
    assert ts == datetime(2026, 3, 15, 14, 30)


def test_timestamp_from_mtime_fallback():
    with tempfile.NamedTemporaryFile(suffix='.xml', delete=False) as f:
        f.write(b'<nmaprun></nmaprun>')
        path = f.name
    try:
        ts = sync_module._timestamp_from_mtime(path)
        assert isinstance(ts, datetime)
    finally:
        os.unlink(path)


def test_resolve_scan_timestamps_prefers_xml_start():
    with tempfile.NamedTemporaryFile(suffix='.xml', delete=False) as f:
        f.write(b'<nmaprun></nmaprun>')
        path = f.name
    try:
        xml_start = datetime(2025, 6, 1, 10, 0)
        xml_end = datetime(2025, 6, 1, 10, 5)
        start, end = sync_module._resolve_scan_timestamps(path, {
            'start_time': xml_start,
            'end_time': xml_end,
        })
        assert start == xml_start
        assert end == xml_end
    finally:
        os.unlink(path)
