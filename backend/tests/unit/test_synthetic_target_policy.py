import pytest

from app.domain.synthetics.models import SyntheticMonitorKind
from app.infrastructure.synthetics import SyntheticTargetPolicyError, validate_monitor_definition


def test_http_monitor_rejects_embedded_credentials() -> None:
    with pytest.raises(SyntheticTargetPolicyError, match="credentials"):
        validate_monitor_definition(
            kind=SyntheticMonitorKind.HTTP,
            target="https://user:secret@example.com/health",
            port=None,
            interval_seconds=60,
            timeout_seconds=5,
            http_method="GET",
            expected_status=200,
        )


def test_tcp_monitor_requires_explicit_port() -> None:
    with pytest.raises(SyntheticTargetPolicyError, match="port"):
        validate_monitor_definition(
            kind=SyntheticMonitorKind.TCP,
            target="example.com",
            port=None,
            interval_seconds=60,
            timeout_seconds=5,
            http_method=None,
            expected_status=None,
        )


def test_monitor_frequency_and_timeout_are_bounded() -> None:
    with pytest.raises(SyntheticTargetPolicyError, match="intervalSeconds"):
        validate_monitor_definition(
            kind=SyntheticMonitorKind.ICMP,
            target="example.com",
            port=None,
            interval_seconds=5,
            timeout_seconds=5,
            http_method=None,
            expected_status=None,
        )

    with pytest.raises(SyntheticTargetPolicyError, match="timeoutSeconds"):
        validate_monitor_definition(
            kind=SyntheticMonitorKind.ICMP,
            target="example.com",
            port=None,
            interval_seconds=60,
            timeout_seconds=60,
            http_method=None,
            expected_status=None,
        )
