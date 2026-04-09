"""Log loading and aggregation for production tracking data."""

from __future__ import annotations

import datetime
import json
from pathlib import Path

from agentmodelctl.models import AgentProductionStats, TrackingEvent


def get_log_dir(project_root: Path) -> Path:
    """Return .agentmodelctl/logs/ path (does NOT create it)."""
    return project_root / ".agentmodelctl" / "logs"


def list_tracked_agents(project_root: Path) -> list[str]:
    """Return sorted list of agent names that have JSONL log files."""
    log_dir = get_log_dir(project_root)
    if not log_dir.exists():
        return []
    return sorted(p.stem for p in log_dir.glob("*.jsonl"))


def load_events(
    agent_name: str,
    project_root: Path,
    since: str | None = None,
    until: str | None = None,
) -> list[TrackingEvent]:
    """Read and parse JSONL for one agent. Skips malformed lines.

    If since/until are provided (ISO timestamps), filters entries accordingly.
    """
    log_file = get_log_dir(project_root) / f"{agent_name}.jsonl"
    if not log_file.exists():
        return []

    events: list[TrackingEvent] = []
    for line in log_file.read_text().strip().split("\n"):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            event = TrackingEvent(**data)
        except (json.JSONDecodeError, Exception):
            continue

        if since and event.timestamp < since:
            continue
        if until and event.timestamp > until:
            continue
        events.append(event)
    return events


def load_all_logs(
    project_root: Path,
    since: str | None = None,
    until: str | None = None,
) -> dict[str, list[TrackingEvent]]:
    """Load logs for all tracked agents. Returns {agent_name: [TrackingEvent, ...]}."""
    result: dict[str, list[TrackingEvent]] = {}
    for agent_name in list_tracked_agents(project_root):
        events = load_events(agent_name, project_root, since=since, until=until)
        if events:
            result[agent_name] = events
    return result


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Compute percentile from a sorted list using nearest-rank method."""
    if not sorted_values:
        return 0.0
    idx = int(len(sorted_values) * pct)
    idx = min(idx, len(sorted_values) - 1)
    return sorted_values[idx]


def compute_stats(
    agent_name: str,
    events: list[TrackingEvent],
) -> AgentProductionStats:
    """Compute aggregated statistics from a list of tracking events."""
    if not events:
        return AgentProductionStats(
            agent_name=agent_name,
            total_invocations=0,
            error_count=0,
            error_rate=0.0,
            latency_p50=0.0,
            latency_p95=0.0,
            latency_p99=0.0,
            avg_cost_usd=0.0,
            total_cost_usd=0.0,
            avg_input_tokens=0.0,
            avg_output_tokens=0.0,
            models_used=[],
            first_seen="",
            last_seen="",
            period_days=0.0,
        )

    total = len(events)
    error_count = sum(1 for e in events if e.error)
    latencies = sorted(e.latency_seconds for e in events)
    total_cost = sum(e.cost_usd for e in events)
    total_input = sum(e.input_tokens for e in events)
    total_output = sum(e.output_tokens for e in events)
    models = sorted(set(e.model for e in events))
    timestamps = sorted(e.timestamp for e in events)

    first = timestamps[0]
    last = timestamps[-1]

    # Compute period in days from ISO timestamps
    try:
        t_first = datetime.datetime.fromisoformat(first)
        t_last = datetime.datetime.fromisoformat(last)
        period_days = max((t_last - t_first).total_seconds() / 86400, 0.0)
    except (ValueError, TypeError):
        period_days = 0.0

    return AgentProductionStats(
        agent_name=agent_name,
        total_invocations=total,
        error_count=error_count,
        error_rate=error_count / total if total > 0 else 0.0,
        latency_p50=_percentile(latencies, 0.50),
        latency_p95=_percentile(latencies, 0.95),
        latency_p99=_percentile(latencies, 0.99),
        avg_cost_usd=total_cost / total if total > 0 else 0.0,
        total_cost_usd=total_cost,
        avg_input_tokens=total_input / total if total > 0 else 0.0,
        avg_output_tokens=total_output / total if total > 0 else 0.0,
        models_used=models,
        first_seen=first,
        last_seen=last,
        period_days=period_days,
    )


def compute_fleet_stats(
    project_root: Path,
    since: str | None = None,
) -> list[AgentProductionStats]:
    """Compute stats for all tracked agents. Returns sorted by agent name."""
    all_logs = load_all_logs(project_root, since=since)
    stats = [compute_stats(name, events) for name, events in all_logs.items()]
    return sorted(stats, key=lambda s: s.agent_name)
