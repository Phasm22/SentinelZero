"""Unit tests for path helpers."""
import os

import pytest

from src.config.paths import (
    get_scans_dir,
    make_named_scan_xml_path,
    make_scan_xml_path,
    resolve_scan_path,
)


def test_default_scans_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("SENTINEL_SCANS_DIR", raising=False)
    scans = get_scans_dir()
    assert scans.name == "scans"
    assert scans.exists()


def test_custom_scans_dir(tmp_path, monkeypatch):
    custom = tmp_path / "custom-scans"
    monkeypatch.setenv("SENTINEL_SCANS_DIR", str(custom))
    assert get_scans_dir() == custom
    assert custom.exists()


def test_make_scan_xml_path_relative_when_default(monkeypatch):
    monkeypatch.delenv("SENTINEL_SCANS_DIR", raising=False)
    stored, absolute = make_scan_xml_path("discovery scan", "2026-01-01_1200")
    assert stored.startswith("scans/")
    assert absolute.name == "discovery_scan_2026-01-01_1200.xml"


def test_resolve_scan_path_absolute_and_relative(tmp_path, monkeypatch):
    monkeypatch.delenv("SENTINEL_SCANS_DIR", raising=False)
    rel = resolve_scan_path("scans/foo.xml")
    assert rel is not None
    assert rel.name == "foo.xml"

    abs_file = tmp_path / "bar.xml"
    abs_file.write_text("x", encoding="utf-8")
    assert resolve_scan_path(str(abs_file)) == abs_file
