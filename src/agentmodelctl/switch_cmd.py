"""Switch command implementation."""

from __future__ import annotations

import typer
from dotenv import load_dotenv

from agentmodelctl.parser import load_project
from agentmodelctl.reporter import console, display_switch_verdict


def run_switch(
    alias: str,
    new_model: str,
    dry_run: bool = False,
    only: str | None = None,
) -> None:
    """Switch a model alias to a new model."""
    load_dotenv()

    try:
        project = load_project()
    except FileNotFoundError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(code=1)

    # Verify alias exists
    if alias not in project.models.aliases:
        available = ", ".join(sorted(project.models.aliases.keys()))
        console.print(f"[red]✗[/red] Model alias '{alias}' not found in models.yaml.")
        console.print(f"  Available: {available}")
        raise typer.Exit(code=1)

    # Parse only filter
    only_list = [s.strip() for s in only.split(",")] if only else None

    from agentmodelctl.switch import apply_switch, find_affected_agents, run_dry_run

    # Check affected agents
    affected = find_affected_agents(alias, project.agents, only=only_list)
    if not affected:
        console.print(f"[yellow]No agents use the '{alias}' alias.[/yellow]")
        return

    # Run dry-run (always, to show verdict)
    console.print(f"\nRunning evals for {len(affected)} affected agent(s)...\n")
    old_model, agent_results = run_dry_run(
        alias=alias,
        new_model=new_model,
        project=project,
        only=only_list,
    )

    # Enrich with production data if available
    from agentmodelctl.logs import compute_stats, load_events

    production_stats = {}
    for agent_name_key in agent_results:
        events = load_events(agent_name_key, project.project_root)
        if events:
            production_stats[agent_name_key] = compute_stats(agent_name_key, events)
        else:
            production_stats[agent_name_key] = None

    display_switch_verdict(
        alias, old_model, new_model, agent_results, production_stats=production_stats
    )

    if dry_run:
        return

    # Prompt for confirmation
    if not typer.confirm("\nApply this switch?"):
        console.print("Switch cancelled.")
        return

    apply_switch(alias, new_model, project.project_root)
    console.print(f"\n[green]✓[/green] Updated models.yaml: {alias} → {new_model}")
