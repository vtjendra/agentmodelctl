"""Implementation of the `agentmodelctl status` command."""

from __future__ import annotations

import datetime

import typer
from rich.console import Console

from agentmodelctl.formatter import format_agent_detail, format_fleet_status
from agentmodelctl.logs import compute_fleet_stats, compute_stats, load_events
from agentmodelctl.models import OutputFormat

console = Console()


def _parse_output_format(output_format: str) -> OutputFormat:
    """Parse and validate output format string."""
    try:
        return OutputFormat(output_format)
    except ValueError:
        console.print(f"[red]Unknown format: {output_format}[/red]")
        console.print("Use: rich, json, markdown")
        raise typer.Exit(code=1)


def run_status(
    agent_name: str | None = None,
    detail: bool = False,
    days: int = 7,
    output_format: str = "rich",
) -> None:
    """Run the status command.

    If agent_name is None: show fleet overview.
    If agent_name is set: show per-agent detail.
    """
    from agentmodelctl.parser import find_project_root

    fmt = _parse_output_format(output_format)

    try:
        project_root = find_project_root()
    except SystemExit:
        console.print("[red]No agentmodelctl project found.[/red]")
        raise typer.Exit(code=1)

    # Time window filter
    since = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=days)).isoformat()

    if agent_name:
        _show_agent_detail(agent_name, project_root, since, fmt)
    else:
        _show_fleet_overview(project_root, since, fmt)


def _show_fleet_overview(project_root, since: str, fmt: OutputFormat) -> None:
    """Display fleet overview from production logs."""
    from agentmodelctl.reporter import display_fleet_status

    stats = compute_fleet_stats(project_root, since=since)

    if not stats:
        console.print("[yellow]No tracking data found.[/yellow]")
        console.print("Start logging with: [bold]from agentmodelctl import track[/bold]")
        return

    output = format_fleet_status(stats, fmt)
    if output is not None:
        console.print(output)
    else:
        display_fleet_status(stats)


def _show_agent_detail(agent_name: str, project_root, since: str, fmt: OutputFormat) -> None:
    """Display per-agent detail view."""
    from agentmodelctl.reporter import display_agent_detail

    events = load_events(agent_name, project_root, since=since)

    if not events:
        console.print(f"[yellow]No tracking data for agent '{agent_name}'.[/yellow]")
        raise typer.Exit(code=1)

    stats = compute_stats(agent_name, events)

    output = format_agent_detail(agent_name, stats, fmt)
    if output is not None:
        console.print(output)
    else:
        display_agent_detail(agent_name, stats, events)
