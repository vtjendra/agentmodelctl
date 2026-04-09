"""Tests for anomaly detection."""

from __future__ import annotations

from agentmodelctl.anomaly import _median, detect_anomalies
from agentmodelctl.models import AgentProductionStats


def _make_stats(
    agent_name: str = "support",
    error_rate: float = 0.01,
    latency_p95: float = 1.0,
    avg_cost: float = 0.01,
    invocations: int = 100,
) -> AgentProductionStats:
    return AgentProductionStats(
        agent_name=agent_name,
        total_invocations=invocations,
        error_count=int(invocations * error_rate),
        error_rate=error_rate,
        latency_p50=0.5,
        latency_p95=latency_p95,
        latency_p99=latency_p95 * 1.2,
        avg_cost_usd=avg_cost,
        total_cost_usd=avg_cost * invocations,
        avg_input_tokens=100.0,
        avg_output_tokens=50.0,
        models_used=["claude-sonnet-4-6"],
        first_seen="2026-04-01T00:00:00+00:00",
        last_seen="2026-04-08T00:00:00+00:00",
        period_days=7.0,
    )


class TestDetectAnomalies:
    def test_healthy_fleet(self) -> None:
        """No anomalies when everything is normal."""
        stats = [
            _make_stats("support", error_rate=0.01, latency_p95=1.0, avg_cost=0.01),
            _make_stats("sales", error_rate=0.02, latency_p95=0.8, avg_cost=0.01),
        ]
        anomalies = detect_anomalies(stats)
        assert anomalies == []

    def test_error_rate_warning(self) -> None:
        """Warning when error rate exceeds 5%."""
        stats = [_make_stats(error_rate=0.07)]
        anomalies = detect_anomalies(stats)
        assert len(anomalies) == 1
        assert anomalies[0].severity == "warning"
        assert anomalies[0].category == "error_rate"

    def test_error_rate_critical(self) -> None:
        """Critical when error rate exceeds 10%."""
        stats = [_make_stats(error_rate=0.15)]
        anomalies = detect_anomalies(stats)
        error_anomalies = [a for a in anomalies if a.category == "error_rate"]
        assert len(error_anomalies) == 1
        assert error_anomalies[0].severity == "critical"

    def test_latency_warning(self) -> None:
        """Warning when p95 latency exceeds threshold."""
        stats = [_make_stats(latency_p95=6.0)]
        anomalies = detect_anomalies(stats)
        latency_anomalies = [a for a in anomalies if a.category == "latency"]
        assert len(latency_anomalies) == 1
        assert latency_anomalies[0].severity == "warning"

    def test_latency_critical(self) -> None:
        """Critical when p95 latency is 2x threshold."""
        stats = [_make_stats(latency_p95=12.0)]
        anomalies = detect_anomalies(stats)
        latency_anomalies = [a for a in anomalies if a.category == "latency"]
        assert len(latency_anomalies) == 1
        assert latency_anomalies[0].severity == "critical"

    def test_cost_outlier(self) -> None:
        """Warning when cost is 2x+ fleet median."""
        stats = [
            _make_stats("cheap", avg_cost=0.01),
            _make_stats("normal", avg_cost=0.01),
            _make_stats("expensive", avg_cost=0.05),
        ]
        anomalies = detect_anomalies(stats)
        cost_anomalies = [a for a in anomalies if a.category == "cost"]
        assert len(cost_anomalies) == 1
        assert cost_anomalies[0].agent_name == "expensive"

    def test_multiple_anomalies(self) -> None:
        """Agent can trigger multiple anomaly types."""
        stats = [
            _make_stats("bad_agent", error_rate=0.12, latency_p95=8.0, avg_cost=0.10),
            _make_stats("good_agent", avg_cost=0.01),
            _make_stats("normal_agent", avg_cost=0.01),
        ]
        anomalies = detect_anomalies(stats)
        bad_anomalies = [a for a in anomalies if a.agent_name == "bad_agent"]
        categories = {a.category for a in bad_anomalies}
        assert "error_rate" in categories
        assert "latency" in categories
        assert "cost" in categories

    def test_custom_thresholds(self) -> None:
        """Custom thresholds override defaults."""
        stats = [_make_stats(error_rate=0.03)]
        # Default threshold is 5%, so 3% shouldn't fire
        assert detect_anomalies(stats) == []
        # Lower threshold to 2%
        anomalies = detect_anomalies(stats, error_rate_warning=0.02)
        assert len(anomalies) == 1

    def test_empty_stats(self) -> None:
        """No anomalies for empty stats list."""
        assert detect_anomalies([]) == []

    def test_zero_invocations_skipped(self) -> None:
        """Agents with zero invocations are skipped."""
        stats = [_make_stats(invocations=0, error_rate=0.5)]
        assert detect_anomalies(stats) == []

    def test_single_agent_no_cost_outlier(self) -> None:
        """Single agent can't be a cost outlier (is the median)."""
        stats = [_make_stats(avg_cost=0.10)]
        anomalies = detect_anomalies(stats)
        cost_anomalies = [a for a in anomalies if a.category == "cost"]
        assert cost_anomalies == []


class TestMedian:
    def test_odd_count(self) -> None:
        assert _median([1, 2, 3]) == 2

    def test_even_count(self) -> None:
        assert _median([1, 2, 3, 4]) == 2.5

    def test_single(self) -> None:
        assert _median([5]) == 5

    def test_empty(self) -> None:
        assert _median([]) == 0.0
