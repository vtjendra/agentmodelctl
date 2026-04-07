"""Tests for the CI command."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from agentmodelctl.cli import app
from agentmodelctl.providers.adapter import LLMResponse

runner = CliRunner()


def _setup_simple_project(tmp_path: Path) -> Path:
    """Create a project with simple evals (no tone/similarity assertions)."""
    (tmp_path / "agentmodelctl.yaml").write_text(
        "version: 1\nproject: test\ndefaults:\n  eval_runs: 1\n"
    )
    (tmp_path / "models.yaml").write_text(
        "aliases:\n  reasoning:\n    provider: anthropic\n    model: claude-sonnet-4-6\n"
    )
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "simple.yaml").write_text(
        "name: simple\nmodel: reasoning\nsystem_prompt: You are helpful.\n"
    )
    evals_dir = tmp_path / "evals" / "simple"
    evals_dir.mkdir(parents=True)
    (evals_dir / "basics.yaml").write_text(
        'tests:\n  - name: greeting\n    input: "Hello"\n    expect_contains: "hello"\n'
    )
    return tmp_path


def _mock_simple_response(*args, **kwargs) -> LLMResponse:
    return LLMResponse(
        content="Hello! How can I help you today?",
        input_tokens=10,
        output_tokens=15,
        cost_usd=0.0005,
        latency_seconds=0.3,
    )


def _mock_fail_response(*args, **kwargs) -> LLMResponse:
    return LLMResponse(
        content="Sorry, I cannot help.",
        input_tokens=10,
        output_tokens=15,
        cost_usd=0.0005,
        latency_seconds=0.3,
    )


class TestCINoChanges:
    def test_no_changes_exits_zero(self, sample_project, monkeypatch) -> None:
        monkeypatch.chdir(sample_project)
        with patch("agentmodelctl.change_detector.subprocess.run") as mock_git:
            mock_git.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            result = runner.invoke(app, ["ci"])
            assert result.exit_code == 0
            assert "nothing to evaluate" in result.output.lower()

    def test_no_changes_json_format(self, sample_project, monkeypatch) -> None:
        monkeypatch.chdir(sample_project)
        with patch("agentmodelctl.change_detector.subprocess.run") as mock_git:
            mock_git.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            result = runner.invoke(app, ["ci", "--format", "json"])
            assert result.exit_code == 0
            assert "skip" in result.output


class TestCIWithChanges:
    def test_all_pass_exits_zero(self, tmp_path, monkeypatch) -> None:
        project_dir = _setup_simple_project(tmp_path)
        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

        with (
            patch("agentmodelctl.change_detector.subprocess.run") as mock_git,
            patch("agentmodelctl.runner.call_model") as mock_llm,
        ):
            mock_git.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="agents/simple.yaml\n", stderr=""
            )
            mock_llm.side_effect = _mock_simple_response

            result = runner.invoke(app, ["ci", "--no-cache"])
            assert result.exit_code == 0

    def test_failures_exit_one(self, tmp_path, monkeypatch) -> None:
        project_dir = _setup_simple_project(tmp_path)
        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

        with (
            patch("agentmodelctl.change_detector.subprocess.run") as mock_git,
            patch("agentmodelctl.runner.call_model") as mock_llm,
        ):
            mock_git.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="agents/simple.yaml\n", stderr=""
            )
            mock_llm.side_effect = _mock_fail_response

            result = runner.invoke(app, ["ci", "--no-cache"])
            assert result.exit_code == 1

    def test_no_fail_on_regression_exits_zero(self, tmp_path, monkeypatch) -> None:
        project_dir = _setup_simple_project(tmp_path)
        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

        with (
            patch("agentmodelctl.change_detector.subprocess.run") as mock_git,
            patch("agentmodelctl.runner.call_model") as mock_llm,
        ):
            mock_git.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="agents/simple.yaml\n", stderr=""
            )
            mock_llm.side_effect = _mock_fail_response

            result = runner.invoke(app, ["ci", "--no-cache", "--no-fail-on-regression"])
            assert result.exit_code == 0


class TestCIAllAgents:
    def test_all_flag_skips_change_detection(self, tmp_path, monkeypatch) -> None:
        project_dir = _setup_simple_project(tmp_path)
        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

        with patch("agentmodelctl.runner.call_model") as mock_llm:
            mock_llm.side_effect = _mock_simple_response

            result = runner.invoke(app, ["ci", "--all", "--no-cache"])
            assert result.exit_code == 0


class TestCIOutputFormats:
    def test_json_format(self, tmp_path, monkeypatch) -> None:
        project_dir = _setup_simple_project(tmp_path)
        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

        with (
            patch("agentmodelctl.change_detector.subprocess.run") as mock_git,
            patch("agentmodelctl.runner.call_model") as mock_llm,
        ):
            mock_git.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="agents/simple.yaml\n", stderr=""
            )
            mock_llm.side_effect = _mock_simple_response

            result = runner.invoke(app, ["ci", "--format", "json", "--no-cache"])
            assert result.exit_code == 0
            assert "simple" in result.output

    def test_markdown_format(self, tmp_path, monkeypatch) -> None:
        project_dir = _setup_simple_project(tmp_path)
        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

        with (
            patch("agentmodelctl.change_detector.subprocess.run") as mock_git,
            patch("agentmodelctl.runner.call_model") as mock_llm,
        ):
            mock_git.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="agents/simple.yaml\n", stderr=""
            )
            mock_llm.side_effect = _mock_simple_response

            result = runner.invoke(app, ["ci", "--format", "markdown", "--no-cache"])
            assert result.exit_code == 0
            assert "agentmodelctl CI Report" in result.output


class TestCIGitError:
    def test_git_error_exits_one(self, sample_project, monkeypatch) -> None:
        monkeypatch.chdir(sample_project)
        with patch("agentmodelctl.change_detector.subprocess.run") as mock_git:
            mock_git.return_value = subprocess.CompletedProcess(
                args=[], returncode=128, stdout="", stderr="fatal: not a git repository"
            )
            result = runner.invoke(app, ["ci"])
            assert result.exit_code == 1
