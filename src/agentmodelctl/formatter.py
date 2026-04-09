"""Output formatting dispatch — JSON, markdown, or Rich passthrough."""

from __future__ import annotations

import json

from agentmodelctl.models import (
    AgentEvalSummary,
    AgentProductionStats,
    Anomaly,
    EvalResult,
    OutputFormat,
)


def summarize_agent_results(agent_name: str, results: list[EvalResult]) -> AgentEvalSummary:
    """Compute aggregated summary for one agent's eval results."""
    n = len(results)
    passed = sum(1 for r in results if r.passed)
    return AgentEvalSummary(
        agent_name=agent_name,
        passed=passed,
        failed=n - passed,
        total=n,
        avg_quality=sum(r.quality_score for r in results) / max(n, 1),
        avg_latency_seconds=sum(r.latency_seconds for r in results) / max(n, 1),
        total_cost_usd=sum(r.cost_usd for r in results),
        results=results,
    )


def format_eval_results(
    agent_name: str, results: list[EvalResult], fmt: OutputFormat
) -> str | None:
    """Format eval results for a single agent.

    Returns a string for json/markdown formats, or None for rich
    (indicating the caller should use reporter.display_eval_results).
    """
    if fmt == OutputFormat.rich:
        return None
    if fmt == OutputFormat.json:
        return _eval_results_to_json(agent_name, results)
    if fmt == OutputFormat.markdown:
        return _eval_results_to_markdown(agent_name, results)
    return None


def format_eval_summary(summaries: list[AgentEvalSummary], fmt: OutputFormat) -> str | None:
    """Format multi-agent eval summary.

    Returns a string for json/markdown formats, or None for rich.
    """
    if fmt == OutputFormat.rich:
        return None
    if fmt == OutputFormat.json:
        return json.dumps(
            [s.model_dump(exclude={"results"}) for s in summaries],
            indent=2,
        )
    if fmt == OutputFormat.markdown:
        return _eval_summary_to_markdown(summaries)
    return None


def _eval_results_to_json(agent_name: str, results: list[EvalResult]) -> str:
    """Serialize eval results to JSON."""
    summary = summarize_agent_results(agent_name, results)
    return json.dumps(summary.model_dump(), indent=2, default=str)


def _eval_results_to_markdown(agent_name: str, results: list[EvalResult]) -> str:
    """Render eval results as a markdown table."""
    summary = summarize_agent_results(agent_name, results)
    lines: list[str] = []

    lines.append(f"## Eval Results: {agent_name}")
    lines.append("")
    lines.append("| Test | Quality | Latency | Tokens | Cost | Status |")
    lines.append("|------|---------|---------|--------|------|--------|")

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        tokens = r.input_tokens + r.output_tokens
        lines.append(
            f"| {r.test_name} | {r.quality_score:.2f} "
            f"| {r.latency_seconds:.1f}s | {tokens} "
            f"| ${r.cost_usd:.4f} | {status} |"
        )

    lines.append("")
    lines.append(
        f"**Summary:** {summary.passed}/{summary.total} passed "
        f"| avg quality {summary.avg_quality:.2f} "
        f"| avg latency {summary.avg_latency_seconds:.1f}s "
        f"| total cost ${summary.total_cost_usd:.4f}"
    )

    # Show failures
    failures = [(r.test_name, r.failures) for r in results if not r.passed]
    if failures:
        lines.append("")
        lines.append("### Failures")
        for test_name, fails in failures:
            for f in fails:
                lines.append(f"- {test_name}: {f}")

    return "\n".join(lines)


def _eval_summary_to_markdown(summaries: list[AgentEvalSummary]) -> str:
    """Render multi-agent summary as markdown."""
    lines: list[str] = []

    lines.append("## agentmodelctl CI Report")
    lines.append("")
    lines.append("| Agent | Result | Pass Rate | Avg Quality | Total Cost | Details |")
    lines.append("|-------|--------|-----------|-------------|------------|---------|")

    for s in summaries:
        if s.failed == 0:
            result = "PASS"
        else:
            result = "WARN"
        details = "—" if s.failed == 0 else f"{s.failed} test(s) failed"
        lines.append(
            f"| {s.agent_name} | {result} "
            f"| {s.passed}/{s.total} | {s.avg_quality:.2f} "
            f"| ${s.total_cost_usd:.4f} | {details} |"
        )

    lines.append("")

    # Per-agent failure details
    for s in summaries:
        failures = [(r.test_name, r.failures) for r in s.results if not r.passed]
        if failures:
            lines.append(f"### {s.agent_name} failures")
            for test_name, fails in failures:
                for f in fails:
                    lines.append(f"- {test_name}: {f}")
            lines.append("")

    return "\n".join(lines)


