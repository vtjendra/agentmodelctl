"""Model switch logic — impact analysis and application."""

from __future__ import annotations

from pathlib import Path

import yaml

from agentmodelctl.models import AgentConfig, Project
from agentmodelctl.router import get_api_key, get_litellm_model_string, resolve_alias
from agentmodelctl.runner import run_agent_evals


def parse_model_string(model_string: str) -> tuple[str, str]:
    """Parse a model string into (provider, model).

    Handles formats like "openai/gpt-4o", "gpt-4o", "claude-sonnet-4-6".
    Returns (provider, model).
    """
    if "/" in model_string:
        parts = model_string.split("/", 1)
        return parts[0], parts[1]

    lower = model_string.lower()
    if lower.startswith("claude") or lower.startswith("anthropic"):
        return "anthropic", model_string
    if lower.startswith("gpt") or lower.startswith("o1") or lower.startswith("o3"):
        return "openai", model_string
    if lower.startswith("gemini"):
        return "google", model_string
    if lower.startswith("llama") or lower.startswith("mistral"):
        return "ollama", model_string

    return "openai", model_string


def find_affected_agents(
    alias: str,
    agents: dict[str, AgentConfig],
    only: list[str] | None = None,
) -> dict[str, AgentConfig]:
    """Find all agents using a given model alias.

    Args:
        alias: The model alias to look for.
        agents: All agent configurations.
        only: If provided, filter to just these agent names.

    Returns:
        Dict of agent_name → AgentConfig for affected agents.
    """
    affected: dict[str, AgentConfig] = {}
    for name, agent in agents.items():
        if agent.model != alias:
            continue
        if only and name not in only:
            continue
        affected[name] = agent
    return affected


def run_dry_run(
    alias: str,
    new_model: str,
    project: Project,
    only: list[str] | None = None,
) -> tuple[str, dict[str, dict]]:
    """Run evals with old and new model for all affected agents.

    Args:
        alias: The model alias being switched.
        new_model: New model string (e.g., "gpt-4o" or "openai/gpt-4o").
        project: Fully loaded project.
        only: If provided, only include these agent names.

    Returns:
        Tuple of (old_model_string, agent_results) where agent_results is:
        {agent_name: {"old": list[EvalResult], "new": list[EvalResult]}}
    """
    # Resolve current model
    old_provider, old_model = resolve_alias(alias, project.models)
    old_model_string = get_litellm_model_string(old_provider, old_model)

    # Parse new model
    new_provider, new_model_name = parse_model_string(new_model)
    new_model_string = get_litellm_model_string(new_provider, new_model_name)

    # Get API keys
    old_api_key = get_api_key(old_provider, project.config)
    new_api_key = get_api_key(new_provider, project.config)

    # Find affected agents
    affected = find_affected_agents(alias, project.agents, only=only)

    agent_results: dict[str, dict] = {}

    for agent_name, agent in affected.items():
        eval_files = project.evals.get(agent_name, [])
        if not eval_files:
            continue

        # Run evals with old model
        old_results = run_agent_evals(
            agent=agent,
            eval_files=eval_files,
            models=project.models,
            config=project.config,
            model_override=old_model_string,
            api_key_override=old_api_key,
        )

        # Run evals with new model
        new_results = run_agent_evals(
            agent=agent,
            eval_files=eval_files,
            models=project.models,
            config=project.config,
            model_override=new_model_string,
            api_key_override=new_api_key,
        )

        agent_results[agent_name] = {
            "old": old_results,
            "new": new_results,
        }

    return old_model, agent_results


def apply_switch(
    alias: str,
    new_model: str,
    project_root: Path,
) -> None:
    """Update models.yaml on disk to change the alias's model string.

    Args:
        alias: The model alias to update.
        new_model: New model string (e.g., "gpt-4o" or "openai/gpt-4o").
        project_root: Path to the project root.
    """
    models_path = project_root / "models.yaml"
    with open(models_path) as f:
        data = yaml.safe_load(f)

    new_provider, new_model_name = parse_model_string(new_model)

    data["aliases"][alias]["model"] = new_model_name
    data["aliases"][alias]["provider"] = new_provider

    with open(models_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
