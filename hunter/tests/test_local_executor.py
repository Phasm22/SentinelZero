from hunter.executors.local import LocalExecutor, host_discovery_probes


def test_host_discovery_probes_on_link_includes_arp():
    probes = host_discovery_probes(True)
    assert "-PR" in probes
    assert "-PM" in probes


def test_local_executor_rejects_out_of_scope_target():
    ex = LocalExecutor(iface="enp6s18", allowed_cidrs=["172.16.0.0/22"])
    out = ex.port_scan_light("192.168.1.10")
    assert "outside mission scope" in out["error"]


def test_iot_scan_rejects_out_of_scope_target():
    ex = LocalExecutor(iface="enp6s18", allowed_cidrs=["172.16.0.0/22"])
    out = ex.port_scan_iot("192.168.1.10")
    assert "outside mission scope" in out["error"]

