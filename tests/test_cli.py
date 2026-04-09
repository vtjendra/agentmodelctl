"""Tests for CLI commands via typer.testing.CliRunner."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from agentmodelctl.cli import app

runner = CliRunner()


class TestVersion:
    def test_version_flag(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "agentmodelctl" in result.output


class TestList:
    def test_list_agents(self, sample_project: Path, monkeypatch):
        monkeypatch.chdir(sample_project)
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "customer-support" in result.output
        assert "reasoning" in result.output

    def test_list_no_project(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["list"])
        assert result.exit_code != 0


class TestValidate:
    def test_valid_project(self, sample_project: Path, monkeypatch):
        monkeypatch.chdir(sample_project)
        result = runner.invoke(app, ["validate"])
        assert result.exit_code == 0
        assert "agentmodelctl.yaml" in result.output

    def test_no_project(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["validate"])
        assert result.exit_code != 0

    def test_detects_missing_alias(self, sample_project: Path, monkeypatch):
        # Modify agent to use non-existent alias
        agent_file = sample_project / "agents" / "customer-support.yaml"
        content = agent_file.read_text().replace("model: reasoning", "model: nonexistent")
        agent_file.write_text(content)

        monkeypatch.chdir(sample_project)
        result = runner.invoke(app, ["validate"])
        assert result.exit_code != 0
        assert "nonexistent" in result.output


class TestInit:
    def test_init_custom(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert (tmp_path / "agentmodelctl.yaml").exists()
        assert (tmp_path / "models.yaml").exists()
        assert (tmp_path / ".env.example").exists()
        assert (tmp_path / ".gitignore").exists()

    def test_init_customer_support(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["init", "--template", "customer-support"])
        assert result.exit_code == 0
        assert (tmp_path / "agents" / "customer-support.yaml").exists()

    def test_init_invalid_template(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["init", "--template", "invalid"])
        assert result.exit_code != 0


class TestReport:
    def test_report(self, sample_project: Path, monkeypatch):
        monkeypatch.chdir(sample_project)
        result = runner.invoke(app, ["report"])
        assert result.exit_code == 0
        assert "FLEET HEALTH REPORT" in result.output
        assert "customer-support" in result.output or "1 total" in result.output
