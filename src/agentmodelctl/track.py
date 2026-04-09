"""Lightweight production tracking SDK for agentmodelctl.

Usage:
    from agentmodelctl import track
    track.log(
        agent_name="support",
        model="claude-sonnet-4-6",
        latency_seconds=1.2,
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.003,
    )
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

from agentmodelctl.models import TrackingEvent


def _get_log_dir(project_root: Path | None = None) -> Path:
    """Locate or create .agentmodelctl/logs/ directory.

    If project_root is None, uses current working directory.
    """
    root = project_root or Path.cwd()
    log_dir = root / ".agentmodelctl" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _write_log_entry(entry: TrackingEvent, log_dir: Path) -> None:
    """Append a single TrackingEvent as one JSON line to {agent_name}.jsonl."""
    log_file = log_dir / f"{entry.agent_name}.jsonl"
    with open(log_file, "a") as f:
        f.write(entry.model_dump_json() + "\n")


def log(
    agent_name: str,
    model: str,
    latency_seconds: float,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float = 0.0,
    error: bool = False,
    metadata: dict[str, Any] | None = None,
    project_root: Path | None = None,
) -> None:
    """Log a production invocation. Public API.

    Creates a TrackingEvent with auto-generated ISO timestamp,
    validates via Pydantic, and appends to JSONL log file.
    """
    timestamp = datetime.datetime.now(datetime.UTC).isoformat()
    entry = TrackingEvent(
        timestamp=timestamp,
        agent_name=agent_name,
        model=model,
        latency_seconds=latency_seconds,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        error=error,
        metadata=metadata or {},
    )
    log_dir = _get_log_dir(project_root)
    _write_log_entry(entry, log_dir)