def format_fleet_status(
    stats: list[AgentProductionStats],
    fmt: OutputFormat,
    anomalies: list[Anomaly] | None = None,
) -> str | None:
    """Format fleet status. Returns None for rich, str for json/markdown."""
    if fmt == OutputFormat.rich:
        return None
    if fmt == OutputFormat.json:
        data = {
            "agents": [s.model_dump() for s in stats],
            "anomalies": [a.model_dump() for a in (anomalies or [])],
        }
        return json.dumps(data, indent=2)
    if fmt == OutputFormat.markdown:
        return _fleet_status_to_markdown(stats, anomalies=anomalies)
    return None


def format_agent_detail(
    agent_name: str,
    stats: AgentProductionStats,
    fmt: OutputFormat,
) -> str | None:
    """Format agent detail. Returns None for rich, str for json/markdown."""
    if fmt == OutputFormat.rich:
        return None
    if fmt == OutputFormat.json:
        return json.dumps(stats.model_dump(), indent=2)
    if fmt == OutputFormat.markdown:
        return _agent_detail_to_markdown(agent_name, stats)
    return None


def _fleet_status_to_markdown(
    stats: list[AgentProductionStats],
    anomalies: list[Anomaly] | None = None,
) -> str:
    """Render fleet status as a markdown table."""
    lines: list[str] = []
    lines.append("## Fleet Production Status")
    lines.append("")
    lines.append("| Agent | Invocations | Error Rate | p50 | p95 | Avg Cost | Models |")
    lines.append("|-------|-------------|------------|-----|-----|----------|--------|")

    total_invocations = 0
    total_cost = 0.0

    for s in stats:
        models = ", ".join(s.models_used[:2])
        lines.append(
            f"| {s.agent_name} | {s.total_invocations:,} "
            f"| {s.error_rate:.1%} | {s.latency_p50:.2f}s "
            f"| {s.latency_p95:.2f}s | ${s.avg_cost_usd:.4f} "
            f"| {models} |"
        )
        total_invocations += s.total_invocations
        total_cost += s.total_cost_usd

    lines.append("")
    lines.append(
        f"**{len(stats)} agents** | {total_invocations:,} total calls "
        f"| ${total_cost:.2f} total cost"
    )

    if anomalies:
        lines.append("")
        lines.append("### Anomalies")
        for a in anomalies:
            prefix = "!!" if a.severity == "critical" else "!"
            lines.append(f"- {prefix} {a.message}")

    return "\n".join(lines)


def _agent_detail_to_markdown(agent_name: str, stats: AgentProductionStats) -> str:
    """Render agent detail as markdown."""
    lines: list[str] = []
    lines.append(f"## Agent Detail: {agent_name}")
    lines.append("")
    lines.append(f"- **Invocations:** {stats.total_invocations:,}")
    lines.append(f"- **Error rate:** {stats.error_rate:.1%} ({stats.error_count} errors)")
    lines.append(f"- **Period:** {stats.period_days:.1f} days")
    lines.append("")
    lines.append("### Latency")
    lines.append(f"- p50: {stats.latency_p50:.3f}s")
    lines.append(f"- p95: {stats.latency_p95:.3f}s")
    lines.append(f"- p99: {stats.latency_p99:.3f}s")
    lines.append("")
    lines.append("### Cost")
    lines.append(f"- Total: ${stats.total_cost_usd:.4f}")
    lines.append(f"- Average: ${stats.avg_cost_usd:.4f}/call")
    lines.append("")
    lines.append(f"### Models used: {', '.join(stats.models_used)}")
    return "\n".join(lines)
