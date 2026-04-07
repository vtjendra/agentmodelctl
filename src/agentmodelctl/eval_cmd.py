"""Eval command implementation."""

from __future__ import annotations

import typer
from dotenv import load_dotenv

from agentmodelctl.models import OutputFormat
from agentmodelctl.parser import load_project
from agentmodelctl.reporter import console, display_eval_results


def _parse_output_format(output_format: str) -> OutputFormat:
    """Parse and validate output format string."""
    try:
        return OutputFormat(output_format)
    except ValueError:
        valid = ", ".join(f.value for f in OutputFormat)
        console.print(f"[red]✗[/red] Invalid format '{output_format}'. Choose from: {valid}")
        raise typer.Exit(code=1)


def run_eval(
    agent_name: str | None = None,
    all_agents: bool = False,
    auto_generate: bool = False,
    output_format: str = "rich",
) -> None:
    """Run evaluations for agents."""
    load_dotenv()
    fmt = _parse_output_format(output_format)

    try:
        project = load_project()
    except FileNotFoundError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(code=1)

    if auto_generate:
        _run_auto_generate(project, agent_name)
        # Reload project to pick up new eval files
        project = load_project(project.project_root)

    # Determine which agents to eval
    if agent_name:
        if agent_name not in project.agents:
            console.print(f"[red]✗[/red] Agent '{agent_name}' not found.")
            console.print(f"  Available: {', '.join(sorted(project.agents.keys()))}")
            raise typer.Exit(code=1)
        target_agents = [agent_name]
    else:
        target_agents = list(project.agents.keys())

    # Check for evals
    agents_with_evals = [n for n in target_agents if n in project.evals]
    if not agents_with_evals:
        console.print("[yellow]No evals found.[/yellow] Run with --auto-generate to create them.")
        raise typer.Exit(code=1)

    # Run evals
    from agentmodelctl.formatter import (
        format_eval_results,
        format_eval_summary,
        summarize_agent_results,
    )
    from agentmodelctl.runner import run_agent_evals

    summaries = []
    for name in agents_with_evals:
        agent = project.agents[name]
        eval_files = project.evals[name]

        if fmt == OutputFormat.rich:
            console.print(f"\nRunning evals for [bold]{name}[/bold]...")

        try:
            results = run_agent_evals(
                agent=agent,
                eval_files=eval_files,
                models=project.models,
                config=project.config,
            )
            formatted = format_eval_results(name, results, fmt)
            if formatted is None:
                display_eval_results(name, results)
            else:
                summaries.append(summarize_agent_results(name, results))
        except (KeyError, ValueError) as e:
            console.print(f"  [red]✗[/red] {e}")
            continue

    # For structured formats, output all results together
    if summaries and fmt != OutputFormat.rich:
        output = format_eval_summary(summaries, fmt)
        if output:
            console.print(output, highlight=False)


def _run_auto_generate(project, agent_name: str | None) -> None:
    """Auto-generate evals for agents."""
    from agentmodelctl.generator import auto_generate_evals, save_eval_file

    if agent_name:
        if agent_name not in project.agents:
            console.print(f"[red]✗[/red] Agent '{agent_name}' not found.")
            raise typer.Exit(code=1)
        targets = {agent_name: project.agents[agent_name]}
    else:
        targets = project.agents

    for name, agent in targets.items():
        console.print(f"\nGenerating evals for [bold]{name}[/bold]...")

        try:
            eval_file = auto_generate_evals(
                agent=agent,
                models=project.models,
                config=project.config,
            )
            path = save_eval_file(eval_file, name, project.project_root)
            console.print(f"  [green]✓[/green] Created: {path.relative_to(project.project_root)}")
            console.print(f"    {len(eval_file.tests)} test cases generated")
        except Exception as e:
            console.print(f"  [red]✗[/red] Failed to generate evals: {e}")
