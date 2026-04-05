"""Tests for YAML parsing and project loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentmodelctl.parser import (
    find_project_root,
    load_agents,
    load_evals,
    load_models,
    load_project,
    load_project_config,
)


class TestFindProjectRoot:
    def test_finds_root(self, sample_project: Path):
        root = find_project_root(sample_project)
        assert root == sample_project

    def test_finds_root_from_subdirectory(self, sample_project: Path):
        subdir = sample_project / "agents"
        root = find_project_root(subdir)
        assert root == sample_project

    def test_raises_when_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="Could not find agentmodelctl.yaml"):
            find_project_root(tmp_path)


class TestLoadProjectConfig:
    def test_loads_valid(self, sample_project: Path):
        config = load_project_config(sample_project)
        assert config.project == "test-project"
        assert config.defaults.eval_runs == 3

    def test_raises_on_missing(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_project_config(tmp_path)


class TestLoadModels:
    def test_loads_valid(self, sample_project: Path):
        models = load_models(sample_project)
        assert "reasoning" in models.aliases
        assert models.aliases["reasoning"].provider == "anthropic"
        assert models.aliases["reasoning"].model == "claude-sonnet-4-6"

    def test_raises_on_missing(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_models(tmp_path)


class TestLoadAgents:
    def test_loads_valid(self, sample_project: Path):
        agents = load_agents(sample_project)
        assert "customer-support" in agents
        agent = agents["customer-support"]
        assert agent.model == "reasoning"
        assert len(agent.tools) == 3

    def test_empty_when_no_dir(self, tmp_path: Path):
        agents = load_agents(tmp_path)
        assert agents == {}

    def test_raises_on_invalid(self, tmp_path: Path, fixtures_dir: Path):
        import shutil

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        shutil.copy(fixtures_dir / "invalid_agent.yaml", agents_dir / "bad.yaml")
        with pytest.raises(ValueError, match="Invalid agent config"):
            load_agents(tmp_path)


class TestLoadEvals:
    def test_loads_valid(self, sample_project: Path):
        evals = load_evals(sample_project)
        assert "customer-support" in evals
        assert len(evals["customer-support"]) == 1
        eval_file = evals["customer-support"][0]
        assert len(eval_file.tests) == 3
        assert eval_file.tests[0].name == "refund_request"

    def test_empty_when_no_dir(self, tmp_path: Path):
        evals = load_evals(tmp_path)
        assert evals == {}


class TestLoadProject:
    def test_loads_full_project(self, sample_project: Path):
        project = load_project(sample_project)
        assert project.config.project == "test-project"
        assert "reasoning" in project.models.aliases
        assert "customer-support" in project.agents
        assert "customer-support" in project.evals
        assert project.project_root == sample_project
