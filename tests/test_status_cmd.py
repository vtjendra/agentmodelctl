"""Tests for the status command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from agentmodelctl.cli import app
from agentmodelctl.formatter import format_agent_detail, format_fleet_status
from agentmodelctl.models import AgentProductionStats, OutputFormat

runner = CliRunner()


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
) -> dict:
    return {
        "timestamp": timestamp,
        "agent_name": agent_name,
        "model": model,
        "latency_seconds": latency,
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_usd": cost,
        "error": error,
        "metadata": {},
    }


def _sample_stats(agent_name: str = "support") -> AgentProductionStats:
    return AgentProductionStats(
        agent_name=agent_name,
        total_invocations=100,
        error_count=5,
        error_rate=0.05,
        latency_p50=0.5,
        latency_p95=1.2,
        latency_p99=2.0,
        avg_cost_usd=0.01,
        total_cost_usd=1.0,
        avg_input_tokens=100.0,
        avg_output_tokens=50.0,
        models_used=["claude-sonnet-4-6"],
        first_seen="2026-04-01T00:00:00+00:00",
        last_seen="2026-04-08T00:00:00+00:00",
        period_days=7.0,
    )


class TestStatusCLI:
    def test_status_help(self) -> None:
        result = runner.invoke(app, ["status", "--help"])
        assert result.exit_code == 0
        assert "tracking logs" in result.output.lower() or "status" in result.output.lower()

    def test_status_no_project(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["status"])
        assert result.exit_code != 0

    def test_status_no_logs(self, tmp_path: Path, monkeypatch) -> None:
        # Create a minimal project so find_project_root works
        (tmp_path / "agentmodelctl.yaml").write_text("version: 1\nproject: test\n")
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["status"])
        assert "no tracking data" in result.output.lower()

    def test_status_with_logs(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "agentmodelctl.yaml").write_text("version: 1\nproject: test\n")
        monkeypatch.chdir(tmp_path)
        _write_events(
            tmp_path,
            "support",
            [
                _make_event(timestamp="2026-04-08T12:00:00+00:00"),
                _make_event(timestamp="2026-04-08T13:00:00+00:00"),
            ],
        )
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0

    def test_status_agent_not_found(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "agentmodelctl.yaml").write_text("version: 1\nproject: test\n")
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["status", "nonexistent"])
        assert result.exit_code != 0

    def test_status_json_format(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "agentmodelctl.yaml").write_text("version: 1\nproject: test\n")
        monkeypatch.chdir(tmp_path)
        _write_events(
            tmp_path,
            "support",
            [
                _make_event(timestamp="2026-04-08T12:00:00+00:00"),
            ],
        )
        result = runner.invoke(app, ["status", "-f", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["agent_name"] == "support"


class TestFormatFleetStatus:
    def test_json(self) -> None:
        stats = [_sample_stats()]
        result = format_fleet_status(stats, OutputFormat.json)
        assert result is not None
        data = json.loads(result)
        assert data[0]["agent_name"] == "support"

    def test_markdown(self) -> None:
        stats = [_sample_stats()]
        result = format_fleet_status(stats, OutputFormat.markdown)
        assert result is not None
        assert "## Fleet Production Status" in result
        assert "support" in result

    def test_rich_returns_none(self) -> None:
        stats = [_sample_stats()]
        assert format_fleet_status(stats, OutputFormat.rich) is None


class TestFormatAgentDetail:
    def test_json(self) -> None:
        stats = _sample_stats()
        result = format_agent_detail("support", stats, OutputFormat.json)
        assert result is not None
        data = json.loads(result)
        assert data["agent_name"] == "support"

    def test_markdown(self) -> None:
        stats = _sample_stats()
        result = format_agent_detail("support", stats, OutputFormat.markdown)
        assert result is not None
        assert "## Agent Detail: support" in result
        assert "p50" in result

    def test_rich_returns_none(self) -> None:
        stats = _sample_stats()
        assert format_agent_detail("support", stats, OutputFormat.rich) is None
