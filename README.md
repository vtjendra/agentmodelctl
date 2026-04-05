# agentmodelctl
Control all your agents and setup with the most optimal models
[README.md](https://github.com/user-attachments/files/26488753/README.md)
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
