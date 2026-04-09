"""Tests for the production tracking SDK."""

from __future__ import annotations

import json
from pathlib import Path

from agentmodelctl.models import TrackingEvent
from agentmodelctl.track import _get_log_dir, _write_log_entry, log


class TestTrackingEvent:
    """Tests for the TrackingEvent Pydantic model."""

    def test_valid_entry(self) -> None:
        entry = TrackingEvent(
            timestamp="2026-04-08T12:00:00+00:00",
            agent_name="support",
            model="claude-sonnet-4-6",
            latency_seconds=1.2,
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.003,
        )
        assert entry.agent_name == "support"
        assert entry.model == "claude-sonnet-4-6"
        assert entry.latency_seconds == 1.2

    def test_defaults(self) -> None:
        entry = TrackingEvent(
            timestamp="2026-04-08T12:00:00+00:00",
            agent_name="support",
            model="gpt-4o",
            latency_seconds=0.5,
        )
        assert entry.input_tokens == 0
        assert entry.output_tokens == 0
        assert entry.cost_usd == 0.0
        assert entry.error is False
        assert entry.metadata == {}

    def test_no_content_fields(self) -> None:
        """TrackingEvent should not have prompt/response/content fields."""
        fields = TrackingEvent.model_fields
        assert "content" not in fields
        assert "prompt" not in fields
        assert "response" not in fields


class TestGetLogDir:
    """Tests for _get_log_dir."""

    def test_creates_log_dir(self, tmp_path: Path) -> None:
        log_dir = _get_log_dir(tmp_path)
        assert log_dir == tmp_path / ".agentmodelctl" / "logs"
        assert log_dir.exists()

    def test_idempotent(self, tmp_path: Path) -> None:
        _get_log_dir(tmp_path)
        log_dir = _get_log_dir(tmp_path)
        assert log_dir.exists()

    def test_uses_cwd_when_none(self, tmp_path: Path, monkeypatch: object) -> None:
        monkeypatch.chdir(tmp_path)
        log_dir = _get_log_dir(None)
        assert log_dir == tmp_path / ".agentmodelctl" / "logs"


class TestWriteLogEntry:
    """Tests for _write_log_entry."""

    def test_writes_jsonl_line(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        entry = TrackingEvent(
            timestamp="2026-04-08T12:00:00+00:00",
            agent_name="support",
            model="claude-sonnet-4-6",
            latency_seconds=1.2,
        )
        _write_log_entry(entry, log_dir)

        log_file = log_dir / "support.jsonl"
        assert log_file.exists()
        data = json.loads(log_file.read_text().strip())
        assert data["agent_name"] == "support"
        assert data["latency_seconds"] == 1.2

    def test_appends_multiple(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        for i in range(3):
            entry = TrackingEvent(
                timestamp=f"2026-04-08T12:0{i}:00+00:00",
                agent_name="support",
                model="gpt-4o",
                latency_seconds=float(i),
            )
            _write_log_entry(entry, log_dir)

        lines = (log_dir / "support.jsonl").read_text().strip().split("\n")
        assert len(lines) == 3


class TestLog:
    """Tests for the public log() function."""

    def test_basic_log(self, tmp_path: Path) -> None:
        log(
            agent_name="support",
            model="claude-sonnet-4-6",
            latency_seconds=1.2,
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.003,
            project_root=tmp_path,
        )
        log_file = tmp_path / ".agentmodelctl" / "logs" / "support.jsonl"
        assert log_file.exists()
        data = json.loads(log_file.read_text().strip())
        assert data["agent_name"] == "support"
        assert data["cost_usd"] == 0.003

    def test_auto_timestamp(self, tmp_path: Path) -> None:
        log(
            agent_name="support",
            model="gpt-4o",
            latency_seconds=0.5,
            project_root=tmp_path,
        )
        log_file = tmp_path / ".agentmodelctl" / "logs" / "support.jsonl"
        data = json.loads(log_file.read_text().strip())
        assert "timestamp" in data
        # ISO format contains 'T'
        assert "T" in data["timestamp"]

    def test_error_flag(self, tmp_path: Path) -> None:
        log(
            agent_name="support",
            model="gpt-4o",
            latency_seconds=0.5,
            error=True,
            project_root=tmp_path,
        )
        log_file = tmp_path / ".agentmodelctl" / "logs" / "support.jsonl"
        data = json.loads(log_file.read_text().strip())
        assert data["error"] is True

    def test_metadata(self, tmp_path: Path) -> None:
        log(
            agent_name="support",
            model="gpt-4o",
            latency_seconds=0.5,
            metadata={"region": "us-east-1", "user_id": "abc123"},
            project_root=tmp_path,
        )
        log_file = tmp_path / ".agentmodelctl" / "logs" / "support.jsonl"
        data = json.loads(log_file.read_text().strip())
        assert data["metadata"]["region"] == "us-east-1"

    def test_file_per_agent(self, tmp_path: Path) -> None:
        log(agent_name="support", model="gpt-4o", latency_seconds=0.5, project_root=tmp_path)
        log(agent_name="sales", model="gpt-4o", latency_seconds=0.3, project_root=tmp_path)

        logs_dir = tmp_path / ".agentmodelctl" / "logs"
        assert (logs_dir / "support.jsonl").exists()
        assert (logs_dir / "sales.jsonl").exists()
