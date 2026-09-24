from types import SimpleNamespace

from devicemesh_probe import synthetics
from devicemesh_probe.synthetics import SyntheticMonitorSpec, execute_monitor


class _Response:
    status = 204

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None


class _Opener:
    def __init__(self) -> None:
        self.requests: list[object] = []

    def open(self, request: object, timeout: int) -> _Response:
        self.requests.append((request, timeout))
        return _Response()


def test_http_check_uses_bounded_get_without_redirect_following(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    opener = _Opener()
    handlers: list[object] = []

    def fake_build_opener(*items: object) -> _Opener:
        handlers.extend(items)
        return opener

    monkeypatch.setattr(synthetics, "build_opener", fake_build_opener)
    result = execute_monitor(
        SyntheticMonitorSpec(
            id="http-1",
            monitor_type="http",
            target="https://example.com/health",
            port=None,
            expected_status_min=200,
            expected_status_max=299,
            timeout_seconds=5,
        )
    )

    assert result.success is True
    assert result.http_status == 204
    assert result.latency_ms is not None
    assert any(isinstance(handler, synthetics._NoRedirect) for handler in handlers)
    request, timeout = opener.requests[0]
    assert request.get_method() == "GET"  # type: ignore[attr-defined]
    assert timeout == 5


def test_tcp_check_uses_socket_connection_with_explicit_host_port(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[tuple[tuple[str, int], int]] = []

    class Connection:
        def __enter__(self) -> "Connection":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_connection(address: tuple[str, int], timeout: int) -> Connection:
        calls.append((address, timeout))
        return Connection()

    monkeypatch.setattr(synthetics.socket, "create_connection", fake_connection)
    result = execute_monitor(
        SyntheticMonitorSpec(
            id="tcp-1",
            monitor_type="tcp",
            target="example.com",
            port=443,
            expected_status_min=None,
            expected_status_max=None,
            timeout_seconds=3,
        )
    )

    assert result.success is True
    assert calls == [(('example.com', 443), 3)]


def test_icmp_check_never_uses_shell_and_rejects_command_text(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[tuple[list[str], bool]] = []

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append((command, bool(kwargs.get("shell"))))
        return SimpleNamespace(returncode=0, stdout="time=12.5 ms", stderr="")

    monkeypatch.setattr(synthetics.subprocess, "run", fake_run)
    good = execute_monitor(
        SyntheticMonitorSpec(
            id="icmp-1",
            monitor_type="icmp",
            target="example.com",
            port=None,
            expected_status_min=None,
            expected_status_max=None,
            timeout_seconds=2,
        )
    )
    bad = execute_monitor(
        SyntheticMonitorSpec(
            id="icmp-2",
            monitor_type="icmp",
            target="example.com; id",
            port=None,
            expected_status_min=None,
            expected_status_max=None,
            timeout_seconds=2,
        )
    )

    assert good.success is True
    assert good.latency_ms == 12.5
    assert calls and calls[0][0][-1] == "example.com"
    assert calls[0][1] is False
    assert bad.success is False
    assert bad.failure_reason == "invalid_target"
    assert len(calls) == 1
