"""Validate command implementation."""

from __future__ import annotations

import typer

from agentmodelctl.parser import find_project_root, load_agents, load_evals, load_models, load_project_config
from agentmodelctl.reporter import console, display_validation_results
from agentmodelctl.security import scan_project_for_keys


def run_validate() -> None:
    """Validate all project configuration files."""
    errors: list[str] = []
    warnings: list[str] = []
    successes: list[str] = []

    console.print("Validating project...\n")

    # Find project root
    try:
        root = find_project_root()
    except FileNotFoundError as e:
        console.print(f"  [red]✗[/red] {e}")
        raise typer.Exit(code=1)

    # Load project config
    try:
        config = load_project_config(root)
        successes.append(f"agentmodelctl.yaml — valid")
    except (FileNotFoundError, ValueError) as e:
        errors.append(f"agentmodelctl.yaml — {e}")
        display_validation_results(errors, warnings, successes)
        raise typer.Exit(code=1)

    # Load models
    models = None
    try:
        models = load_models(root)
        alias_count = len(models.aliases)
        successes.append(f"models.yaml — valid, {alias_count} aliases defined")
    except (FileNotFoundError, ValueError) as e:
        errors.append(f"models.yaml — {e}")

    # Load agents
    agents = {}
    try:
        agents = load_agents(root)
        for name in sorted(agents):
            successes.append(f"agents/{name}.yaml — valid")
    except ValueError as e:
        errors.append(str(e))

    # Load evals
    try:
        evals = load_evals(root)
        for agent_name, eval_files in sorted(evals.items()):
            total = sum(len(ef.tests) for ef in eval_files)
            successes.append(f"evals/{agent_name}/ — {total} tests")
    except ValueError as e:
        errors.append(str(e))

    # Cross-reference: each agent's model alias must exist in models.yaml
    if models and agents:
        for name, agent in sorted(agents.items()):
            if agent.model not in models.aliases:
                available = ", ".join(sorted(models.aliases.keys()))
                errors.append(
                    f"agents/{name}.yaml — references model alias '{agent.model}' "
                    f"but it's not defined in models.yaml. "
                    f"Available: {available}"
                )

        # Check for unused aliases
        used_aliases = {a.model for a in agents.values()}
        for alias in models.aliases:
            if alias not in used_aliases:
                warnings.append(f"Model alias '{alias}' is defined but not used by any agent")

    # Check eval coverage
    if agents:
        evals_loaded = evals if "evals" in dir() else {}
        for name in sorted(agents):
            if name not in evals_loaded:
                warnings.append(f"{name} has no evals defined")

    # Security scan
    key_findings = scan_project_for_keys(root)
    for filepath, findings in key_findings.items():
        for line_num, _, desc in findings:
            warnings.append(
                f"Possible {desc} detected in {filepath} (line {line_num}). "
                f"Never commit API keys to version control."
            )

    # Check for .env with API keys
    env_file = root / ".env"
    if env_file.exists():
        import os
        from dotenv import load_dotenv
        load_dotenv(env_file)
        for provider_name, provider_config in config.providers.items():
            if provider_config.api_key_env:
                if os.environ.get(provider_config.api_key_env):
                    successes.append(f".env — {provider_config.api_key_env} set")
                else:
                    warnings.append(f"{provider_config.api_key_env} not set in .env")

    display_validation_results(errors, warnings, successes)

    if errors:
        raise typer.Exit(code=1)
