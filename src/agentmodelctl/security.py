"""API key detection, redaction, and security scanning."""

from __future__ import annotations

import re
from pathlib import Path

KEY_PATTERNS = [
    (r"sk-ant-[a-zA-Z0-9\-_]{20,}", "Anthropic API key"),
    (r"sk-[a-zA-Z0-9]{20,}", "OpenAI API key"),
    (r"AIza[a-zA-Z0-9\-_]{35}", "Google API key"),
    (r"key-[a-zA-Z0-9]{20,}", "Generic API key"),
]

_compiled_patterns = [(re.compile(p), desc) for p, desc in KEY_PATTERNS]


def scan_file_for_keys(path: Path) -> list[tuple[int, str, str]]:
    """Scan a file for potential API keys.

    Returns list of (line_number, matched_text, description).
    """
    findings: list[tuple[int, str, str]] = []
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return findings
    for i, line in enumerate(text.splitlines(), start=1):
        for pattern, desc in _compiled_patterns:
            for match in pattern.finditer(line):
                findings.append((i, match.group(), desc))
    return findings


def scan_project_for_keys(root: Path) -> dict[str, list[tuple[int, str, str]]]:
    """Scan all YAML files in a project for potential API keys.

    Returns dict of filepath → list of findings.
    """
    results: dict[str, list[tuple[int, str, str]]] = {}
    yaml_files = list(root.glob("**/*.yaml")) + list(root.glob("**/*.yml"))
    for path in yaml_files:
        # Skip hidden directories
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        findings = scan_file_for_keys(path)
        if findings:
            results[str(path.relative_to(root))] = findings
    return results


def redact_key(text: str) -> str:
    """Replace any detected API keys in text with redacted versions."""
    result = text
    for pattern, _ in _compiled_patterns:
        result = pattern.sub(lambda m: m.group()[:8] + "..." + m.group()[-4:], result)
    return result
