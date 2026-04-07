"""Tests for the change detection module."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from agentmodelctl.change_detector import (
    classify_changes,
    detect_affected_agents,
    get_changed_files,
)
from agentmodelctl.models import (
    AgentConfig,
    ModelAlias,
    ModelsConfig,
    Project,
    ProjectConfig,
)


def _make_project(tmp_path: Path, agent_names: list[str] | None = None) -> Project:
    """Create a minimal Project for testing."""
    if agent_names is None:
        agent_names = ["customer-support", "email-drafter", "summarizer"]

    agents = {}
    for name in agent_names:
        agents[name] = AgentConfig(
            name=name,
            model="reasoning",
            system_prompt="You are a helpful agent.",
        )

    return Project(
        config=ProjectConfig(project="test"),
        models=ModelsConfig(
            aliases={"reasoning": ModelAlias(provider="anthropic", model="claude-sonnet-4-6")}
        ),
        agents=agents,
        evals={},
        project_root=tmp_path,
    )


class TestClassifyChanges:
    def test_empty_changes(self) -> None:
        changes = classify_changes([])
        assert not changes.config_changed
        assert not changes.models_changed
        assert changes.agents_changed == []
        assert changes.evals_changed == []

    def test_config_change(self) -> None:
        changes = classify_changes(["agentmodelctl.yaml"])
        assert changes.config_changed
        assert not changes.models_changed

    def test_models_change(self) -> None:
        changes = classify_changes(["models.yaml"])
        assert changes.models_changed
        assert not changes.config_changed

    def test_agent_change(self) -> None:
        changes = classify_changes(["agents/customer-support.yaml"])
        assert changes.agents_changed == ["customer-support"]

    def test_eval_change(self) -> None:
        changes = classify_changes(["evals/customer-support/basics.yaml"])
        assert changes.evals_changed == ["customer-support"]

    def test_multiple_changes(self) -> None:
        changes = classify_changes(
            [
                "models.yaml",
                "agents/email-drafter.yaml",
                "evals/summarizer/auto_generated.yaml",
            ]
        )
        assert changes.models_changed
        assert changes.agents_changed == ["email-drafter"]
        assert changes.evals_changed == ["summarizer"]

    def test_unrelated_files_ignored(self) -> None:
        changes = classify_changes(["README.md", "src/main.py", "docs/guide.md"])
        assert not changes.config_changed
        assert not changes.models_changed
        assert changes.agents_changed == []
        assert changes.evals_changed == []

    def test_deduplicates_agents(self) -> None:
        changes = classify_changes(
            [
                "agents/foo.yaml",
                "agents/foo.yaml",
            ]
        )
        assert changes.agents_changed == ["foo"]

    def test_deduplicates_evals(self) -> None:
        changes = classify_changes(
            [
                "evals/bar/test1.yaml",
                "evals/bar/test2.yaml",
            ]
        )
        assert changes.evals_changed == ["bar"]


class TestDetectAffectedAgents:
    def test_models_change_affects_all(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        affected = detect_affected_agents(["models.yaml"], project)
        assert affected == sorted(project.agents.keys())

    def test_config_change_affects_all(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        affected = detect_affected_agents(["agentmodelctl.yaml"], project)
        assert affected == sorted(project.agents.keys())

    def test_agent_change_affects_only_that_agent(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        affected = detect_affected_agents(["agents/email-drafter.yaml"], project)
        assert affected == ["email-drafter"]

    def test_eval_change_affects_only_that_agent(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        affected = detect_affected_agents(["evals/summarizer/auto_generated.yaml"], project)
        assert affected == ["summarizer"]

    def test_unknown_agent_ignored(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        affected = detect_affected_agents(["agents/nonexistent.yaml"], project)
        assert affected == []

    def test_no_changes_returns_empty(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        affected = detect_affected_agents([], project)
        assert affected == []

    def test_unrelated_files_return_empty(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        affected = detect_affected_agents(["README.md", "src/main.py"], project)
        assert affected == []

    def test_combined_agent_and_eval_changes(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        affected = detect_affected_agents(
            ["agents/email-drafter.yaml", "evals/summarizer/basics.yaml"],
            project,
        )
        assert affected == ["email-drafter", "summarizer"]


class TestGetChangedFiles:
    def test_returns_changed_files(self) -> None:
        with patch("agentmodelctl.change_detector.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="agents/foo.yaml\nmodels.yaml\n",
                stderr="",
            )
            files = get_changed_files("HEAD")
            assert files == ["agents/foo.yaml", "models.yaml"]

    def test_no_changes_returns_empty(self) -> None:
        with patch("agentmodelctl.change_detector.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="",
                stderr="",
            )
            files = get_changed_files("HEAD")
            assert files == []

    def test_passes_ref_to_git(self) -> None:
        with patch("agentmodelctl.change_detector.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="",
                stderr="",
            )
            get_changed_files("origin/main")
            args = mock_run.call_args[0][0]
            assert args == ["git", "diff", "--name-only", "origin/main"]

    def test_git_not_available_raises(self) -> None:
        with patch("agentmodelctl.change_detector.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            with pytest.raises(RuntimeError, match="git is not installed"):
                get_changed_files("HEAD")

    def test_git_error_raises(self) -> None:
        with patch("agentmodelctl.change_detector.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=128,
                stdout="",
                stderr="not a git repo",
            )
            with pytest.raises(RuntimeError, match="git diff failed"):
                get_changed_files("HEAD")
