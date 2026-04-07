"""Hash-based eval caching — skip re-running unchanged agent+eval+model combos."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from agentmodelctl.models import AgentConfig, EvalFile, EvalResult, ModelAlias


def compute_eval_fingerprint(
    agent: AgentConfig,
    eval_files: list[EvalFile],
    model_alias: ModelAlias,
) -> str:
    """Compute a SHA-256 fingerprint for an agent+eval+model combination.

    The fingerprint changes when any of these change, triggering re-evaluation.
    """
    parts = [
        agent.model_dump_json(exclude={"metadata"}),
        model_alias.model_dump_json(),
    ]
    for ef in sorted(eval_files, key=lambda e: e.model_dump_json()):
        parts.append(ef.model_dump_json())

    combined = "\n".join(parts)
    return hashlib.sha256(combined.encode()).hexdigest()


def get_cache_dir(project_root: Path) -> Path:
    """Get (and create) the cache directory."""
    cache_dir = project_root / ".agentmodelctl" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def load_cached_results(fingerprint: str, cache_dir: Path) -> list[EvalResult] | None:
    """Load cached eval results for a fingerprint.

    Returns None on cache miss or invalid data.
    """
    cache_file = cache_dir / f"{fingerprint}.json"
    if not cache_file.exists():
        return None

    try:
        data = json.loads(cache_file.read_text())
        return [EvalResult.model_validate(r) for r in data]
    except (json.JSONDecodeError, ValueError, KeyError):
        # Corrupted cache — remove and return miss
        cache_file.unlink(missing_ok=True)
        return None


def save_cached_results(fingerprint: str, results: list[EvalResult], cache_dir: Path) -> None:
    """Save eval results to the cache."""
    cache_file = cache_dir / f"{fingerprint}.json"
    data = [r.model_dump() for r in results]
    cache_file.write_text(json.dumps(data, default=str))


def clear_cache(project_root: Path) -> int:
    """Delete all cached eval results. Returns count of files removed."""
    cache_dir = project_root / ".agentmodelctl" / "cache"
    if not cache_dir.exists():
        return 0

    count = 0
    for f in cache_dir.iterdir():
        if f.is_file():
            f.unlink()
            count += 1
    return count
