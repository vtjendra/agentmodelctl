"""Model alias resolution and API key lookup."""

from __future__ import annotations

import os

from agentmodelctl.models import AgentConfig, ModelsConfig, ProjectConfig

# Standard env var names for each provider
DEFAULT_KEY_ENV_VARS: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
    "ollama": "OLLAMA_HOST",
    "bedrock": "AWS_ACCESS_KEY_ID",
    "azure": "AZURE_API_KEY",
}


def resolve_alias(alias: str, models: ModelsConfig) -> tuple[str, str]:
    """Resolve a model alias to (provider, model_string).

    Raises KeyError if alias is not defined.
    """
    if alias not in models.aliases:
        available = ", ".join(sorted(models.aliases.keys()))
        raise KeyError(
            f"Model alias '{alias}' is not defined in models.yaml. Available aliases: {available}"
        )
    entry = models.aliases[alias]
    return entry.provider, entry.model


def get_api_key(provider: str, config: ProjectConfig) -> str:
    """Get the API key for a provider from environment variables.

    Checks project config for custom env var names, falls back to defaults.
    Raises ValueError if key is not set.
    """
    # Check project config for custom env var name
    if provider in config.providers and config.providers[provider].api_key_env:
        env_var = config.providers[provider].api_key_env
    else:
        env_var = DEFAULT_KEY_ENV_VARS.get(provider)

    if not env_var:
        raise ValueError(
            f"No API key configuration for provider '{provider}'. "
            f"Set a key env var in agentmodelctl.yaml providers section."
        )

    key = os.environ.get(env_var, "")
    if not key:
        raise ValueError(
            f"{env_var} not set. Set it in your environment or in .env file. See: .env.example"
        )
    return key


def resolve_agent_model(
    agent: AgentConfig, models: ModelsConfig, config: ProjectConfig
) -> tuple[str, str]:
    """Resolve an agent's model alias to (model_string, api_key).

    Returns the full model string (e.g., 'anthropic/claude-sonnet-4-6') and API key.
    """
    provider, model_string = resolve_alias(agent.model, models)
    api_key = get_api_key(provider, config)
    return model_string, api_key


def get_litellm_model_string(provider: str, model: str) -> str:
    """Build the LiteLLM model string from provider and model name."""
    if provider == "ollama":
        return f"ollama/{model}"
    if provider == "anthropic":
        return model  # LiteLLM handles anthropic models directly
    if provider == "openai":
        return model  # LiteLLM handles openai models directly
    return f"{provider}/{model}"
