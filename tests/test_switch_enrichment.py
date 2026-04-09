"""Tests for switch enrichment with production data."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from agentmodelctl.models import AgentProductionStats, EvalResult
from agentmodelctl.reporter import display_switch_verdict


def _make_eval_result(passed: bool = True, cost: float = 0.01, latency: float = 1.0) -> EvalResult:
    return EvalResult(
        test_name="test_greeting",
        passed=passed,
        quality_score=1.0 if passed else 0.5,
        latency_seconds=latency,
        input_tokens=100,
        output_tokens=50,
        cost_usd=cost,
        output="Hello!",
        failures=[] if passed else ["did not match"],
    )


def _make_prod_stats(
    agent_name: str = "support",
    invocations: int = 1000,
    period_days: float = 7.0,
) -> AgentProductionStats:
    return AgentProductionStats(
        agent_name=agent_name,
        total_invocations=invocations,
        error_count=10,
        error_rate=0.01,
        latency_p50=0.5,
        latency_p95=1.2,
        latency_p99=2.0,
        avg_cost_usd=0.01,
        total_cost_usd=10.0,
        avg_input_tokens=100.0,
        avg_output_tokens=50.0,
        models_used=["claude-sonnet-4-6"],
        first_seen="2026-04-01T00:00:00+00:00",
        last_seen="2026-04-08T00:00:00+00:00",
        period_days=period_days,
    )


def _capture_verdict(agent_results, production_stats=None) -> str:
    """Capture Rich output from display_switch_verdict."""
    buf = StringIO()
    test_console = Console(file=buf, width=120, force_terminal=True)

    # Monkey-patch the console used by reporter
    import agentmodelctl.reporter as reporter_mod

    original_console = reporter_mod.console
    reporter_mod.console = test_console
    try:
        display_switch_verdict(
            alias="reasoning",
            old_model="claude-sonnet-4-6",
            new_model="gpt-4o",
            agent_results=agent_results,
            production_stats=production_stats,
        )
    finally:
        reporter_mod.console = original_console

    return buf.getvalue()


class TestSwitchWithProductionData:
    def test_verdict_without_production_stats(self) -> None:
        """Existing behavior — no production data, no crash."""
        agent_results = {
            "support": {
                "old": [_make_eval_result()],
                "new": [_make_eval_result()],
            },
        }
        output = _capture_verdict(agent_results)
        assert "support" in output
        assert "production" not in output.lower()

    def test_verdict_with_production_stats(self) -> None:
        """When production data exists, show volume."""
        agent_results = {
            "support": {
                "old": [_make_eval_result()],
                "new": [_make_eval_result()],
            },
        }
        production_stats = {"support": _make_prod_stats()}
        output = _capture_verdict(agent_results, production_stats)
        assert "1,000 calls" in output
        assert "production" in output.lower()

    def test_verdict_partial_stats(self) -> None:
        """Some agents have stats, some don't."""
        agent_results = {
            "support": {
                "old": [_make_eval_result()],
                "new": [_make_eval_result()],
            },
            "sales": {
                "old": [_make_eval_result()],
                "new": [_make_eval_result()],
            },
        }
        production_stats = {
            "support": _make_prod_stats(),
            "sales": None,
        }
        output = _capture_verdict(agent_results, production_stats)
        # support should show production data, sales should not
        assert "1,000 calls" in output

    def test_estimated_savings(self) -> None:
        """Show estimated monthly savings when cost differs."""
        agent_results = {
            "support": {
                "old": [_make_eval_result(cost=0.05)],
                "new": [_make_eval_result(cost=0.01)],
            },
        }
        # 1000 calls over 7 days = ~143/day
        production_stats = {"support": _make_prod_stats(invocations=1000, period_days=7.0)}
        output = _capture_verdict(agent_results, production_stats)
        assert "estimated savings" in output.lower()
        assert "/month" in output

    def test_no_savings_shown_when_costs_equal(self) -> None:
        """When costs are the same, no estimated savings line."""
        agent_results = {
            "support": {
                "old": [_make_eval_result(cost=0.01)],
                "new": [_make_eval_result(cost=0.01)],
            },
        }
        production_stats = {"support": _make_prod_stats()}
        output = _capture_verdict(agent_results, production_stats)
        assert "estimated savings" not in output.lower()
        assert "estimated extra cost" not in output.lower()
