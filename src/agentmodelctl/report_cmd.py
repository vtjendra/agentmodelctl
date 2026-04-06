"""Report command implementation."""

from __future__ import annotations

import typer

from agentmodelctl.parser import load_project
from agentmodelctl.reporter import console, display_report


def run_report() -> None:
    """Generate a fleet health report."""
    try:
        project = load_project()
    except FileNotFoundError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(code=1)

    display_report(project)
