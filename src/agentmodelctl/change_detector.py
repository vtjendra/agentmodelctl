"""Change detection — identify which agents are affected by config changes."""

from __future__ import annotations

import subprocess
from pathlib import Path, PurePosixPath

from agentmodelctl.models import ChangeSet, Project


def get_changed_files(ref: str = "HEAD", project_root: Path | None = None) -> list[str]:
    """Get list of changed files relative to a git ref.

    Args:
        ref: Git ref to diff against (e.g. "HEAD", "origin/main").
        project_root: Directory to run git from. Defaults to cwd.

    Returns:
        List of changed file paths (relative to repo root).

    Raises:
        RuntimeError: If git is not available or not a git repo.
    """
    cmd = ["git", "diff", "--name-only", ref]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=project_root,
            check=False,
        )
    except FileNotFoundError:
        raise RuntimeError("git is not installed or not in PATH")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(f"git diff failed: {stderr}")

    lines = result.stdout.strip().splitlines()
    return [line.strip() for line in lines if line.strip()]


def classify_changes(changed_files: list[str]) -> ChangeSet:
    """Classify changed files into categories relevant to agentmodelctl.

    Args:
        changed_files: List of changed file paths (relative to repo root).

    Returns:
        ChangeSet with categorized changes.
    """
    config_changed = False
    models_changed = False
    agents_changed: list[str] = []
    evals_changed: list[str] = []

    for filepath in changed_files:
        parts = PurePosixPath(filepath)
        name = parts.name

        if name == "agentmodelctl.yaml":
            config_changed = True
        elif name == "models.yaml" and str(parts.parent) in (".", ""):
            models_changed = True
        elif len(parts.parts) >= 2 and parts.parts[0] == "agents":
            # agents/foo.yaml → agent name "foo"
            agent_name = parts.stem
            if agent_name not in agents_changed:
                agents_changed.append(agent_name)
        elif len(parts.parts) >= 2 and parts.parts[0] == "evals":
            # evals/foo/basics.yaml → agent name "foo"
            agent_name = parts.parts[1]
            if agent_name not in evals_changed:
                evals_changed.append(agent_name)

    return ChangeSet(
        config_changed=config_changed,
        models_changed=models_changed,
        agents_changed=sorted(agents_changed),
        evals_changed=sorted(evals_changed),
    )


def detect_affected_agents(changed_files: list[str], project: Project) -> list[str]:
    """Determine which agents need re-evaluation based on file changes.

    Args:
        changed_files: List of changed file paths (relative to repo root).
        project: Loaded project with agent definitions.

    Returns:
        Sorted, deduplicated list of affected agent names.
    """
    changes = classify_changes(changed_files)

    # Global config or model changes affect all agents
    if changes.config_changed or changes.models_changed:
        affected = set(project.agents.keys())
    else:
        affected = set()

    # Add specifically changed agents
    for agent_name in changes.agents_changed:
        if agent_name in project.agents:
            affected.add(agent_name)

    # Add agents whose evals changed
    for agent_name in changes.evals_changed:
        if agent_name in project.agents:
            affected.add(agent_name)

    # Update the changeset with resolved affected agents
    all_affected = sorted(affected)
    changes.all_affected_agents = all_affected

    return all_affected
