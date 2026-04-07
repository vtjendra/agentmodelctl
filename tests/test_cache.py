"""Tests for the eval caching module."""

from __future__ import annotations

from pathlib import Path

from agentmodelctl.cache import (
    clear_cache,
    compute_eval_fingerprint,
    get_cache_dir,
    load_cached_results,
    save_cached_results,
)
from agentmodelctl.models import (
    AgentConfig,
    EvalFile,
    EvalResult,
    EvalTest,
    ModelAlias,
)


def _make_agent() -> AgentConfig:
    return AgentConfig(
        name="test-agent",
        model="reasoning",
        system_prompt="You are helpful.",
        temperature=0.7,
    )


def _make_eval_files() -> list[EvalFile]:
    return [
        EvalFile(
            tests=[
                EvalTest(name="t1", input="Hello"),
                EvalTest(name="t2", input="Goodbye"),
            ]
        )
    ]


def _make_model_alias() -> ModelAlias:
    return ModelAlias(provider="anthropic", model="claude-sonnet-4-6")


def _make_results() -> list[EvalResult]:
    return [
        EvalResult(
            test_name="t1",
            passed=True,
            quality_score=0.9,
            latency_seconds=1.0,
            input_tokens=50,
            output_tokens=30,
            cost_usd=0.001,
            output="Hello there!",
        ),
        EvalResult(
            test_name="t2",
            passed=True,
            quality_score=0.85,
            latency_seconds=0.8,
            input_tokens=40,
            output_tokens=25,
            cost_usd=0.0008,
            output="Goodbye!",
        ),
    ]


class TestComputeEvalFingerprint:
    def test_consistent_hash(self) -> None:
        agent = _make_agent()
        evals = _make_eval_files()
        alias = _make_model_alias()
        fp1 = compute_eval_fingerprint(agent, evals, alias)
        fp2 = compute_eval_fingerprint(agent, evals, alias)
        assert fp1 == fp2

    def test_different_agent_different_hash(self) -> None:
        evals = _make_eval_files()
        alias = _make_model_alias()
        agent1 = _make_agent()
        agent2 = AgentConfig(
            name="other-agent",
            model="reasoning",
            system_prompt="Different prompt.",
        )
        fp1 = compute_eval_fingerprint(agent1, evals, alias)
        fp2 = compute_eval_fingerprint(agent2, evals, alias)
        assert fp1 != fp2

    def test_different_model_different_hash(self) -> None:
        agent = _make_agent()
        evals = _make_eval_files()
        alias1 = ModelAlias(provider="anthropic", model="claude-sonnet-4-6")
        alias2 = ModelAlias(provider="openai", model="gpt-4o")
        fp1 = compute_eval_fingerprint(agent, evals, alias1)
        fp2 = compute_eval_fingerprint(agent, evals, alias2)
        assert fp1 != fp2

    def test_different_evals_different_hash(self) -> None:
        agent = _make_agent()
        alias = _make_model_alias()
        evals1 = _make_eval_files()
        evals2 = [EvalFile(tests=[EvalTest(name="different", input="What?")])]
        fp1 = compute_eval_fingerprint(agent, evals1, alias)
        fp2 = compute_eval_fingerprint(agent, evals2, alias)
        assert fp1 != fp2

    def test_returns_hex_string(self) -> None:
        fp = compute_eval_fingerprint(_make_agent(), _make_eval_files(), _make_model_alias())
        assert len(fp) == 64  # SHA-256 hex digest
        assert all(c in "0123456789abcdef" for c in fp)


class TestGetCacheDir:
    def test_creates_directory(self, tmp_path: Path) -> None:
        cache_dir = get_cache_dir(tmp_path)
        assert cache_dir.exists()
        assert cache_dir == tmp_path / ".agentmodelctl" / "cache"

    def test_idempotent(self, tmp_path: Path) -> None:
        dir1 = get_cache_dir(tmp_path)
        dir2 = get_cache_dir(tmp_path)
        assert dir1 == dir2


class TestSaveLoadCachedResults:
    def test_round_trip(self, tmp_path: Path) -> None:
        cache_dir = get_cache_dir(tmp_path)
        results = _make_results()
        fp = "abc123"

        save_cached_results(fp, results, cache_dir)
        loaded = load_cached_results(fp, cache_dir)

        assert loaded is not None
        assert len(loaded) == 2
        assert loaded[0].test_name == "t1"
        assert loaded[0].quality_score == 0.9
        assert loaded[1].test_name == "t2"

    def test_cache_miss_returns_none(self, tmp_path: Path) -> None:
        cache_dir = get_cache_dir(tmp_path)
        assert load_cached_results("nonexistent", cache_dir) is None

    def test_corrupted_cache_returns_none(self, tmp_path: Path) -> None:
        cache_dir = get_cache_dir(tmp_path)
        cache_file = cache_dir / "bad.json"
        cache_file.write_text("not valid json{{{")
        assert load_cached_results("bad", cache_dir) is None
        # Corrupted file should be cleaned up
        assert not cache_file.exists()


class TestClearCache:
    def test_clears_files(self, tmp_path: Path) -> None:
        cache_dir = get_cache_dir(tmp_path)
        (cache_dir / "a.json").write_text("{}")
        (cache_dir / "b.json").write_text("{}")

        count = clear_cache(tmp_path)
        assert count == 2
        assert list(cache_dir.iterdir()) == []

    def test_no_cache_dir_returns_zero(self, tmp_path: Path) -> None:
        count = clear_cache(tmp_path)
        assert count == 0
