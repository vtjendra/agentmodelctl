"""agentmodelctl CLI — Fleet management for AI agents."""

from __future__ import annotations

import typer

from agentmodelctl import __version__

app = typer.Typer(
    name="agentmodelctl",
    help="Fleet management for AI agents — know what breaks before you switch models.",
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"agentmodelctl {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """agentmodelctl — Fleet management for AI agents."""


@app.command()
def init(
    template: str = typer.Option(
        "custom", help="Template: customer-support, productivity, sales, custom"
    ),
) -> None:
    """Scaffold a new agentmodelctl project."""
    from agentmodelctl.init_cmd import run_init

    run_init(template)


@app.command(name="list")
def list_agents(
    env: str | None = typer.Option(None, help="Filter by environment"),
    owner: str | None = typer.Option(None, help="Filter by owner"),
    tag: str | None = typer.Option(None, help="Filter by tag"),
) -> None:
    """Show fleet overview — agents, models, eval status."""
    from agentmodelctl.parser import load_project
    from agentmodelctl.reporter import display_agent_list

    project = load_project()
    display_agent_list(project, env=env, owner=owner, tag=tag)


@app.command()
def validate() -> None:
    """Validate all project configuration files."""
    from agentmodelctl.validate_cmd import run_validate

    run_validate()


@app.command(name="eval")
def eval_cmd(
    agent_name: str | None = typer.Argument(None, help="Agent to evaluate (all if omitted)"),
    all_agents: bool = typer.Option(False, "--all", help="Run all agents"),
    auto_generate: bool = typer.Option(
        False, "--auto-generate", help="Generate evals from agent definition"
    ),
    output_format: str = typer.Option(
        "rich", "--format", "-f", help="Output: rich, json, markdown"
    ),
) -> None:
    """Run evaluations for agents (quality + speed + cost)."""
    from agentmodelctl.eval_cmd import run_eval

    run_eval(
        agent_name=agent_name,
        all_agents=all_agents,
        auto_generate=auto_generate,
        output_format=output_format,
    )


@app.command()
def switch(
    alias: str = typer.Argument(help="Model alias to switch"),
    new_model: str = typer.Argument(help="New model string"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without applying"),
    only: str | None = typer.Option(None, help="Comma-separated list of agents to include"),
) -> None:
    """Switch a model alias to a new model."""
    from agentmodelctl.switch_cmd import run_switch

    run_switch(alias=alias, new_model=new_model, dry_run=dry_run, only=only)


@app.command()
def compare(
    agent_name: str = typer.Argument(help="Agent to compare"),
    models: list[str] = typer.Option(..., "--models", "-m", help="Models to compare"),
) -> None:
    """Compare an agent across multiple models side by side."""
    from agentmodelctl.compare_cmd import run_compare

    run_compare(agent_name=agent_name, models=models)


@app.command()
def report() -> None:
    """Generate a fleet health report."""
    from agentmodelctl.report_cmd import run_report

    run_report()
