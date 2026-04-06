"""Compare command implementation."""

from __future__ import annotations

import typer
from dotenv import load_dotenv

from agentmodelctl.parser import load_project
from agentmodelctl.reporter import console, display_compare_table


def run_compare(agent_name: str, models: list[str]) -> None:
    """Compare an agent across multiple models."""
    load_dotenv()

    try:
        project = load_project()
    except FileNotFoundError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(code=1)

    # Verify agent exists
    if agent_name not in project.agents:
        console.print(f"[red]✗[/red] Agent '{agent_name}' not found.")
        console.print(f"  Available: {', '.join(sorted(project.agents.keys()))}")
        raise typer.Exit(code=1)

    # Verify agent has evals
    eval_files = project.evals.get(agent_name, [])
    if not eval_files:
        console.print(
            f"[yellow]No evals found for '{agent_name}'.[/yellow] "
            f"Run: agentmodelctl eval --auto-generate {agent_name}"
        )
        raise typer.Exit(code=1)

    agent = project.agents[agent_name]

    from agentmodelctl.runner import run_agent_evals

    model_results: dict[str, dict] = {}

    for model_str in models:
        console.print(f"  Running evals with [bold]{model_str}[/bold]...")

        try:
            results = run_agent_evals(
                agent=agent,
                eval_files=eval_files,
                models=project.models,
                config=project.config,
                model_override=model_str,
            )
            model_results[model_str] = {"results": results}
        except (KeyError, ValueError) as e:
            console.print(f"  [red]✗[/red] {model_str}: {e}")
            model_results[model_str] = {"results": []}

    console.print()
    display_compare_table(agent_name, model_results)
