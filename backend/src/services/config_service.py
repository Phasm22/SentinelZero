"""
Server-side reader for persisted UI settings.

The settings routes write camelCase payloads to snake_case JSON files in the
backend root (e.g. network_settings.json). This module reads those files so
non-request code (like the agent subprocess launcher) can consult the same
settings without going through the HTTP layer.
"""
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# backend/src/services/config_service.py -> backend/
_BACKEND_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OLLAMA_BASE_URL = "http://192.168.68.202:11434/v1"
DEFAULT_OLLAMA_MODEL = "qwen2.5:14b"


def _read_settings_file(filename: str) -> dict:
    """Read a snake_case settings JSON file from the backend root. The settings
    routes resolve these by CWD-relative name, so try CWD first, then backend root."""
    for path in (Path(filename), _BACKEND_ROOT / filename):
        try:
            if path.exists():
                with open(path, "r") as f:
                    return json.load(f) or {}
        except Exception as exc:
            logger.warning("config_service: failed reading %s: %s", path, exc)
    return {}


def get_local_mode() -> dict:
    """Return local-AI (Ollama) configuration derived from network settings.

    Returns {enabled, base_url, model}. When enabled, the agent subprocess is
    pointed at a local Ollama server instead of OpenAI.
    """
    net = _read_settings_file("network_settings.json")
    enabled = bool(net.get("local_mode_enabled", False))
    return {
        "enabled": enabled,
        "base_url": net.get("ollama_base_url") or DEFAULT_OLLAMA_BASE_URL,
        "model": net.get("ollama_model") or DEFAULT_OLLAMA_MODEL,
    }
