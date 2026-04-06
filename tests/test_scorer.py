"""Tests for eval scoring functions."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from agentmodelctl.models import EvalTest
from agentmodelctl.scorer import (
    score_contains,
    score_eval_test,
    score_language,
    score_max_tokens,
    score_not_contains,
    score_regex,
    score_similarity,
    score_tone,
    score_tool_called,
)


class TestScoreContains:
    def test_all_present(self):
        score, failures = score_contains("Hello world, how are you?", ["hello", "world"])
        assert score == 1.0
        assert failures == []

    def test_some_missing(self):
        score, failures = score_contains("Hello world", ["hello", "missing"])
        assert score == 0.5
        assert len(failures) == 1
        assert "missing" in failures[0]

    def test_none_present(self):
        score, failures = score_contains("Hello", ["foo", "bar"])
        assert score == 0.0
        assert len(failures) == 2

    def test_case_insensitive(self):
        score, _ = score_contains("HELLO WORLD", ["hello", "world"])
        assert score == 1.0

    def test_empty_expected(self):
        score, failures = score_contains("anything", [])
        assert score == 1.0
        assert failures == []


class TestScoreNotContains:
    def test_none_present(self):
        score, failures = score_not_contains("Hello world", ["foo", "bar"])
        assert score == 1.0
        assert failures == []

    def test_one_present(self):
        score, failures = score_not_contains("Hello world", ["hello", "bar"])
        assert score == 0.5
        assert len(failures) == 1

    def test_all_present(self):
        score, failures = score_not_contains("Hello world", ["hello", "world"])
        assert score == 0.0
        assert len(failures) == 2

    def test_empty_forbidden(self):
        score, failures = score_not_contains("anything", [])
        assert score == 1.0


class TestScoreRegex:
    def test_match(self):
        score, failures = score_regex("Order #12345 confirmed", r"#\d{5}")
        assert score == 1.0
        assert failures == []

    def test_no_match(self):
        score, failures = score_regex("No numbers here", r"#\d{5}")
        assert score == 0.0
        assert len(failures) == 1


class TestScoreToolCalled:
    def test_tool_found(self):
        tool_calls = [{"name": "lookup_order", "arguments": "{}"}]
        score, failures = score_tool_called(tool_calls, "lookup_order")
        assert score == 1.0
        assert failures == []

    def test_tool_not_found(self):
        tool_calls = [{"name": "other_tool", "arguments": "{}"}]
        score, failures = score_tool_called(tool_calls, "lookup_order")
        assert score == 0.0
        assert "lookup_order" in failures[0]

    def test_empty_tool_calls(self):
        score, failures = score_tool_called([], "lookup_order")
        assert score == 0.0


class TestScoreMaxTokens:
    def test_within_limit(self):
        score, failures = score_max_tokens(50, 100)
        assert score == 1.0
        assert failures == []

    def test_at_limit(self):
        score, failures = score_max_tokens(100, 100)
        assert score == 1.0

    def test_over_limit(self):
        score, failures = score_max_tokens(200, 100)
        assert score == 0.5
        assert len(failures) == 1
        assert "200" in failures[0]


class TestScoreLanguage:
    def test_without_langdetect(self):
        # Without langdetect installed, should always pass
        score, failures = score_language("Hello world", "en")
        assert score == 1.0


class TestScoreSimilarity:
    def test_identical(self):
        score, failures = score_similarity("hello world", "hello world")
        assert score == 1.0
        assert failures == []

    def test_similar(self):
        score, failures = score_similarity(
            "Hello, how are you doing today?",
            "Hello, how are you doing today!",
            threshold=0.8,
        )
        assert score >= 0.9
        assert failures == []

    def test_below_threshold(self):
        score, failures = score_similarity("apple", "orange", threshold=0.8)
        assert score < 0.8
        assert len(failures) == 1
        assert "below threshold" in failures[0]


class TestScoreTone:
    @patch("agentmodelctl.providers.adapter.call_model")
    def test_yes_response(self, mock_call):
        mock_response = MagicMock()
        mock_response.content = "YES 0.9"
        mock_call.return_value = mock_response

        score, failures = score_tone("I understand your frustration", "empathetic", "model", "key")
        assert score == 0.9
        assert failures == []

    @patch("agentmodelctl.providers.adapter.call_model")
    def test_no_response(self, mock_call):
        mock_response = MagicMock()
        mock_response.content = "NO 0.8"
        mock_call.return_value = mock_response

        score, failures = score_tone("Buy now!", "empathetic", "model", "key")
        assert abs(score - 0.2) < 0.01  # 1.0 - 0.8
        assert len(failures) == 1

    @patch("agentmodelctl.providers.adapter.call_model")
    def test_error_graceful(self, mock_call):
        mock_call.side_effect = Exception("API error")
        score, failures = score_tone("text", "tone", "model", "key")
        assert score == 1.0  # Graceful fallback
        assert failures == []


class TestScoreEvalTest:
    def test_all_pass(self):
        test = EvalTest(input="Hello", expect_contains=["hello"])
        quality, passed, failures = score_eval_test("Hello world", [], test)
        assert passed is True
        assert quality == 1.0
        assert failures == []

    def test_some_fail(self):
        test = EvalTest(input="Hello", expect_contains=["hello"], expect_not_contains=["hello"])
        quality, passed, failures = score_eval_test("Hello world", [], test)
        assert passed is False
        assert len(failures) == 1

    def test_no_assertions_passes(self):
        test = EvalTest(input="Hello")
        quality, passed, failures = score_eval_test("anything", [], test)
        assert passed is True
        assert quality == 1.0

    def test_tool_assertion(self):
        test = EvalTest(input="Hello", expect_tool="lookup_order")
        tool_calls = [{"name": "lookup_order"}]
        quality, passed, failures = score_eval_test("output", tool_calls, test)
        assert passed is True

    def test_similarity_with_golden(self):
        test = EvalTest(input="Hello", golden="Hello there, how can I help you?")
        quality, passed, failures = score_eval_test(
            "Hello there, how can I help you?", [], test, similarity_threshold=0.8
        )
        assert passed is True
        assert quality >= 0.8
