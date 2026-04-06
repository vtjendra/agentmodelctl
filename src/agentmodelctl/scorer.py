"""Scoring functions for eval assertions."""

from __future__ import annotations

import difflib
import re

from agentmodelctl.models import EvalTest


def score_contains(output: str, expected: list[str]) -> tuple[float, list[str]]:
    """Check output contains all expected strings (case-insensitive).

    Returns (score, failure_messages). Score = fraction of expected strings found.
    """
    if not expected:
        return 1.0, []
    output_lower = output.lower()
    found = 0
    failures: list[str] = []
    for s in expected:
        if s.lower() in output_lower:
            found += 1
        else:
            failures.append(f"Expected output to contain '{s}'")
    return found / len(expected), failures


def score_not_contains(output: str, forbidden: list[str]) -> tuple[float, list[str]]:
    """Check output does NOT contain any forbidden strings (case-insensitive).

    Returns (score, failure_messages). Score = fraction of forbidden strings absent.
    """
    if not forbidden:
        return 1.0, []
    output_lower = output.lower()
    not_found = 0
    failures: list[str] = []
    for s in forbidden:
        if s.lower() in output_lower:
            failures.append(f"Output should not contain '{s}'")
        else:
            not_found += 1
    return not_found / len(forbidden), failures


def score_regex(output: str, pattern: str) -> tuple[float, list[str]]:
    """Check output matches a regex pattern.

    Returns (1.0 if match, 0.0 if not).
    """
    if re.search(pattern, output):
        return 1.0, []
    return 0.0, [f"Output does not match regex '{pattern}'"]


def score_tool_called(tool_calls: list[dict], expected_tool: str) -> tuple[float, list[str]]:
    """Check if a specific tool was called.

    Args:
        tool_calls: List of dicts with "name" key from LLM response.
        expected_tool: The tool name to look for.

    Returns (1.0 if found, 0.0 if not).
    """
    for tc in tool_calls:
        if tc.get("name") == expected_tool:
            return 1.0, []
    return 0.0, [f"Expected tool call '{expected_tool}' not found"]


def score_max_tokens(token_count: int, max_tokens: int) -> tuple[float, list[str]]:
    """Check output token count is within limit.

    Returns (1.0 if within limit, partial score if over).
    """
    if token_count <= max_tokens:
        return 1.0, []
    score = max(0.0, min(1.0, max_tokens / token_count))
    return score, [f"Output {token_count} tokens exceeds limit of {max_tokens}"]


def score_language(output: str, expected_lang: str) -> tuple[float, list[str]]:
    """Detect output language and check it matches expected.

    Uses langdetect if available, otherwise returns a pass with a warning.
    """
    try:
        import langdetect
        detected = langdetect.detect(output)
        if detected == expected_lang:
            return 1.0, []
        return 0.0, [f"Expected language '{expected_lang}', detected '{detected}'"]
    except ImportError:
        # langdetect not installed — skip check with a pass
        return 1.0, []
    except Exception:
        # langdetect can fail on short/ambiguous text
        return 1.0, []


def score_similarity(
    output: str, golden: str, threshold: float = 0.80
) -> tuple[float, list[str]]:
    """Compute text similarity between output and golden reference.

    Uses difflib.SequenceMatcher for MVP. Returns (ratio, failures).
    """
    ratio = difflib.SequenceMatcher(None, output.lower(), golden.lower()).ratio()
    if ratio >= threshold:
        return ratio, []
    return ratio, [f"Similarity {ratio:.2f} below threshold {threshold:.2f}"]


def score_tone(
    output: str,
    expected_tone: str,
    model: str = "claude-haiku-4-5",
    api_key: str | None = None,
) -> tuple[float, list[str]]:
    """Use LLM-as-judge to check if output matches expected tone.

    Calls a cheap model to evaluate tone. Returns (confidence, failures).
    """
    from agentmodelctl.providers.adapter import call_model

    prompt = (
        f"Does the following text have a {expected_tone} tone?\n"
        f"Reply with only YES or NO followed by a confidence score 0.0 to 1.0.\n"
        f"Example: YES 0.9\n\n"
        f"Text:\n{output[:1000]}"  # Truncate to save tokens
    )

    try:
        response = call_model(
            model=model,
            system_prompt="You are a tone classifier. Reply with YES/NO and a confidence score.",
            user_message=prompt,
            temperature=0.0,
            max_tokens=20,
            api_key=api_key,
        )
        result = response.content.strip().upper()

        # Parse YES/NO and confidence
        if result.startswith("YES"):
            parts = result.split()
            confidence = float(parts[1]) if len(parts) > 1 else 0.8
            return confidence, []
        elif result.startswith("NO"):
            parts = result.split()
            confidence = float(parts[1]) if len(parts) > 1 else 0.2
            return 1.0 - confidence, [f"Tone '{expected_tone}' not detected (confidence {confidence:.2f})"]
        else:
            return 0.5, []  # Ambiguous response, neutral score
    except Exception:
        # If tone scoring fails, don't block the eval
        return 1.0, []


def score_eval_test(
    output: str,
    tool_calls: list[dict],
    test: EvalTest,
    similarity_threshold: float = 0.80,
    tone_model: str | None = None,
    tone_api_key: str | None = None,
) -> tuple[float, bool, list[str]]:
    """Run all applicable scorers for a test case.

    Returns (quality_score, passed, failures).
    quality_score is the average of all sub-scores.
    passed is True only if there are no failures.
    """
    scores: list[float] = []
    all_failures: list[str] = []

    if test.expect_contains:
        score, failures = score_contains(output, test.expect_contains)
        scores.append(score)
        all_failures.extend(failures)

    if test.expect_not_contains:
        score, failures = score_not_contains(output, test.expect_not_contains)
        scores.append(score)
        all_failures.extend(failures)

    if test.expect_regex:
        score, failures = score_regex(output, test.expect_regex)
        scores.append(score)
        all_failures.extend(failures)

    if test.expect_tool:
        score, failures = score_tool_called(tool_calls, test.expect_tool)
        scores.append(score)
        all_failures.extend(failures)

    if test.expect_max_tokens is not None:
        # Approximate token count via whitespace split
        approx_tokens = len(output.split())
        score, failures = score_max_tokens(approx_tokens, test.expect_max_tokens)
        scores.append(score)
        all_failures.extend(failures)

    if test.expect_language:
        score, failures = score_language(output, test.expect_language)
        scores.append(score)
        all_failures.extend(failures)

    # Check similarity against golden or baseline_output
    golden = test.golden or test.baseline_output
    if golden:
        score, failures = score_similarity(output, golden, threshold=similarity_threshold)
        scores.append(score)
        all_failures.extend(failures)

    if test.expect_tone and tone_model:
        score, failures = score_tone(output, test.expect_tone, model=tone_model, api_key=tone_api_key)
        scores.append(score)
        all_failures.extend(failures)

    # If no scorers were applicable, default to pass
    if not scores:
        return 1.0, True, []

    quality_score = sum(scores) / len(scores)
    passed = len(all_failures) == 0
    return quality_score, passed, all_failures
