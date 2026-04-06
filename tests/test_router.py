"""Tests for model alias resolution and API key lookup."""

from __future__ import annotations

import os

import pytest

from agentmodelctl.models import AgentConfig, ModelAlias, ModelsConfig, ProjectConfig, ProviderConfig
from agentmodelctl.router import get_api_key, get_litellm_model_string, resolve_alias, resolve_agent_model


@pytest.fixture
def models() -> ModelsConfig:
    return ModelsConfig(
        aliases={
            "reasoning": ModelAlias(provider="anthropic", model="claude-sonnet-4-6"),
            "fast": ModelAlias(provider="openai", model="gpt-4o-mini"),
            "local": ModelAlias(provider="ollama", model="llama3.1:8b"),
        }
    )


@pytest.fixture
def config() -> ProjectConfig:
    return ProjectConfig(
        providers={
            "anthropic": ProviderConfig(api_key_env="ANTHROPIC_API_KEY"),
            "openai": ProviderConfig(api_key_env="OPENAI_API_KEY"),
        }
    )


class TestResolveAlias:
    def test_valid_alias(self, models: ModelsConfig):
        provider, model = resolve_alias("reasoning", models)
        assert provider == "anthropic"
        assert model == "claude-sonnet-4-6"

    def test_another_alias(self, models: ModelsConfig):
        provider, model = resolve_alias("fast", models)
        assert provider == "openai"
        assert model == "gpt-4o-mini"

    def test_unknown_alias_raises(self, models: ModelsConfig):
        with pytest.raises(KeyError, match="not defined in models.yaml"):
            resolve_alias("nonexistent", models)

    def test_error_lists_available(self, models: ModelsConfig):
        with pytest.raises(KeyError, match="fast"):
            resolve_alias("nonexistent", models)


class TestGetApiKey:
    def test_key_from_env(self, config: ProjectConfig, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
        key = get_api_key("anthropic", config)
        assert key == "sk-test-123"

    def test_missing_key_raises(self, config: ProjectConfig, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY not set"):
            get_api_key("anthropic", config)

    def test_custom_env_var(self, monkeypatch):
        custom_config = ProjectConfig(
            providers={"mycloud": ProviderConfig(api_key_env="MY_CUSTOM_KEY")}
        )
        monkeypatch.setenv("MY_CUSTOM_KEY", "custom-key-val")
        key = get_api_key("mycloud", custom_config)
        assert key == "custom-key-val"

    def test_default_env_var_fallback(self, monkeypatch):
        empty_config = ProjectConfig()
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-123")
        key = get_api_key("openai", empty_config)
        assert key == "sk-openai-123"

    def test_unknown_provider_no_config(self):
        empty_config = ProjectConfig()
        with pytest.raises(ValueError, match="No API key configuration"):
            get_api_key("unknowncloud", empty_config)


class TestGetLitellmModelString:
    def test_anthropic(self):
        assert get_litellm_model_string("anthropic", "claude-sonnet-4-6") == "claude-sonnet-4-6"

    def test_openai(self):
        assert get_litellm_model_string("openai", "gpt-4o") == "gpt-4o"

    def test_ollama(self):
        assert get_litellm_model_string("ollama", "llama3.1:8b") == "ollama/llama3.1:8b"

    def test_other_provider(self):
        assert get_litellm_model_string("bedrock", "some-model") == "bedrock/some-model"


class TestResolveAgentModel:
    def test_resolves_full(self, models: ModelsConfig, config: ProjectConfig, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        agent = AgentConfig(name="test", model="reasoning", system_prompt="test")
        model_string, api_key = resolve_agent_model(agent, models, config)
        assert model_string == "claude-sonnet-4-6"
        assert api_key == "sk-test-key"
