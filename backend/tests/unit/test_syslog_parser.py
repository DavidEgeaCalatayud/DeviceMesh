import pytest

from app.syslog_receiver import parse_syslog


def test_rfc5424_syslog_is_normalized() -> None:
    parsed = parse_syslog(
        b"<134>1 2026-10-12T01:00:00Z edge-1 linkd 431 LINK_DOWN - uplink lost"
    )
    assert parsed.facility == 16
    assert parsed.severity == 6
    assert parsed.hostname == "edge-1"
    assert parsed.app_name == "linkd"
    assert parsed.proc_id == "431"
    assert parsed.msg_id == "LINK_DOWN"
    assert parsed.message == "uplink lost"
    assert parsed.protocol == "rfc5424"


def test_rfc3164_fallback_and_bounds() -> None:
    parsed = parse_syslog(b"<34>Oct 12 01:00:00 router-1 interface Gi0/1 changed state")
    assert parsed.facility == 4
    assert parsed.severity == 2
    assert parsed.hostname == "router-1"
    assert parsed.message == "interface Gi0/1 changed state"
    assert parsed.protocol == "rfc3164"

    with pytest.raises(ValueError):
        parse_syslog(b"<999>invalid")
    with pytest.raises(ValueError):
        parse_syslog(b"x" * 8193)
    with pytest.raises(ValueError):
        parse_syslog(b"<34>router message\nsecond line")
