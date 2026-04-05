"""LiteLLM adapter for making LLM calls with tracking."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import litellm


@dataclass
class LLMResponse:
    """Tracked LLM response with metrics."""

    content: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_seconds: float
    tool_calls: list[dict] = field(default_factory=list)


def _build_tools(tools: list[dict] | None) -> list[dict] | None:
    """Convert simple tool defs to OpenAI function-calling format."""
    if not tools:
        return None
    result = []
    for tool in tools:
        result.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
            },
        })
    return result


def call_model(
    model: str,
    system_prompt: str,
    user_message: str,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    api_key: str | None = None,
    tools: list[dict] | None = None,
) -> LLMResponse:
    """Call an LLM via LiteLLM and return a tracked response.

    Args:
        model: LiteLLM model string (e.g., "claude-sonnet-4-6", "gpt-4o").
        system_prompt: System message for the model.
        user_message: User input message.
        temperature: Sampling temperature.
        max_tokens: Maximum output tokens.
        api_key: API key (overrides env var if provided).
        tools: List of tool definitions (simple format: name + description).

    Returns:
        LLMResponse with content, token counts, cost, latency, and tool calls.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    kwargs: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if api_key:
        kwargs["api_key"] = api_key

    tool_defs = _build_tools(tools)
    if tool_defs:
        kwargs["tools"] = tool_defs

    start = time.monotonic()
    response = litellm.completion(**kwargs)
    latency = time.monotonic() - start

    # Extract content
    message = response.choices[0].message
    content = message.content or ""

    # Extract tool calls
    extracted_tool_calls: list[dict] = []
    if hasattr(message, "tool_calls") and message.tool_calls:
        for tc in message.tool_calls:
            extracted_tool_calls.append({
                "name": tc.function.name,
                "arguments": tc.function.arguments,
            })
            # Append tool call info to content for scoring visibility
            content += f"\n[Tool call: {tc.function.name}({tc.function.arguments})]"

    # Extract token usage
    usage = response.usage
    input_tokens = usage.prompt_tokens if usage else 0
    output_tokens = usage.completion_tokens if usage else 0

    # Calculate cost
    try:
        cost = litellm.completion_cost(completion_response=response)
    except Exception:
        cost = 0.0

    return LLMResponse(
        content=content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        latency_seconds=latency,
        tool_calls=extracted_tool_calls,
    )
