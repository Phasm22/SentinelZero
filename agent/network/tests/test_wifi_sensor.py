"""Tests for the passive Wi-Fi / RF summary sensor (no live capture)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

NET = Path(__file__).resolve().parents[1]
if str(NET) not in sys.path:
    sys.path.insert(0, str(NET))

import wifi_sensor  # noqa: E402


def test_registration_identity_matches_hermes_spec():
    ident = wifi_sensor.registration_identity()
    assert ident == {
        "agent_id": "t470s-rf",
        "hostname": "phasm-T470s",
        "host_ip": "192.168.68.111",
        "role": "wireless",
        "tags": ["rf", "passive"],
    }


def test_empty_summary_is_under_budget_and_marks_deferred():
    block = wifi_sensor.empty_wifi_summary()
    assert set(block) >= {"aps", "clients_summary", "channels", "events"}
    assert block["sensor"]["capture"] == "deferred_hardware_poc"
    assert block["sensor"]["sniff_iface_expected"] == "wlx54c9ff02d309"
    assert block["sensor"]["uplink_iface_refused"] == "wlp58s0"
    size = len(json.dumps(block, separators=(",", ":")).encode("utf-8"))
    assert size <= wifi_sensor.WIFI_MAX_BYTES


def test_enforce_wifi_budget_strips_secrets_and_caps_size():
    raw = {
        "aps": [{"bssid": f"aa:bb:cc:dd:{i:02x}:01", "pad": "z" * 180} for i in range(60)],
        "clients_summary": {"associated": 2, "psk": "SECRET"},
        "channels": [],
        "events": [{"event": "x", "blob": "y" * 180} for _ in range(60)],
        "password": "nope",
        "token": "nope",
    }
    out = wifi_sensor.enforce_wifi_budget(raw)
    assert "password" not in out
    assert "token" not in out
    assert "psk" not in out.get("clients_summary", {})
    assert len(json.dumps(out, separators=(",", ":")).encode("utf-8")) <= wifi_sensor.WIFI_MAX_BYTES


def test_build_ingest_payload_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(wifi_sensor, "collect_system", lambda: {"cpu_pct": 1.0, "mem_pct": 2.0, "load_avg": [0.1]})
    wifi = {
        "aps": [{"bssid": "a8:42:a1:00:00:01", "channel": "2g-6"}],
        "clients_summary": {"associated": 1, "probe_noise_count": 0, "unresolved": 0},
        "channels": [{"id": "2g-6"}],
        "events": [],
    }
    payload = wifi_sensor.build_ingest_payload(wifi=wifi, ts="2026-11-06T00:00:00+00:00")
    assert payload["agent_id"] == "t470s-rf"
    assert payload["role"] == "wireless"
    assert "system" in payload["collectors"]
    assert payload["collectors"]["wifi"]["aps"][0]["bssid"] == "a8:42:a1:00:00:01"
    wifi_bytes = len(
        json.dumps(payload["collectors"]["wifi"], separators=(",", ":")).encode("utf-8")
    )
    assert wifi_bytes <= wifi_sensor.WIFI_MAX_BYTES


def test_load_summary_file_reads_wifi_block(tmp_path):
    path = tmp_path / "summary.json"
    path.write_text(
        json.dumps({
            "wifi": {
                "aps": [{"bssid": "aa:bb:cc:dd:ee:ff"}],
                "clients_summary": {"associated": 0},
                "channels": [],
                "events": [],
            }
        }),
        encoding="utf-8",
    )
    loaded = wifi_sensor.load_summary_file(path)
    assert loaded["aps"][0]["bssid"] == "aa:bb:cc:dd:ee:ff"
    assert wifi_sensor.load_summary_file(tmp_path / "missing.json") is None


def test_never_mentions_operating_uplink_as_sniff_target():
    # Guardrail: uplink must stay refused; only the USB dongle is named as sniff.
    assert wifi_sensor.SNIFF_IFACE == "wlx54c9ff02d309"
    assert wifi_sensor.UPLINK_IFACE == "wlp58s0"
    assert wifi_sensor.SNIFF_IFACE != wifi_sensor.UPLINK_IFACE
