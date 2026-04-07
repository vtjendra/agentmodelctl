"""Tests for the output formatter module."""

from __future__ import annotations

import json

from agentmodelctl.formatter import (
    format_eval_results,
    format_eval_summary,
    summarize_agent_results,
)
from agentmodelctl.models import EvalResult, OutputFormat


def _make_results() -> list[EvalResult]:
    """Create sample eval results for testing."""
    return [
        EvalResult(
            test_name="refund_request",
            passed=True,
            quality_score=0.95,
            latency_seconds=1.2,
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.003,
            output="I can help with your refund.",
            failures=[],
        ),
        EvalResult(
            test_name="escalation_trigger",
            passed=False,
            quality_score=0.60,
            latency_seconds=0.9,
            input_tokens=80,
            output_tokens=40,
            cost_usd=0.002,
            output="Let me help you directly.",
            failures=["Expected output to contain 'escalate'"],
        ),
    ]


class TestSummarizeAgentResults:
    def test_computes_correct_counts(self) -> None:
        results = _make_results()
        summary = summarize_agent_results("test-agent", results)
        assert summary.agent_name == "test-agent"
        assert summary.passed == 1
        assert summary.failed == 1
        assert summary.total == 2

    def test_computes_correct_averages(self) -> None:
        results = _make_results()
        summary = summarize_agent_results("test-agent", results)
        assert summary.avg_quality == (0.95 + 0.60) / 2
        assert summary.avg_latency_seconds == (1.2 + 0.9) / 2
        assert summary.total_cost_usd == 0.003 + 0.002

    def test_empty_results(self) -> None:
        summary = summarize_agent_results("empty", [])
        assert summary.passed == 0
        assert summary.failed == 0
        assert summary.total == 0
        assert summary.avg_quality == 0.0


class TestFormatEvalResults:
    def test_rich_returns_none(self) -> None:
        results = _make_results()
        assert format_eval_results("agent", results, OutputFormat.rich) is None

    def test_json_returns_valid_json(self) -> None:
        results = _make_results()
        output = format_eval_results("agent", results, OutputFormat.json)
        assert output is not None
        data = json.loads(output)
        assert data["agent_name"] == "agent"
        assert data["passed"] == 1
        assert data["failed"] == 1
        assert data["total"] == 2
        assert len(data["results"]) == 2

    def test_json_contains_result_fields(self) -> None:
        results = _make_results()
        output = format_eval_results("agent", results, OutputFormat.json)
        data = json.loads(output)
        first = data["results"][0]
        assert "test_name" in first
        assert "quality_score" in first
        assert "latency_seconds" in first
        assert "cost_usd" in first
        assert "passed" in first

    def test_markdown_returns_string(self) -> None:
        results = _make_results()
        output = format_eval_results("agent", results, OutputFormat.markdown)
        assert output is not None
        assert isinstance(output, str)

    def test_markdown_contains_table_headers(self) -> None:
        results = _make_results()
        output = format_eval_results("agent", results, OutputFormat.markdown)
        assert "| Test |" in output
        assert "| Quality |" in output
        assert "| Status |" in output

    def test_markdown_contains_test_names(self) -> None:
        results = _make_results()
        output = format_eval_results("agent", results, OutputFormat.markdown)
        assert "refund_request" in output
        assert "escalation_trigger" in output

    def test_markdown_contains_pass_fail(self) -> None:
        results = _make_results()
        output = format_eval_results("agent", results, OutputFormat.markdown)
        assert "PASS" in output
        assert "FAIL" in output

    def test_markdown_contains_failures_section(self) -> None:
        results = _make_results()
        output = format_eval_results("agent", results, OutputFormat.markdown)
        assert "### Failures" in output
        assert "escalation_trigger: Expected output to contain 'escalate'" in output

    def test_markdown_contains_summary(self) -> None:
        results = _make_results()
        output = format_eval_results("agent", results, OutputFormat.markdown)
        assert "**Summary:** 1/2 passed" in output


class TestFormatEvalSummary:
    def test_rich_returns_none(self) -> None:
        summaries = [summarize_agent_results("a", _make_results())]
        assert format_eval_summary(summaries, OutputFormat.rich) is None

    def test_json_returns_valid_json(self) -> None:
        summaries = [summarize_agent_results("a", _make_results())]
        output = format_eval_summary(summaries, OutputFormat.json)
        assert output is not None
        data = json.loads(output)
        assert isinstance(data, list)
        assert data[0]["agent_name"] == "a"
        # Summary JSON excludes individual results
        assert "results" not in data[0]

    def test_markdown_contains_ci_report_header(self) -> None:
        summaries = [summarize_agent_results("agent-a", _make_results())]
        output = format_eval_summary(summaries, OutputFormat.markdown)
        assert output is not None
        assert "## agentmodelctl CI Report" in output
        assert "agent-a" in output

    def test_markdown_multi_agent(self) -> None:
        all_pass = [
            EvalResult(
                test_name="t1",
                passed=True,
                quality_score=1.0,
                latency_seconds=0.5,
                input_tokens=50,
                output_tokens=30,
                cost_usd=0.001,
                output="ok",
            )
        ]
        summaries = [
            summarize_agent_results("agent-a", _make_results()),
            summarize_agent_results("agent-b", all_pass),
        ]
        output = format_eval_summary(summaries, OutputFormat.markdown)
        assert "agent-a" in output
        assert "agent-b" in output
        assert "WARN" in output  # agent-a has failures
        assert "PASS" in output  # agent-b all pass
