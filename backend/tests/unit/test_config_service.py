"""Unit tests for config_service."""
import json

import pytest

from src.services import config_service


def test_get_local_mode_defaults_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = config_service.get_local_mode()
    assert result["enabled"] is False
    assert "11434" in result["base_url"] or result["base_url"]


def test_get_local_mode_reads_network_settings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = {
        "local_mode_enabled": True,
        "ollama_base_url": "http://127.0.0.1:11434/v1",
        "ollama_model": "llama3",
    }
    (tmp_path / "network_settings.json").write_text(json.dumps(settings), encoding="utf-8")

    result = config_service.get_local_mode()
    assert result["enabled"] is True
    assert result["base_url"] == "http://127.0.0.1:11434/v1"
    assert result["model"] == "llama3"
