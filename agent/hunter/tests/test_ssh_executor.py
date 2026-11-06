from hunter.executors.ssh import (
    ALLOWED_REMOTE_COMMANDS,
    DEFAULT_RF_HOST,
    REFUSED_REMOTE_COMMANDS,
    SshExecutor,
    allow_list_manifest,
)


def test_allow_list_covers_spec_commands():
    assert {"discover_hosts", "port_scan_light", "port_scan_iot", "rf_whereis", "rf_clients"} <= ALLOWED_REMOTE_COMMANDS
    assert "wifi-mon" in REFUSED_REMOTE_COMMANDS
    assert "sudo" in REFUSED_REMOTE_COMMANDS
    assert "tshark" in REFUSED_REMOTE_COMMANDS


def test_ssh_executor_rejects_out_of_scope_without_calling_ssh():
    ex = SshExecutor(allowed_cidrs=["172.16.0.0/22"], user="rf-bot")
    out = ex.port_scan_light("192.168.1.10")
    assert "outside mission scope" in out["error"]


def test_ssh_executor_unconfigured_returns_structured_error():
    ex = SshExecutor(allowed_cidrs=["192.168.68.0/22"], user="")
    out = ex.rf_whereis("aa:bb:cc:dd:ee:ff")
    assert out.get("configured") is False
    assert "HUNTER_RF_SSH_USER" in out["error"]
    assert ex.host == DEFAULT_RF_HOST


def test_ssh_executor_refuses_unsafe_args(monkeypatch):
    ex = SshExecutor(allowed_cidrs=["192.168.68.0/22"], user="rf-bot", host="192.168.68.111")
    called = {"n": 0}

    def _boom(*_a, **_k):
        called["n"] += 1
        raise AssertionError("ssh must not run for unsafe args")

    monkeypatch.setattr("hunter.executors.ssh.subprocess.run", _boom)
    out = ex._run_allowed("rf_whereis", ["aa;rm -rf /"])
    assert "unsafe" in out["error"]
    assert called["n"] == 0


def test_allow_list_manifest_documents_env_not_secrets():
    manifest = allow_list_manifest()
    assert manifest["host_default"] == "192.168.68.111"
    assert "HUNTER_RF_SSH_USER" in manifest["env"]
    blob = str(manifest).lower()
    assert "psk" not in blob
    assert "password" not in blob
    assert "sensor_api_key" not in blob
