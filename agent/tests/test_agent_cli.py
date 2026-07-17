import importlib.util
import sys
from pathlib import Path


def _load_agent_module():
    path = Path(__file__).resolve().parents[1] / "agent.py"
    spec = importlib.util.spec_from_file_location("sentinel_agent_cli", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_latest_without_completed_scans_is_noop_exit_zero(monkeypatch, capsys):
    agent = _load_agent_module()

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.setattr(sys, "argv", ["agent.py", "--latest"])
    monkeypatch.setattr(agent._http, "get", lambda *args, **kwargs: _Response({"scans": []}))

    agent.main()

    out = capsys.readouterr()
    assert "No completed scans found; nothing to analyze." in out.out


def test_get_latest_scan_id_returns_first_completed(monkeypatch):
    agent = _load_agent_module()
    monkeypatch.setattr(
        agent._http,
        "get",
        lambda *args, **kwargs: _Response({
            "scans": [
                {"id": 1, "status": "running"},
                {"id": 2, "status": "complete"},
            ],
        }),
    )

    assert agent._get_latest_scan_id() == 2
