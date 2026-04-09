"""Pydantic models for agentmodelctl configuration and results."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, field_validator


class OutputFormat(str, Enum):
    """Output format for command results."""

    rich = "rich"
    json = "json"
    markdown = "markdown"


class ModelAlias(BaseModel):
    """A model alias mapping to a concrete provider and model."""

    provider: str
    model: str
    fallback: str | None = None


class ModelsConfig(BaseModel):
    """Top-level models.yaml schema."""

    aliases: dict[str, ModelAlias]


class ToolDef(BaseModel):
    """A tool available to an agent."""

    name: str
    description: str = ""


class AgentMetadata(BaseModel):
    """Optional metadata for an agent."""

    owner: str = ""
    env: str = "development"
    tags: list[str] = []
    last_evaluated: str | None = None


class OptimizationConfig(BaseModel):
    """Optimization preferences for an agent."""

    priority: list[str] = ["quality", "cost", "speed"]
    constraints: dict[str, Any] = {}


class AgentConfig(BaseModel):
    """An agent definition from agents/*.yaml."""

    name: str
    description: str = ""
    version: int = 1
    model: str  # alias name, NOT a model string
    system_prompt: str
    tools: list[ToolDef] = []
    temperature: float = 0.7
    max_tokens: int = 1024
    metadata: AgentMetadata = AgentMetadata()
    optimization: OptimizationConfig | None = None


class EvalTest(BaseModel):
    """A single eval test case."""

    name: str = ""
    input: str
    baseline_output: str | None = None
    expect_contains: str | list[str] | None = None
    expect_not_contains: str | list[str] | None = None
    expect_tool: str | None = None
    expect_regex: str | None = None
    expect_tone: str | None = None
    expect_language: str | None = None
    expect_max_tokens: int | None = None
    golden: str | None = None

    @field_validator("expect_contains", "expect_not_contains", mode="before")
    @classmethod
    def normalize_to_list(cls, v: str | list[str] | None) -> list[str] | None:
        """Accept a single string or a list of strings."""
        if isinstance(v, str):
            return [v]
        return v


class EvalFile(BaseModel):
    """An eval file containing multiple test cases."""

    generated_at: str | None = None
    baseline_model: str | None = None
    tests: list[EvalTest]


class EvalResult(BaseModel):
    """Result of running a single eval test."""

    test_name: str
    passed: bool
    quality_score: float  # 0.0 to 1.0
    latency_seconds: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    output: str
    failures: list[str] = []


class AgentEvalSummary(BaseModel):
    """Serializable summary of eval results for one agent."""

    agent_name: str
    passed: int
    failed: int
    total: int
    avg_quality: float
    avg_latency_seconds: float
    total_cost_usd: float
    results: list[EvalResult]


class ChangeSet(BaseModel):
    """Categorized file changes for CI decision-making."""

    config_changed: bool = False
    models_changed: bool = False
    agents_changed: list[str] = []
    evals_changed: list[str] = []
    all_affected_agents: list[str] = []


class ProviderConfig(BaseModel):
    """Provider-specific configuration."""

    api_key_env: str | None = None
    base_url: str | None = None


class DefaultsConfig(BaseModel):
    """Default settings for the project."""

    eval_runs: int = 3
    similarity_threshold: float = 0.80
    auto_generate_count: int = 10


class ProjectConfig(BaseModel):
    """Top-level agentmodelctl.yaml schema."""

    version: int = 1
    project: str = ""
    defaults: DefaultsConfig = DefaultsConfig()
    providers: dict[str, ProviderConfig] = {}


class TrackingEvent(BaseModel):
    """A single production invocation log entry."""

    timestamp: str  # ISO 8601 UTC
    agent_name: str
    model: str  # actual model string (not alias)
    latency_seconds: float
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    error: bool = False
    metadata: dict[str, Any] = {}


class Project(BaseModel):
    """Fully loaded project with all configs."""

    config: ProjectConfig
    models: ModelsConfig
    agents: dict[str, AgentConfig]
    evals: dict[str, list[EvalFile]]
    project_root: Path
