from src.services import scanner as scanner_module


def test_udp_open_filtered_state_is_reportable():
    assert scanner_module._is_reportable_port_state("udp", "open|filtered") is True


def test_tcp_open_filtered_state_is_not_reportable():
    assert scanner_module._is_reportable_port_state("tcp", "open|filtered") is False


def test_open_state_is_reportable_for_any_protocol():
    assert scanner_module._is_reportable_port_state("tcp", "open") is True
    assert scanner_module._is_reportable_port_state("udp", "open") is True
