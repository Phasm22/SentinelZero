"""Filesystem path helpers for SentinelZero backend."""
from __future__ import annotations

import os
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def get_backend_root() -> Path:
    return _BACKEND_ROOT


def get_scans_dir() -> Path:
    """Absolute scans directory; override with SENTINEL_SCANS_DIR."""
    env = os.environ.get("SENTINEL_SCANS_DIR")
    if env:
        path = Path(env)
        if not path.is_absolute():
            path = _BACKEND_ROOT / path
    else:
        path = _BACKEND_ROOT / "scans"
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_scan_xml_filename(scan_type_normalized: str, timestamp: str) -> str:
    safe_type = scan_type_normalized.replace(" ", "_")
    return f"{safe_type}_{timestamp}.xml"


def make_scan_xml_path(scan_type_normalized: str, timestamp: str) -> tuple[str, Path]:
    """Return (stored_path, absolute_path) for a new scan XML artifact."""
    filename = make_scan_xml_filename(scan_type_normalized, timestamp)
    absolute = get_scans_dir() / filename
    scans_dir = get_scans_dir()
    if scans_dir == _BACKEND_ROOT / "scans":
        stored = f"scans/{filename}"
    else:
        stored = str(absolute)
    return stored, absolute


def resolve_scan_path(stored_path: str | None) -> Path | None:
    """Resolve a DB-stored scan path to an absolute filesystem path."""
    if not stored_path:
        return None
    path = Path(stored_path)
    if path.is_absolute():
        return path
    return _BACKEND_ROOT / path


def make_named_scan_xml_path(filename: str) -> tuple[str, Path]:
    """Return (stored_path, absolute_path) for an arbitrary scan XML filename."""
    absolute = get_scans_dir() / filename
    if get_scans_dir() == _BACKEND_ROOT / "scans":
        stored = f"scans/{filename}"
    else:
        stored = str(absolute)
    return stored, absolute


def scans_dir_for_sync() -> str:
    """Directory name/path passed to sync helpers (absolute when overridden)."""
    env = os.environ.get("SENTINEL_SCANS_DIR")
    if env:
        return str(get_scans_dir())
    return "scans"
