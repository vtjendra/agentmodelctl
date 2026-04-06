"""Tests for model switch logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from agentmodelctl.models import AgentConfig, ModelAlias, ModelsConfig
from agentmodelctl.switch import apply_switch, find_affected_agents, parse_model_string


class TestParseModelString:
    def test_with_provider_slash(self):
        assert parse_model_string("openai/gpt-4o") == ("openai", "gpt-4o")

    def test_claude_prefix(self):
        assert parse_model_string("claude-sonnet-4-6") == ("anthropic", "claude-sonnet-4-6")

    def test_gpt_prefix(self):
        assert parse_model_string("gpt-4o") == ("openai", "gpt-4o")

    def test_ollama_prefix(self):
        assert parse_model_string("llama3.1:8b") == ("ollama", "llama3.1:8b")

    def test_gemini_prefix(self):
        assert parse_model_string("gemini-pro") == ("google", "gemini-pro")

    def test_unknown_defaults_openai(self):
        assert parse_model_string("some-model") == ("openai", "some-model")


class TestFindAffectedAgents:
    @pytest.fixture
    def agents(self) -> dict[str, AgentConfig]:
        return {
            "agent-a": AgentConfig(name="agent-a", model="reasoning", system_prompt="A"),
            "agent-b": AgentConfig(name="agent-b", model="reasoning", system_prompt="B"),
            "agent-c": AgentConfig(name="agent-c", model="fast", system_prompt="C"),
        }

    def test_finds_matching(self, agents):
        affected = find_affected_agents("reasoning", agents)
        assert set(affected.keys()) == {"agent-a", "agent-b"}

    def test_no_match(self, agents):
        affected = find_affected_agents("cheap", agents)
        assert affected == {}

    def test_only_filter(self, agents):
        affected = find_affected_agents("reasoning", agents, only=["agent-a"])
        assert set(affected.keys()) == {"agent-a"}

    def test_only_filter_no_match(self, agents):
        affected = find_affected_agents("reasoning", agents, only=["agent-c"])
        assert affected == {}


class TestApplySwitch:
    def test_updates_models_yaml(self, tmp_path: Path):
        models_data = {
            "aliases": {
                "reasoning": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
                "fast": {"provider": "openai", "model": "gpt-4o-mini"},
            }
        }
        models_path = tmp_path / "models.yaml"
        with open(models_path, "w") as f:
            yaml.dump(models_data, f)

        apply_switch("reasoning", "openai/gpt-4o", tmp_path)

        with open(models_path) as f:
            updated = yaml.safe_load(f)

        assert updated["aliases"]["reasoning"]["model"] == "gpt-4o"
        assert updated["aliases"]["reasoning"]["provider"] == "openai"
        # Other aliases unchanged
        assert updated["aliases"]["fast"]["model"] == "gpt-4o-mini"

    def test_infers_provider(self, tmp_path: Path):
        models_data = {
            "aliases": {
                "reasoning": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
            }
        }
        models_path = tmp_path / "models.yaml"
        with open(models_path, "w") as f:
            yaml.dump(models_data, f)

        apply_switch("reasoning", "gpt-4o", tmp_path)

        with open(models_path) as f:
            updated = yaml.safe_load(f)

        assert updated["aliases"]["reasoning"]["model"] == "gpt-4o"
        assert updated["aliases"]["reasoning"]["provider"] == "openai"
