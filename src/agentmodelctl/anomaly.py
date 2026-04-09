"""Basic anomaly detection for production tracking data."""

from __future__ import annotations

from agentmodelctl.models import AgentProductionStats, Anomaly


def detect_anomalies(
    stats: list[AgentProductionStats],
    error_rate_warning: float = 0.05,
    error_rate_critical: float = 0.10,
    latency_p95_warning: float = 5.0,
    cost_outlier_factor: float = 2.0,
) -> list[Anomaly]:
    """Run all anomaly checks across fleet stats.

    Args:
        stats: List of agent production stats.
        error_rate_warning: Error rate threshold for warnings (default 5%).
        error_rate_critical: Error rate threshold for critical (default 10%).
        latency_p95_warning: Absolute p95 latency threshold in seconds.
        cost_outlier_factor: Factor above fleet median to flag cost outlier.

    Returns:
        List of detected anomalies.
    """
    anomalies: list[Anomaly] = []

    # Compute fleet median cost for outlier detection
    costs = [s.avg_cost_usd for s in stats if s.total_invocations > 0]
    fleet_median_cost = _median(costs) if costs else 0.0

    for s in stats:
        if s.total_invocations == 0:
            continue

        anomalies.extend(_check_error_rate(s, error_rate_warning, error_rate_critical))
        anomalies.extend(_check_latency(s, latency_p95_warning))
        anomalies.extend(_check_cost_outlier(s, fleet_median_cost, cost_outlier_factor))

    return anomalies


def _check_error_rate(
    stats: AgentProductionStats,
    warning_threshold: float,
    critical_threshold: float,
) -> list[Anomaly]:
    """Check error rate against thresholds."""
    anomalies: list[Anomaly] = []

    if stats.error_rate >= critical_threshold:
        anomalies.append(
            Anomaly(
                agent_name=stats.agent_name,
                severity="critical",
                category="error_rate",
                message=(
                    f"{stats.agent_name}: error rate {stats.error_rate:.1%} "
                    f"exceeds {critical_threshold:.0%} threshold"
                ),
                current_value=stats.error_rate,
                threshold=critical_threshold,
            )
        )
    elif stats.error_rate >= warning_threshold:
        anomalies.append(
            Anomaly(
                agent_name=stats.agent_name,
                severity="warning",
                category="error_rate",
                message=(
                    f"{stats.agent_name}: error rate {stats.error_rate:.1%} "
                    f"exceeds {warning_threshold:.0%} threshold"
                ),
                current_value=stats.error_rate,
                threshold=warning_threshold,
            )
        )

    return anomalies


def _check_latency(
    stats: AgentProductionStats,
    p95_threshold: float,
) -> list[Anomaly]:
    """Check p95 latency against threshold."""
    anomalies: list[Anomaly] = []

    if stats.latency_p95 > p95_threshold:
        severity = "critical" if stats.latency_p95 > p95_threshold * 2 else "warning"
        anomalies.append(
            Anomaly(
                agent_name=stats.agent_name,
                severity=severity,
                category="latency",
                message=(
                    f"{stats.agent_name}: p95 latency {stats.latency_p95:.2f}s "
                    f"exceeds {p95_threshold:.1f}s threshold"
                ),
                current_value=stats.latency_p95,
                threshold=p95_threshold,
            )
        )

    return anomalies


def _check_cost_outlier(
    stats: AgentProductionStats,
    fleet_median_cost: float,
    factor: float,
) -> list[Anomaly]:
    """Check if agent's avg cost is an outlier vs fleet median."""
    anomalies: list[Anomaly] = []

    if fleet_median_cost <= 0:
        return anomalies

    threshold = fleet_median_cost * factor
    if stats.avg_cost_usd > threshold:
        severity = "critical" if stats.avg_cost_usd > fleet_median_cost * factor * 2 else "warning"
        anomalies.append(
            Anomaly(
                agent_name=stats.agent_name,
                severity=severity,
                category="cost",
                message=(
                    f"{stats.agent_name}: avg cost ${stats.avg_cost_usd:.4f} "
                    f"is {stats.avg_cost_usd / fleet_median_cost:.1f}x fleet median "
                    f"(${fleet_median_cost:.4f})"
                ),
                current_value=stats.avg_cost_usd,
                threshold=threshold,
            )
        )

    return anomalies


def _median(values: list[float]) -> float:
    """Compute median of a list of values."""
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2
