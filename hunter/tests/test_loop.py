from hunter.loop import _parse_faux_tool_call


def test_parse_faux_tool_call():
    assert _parse_faux_tool_call('{"name":"discover_hosts","arguments":{"cidr":"172.16.0.0/24"}}') == (
        "discover_hosts",
        {"cidr": "172.16.0.0/24"},
    )
    assert _parse_faux_tool_call("not json") is None
    assert _parse_faux_tool_call('{"status":"complete"}') is None
