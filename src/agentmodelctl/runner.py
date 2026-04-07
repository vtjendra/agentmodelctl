"""Eval execution engine — run agents against test cases and collect results."""

from __future__ import annotations

from agentmodelctl.models import (
    AgentConfig,
    EvalFile,
    EvalResult,
    EvalTest,
    ModelsConfig,
    Project,
    ProjectConfig,
)
from agentmodelctl.providers.adapter import LLMResponse, call_model
from agentmodelctl.router import get_api_key, get_litellm_model_string, resolve_alias
from agentmodelctl.scorer import score_eval_test


def run_single_eval(
    test: EvalTest,
    agent: AgentConfig,
    model_string: str,
    api_key: str,
    similarity_threshold: float = 0.80,
) -> EvalResult:
    """Run a single eval test against a model.

    Args:
        test: The eval test case to run.
        agent: The agent configuration.
        model_string: Resolved LiteLLM model string.
        api_key: API key for the provider.
        similarity_threshold: Minimum similarity score to pass.

    Returns:
        EvalResult with all metrics and pass/fail status.
    """
    # Build tool definitions from agent config
    tools = [{"name": t.name, "description": t.description} for t in agent.tools] or None

    # Call the model
    response: LLMResponse = call_model(
        model=model_string,
        system_prompt=agent.system_prompt,
        user_message=test.input,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
        api_key=api_key,
        tools=tools,
    )

    # Score the response
    quality_score, passed, failures = score_eval_test(
        output=response.content,
        tool_calls=response.tool_calls,
        test=test,
        similarity_threshold=similarity_threshold,
    )

    test_name = test.name or test.input[:50]

    return EvalResult(
        test_name=test_name,
        passed=passed,
        quality_score=quality_score,
        latency_seconds=response.latency_seconds,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost_usd=response.cost_usd,
        output=response.content,
        failures=failures,
    )


def run_agent_evals(
    agent: AgentConfig,
    eval_files: list[EvalFile],
    models: ModelsConfig,
    config: ProjectConfig,
    model_override: str | None = None,
    api_key_override: str | None = None,
) -> list[EvalResult]:
    """Run all eval tests for an agent.

    Args:
        agent: The agent to evaluate.
        eval_files: Eval files containing test cases.
        models: Model alias configuration.
        config: Project configuration.
        model_override: If set, use this model string instead of the agent's alias.
        api_key_override: If set, use this API key instead of resolving from env.

    Returns:
        List of EvalResult for each test case.
    """
    # Resolve model
    if model_override:
        model_string = model_override
        if api_key_override:
            api_key = api_key_override
        else:
            # Try to infer provider from model string for key lookup
            provider, _ = _infer_provider(model_override)
            api_key = get_api_key(provider, config)
    else:
        provider, model = resolve_alias(agent.model, models)
        model_string = get_litellm_model_string(provider, model)
        api_key = get_api_key(provider, config)

    similarity_threshold = config.defaults.similarity_threshold

    # Collect all tests from all eval files
    all_tests: list[EvalTest] = []
    for ef in eval_files:
        all_tests.extend(ef.tests)

    # Run each test sequentially
    results: list[EvalResult] = []
    for test in all_tests:
        result = run_single_eval(
            test=test,
            agent=agent,
            model_string=model_string,
            api_key=api_key,
            similarity_threshold=similarity_threshold,
        )
        results.append(result)

    return results


def run_all_evals(
    project: Project,
    agent_filter: str | None = None,
) -> dict[str, list[EvalResult]]:
    """Run evals for all (or filtered) agents that have eval definitions.

    Args:
        project: Fully loaded project.
        agent_filter: If set, only run this agent.

    Returns:
        Dict of agent_name → list of EvalResult.
    """
    results: dict[str, list[EvalResult]] = {}

    for agent_name, agent in project.agents.items():
        if agent_filter and agent_name != agent_filter:
            continue

        eval_files = project.evals.get(agent_name, [])
        if not eval_files:
            continue

        agent_results = run_agent_evals(
            agent=agent,
            eval_files=eval_files,
            models=project.models,
            config=project.config,
        )
        results[agent_name] = agent_results

    return results


def _infer_provider(model_string: str) -> tuple[str, str]:
    """Infer provider from a model string.

    Handles formats like "openai/gpt-4o", "gpt-4o", "claude-sonnet-4-6", etc.
    Returns (provider, model).
    """
    if "/" in model_string:
        parts = model_string.split("/", 1)
        return parts[0], parts[1]

    # Infer from known prefixes
    lower = model_string.lower()
    if lower.startswith("claude") or lower.startswith("anthropic"):
        return "anthropic", model_string
    if lower.startswith("gpt") or lower.startswith("o1") or lower.startswith("o3"):
        return "openai", model_string
    if lower.startswith("gemini"):
        return "google", model_string
    if lower.startswith("llama") or lower.startswith("mistral") or lower.startswith("codellama"):
        return "ollama", model_string

    # Default to openai
    return "openai", model_string
