"""Shared test fixtures for agentmodelctl."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Create a complete sample project in a temp directory."""
    # Project config
    shutil.copy(FIXTURES_DIR / "valid_project.yaml", tmp_path / "agentmodelctl.yaml")
    shutil.copy(FIXTURES_DIR / "valid_models.yaml", tmp_path / "models.yaml")

    # Agents
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    shutil.copy(FIXTURES_DIR / "valid_agent.yaml", agents_dir / "customer-support.yaml")

    # Evals
    evals_dir = tmp_path / "evals" / "customer-support"
    evals_dir.mkdir(parents=True)
    shutil.copy(FIXTURES_DIR / "sample_evals.yaml", evals_dir / "auto_generated.yaml")

    return tmp_path


@pytest.fixture
def empty_project(tmp_path: Path) -> Path:
    """Create a minimal project with just the config files."""
    shutil.copy(FIXTURES_DIR / "valid_project.yaml", tmp_path / "agentmodelctl.yaml")
    shutil.copy(FIXTURES_DIR / "valid_models.yaml", tmp_path / "models.yaml")
    (tmp_path / "agents").mkdir()
    return tmp_path
