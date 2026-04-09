# agentmodelctl

**Your agents work today. Will they work after you change the model?**

agentmodelctl is a CLI that defines your AI agents as code, and tells you exactly what breaks before you switch models. Quality, speed, and cost — in one command.

```bash
pip install agentmodelctl
```

---

## The Problem

You have 50 agents in production. A new model drops that's 40% cheaper. Your boss asks: "Can we switch?"

You have no idea what will break.

agentmodelctl gives you the answer in 60 seconds:

```
agentmodelctl switch reasoning gpt-4o --dry-run
```
```
┌──────────────────────────────────────────────────────────┐
│  MODEL SWITCH: reasoning                                 │
│  claude-sonnet-4-6 → gpt-4o                              │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  AFFECTED AGENTS: 2 of 4                                 │
│                                                          │
│  customer-support         4/5 pass        ⚠ RISKY        │
│    ✗ test_escalation — agent tried to resolve            │
│      instead of escalating to human                      │
│    💰 saves $1.20 / 1K calls                             │
│    ⚡ 300ms faster                                        │
│                                                          │
│  email-drafter            5/5 pass        ✅ SAFE         │
│    💰 saves $0.90 / 1K calls                             │
│    ⚡ 250ms faster                                        │
│                                                          │
│  VERDICT: 1 safe to switch, 1 needs work                 │
│  POTENTIAL SAVINGS: $2.10 / 1K calls                     │
└──────────────────────────────────────────────────────────┘
```

## Quick Start (3 minutes)

```bash
# 1. Install
pip install agentmodelctl

# 2. Initialize a project
agentmodelctl init --template customer-support

# 3. Add your API keys
cp .env.example .env
# Edit .env with your keys

# 4. Auto-generate evals (no manual work needed)
agentmodelctl eval --auto-generate

# 5. See what breaks before switching models
agentmodelctl switch reasoning gpt-4o --dry-run
```

## How It Works

### 1. Define agents as YAML

```yaml
# agents/customer-support.yaml
name: customer-support
model: reasoning          # alias, not a model string
system_prompt: |
  You are a support agent for Acme Corp.
  If the issue requires billing access, escalate to a human.
tools:
  - name: lookup_order
  - name: escalate
```

### 2. Define model aliases (change once, update everywhere)

```yaml
# models.yaml
aliases:
  reasoning:
    provider: anthropic
    model: claude-sonnet-4-6
    fallback: gpt-4o
  fast:
    provider: openai
    model: gpt-4o-mini
  cheap:
    provider: anthropic
    model: claude-haiku-4-5
```

### 3. Don't have evals? We'll generate them.

```bash
agentmodelctl eval --auto-generate
```

agentmodelctl sends realistic test inputs to your agent, captures the current outputs as baselines, and creates eval files automatically. No manual work.

### 4. Switch models safely

```bash
agentmodelctl switch reasoning gpt-4o --dry-run
```

Runs all evals for affected agents on the new model. Shows quality, speed, and cost impact. You decide.

## Commands

| Command | What it does |
|---------|-------------|
| `agentmodelctl init` | Scaffold a project with templates |
| `agentmodelctl list` | Fleet overview — agents, models, eval status |
| `agentmodelctl validate` | Check all configs are valid |
| `agentmodelctl eval [agent]` | Run evals (quality + speed + cost) |
| `agentmodelctl eval --auto-generate` | Generate evals from agent behavior |
| `agentmodelctl switch <alias> <model> --dry-run` | Preview model migration impact |
| `agentmodelctl compare <agent> --models A B C` | Side-by-side model comparison |
| `agentmodelctl report` | Fleet health report |
| `agentmodelctl ci` | CI-optimized evals with change detection and caching |
| `agentmodelctl status` | Fleet production status from tracking logs |

## CI/CD Integration (v0.2)

Catch regressions in every PR. The `ci` command detects which agents are affected by your changes, runs only those evals, and outputs structured results for PR comments.

```bash
# Run in your pipeline — exits 1 if any eval fails
agentmodelctl ci --ref origin/main
```

**What it does automatically:**
- **Change detection** — only re-evaluates agents affected by the PR (touches to `models.yaml`, `agents/`, or `evals/`)
- **Eval caching** — skips unchanged agent+model+eval combos via SHA-256 fingerprinting
- **Structured output** — `--format markdown` (default) for PR comments, `--format json` for programmatic use

### GitHub Actions

`agentmodelctl init` generates a ready-to-use workflow at `.github/workflows/agent-eval.yaml`:

