"""Rich terminal output for agentmodelctl."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agentmodelctl.models import (
    AgentProductionStats,
    Anomaly,
    EvalResult,
    Project,
    TrackingEvent,
)

console = Console()


def display_agent_list(
    project: Project,
    env: str | None = None,
    owner: str | None = None,
    tag: str | None = None,
) -> None:
    """Display fleet overview table."""
    table = Table(title="Agent Fleet")
    table.add_column("Agent", style="bold")
    table.add_column("Model Alias")
    table.add_column("Actual Model")
    table.add_column("Evals")
    table.add_column("Status")

    agents = project.agents
    models = project.models

    # Apply filters
    filtered = {}
    for name, agent in agents.items():
        if env and agent.metadata.env != env:
            continue
        if owner and agent.metadata.owner != owner:
            continue
        if tag and tag not in agent.metadata.tags:
            continue
        filtered[name] = agent

    if not filtered:
        console.print("[yellow]No agents found.[/yellow]")
        return

    provider_set = set()
    for name, agent in sorted(filtered.items()):
        # Resolve model
        alias = agent.model
        if alias in models.aliases:
            actual = models.aliases[alias].model
            provider_set.add(models.aliases[alias].provider)
        else:
            actual = f"[red]unknown ({alias})[/red]"

        # Eval status
        agent_evals = project.evals.get(name, [])
        total_tests = sum(len(ef.tests) for ef in agent_evals)
        if total_tests == 0:
            eval_str = "[dim]—[/dim]"
            status = "[dim]no evals[/dim]"
        else:
            eval_str = f"{total_tests} tests"
            status = "[green]active[/green]"

        table.add_row(name, alias, actual, eval_str, status)

    console.print(table)

    # Summary line
    alias_count = len(set(a.model for a in filtered.values()))
    console.print(
        f"\n{len(filtered)} agents | {alias_count} model tiers | {len(provider_set)} providers"
    )


def display_validation_results(
    errors: list[str], warnings: list[str], successes: list[str]
) -> None:
    """Display validation results."""
    for msg in successes:
        console.print(f"  [green]✓[/green] {msg}")
    for msg in warnings:
        console.print(f"  [yellow]⚠[/yellow] {msg}")
    for msg in errors:
        console.print(f"  [red]✗[/red] {msg}")

    if errors:
        console.print(f"\n[red]{len(errors)} error(s) found. Fix before running evals.[/red]")
    elif warnings:
        console.print(f"\n[yellow]{len(warnings)} warning(s).[/yellow] No errors.")
    else:
        console.print("\n[green]All checks passed.[/green]")


def display_eval_results(agent_name: str, results: list[EvalResult]) -> None:
    """Display eval results as a Rich table."""
    table = Table(title=f"{agent_name}")
    table.add_column("Test", style="bold")
    table.add_column("Quality", justify="right")
    table.add_column("Latency", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Cost", justify="right")

    passed = 0
    total_latency = 0.0
    total_cost = 0.0
    total_quality = 0.0

    for r in results:
        status = "[green]✓[/green]" if r.passed else "[red]✗[/red]"
        quality_str = f"{status} {r.quality_score:.2f}"
        latency_str = f"{r.latency_seconds:.1f}s"
        tokens_str = str(r.input_tokens + r.output_tokens)
        cost_str = f"${r.cost_usd:.4f}"
        table.add_row(r.test_name, quality_str, latency_str, tokens_str, cost_str)
        if r.passed:
            passed += 1
        total_latency += r.latency_seconds
        total_cost += r.cost_usd
        total_quality += r.quality_score

    console.print(table)

    n = len(results)
    if n > 0:
        avg_latency = total_latency / n
        avg_quality = total_quality / n
        console.print(
            f"\n  SUMMARY: {passed}/{n} passed | "
            f"avg {avg_latency:.2f}s | "
            f"avg ${total_cost / n:.4f}/call | "
            f"quality {avg_quality:.2f}"
        )


def display_switch_verdict(
    alias: str,
    old_model: str,
    new_model: str,
    agent_results: dict[str, dict],
    production_stats: dict[str, AgentProductionStats | None] | None = None,
) -> None:
    """Display the switch dry-run verdict as a Rich panel."""
    lines: list[str] = []
    lines.append(f"  [bold]MODEL SWITCH: {alias}[/bold]")
    lines.append(f"  {old_model} → {new_model}")
    lines.append("")

    safe_count = 0
    risky_count = 0
    total_savings = 0.0

    for agent_name, data in agent_results.items():
        old_results: list[EvalResult] = data["old"]
        new_results: list[EvalResult] = data["new"]

        new_passed = sum(1 for r in new_results if r.passed)
        total_tests = len(new_results)

        old_cost = sum(r.cost_usd for r in old_results)
        new_cost = sum(r.cost_usd for r in new_results)
        cost_savings = (old_cost - new_cost) * 1000  # per 1K calls

        old_avg_latency = sum(r.latency_seconds for r in old_results) / max(len(old_results), 1)
        new_avg_latency = sum(r.latency_seconds for r in new_results) / max(len(new_results), 1)
        latency_diff_ms = (old_avg_latency - new_avg_latency) * 1000

        old_quality = sum(r.quality_score for r in old_results) / max(len(old_results), 1)
        new_quality = sum(r.quality_score for r in new_results) / max(len(new_results), 1)

        all_passed = new_passed == total_tests
        if all_passed:
            safe_count += 1
            verdict = "[green]✅ SAFE[/green]"
        else:
            risky_count += 1
            verdict = "[yellow]⚠ RISKY[/yellow]"

        lines.append(
            f"  [bold]{agent_name}[/bold]         {new_passed}/{total_tests} pass        {verdict}"
        )

        # Show failures
        for r in new_results:
            if not r.passed:
                for f in r.failures:
                    lines.append(f"    [red]✗[/red] {r.test_name} — {f}")

        if cost_savings > 0:
            lines.append(f"    💰 saves ${cost_savings:.2f} / 1K calls")
        elif cost_savings < 0:
            lines.append(f"    💰 costs ${-cost_savings:.2f} more / 1K calls")

        if latency_diff_ms > 0:
            lines.append(f"    ⚡ {latency_diff_ms:.0f}ms faster avg")
        elif latency_diff_ms < 0:
            lines.append(f"    ⚡ {-latency_diff_ms:.0f}ms slower avg")

        quality_pct = ((new_quality - old_quality) / max(old_quality, 0.001)) * 100
        lines.append(f"    📊 quality: {old_quality:.2f} → {new_quality:.2f} ({quality_pct:+.1f}%)")

        # Production volume context (if available)
        prod = (production_stats or {}).get(agent_name)
        if prod and prod.total_invocations > 0:
            daily_rate = prod.total_invocations / max(prod.period_days, 1.0)
            lines.append(
                f"    🏭 production: {prod.total_invocations:,} calls ({daily_rate:,.0f}/day)"
            )
            if cost_savings != 0:
                # Per-call savings * daily rate * 30 days
                old_per_call = sum(r.cost_usd for r in old_results) / max(len(old_results), 1)
                new_per_call = sum(r.cost_usd for r in new_results) / max(len(new_results), 1)
                monthly = (old_per_call - new_per_call) * daily_rate * 30
                if monthly > 0:
                    lines.append(f"    💰 estimated savings: ${monthly:.2f}/month")
                elif monthly < 0:
                    lines.append(f"    💰 estimated extra cost: ${-monthly:.2f}/month")

        lines.append("")
        total_savings += cost_savings

    lines.append(f"  [bold]VERDICT: {safe_count} safe to switch, {risky_count} needs work[/bold]")
    if total_savings > 0:
        lines.append(f"  [bold]POTENTIAL SAVINGS: ${total_savings:.2f} / 1K calls[/bold]")

    content = "\n".join(lines)
    panel = Panel(
        content,
        title=f"MODEL SWITCH: {alias}",
        subtitle=f"{old_model} → {new_model}",
        border_style="bold",
    )
    console.print(panel)


def display_compare_table(
    agent_name: str,
    model_results: dict[str, dict],
) -> None:
    """Display model comparison table."""
    table = Table(title=f"MODEL COMPARISON: {agent_name}")
    table.add_column("Model", style="bold")
    table.add_column("Quality", justify="right")
    table.add_column("Latency", justify="right")
    table.add_column("Cost/1K", justify="right")
    table.add_column("QPD", justify="right")

    best_qpd = ("", 0.0)
    cheapest = ("", float("inf"))

    for model, data in model_results.items():
        results: list[EvalResult] = data["results"]
        if not results:
            continue
        n = len(results)
        avg_quality = sum(r.quality_score for r in results) / n
        avg_latency = sum(r.latency_seconds for r in results) / n
        total_cost = sum(r.cost_usd for r in results)
        cost_per_1k = total_cost * 1000 / n
        qpd = avg_quality / max(cost_per_1k, 0.001)

        note = ""
        if qpd > best_qpd[1]:
            best_qpd = (model, qpd)
        if cost_per_1k < cheapest[1]:
            cheapest = (model, cost_per_1k)

        table.add_row(
            model,
            f"{avg_quality:.2f}",
            f"{avg_latency:.1f}s",
            f"${cost_per_1k:.2f}",
            f"{qpd:.2f}{note}",
        )

    console.print(table)
    console.print("\nQPD = Quality Per Dollar (higher = better value)")
    if best_qpd[0]:
        console.print(f"  Best value: [bold]{best_qpd[0]}[/bold]")
    if cheapest[0] and cheapest[0] != best_qpd[0]:
        console.print(f"  Cheapest: [bold]{cheapest[0]}[/bold]")


def display_report(project: Project) -> None:
    """Display fleet health report."""
    agents = project.agents
    models_config = project.models
    evals = project.evals

    total_agents = len(agents)
    total_evals = sum(sum(len(ef.tests) for ef in eval_files) for eval_files in evals.values())
    agents_with_evals = len(evals)
    agents_without_evals = [n for n in agents if n not in evals]

    # Provider distribution
    providers: dict[str, int] = {}
    for agent in agents.values():
        alias = agent.model
        if alias in models_config.aliases:
            prov = models_config.aliases[alias].provider
            providers[prov] = providers.get(prov, 0) + 1

    console.print(Panel("[bold]FLEET HEALTH REPORT[/bold]", border_style="bold"))
    console.print(f"\nAgents: {total_agents} total")
    console.print(f"Models: {len(models_config.aliases)} aliases across {len(providers)} providers")
    console.print(f"Evals:  {total_evals} total ({agents_with_evals} agents covered)")

    # Warnings
    warnings = []
    if agents_without_evals:
        for name in agents_without_evals:
            warnings.append(f"{name} has no evals defined")

    # Provider concentration
    if len(providers) == 1 and total_agents > 1:
        prov = list(providers.keys())[0]
        warnings.append(f"100% provider concentration on {prov.title()} for {total_agents} agents")

    if warnings:
        console.print("\n[yellow]⚠ ATTENTION:[/yellow]")
        for w in warnings:
            console.print(f"  • {w}")

    # Cost estimates per tier
    console.print("\n[bold]💰 MODEL TIERS:[/bold]")
    alias_agents: dict[str, list[str]] = {}
    for name, agent in agents.items():
        alias_agents.setdefault(agent.model, []).append(name)
    for alias, agent_names in sorted(alias_agents.items()):
        if alias in models_config.aliases:
            model = models_config.aliases[alias].model
            console.print(f"  {alias} tier: {model} ({len(agent_names)} agents)")


def display_fleet_status(
    stats: list[AgentProductionStats],
    anomalies: list[Anomaly] | None = None,
) -> None:
    """Display fleet production status as a Rich table."""
    # Build anomaly lookup by agent name
    agent_anomalies: dict[str, list[Anomaly]] = {}
    for a in anomalies or []:
        agent_anomalies.setdefault(a.agent_name, []).append(a)

    table = Table(title="Fleet Production Status")
    table.add_column("Agent", style="bold")
    table.add_column("Invocations", justify="right")
    table.add_column("Error Rate", justify="right")
    table.add_column("p50", justify="right")
    table.add_column("p95", justify="right")
    table.add_column("Avg Cost", justify="right")
    table.add_column("Models")
    table.add_column("Status")

    total_invocations = 0
    total_cost = 0.0

    for s in stats:
        error_style = "red" if s.error_rate > 0.05 else ""
        error_str = (
            f"[{error_style}]{s.error_rate:.1%}[/{error_style}]"
            if error_style
            else (f"{s.error_rate:.1%}")
        )

        # Status badge from anomalies
        aa = agent_anomalies.get(s.agent_name, [])
        if any(a.severity == "critical" for a in aa):
            status_str = "[red]!! CRITICAL[/red]"
        elif aa:
            status_str = "[yellow]! WARNING[/yellow]"
        else:
            status_str = "[green]OK[/green]"

        table.add_row(
            s.agent_name,
            f"{s.total_invocations:,}",
            error_str,
            f"{s.latency_p50:.2f}s",
            f"{s.latency_p95:.2f}s",
            f"${s.avg_cost_usd:.4f}",
            ", ".join(s.models_used[:2]),
            status_str,
        )
        total_invocations += s.total_invocations
        total_cost += s.total_cost_usd

    console.print(table)
    console.print(
        f"\n  {len(stats)} agents | {total_invocations:,} total calls "
        f"| ${total_cost:.2f} total cost"
    )


def display_agent_detail(
    agent_name: str,
    stats: AgentProductionStats,
    events: list[TrackingEvent],
) -> None:
    """Display per-agent production drill-down."""
    lines: list[str] = []
    lines.append(f"  [bold]{agent_name}[/bold]")
    lines.append("")
    lines.append(f"  Invocations:  {stats.total_invocations:,}")
    lines.append(f"  Error rate:   {stats.error_rate:.1%} ({stats.error_count} errors)")
    lines.append(f"  Period:       {stats.period_days:.1f} days")
    lines.append("")
    lines.append("  [bold]Latency[/bold]")
    lines.append(f"    p50:  {stats.latency_p50:.3f}s")
    lines.append(f"    p95:  {stats.latency_p95:.3f}s")
    lines.append(f"    p99:  {stats.latency_p99:.3f}s")
    lines.append("")
    lines.append("  [bold]Cost[/bold]")
    lines.append(f"    Total:   ${stats.total_cost_usd:.4f}")
    lines.append(f"    Average: ${stats.avg_cost_usd:.4f}/call")
    lines.append("")
    lines.append("  [bold]Tokens[/bold]")
    lines.append(f"    Avg input:  {stats.avg_input_tokens:.0f}")
    lines.append(f"    Avg output: {stats.avg_output_tokens:.0f}")
    lines.append("")
    lines.append(f"  [bold]Models used:[/bold] {', '.join(stats.models_used)}")

    panel = Panel(
        "\n".join(lines),
        title=f"Agent Detail: {agent_name}",
        border_style="bold",
    )
    console.print(panel)

    # Recent invocations table
    recent = sorted(events, key=lambda e: e.timestamp, reverse=True)[:10]
    if recent:
        table = Table(title="Recent Invocations")
        table.add_column("Timestamp")
        table.add_column("Model")
        table.add_column("Latency", justify="right")
        table.add_column("Cost", justify="right")
        table.add_column("Error")
        for e in recent:
            error_str = "[red]yes[/red]" if e.error else ""
            table.add_row(
                e.timestamp[:19],
                e.model,
                f"{e.latency_seconds:.3f}s",
                f"${e.cost_usd:.4f}",
                error_str,
            )
        console.print(table)


def display_anomalies(anomalies: list[Anomaly]) -> None:
    """Display detected anomalies as a Rich panel."""
    if not anomalies:
        return

    lines: list[str] = []
    for a in anomalies:
        if a.severity == "critical":
            lines.append(f"  [red]!! {a.message}[/red]")
        else:
            lines.append(f"  [yellow]! {a.message}[/yellow]")

    panel = Panel(
        "\n".join(lines),
        title="ANOMALIES DETECTED",
        border_style="yellow",
    )
    console.print(panel)
