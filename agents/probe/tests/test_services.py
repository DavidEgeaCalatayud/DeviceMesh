from devicemesh_probe.discovery import scan_tcp_services


def test_service_scan_only_uses_requested_ports() -> None:
    attempted: list[int] = []

    def fake_probe(_: str, port: int, __: float) -> bool:
        attempted.append(port)
        return port in {22, 443}

    services = scan_tcp_services(
        "127.0.0.1",
        (22, 80, 443),
        port_probe=fake_probe,
    )

    assert attempted == [22, 80, 443]
    assert [(service.port, service.name) for service in services] == [
        (22, "ssh"),
        (443, "https"),
    ]


def test_service_scan_rejects_unbounded_port_lists() -> None:
    try:
        scan_tcp_services("127.0.0.1", tuple(range(1, 34)), port_probe=lambda *_: False)
    except ValueError as exc:
        assert "at most 32" in str(exc)
    else:
        raise AssertionError("expected bounded port validation")