```yaml
# Runs automatically on PRs that touch agent configs
name: Agent Eval CI
on:
  pull_request:
    paths: ['agents/**', 'evals/**', 'models.yaml', 'agentmodelctl.yaml']
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install agentmodelctl
      - run: agentmodelctl ci --ref origin/${{ github.base_ref }} --format markdown > eval-results.md
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      - uses: marocchino/sticky-pull-request-comment@v2
        with: { path: eval-results.md }
```

### PR Comment Output

The CI report posts a summary table directly on your PR:

```
## agentmodelctl CI Report

| Agent | Result | Pass Rate | Avg Quality | Total Cost | Details |
|-------|--------|-----------|-------------|------------|---------|
| customer-support | WARN | 4/5 | 0.92 | $0.0150 | 1 test(s) failed |
| email-drafter | PASS | 5/5 | 0.97 | $0.0120 | — |
```

### Output Formats

All eval commands support `--format`:

```bash
agentmodelctl eval --format json        # JSON for programmatic consumption
agentmodelctl eval --format markdown    # Markdown tables
agentmodelctl eval --cache              # Skip unchanged evals
```

## Production Awareness (v0.3)

Know what your agents are doing in production — invocation volume, latency, error rates, cost — and use real data to make smarter model-switching decisions.

### Track Production Invocations

Add one line to your agent code:

```python
from agentmodelctl import track

track.log(
    agent_name="customer-support",
    model="claude-sonnet-4-6",
    latency_seconds=1.2,
    input_tokens=100,
    output_tokens=50,
    cost_usd=0.003,
)
```

Logs are stored as JSONL in `.agentmodelctl/logs/` — no server, no external dependencies.

### Fleet Status

```bash
agentmodelctl status
```
```
┌────────────────────────────────────────────────────────────────────────┐
│ Agent        │ Invocations │ Error Rate │  p50  │  p95  │ Avg Cost   │
├──────────────┼─────────────┼────────────┼───────┼───────┼────────────┤
│ support      │      12,340 │      1.2%  │ 0.45s │ 1.20s │ $0.0030    │
│ email-drafter│       8,200 │      0.3%  │ 0.30s │ 0.80s │ $0.0025    │
│ sales        │       3,100 │      8.5%  │ 0.60s │ 2.10s │ $0.0041    │
└────────────────────────────────────────────────────────────────────────┘

┌─────────── ANOMALIES DETECTED ────────────┐
│  ! sales: error rate 8.5% exceeds 5%      │
└────────────────────────────────────────────┘
```

### Smarter Model Switching

`switch --dry-run` now shows production volume and estimated real savings:

```
  customer-support    5/5 pass    ✅ SAFE
    💰 saves $1.20 / 1K calls
    🏭 production: 12,340 calls (1,763/day)
    💰 estimated savings: $74.72/month
```

### Status Options

```bash
agentmodelctl status                    # Fleet overview (last 7 days)
agentmodelctl status support            # Per-agent drill-down
agentmodelctl status --days 30          # Custom time window
agentmodelctl status --format json      # JSON output for dashboards
```

## No Evals? No Problem.

Most teams don't have evals. agentmodelctl has three tiers:

**Zero effort** — auto-generated from your agent's current behavior:
```bash
agentmodelctl eval --auto-generate
```

**Low effort** — just provide inputs, we capture baselines:
```yaml
tests:
  - input: "I want to cancel my subscription"
  - input: "Do you ship to San Fransisco?"
```

**Full control** — define expectations explicitly:
```yaml
tests:
  - input: "I want to cancel my subscription"
    expect_contains: "sorry to see you go"
    expect_tool: transfer_to_retention
```

## Security

- API keys are **never stored** in config files
- Keys are read from environment variables or `.env` files
- `.env` is automatically added to `.gitignore` on init
- The tool warns if it detects keys in any tracked file

## What agentmodelctl Is (and Isn't)

| ✅ It is | ❌ It is not |
|----------|-------------|
| A CLI for managing agent configs | An agent framework |
| A pre-deploy safety net | An observability platform |
| An eval runner (quality + speed + cost) | A prompt management tool |
| A fleet health dashboard | A hosted service |

**Works with any framework** — LangChain, CrewAI, OpenAI Agents SDK, raw API calls, or anything else. agentmodelctl manages the config layer, not the runtime.

**Complements existing tools** — Use Langfuse for tracing, Agenta for prompt versioning, agentmodelctl for model migration safety. They're complementary, not competing.

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT
