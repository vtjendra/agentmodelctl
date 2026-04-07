# CLAUDE.md — agentmodelctl

## Project Overview

agentmodelctl is an open-source Python CLI tool for managing fleets of AI agents. It defines agents as YAML config files, uses model aliases instead of hardcoded model strings, and runs evaluations to ensure model swaps don't break agent behavior. The tagline: "Know what breaks before you switch AI models."

## Tech Stack

- **Python 3.10+** — minimum version, use modern typing (X | None, not Optional[X])
- **Typer** — CLI framework (not Click directly). Use type hints for all parameters.
- **Pydantic v2** — all config schemas. Use `model_validator`, `field_validator` where needed.
- **PyYAML** — YAML parsing, always through Pydantic models for validation.
- **LiteLLM** — unified LLM API calls. Never call provider SDKs directly.
- **Rich** — all terminal output. Use Tables, Panels, Progress bars, Console markup.
- **python-dotenv** — .env file loading. Load early in CLI entrypoint.
- **pytest** — testing. Mock all LLM calls in tests.

## Package Structure

```
src/agentmodelctl/       # All source code here (src layout)
tests/                    # pytest tests
```

Use `pyproject.toml` for packaging (no setup.py, no setup.cfg). Entry point: `agentmodelctl = "agentmodelctl.cli:app"`.

## Architecture

### Module Dependency Graph

```
cli.py → *_cmd.py → runner.py → adapter.py (LiteLLM)
                   → generator.py → adapter.py
                   → switch.py → runner.py
                   → reporter.py (Rich output)
                   → parser.py (YAML loading)
                   → security.py (key scanning)
                   → router.py (alias resolution)

models.py ← everything (Pydantic schemas)
```

### Config Loading Flow

1. CLI command invoked
2. Load `.env` file (python-dotenv)
3. Load `agentmodelctl.yaml` (project config)
4. Load `models.yaml` (model aliases)
5. Load `agents/*.yaml` (agent definitions)
6. Load `evals/**/*.yaml` (eval definitions)
7. Validate all configs through Pydantic models
8. Execute command

### Model Resolution Flow

1. Agent config says `model: reasoning`
2. Router looks up `reasoning` in `models.yaml` → `anthropic/claude-sonnet-4-6`
3. Router finds API key from env var `ANTHROPIC_API_KEY`
4. LiteLLM call with resolved model + key

### Eval Execution Flow

1. Load agent config + eval definitions
2. For each eval test case:
   a. Start timer
   b. Send input to LLM via LiteLLM (with agent's system prompt, tools, params)
   c. Stop timer, record latency
   d. Record token usage from LiteLLM response
   e. Calculate cost using LiteLLM's cost tracking
   f. Run all scorers (contains, not_contains, tool_called, regex, tone, similarity)
   g. Store EvalResult
3. Aggregate results, format output via Reporter

## CLI Commands (priority order)

1. `agentmodelctl validate` — parse and validate all YAML
2. `agentmodelctl list` — load agents, resolve aliases, display Rich table
3. `agentmodelctl eval [agent]` — run evals, display results
4. `agentmodelctl eval --auto-generate` — generate evals from agent definition
5. `agentmodelctl switch <alias> <model> --dry-run` — the killer feature
6. `agentmodelctl compare <agent> --models A B C` — side-by-side comparison
7. `agentmodelctl report` — fleet health overview
8. `agentmodelctl init [--template <name>]` — scaffold project

## Security Rules

### NEVER do:
- Store API keys in any YAML config file
- Log API keys in eval outputs or reports
- Include API keys in error messages

### ALWAYS do:
- Read keys from environment variables (via python-dotenv)
- On `init`, create `.env.example` (template) and add `.env` to `.gitignore`
- On `validate`, scan all YAML files for potential key exposure
- Redact any key-like strings in error messages

## Code Style

- Use `ruff` for linting and formatting (line-length 100)
- All modules use `from __future__ import annotations`
- Type hints on all functions
- No print() statements — always use Rich Console
- Error messages should be helpful and suggest next steps
- Use `typer.Exit(code=1)` for errors, not `sys.exit()`

## Testing

- `pytest tests/ -v` to run all tests
- Mock all LLM calls with `unittest.mock.patch`
- Test fixtures in `tests/fixtures/` and `tests/conftest.py`
- Use `typer.testing.CliRunner` for CLI command tests

## Running

```bash
pip install -e ".[dev]"    # Install in dev mode
pytest tests/ -v           # Run tests
ruff check src/ tests/     # Lint
ruff format src/ tests/    # Format
agentmodelctl --help       # CLI help
```
