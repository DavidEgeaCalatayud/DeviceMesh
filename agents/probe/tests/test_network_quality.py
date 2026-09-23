import pytest

from devicemesh_probe.discovery import summarize_network_quality


def test_quality_summary_calculates_latency_jitter_and_packet_loss() -> None:
    quality = summarize_network_quality((10.0, 14.0, None, 20.0))
    assert quality is not None
    assert quality.latency_ms == pytest.approx(14.6666667)
    assert quality.jitter_ms == pytest.approx(5.0)
    assert quality.packet_loss_percent == 25.0
    assert quality.attempts == 4
    assert quality.successes == 3


def test_quality_summary_keeps_jitter_unknown_with_one_success() -> None:
    quality = summarize_network_quality((None, 12.0, None, None))
    assert quality is not None
    assert quality.jitter_ms is None
    assert quality.packet_loss_percent == 75.0


def test_quality_summary_returns_none_when_host_never_replies() -> None:
    assert summarize_network_quality((None, None, None, None)) is None
