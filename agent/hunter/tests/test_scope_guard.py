from hunter.executors.local import ip_in_allowed


def test_scope_guard_accepts_in_scope_ip():
    assert ip_in_allowed("172.16.0.10", ["172.16.0.0/22"])


def test_scope_guard_rejects_out_of_scope_ip():
    assert not ip_in_allowed("10.10.10.10", ["172.16.0.0/22"])

