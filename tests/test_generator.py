"""Tests for eval auto-generation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agentmodelctl.generator import (
    _parse_tests_from_response,
    auto_generate_evals,
    capture_baselines,
    save_eval_file,
)
from agentmodelctl.models import (
    AgentConfig,
    EvalFile,
    EvalTest,
    ModelAlias,
    ModelsConfig,
    ProjectConfig,
    ProviderConfig,
)
from agentmodelctl.providers.adapter import LLMResponse

VALID_YAML_RESPONSE = """\
tests:
  - name: greeting
    input: "Hello, I need help"
    expect_contains: "help"
  - name: order_check
    input: "Check order #123"
    expect_tool: lookup_order
"""

FENCED_YAML_RESPONSE = """\
```yaml
tests:
  - name: greeting
    input: "Hello"
    expect_contains: "hello"
```
"""


@pytest.fixture
def agent() -> AgentConfig:
    return AgentConfig(
        name="test-agent",
        description="A test agent",
        model="reasoning",
        system_prompt="You are helpful.",
    )


@pytest.fixture
def models() -> ModelsConfig:
    return ModelsConfig(
        aliases={"reasoning": ModelAlias(provider="anthropic", model="claude-sonnet-4-6")}
    )


@pytest.fixture
def config() -> ProjectConfig:
    return ProjectConfig(providers={"anthropic": ProviderConfig(api_key_env="ANTHROPIC_API_KEY")})


class TestParseTestsFromResponse:
    def test_valid_yaml(self):
        tests = _parse_tests_from_response(VALID_YAML_RESPONSE)
        assert len(tests) == 2
        assert tests[0].name == "greeting"
        assert tests[1].expect_tool == "lookup_order"

    def test_fenced_yaml(self):
        tests = _parse_tests_from_response(FENCED_YAML_RESPONSE)
        assert len(tests) == 1
        assert tests[0].name == "greeting"

    def test_invalid_yaml(self):
        tests = _parse_tests_from_response("not yaml at all {{{")
        assert tests == []

    def test_missing_input_field(self):
        yaml_str = "tests:\n  - name: bad_test\n    expect_contains: hello\n"
        tests = _parse_tests_from_response(yaml_str)
        assert tests == []

    def test_empty_response(self):
        tests = _parse_tests_from_response("")
        assert tests == []


class TestCaptureBaselines:
    @patch("agentmodelctl.generator.call_model")
    def test_fills_baseline(self, mock_call, agent):
        mock_call.return_value = LLMResponse(
            content="Baseline response",
            input_tokens=10,
            output_tokens=20,
            cost_usd=0.001,
            latency_seconds=0.5,
            tool_calls=[],
        )

        tests = [EvalTest(name="t1", input="Hello")]
        updated = capture_baselines(agent, tests, "model", "key")

        assert len(updated) == 1
        assert updated[0].baseline_output == "Baseline response"
        mock_call.assert_called_once()


class TestAutoGenerateEvals:
    @patch("agentmodelctl.generator.call_model")
    def test_generates_evals(self, mock_call, agent, models, config, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        # First call: generate test YAML, subsequent calls: capture baselines
        mock_call.side_effect = [
            LLMResponse(
                content=VALID_YAML_RESPONSE,
                input_tokens=100,
                output_tokens=200,
                cost_usd=0.01,
                latency_seconds=2.0,
                tool_calls=[],
            ),
            LLMResponse(
                content="Baseline 1",
                input_tokens=10,
                output_tokens=20,
                cost_usd=0.001,
                latency_seconds=0.5,
                tool_calls=[],
            ),
            LLMResponse(
                content="Baseline 2",
                input_tokens=10,
                output_tokens=20,
                cost_usd=0.001,
                latency_seconds=0.5,
                tool_calls=[],
            ),
        ]

        eval_file = auto_generate_evals(agent, models, config, count=5)

        assert len(eval_file.tests) == 2
        assert eval_file.baseline_model == "claude-sonnet-4-6"
        assert eval_file.generated_at is not None
        assert eval_file.tests[0].baseline_output == "Baseline 1"
        assert eval_file.tests[1].baseline_output == "Baseline 2"


class TestSaveEvalFile:
    def test_saves_to_disk(self, tmp_path: Path):
        eval_file = EvalFile(
            generated_at="2026-04-06",
            baseline_model="claude-sonnet-4-6",
            tests=[EvalTest(name="t1", input="hello", expect_contains=["hi"])],
        )

        path = save_eval_file(eval_file, "my-agent", tmp_path)

        assert path.exists()
        assert path == tmp_path / "evals" / "my-agent" / "auto_generated.yaml"

        content = path.read_text()
        assert "AUTO-GENERATED" in content
        assert "hello" in content

    def test_creates_directories(self, tmp_path: Path):
        eval_file = EvalFile(tests=[EvalTest(input="test")])
        path = save_eval_file(eval_file, "new-agent", tmp_path)
        assert path.parent.exists()
