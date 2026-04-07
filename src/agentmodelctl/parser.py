"""YAML loading, validation, and project discovery."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from agentmodelctl.models import (
    AgentConfig,
    EvalFile,
    ModelsConfig,
    Project,
    ProjectConfig,
)

CONFIG_FILENAME = "agentmodelctl.yaml"


def find_project_root(start: Path | None = None) -> Path:
    """Walk up directories to find the project root containing agentmodelctl.yaml."""
    current = (start or Path.cwd()).resolve()
    while True:
        if (current / CONFIG_FILENAME).exists():
            return current
        parent = current.parent
        if parent == current:
            raise FileNotFoundError(
                f"Could not find {CONFIG_FILENAME} in current directory or any parent. "
                "Run 'agentmodelctl init' to create a project."
            )
        current = parent


def load_project_config(root: Path) -> ProjectConfig:
    """Load and validate agentmodelctl.yaml."""
    config_path = root / CONFIG_FILENAME
    if not config_path.exists():
        raise FileNotFoundError(f"{CONFIG_FILENAME} not found at {root}")
    with open(config_path) as f:
        data = yaml.safe_load(f) or {}
    try:
        return ProjectConfig(**data)
    except ValidationError as e:
        raise ValueError(f"Invalid {CONFIG_FILENAME}: {e}") from e


def load_models(root: Path) -> ModelsConfig:
    """Load and validate models.yaml."""
    models_path = root / "models.yaml"
    if not models_path.exists():
        raise FileNotFoundError("models.yaml not found. Create it or run 'agentmodelctl init'.")
    with open(models_path) as f:
        data = yaml.safe_load(f) or {}
    try:
        return ModelsConfig(**data)
    except ValidationError as e:
        raise ValueError(f"Invalid models.yaml: {e}") from e


def load_agents(root: Path) -> dict[str, AgentConfig]:
    """Load all agent definitions from agents/*.yaml."""
    agents_dir = root / "agents"
    agents: dict[str, AgentConfig] = {}
    if not agents_dir.exists():
        return agents
    for path in sorted(agents_dir.glob("*.yaml")):
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        try:
            agent = AgentConfig(**data)
            agents[agent.name] = agent
        except ValidationError as e:
            raise ValueError(f"Invalid agent config {path.name}: {e}") from e
    return agents


def load_evals(root: Path) -> dict[str, list[EvalFile]]:
    """Load all eval definitions from evals/**/*.yaml."""
    evals_dir = root / "evals"
    evals: dict[str, list[EvalFile]] = {}
    if not evals_dir.exists():
        return evals
    for agent_dir in sorted(evals_dir.iterdir()):
        if not agent_dir.is_dir():
            continue
        agent_name = agent_dir.name
        agent_evals: list[EvalFile] = []
        for path in sorted(agent_dir.glob("*.yaml")):
            with open(path) as f:
                data = yaml.safe_load(f) or {}
            try:
                eval_file = EvalFile(**data)
                agent_evals.append(eval_file)
            except ValidationError as e:
                raise ValueError(f"Invalid eval file {path}: {e}") from e
        if agent_evals:
            evals[agent_name] = agent_evals
    return evals


def load_project(start: Path | None = None) -> Project:
    """Load the entire project from the nearest agentmodelctl.yaml."""
    root = find_project_root(start)
    config = load_project_config(root)
    models = load_models(root)
    agents = load_agents(root)
    evals = load_evals(root)
    return Project(
        config=config,
        models=models,
        agents=agents,
        evals=evals,
        project_root=root,
    )
