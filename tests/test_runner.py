"""Tests for eval execution engine."""

from __future__ import annotations

from unittest.mock import patch

import pytest

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
from agentmodelctl.runner import _infer_provider, run_agent_evals, run_single_eval


def _mock_llm_response(**kwargs) -> LLMResponse:
    """Create a mock LLMResponse with defaults."""
    defaults = {
        "content": "I can help you with that.",
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_usd": 0.003,
        "latency_seconds": 1.2,
        "tool_calls": [],
    }
    defaults.update(kwargs)
    return LLMResponse(**defaults)


@pytest.fixture
def agent() -> AgentConfig:
    return AgentConfig(
        name="test-agent",
        model="reasoning",
        system_prompt="You are a test agent.",
        temperature=0.3,
        max_tokens=512,
    )


@pytest.fixture
def models() -> ModelsConfig:
    return ModelsConfig(
        aliases={"reasoning": ModelAlias(provider="anthropic", model="claude-sonnet-4-6")}
    )


@pytest.fixture
def config() -> ProjectConfig:
    return ProjectConfig(providers={"anthropic": ProviderConfig(api_key_env="ANTHROPIC_API_KEY")})


class TestRunSingleEval:
    @patch("agentmodelctl.runner.call_model")
    def test_basic(self, mock_call, agent):
        mock_call.return_value = _mock_llm_response(content="Here is your refund info.")
        test = EvalTest(name="refund", input="I need a refund", expect_contains=["refund"])

        result = run_single_eval(test, agent, "claude-sonnet-4-6", "sk-key")

        assert result.test_name == "refund"
        assert result.passed is True
        assert result.quality_score == 1.0
        assert result.latency_seconds == 1.2
        assert result.cost_usd == 0.003
        mock_call.assert_called_once()

    @patch("agentmodelctl.runner.call_model")
    def test_failure(self, mock_call, agent):
        mock_call.return_value = _mock_llm_response(content="I don't know.")
        test = EvalTest(name="refund", input="I need a refund", expect_contains=["refund"])

        result = run_single_eval(test, agent, "claude-sonnet-4-6", "sk-key")

        assert result.passed is False
        assert len(result.failures) == 1

    @patch("agentmodelctl.runner.call_model")
    def test_uses_test_name(self, mock_call, agent):
        mock_call.return_value = _mock_llm_response()
        test = EvalTest(name="my_test", input="hello")

        result = run_single_eval(test, agent, "model", "key")
        assert result.test_name == "my_test"

    @patch("agentmodelctl.runner.call_model")
    def test_unnamed_test_uses_input(self, mock_call, agent):
        mock_call.return_value = _mock_llm_response()
        test = EvalTest(input="What is the meaning of life?")

        result = run_single_eval(test, agent, "model", "key")
        assert result.test_name == "What is the meaning of life?"


class TestRunAgentEvals:
    @patch("agentmodelctl.runner.call_model")
    def test_multiple_tests(self, mock_call, agent, models, config, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        mock_call.return_value = _mock_llm_response()

        eval_files = [
            EvalFile(
                tests=[
                    EvalTest(name="test1", input="Hello"),
                    EvalTest(name="test2", input="World"),
                ]
            )
        ]

        results = run_agent_evals(agent, eval_files, models, config)
        assert len(results) == 2
        assert results[0].test_name == "test1"
        assert results[1].test_name == "test2"
        assert mock_call.call_count == 2

    @patch("agentmodelctl.runner.call_model")
    def test_model_override(self, mock_call, agent, models, config, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        mock_call.return_value = _mock_llm_response()

        eval_files = [EvalFile(tests=[EvalTest(name="t", input="hi")])]
        results = run_agent_evals(agent, eval_files, models, config, model_override="gpt-4o")

        assert len(results) == 1
        call_kwargs = mock_call.call_args
        assert call_kwargs[1]["model"] == "gpt-4o" or call_kwargs[0][0] == "gpt-4o"

    @patch("agentmodelctl.runner.call_model")
    def test_empty_evals(self, mock_call, agent, models, config, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        results = run_agent_evals(agent, [], models, config)
        assert results == []
        mock_call.assert_not_called()


class TestInferProvider:
    def test_with_slash(self):
        assert _infer_provider("openai/gpt-4o") == ("openai", "gpt-4o")

    def test_claude(self):
        assert _infer_provider("claude-sonnet-4-6") == ("anthropic", "claude-sonnet-4-6")

    def test_gpt(self):
        assert _infer_provider("gpt-4o") == ("openai", "gpt-4o")

    def test_ollama(self):
        assert _infer_provider("llama3.1:8b") == ("ollama", "llama3.1:8b")

    def test_unknown_defaults_openai(self):
        assert _infer_provider("some-random-model") == ("openai", "some-random-model")
