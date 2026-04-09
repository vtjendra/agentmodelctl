"""Tests for log loading and aggregation."""

from __future__ import annotations

import json
from pathlib import Path

from agentmodelctl.logs import (
    _percentile,
    compute_fleet_stats,
    compute_stats,
    get_log_dir,
    list_tracked_agents,
    load_all_logs,
    load_events,
)
from agentmodelctl.models import TrackingEvent


def _write_events(tmp_path: Path, agent_name: str, events: list[dict]) -> None:
    """Helper to write JSONL log entries."""
    log_dir = tmp_path / ".agentmodelctl" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{agent_name}.jsonl"
    with open(log_file, "a") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")


def _make_event(
    agent_name: str = "support",
    timestamp: str = "2026-04-08T12:00:00+00:00",
    model: str = "claude-sonnet-4-6",
    latency: float = 1.0,
    error: bool = False,
    cost: float = 0.01,
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> dict:
    return {
        "timestamp": timestamp,
        "agent_name": agent_name,
        "model": model,
        "latency_seconds": latency,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
        "error": error,
        "metadata": {},
    }


class TestGetLogDir:
    def test_returns_correct_path(self, tmp_path: Path) -> None:
        assert get_log_dir(tmp_path) == tmp_path / ".agentmodelctl" / "logs"

    def test_nonexistent_dir_no_error(self, tmp_path: Path) -> None:
        log_dir = get_log_dir(tmp_path)
        assert not log_dir.exists()


class TestListTrackedAgents:
    def test_no_logs(self, tmp_path: Path) -> None:
        assert list_tracked_agents(tmp_path) == []

    def test_finds_agents(self, tmp_path: Path) -> None:
        _write_events(tmp_path, "support", [_make_event()])
        _write_events(tmp_path, "sales", [_make_event(agent_name="sales")])
        result = list_tracked_agents(tmp_path)
        assert result == ["sales", "support"]

    def test_ignores_non_jsonl(self, tmp_path: Path) -> None:
        log_dir = tmp_path / ".agentmodelctl" / "logs"
        log_dir.mkdir(parents=True)
        (log_dir / "notes.txt").write_text("not a log")
        _write_events(tmp_path, "support", [_make_event()])
        assert list_tracked_agents(tmp_path) == ["support"]


class TestLoadEvents:
    def test_loads_entries(self, tmp_path: Path) -> None:
        events = [_make_event(timestamp=f"2026-04-08T12:0{i}:00+00:00") for i in range(3)]
        _write_events(tmp_path, "support", events)
        loaded = load_events("support", tmp_path)
        assert len(loaded) == 3
        assert all(isinstance(e, TrackingEvent) for e in loaded)

    def test_skips_malformed(self, tmp_path: Path) -> None:
        log_dir = tmp_path / ".agentmodelctl" / "logs"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "support.jsonl"
        good = json.dumps(_make_event())
        log_file.write_text(good + "\n" + "not valid json\n" + good + "\n")
        loaded = load_events("support", tmp_path)
        assert len(loaded) == 2

    def test_missing_file(self, tmp_path: Path) -> None:
        assert load_events("nonexistent", tmp_path) == []

    def test_since_filter(self, tmp_path: Path) -> None:
        events = [
            _make_event(timestamp="2026-04-01T00:00:00+00:00"),
            _make_event(timestamp="2026-04-05T00:00:00+00:00"),
            _make_event(timestamp="2026-04-08T00:00:00+00:00"),
        ]
        _write_events(tmp_path, "support", events)
        loaded = load_events("support", tmp_path, since="2026-04-04T00:00:00+00:00")
        assert len(loaded) == 2

    def test_until_filter(self, tmp_path: Path) -> None:
        events = [
            _make_event(timestamp="2026-04-01T00:00:00+00:00"),
            _make_event(timestamp="2026-04-05T00:00:00+00:00"),
            _make_event(timestamp="2026-04-08T00:00:00+00:00"),
        ]
        _write_events(tmp_path, "support", events)
        loaded = load_events("support", tmp_path, until="2026-04-06T00:00:00+00:00")
        assert len(loaded) == 2


class TestLoadAllLogs:
    def test_loads_multiple_agents(self, tmp_path: Path) -> None:
        _write_events(tmp_path, "support", [_make_event()])
        _write_events(tmp_path, "sales", [_make_event(agent_name="sales")])
        result = load_all_logs(tmp_path)
        assert "support" in result
        assert "sales" in result

    def test_empty_when_no_logs(self, tmp_path: Path) -> None:
        assert load_all_logs(tmp_path) == {}


class TestPercentile:
    def test_basic(self) -> None:
        values = list(range(100))
        assert _percentile(values, 0.50) == 50
        assert _percentile(values, 0.95) == 95
        assert _percentile(values, 0.99) == 99

    def test_single_value(self) -> None:
        assert _percentile([5.0], 0.50) == 5.0
        assert _percentile([5.0], 0.95) == 5.0

    def test_empty(self) -> None:
        assert _percentile([], 0.50) == 0.0


class TestComputeStats:
    def test_basic_stats(self) -> None:
        events = [
            TrackingEvent(
                **_make_event(
                    timestamp=f"2026-04-0{i + 1}T12:00:00+00:00",
                    latency=float(i + 1),
                    cost=0.01 * (i + 1),
                    input_tokens=100 * (i + 1),
                    output_tokens=50 * (i + 1),
                )
            )
            for i in range(10)
        ]
        stats = compute_stats("support", events)
        assert stats.agent_name == "support"
        assert stats.total_invocations == 10
        assert stats.total_cost_usd == sum(0.01 * (i + 1) for i in range(10))
        assert stats.models_used == ["claude-sonnet-4-6"]

    def test_error_rate(self) -> None:
        events = []
        for i in range(10):
            events.append(
                TrackingEvent(
                    **_make_event(
                        timestamp=f"2026-04-0{i + 1}T12:00:00+00:00",
                        error=(i < 3),
                    )
                )
            )
        stats = compute_stats("support", events)
        assert stats.error_count == 3
        assert abs(stats.error_rate - 0.3) < 0.001

    def test_latency_percentiles(self) -> None:
        events = [
            TrackingEvent(
                **_make_event(
                    timestamp=f"2026-04-08T12:{i:02d}:00+00:00",
                    latency=float(i + 1),
                )
            )
            for i in range(20)
        ]
        stats = compute_stats("support", events)
        assert stats.latency_p50 == 11.0  # index 10 of sorted 1-20
        assert stats.latency_p95 == 20.0  # index 19
        assert stats.latency_p99 == 20.0  # index 19

    def test_single_entry(self) -> None:
        events = [TrackingEvent(**_make_event())]
        stats = compute_stats("support", events)
        assert stats.latency_p50 == 1.0
        assert stats.latency_p95 == 1.0
        assert stats.latency_p99 == 1.0

    def test_models_used(self) -> None:
        events = [
            TrackingEvent(
                **_make_event(
                    model="gpt-4o",
                    timestamp="2026-04-01T00:00:00+00:00",
                )
            ),
            TrackingEvent(
                **_make_event(
                    model="claude-sonnet-4-6",
                    timestamp="2026-04-02T00:00:00+00:00",
                )
            ),
            TrackingEvent(
                **_make_event(
                    model="gpt-4o",
                    timestamp="2026-04-03T00:00:00+00:00",
                )
            ),
        ]
        stats = compute_stats("support", events)
        assert stats.models_used == ["claude-sonnet-4-6", "gpt-4o"]

    def test_empty_events(self) -> None:
        stats = compute_stats("support", [])
        assert stats.total_invocations == 0
        assert stats.error_rate == 0.0
        assert stats.latency_p50 == 0.0
        assert stats.models_used == []

    def test_period_days(self) -> None:
        events = [
            TrackingEvent(**_make_event(timestamp="2026-04-01T00:00:00+00:00")),
            TrackingEvent(**_make_event(timestamp="2026-04-08T00:00:00+00:00")),
        ]
        stats = compute_stats("support", events)
        assert abs(stats.period_days - 7.0) < 0.01


class TestComputeFleetStats:
    def test_multiple_agents(self, tmp_path: Path) -> None:
        _write_events(tmp_path, "support", [_make_event()])
        _write_events(tmp_path, "sales", [_make_event(agent_name="sales")])
        stats = compute_fleet_stats(tmp_path)
        assert len(stats) == 2
        assert stats[0].agent_name == "sales"
        assert stats[1].agent_name == "support"

    def test_empty(self, tmp_path: Path) -> None:
        assert compute_fleet_stats(tmp_path) == []
