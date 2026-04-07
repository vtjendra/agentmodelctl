"""CI command implementation — optimized eval runner for CI/CD pipelines."""

from __future__ import annotations

import typer
from dotenv import load_dotenv

from agentmodelctl.models import OutputFormat
from agentmodelctl.reporter import console


def run_ci(
    ref: str = "HEAD",
    output_format: str = "markdown",
    use_cache: bool = True,
    fail_on_regression: bool = True,
    all_agents: bool = False,
) -> None:
    """Run CI-optimized evals with change detection and caching."""
    load_dotenv()

    from agentmodelctl.eval_cmd import _parse_output_format

    fmt = _parse_output_format(output_format)

    from agentmodelctl.parser import load_project

    try:
        project = load_project()
    except FileNotFoundError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(code=1)

    # Determine which agents to evaluate
    if all_agents:
        target_agents = list(project.agents.keys())
    else:
        from agentmodelctl.change_detector import detect_affected_agents, get_changed_files

        try:
            changed_files = get_changed_files(ref, project_root=project.project_root)
        except RuntimeError as e:
            console.print(f"[red]✗[/red] {e}")
            raise typer.Exit(code=1)

        target_agents = detect_affected_agents(changed_files, project)

        if not target_agents:
            msg = "No agent configs changed — nothing to evaluate."
            if fmt == OutputFormat.rich:
                console.print(f"[green]✓[/green] {msg}")
            elif fmt == OutputFormat.markdown:
                console.print("## agentmodelctl CI Report\n\n" + msg, highlight=False)
            elif fmt == OutputFormat.json:
                console.print('{"status": "skip", "message": "' + msg + '"}', highlight=False)
            raise typer.Exit(code=0)

    # Filter to agents that have evals
    agents_with_evals = [n for n in target_agents if n in project.evals]
    if not agents_with_evals:
        msg = "Affected agents have no evals defined. Run `agentmodelctl eval --auto-generate`."
        if fmt == OutputFormat.rich:
            console.print(f"[yellow]⚠[/yellow] {msg}")
        else:
            console.print(msg, highlight=False)
        raise typer.Exit(code=1)

    # Run evals
    from agentmodelctl.formatter import (
        format_eval_summary,
        summarize_agent_results,
    )
    from agentmodelctl.reporter import display_eval_results
    from agentmodelctl.runner import run_agent_evals

    summaries = []
    any_failures = False

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
                use_cache=use_cache,
                project_root=project.project_root,
            )

            summary = summarize_agent_results(name, results)
            summaries.append(summary)

            if summary.failed > 0:
                any_failures = True

            if fmt == OutputFormat.rich:
                display_eval_results(name, results)
        except (KeyError, ValueError) as e:
            console.print(f"[red]✗[/red] {name}: {e}")
            any_failures = True
            continue

    # Output formatted results
    if summaries and fmt != OutputFormat.rich:
        output = format_eval_summary(summaries, fmt)
        if output:
            console.print(output, highlight=False)

    # Exit code
    if fail_on_regression and any_failures:
        raise typer.Exit(code=1)
