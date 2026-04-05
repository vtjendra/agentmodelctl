"""Tests for Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentmodelctl.models import (
    AgentConfig,
    EvalFile,
    EvalTest,
    ModelAlias,
    ModelsConfig,
    ProjectConfig,
)


class TestModelAlias:
    def test_valid(self):
        alias = ModelAlias(provider="anthropic", model="claude-sonnet-4-6")
        assert alias.provider == "anthropic"
        assert alias.model == "claude-sonnet-4-6"
        assert alias.fallback is None

    def test_with_fallback(self):
        alias = ModelAlias(provider="anthropic", model="claude-sonnet-4-6", fallback="gpt-4o")
        assert alias.fallback == "gpt-4o"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            ModelAlias(provider="anthropic")  # type: ignore[call-arg]


class TestModelsConfig:
    def test_valid(self):
        config = ModelsConfig(
            aliases={
                "reasoning": ModelAlias(provider="anthropic", model="claude-sonnet-4-6"),
                "fast": ModelAlias(provider="openai", model="gpt-4o-mini"),
            }
        )
        assert len(config.aliases) == 2
        assert config.aliases["reasoning"].provider == "anthropic"


class TestAgentConfig:
    def test_valid(self):
        agent = AgentConfig(
            name="test-agent",
            model="reasoning",
            system_prompt="You are a test agent.",
        )
        assert agent.name == "test-agent"
        assert agent.temperature == 0.7
        assert agent.max_tokens == 1024
        assert agent.metadata.env == "development"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            AgentConfig(name="test")  # type: ignore[call-arg]

    def test_with_tools(self):
        agent = AgentConfig(
            name="test",
            model="fast",
            system_prompt="Test",
            tools=[{"name": "lookup", "description": "Look up something"}],
        )
        assert len(agent.tools) == 1
        assert agent.tools[0].name == "lookup"


class TestEvalTest:
    def test_minimal(self):
        test = EvalTest(input="Hello")
        assert test.input == "Hello"
        assert test.name == ""

    def test_string_normalized_to_list(self):
        test = EvalTest(input="Hello", expect_contains="greeting")
        assert test.expect_contains == ["greeting"]

    def test_list_stays_list(self):
        test = EvalTest(input="Hello", expect_contains=["a", "b"])
        assert test.expect_contains == ["a", "b"]

    def test_not_contains_normalized(self):
        test = EvalTest(input="Hello", expect_not_contains="bad")
        assert test.expect_not_contains == ["bad"]


class TestEvalFile:
    def test_valid(self):
        ef = EvalFile(
            generated_at="2026-04-05",
            baseline_model="claude-sonnet-4-6",
            tests=[EvalTest(input="Hello")],
        )
        assert len(ef.tests) == 1

    def test_empty_tests(self):
        ef = EvalFile(tests=[])
        assert len(ef.tests) == 0


class TestProjectConfig:
    def test_defaults(self):
        config = ProjectConfig()
        assert config.version == 1
        assert config.defaults.eval_runs == 3
        assert config.defaults.similarity_threshold == 0.80

    def test_with_providers(self):
        config = ProjectConfig(
            project="test",
            providers={"anthropic": {"api_key_env": "ANTHROPIC_API_KEY"}},
        )
        assert config.providers["anthropic"].api_key_env == "ANTHROPIC_API_KEY"
