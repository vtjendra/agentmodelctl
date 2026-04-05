"""Tests for security scanning and key redaction."""

from __future__ import annotations

from pathlib import Path

from agentmodelctl.security import redact_key, scan_file_for_keys, scan_project_for_keys


class TestScanFileForKeys:
    def test_detects_anthropic_key(self, tmp_path: Path):
        f = tmp_path / "test.yaml"
        f.write_text("api_key: sk-ant-abcdefghijklmnopqrstuvwxyz1234567890")
        findings = scan_file_for_keys(f)
        assert len(findings) == 1
        assert findings[0][0] == 1  # line number
        assert "Anthropic" in findings[0][2]

    def test_detects_openai_key(self, tmp_path: Path):
        f = tmp_path / "test.yaml"
        f.write_text("key: sk-abcdefghijklmnopqrstuvwxyz1234567890")
        findings = scan_file_for_keys(f)
        assert len(findings) >= 1
        assert any("OpenAI" in desc for _, _, desc in findings)

    def test_detects_google_key(self, tmp_path: Path):
        f = tmp_path / "test.yaml"
        f.write_text("key: AIzaABCDEFGHIJKLMNOPQRSTUVWXYZ01234567890")
        findings = scan_file_for_keys(f)
        assert len(findings) == 1
        assert "Google" in findings[0][2]

    def test_no_findings_clean_file(self, tmp_path: Path):
        f = tmp_path / "test.yaml"
        f.write_text("model: reasoning\nprovider: anthropic\n")
        findings = scan_file_for_keys(f)
        assert findings == []

    def test_handles_binary_file(self, tmp_path: Path):
        f = tmp_path / "binary.yaml"
        f.write_bytes(b"\x00\x01\x02\xff\xfe")
        findings = scan_file_for_keys(f)
        assert findings == []


class TestScanProjectForKeys:
    def test_finds_key_in_yaml(self, tmp_path: Path):
        f = tmp_path / "models.yaml"
        f.write_text("api_key: sk-ant-abcdefghijklmnopqrstuvwxyz1234567890")
        results = scan_project_for_keys(tmp_path)
        assert "models.yaml" in results

    def test_skips_hidden_dirs(self, tmp_path: Path):
        hidden = tmp_path / ".git" / "config"
        hidden.parent.mkdir(parents=True)
        hidden.write_text("key: sk-ant-abcdefghijklmnopqrstuvwxyz1234567890")
        results = scan_project_for_keys(tmp_path)
        assert len(results) == 0

    def test_clean_project(self, sample_project: Path):
        results = scan_project_for_keys(sample_project)
        assert len(results) == 0


class TestRedactKey:
    def test_redacts_anthropic(self):
        text = "key is sk-ant-abcdefghijklmnopqrstuvwxyz1234567890"
        redacted = redact_key(text)
        assert "..." in redacted
        assert "abcdefghijklmnopqrstuvwxyz" not in redacted

    def test_no_key_unchanged(self):
        text = "no keys here"
        assert redact_key(text) == text

    def test_multiple_keys(self):
        text = "a: sk-ant-abcdefghijklmnopqrstuvwxyz1234567890 b: sk-abcdefghijklmnopqrstuvwxyz1234567890"
        redacted = redact_key(text)
        assert redacted.count("...") >= 2
