# ██████╗ ███████╗ ██████╗ ██████╗ ███╗   ██╗██╗    ██╗ █████╗ ██████╗  ██████╗ 
# ██╔══██╗██╔════╝██╔═══██╗██╔══██╗████╗  ██║██║    ██║██╔══██╗██╔══██╗██╔═══██╗
# ██████╔╝█████╗  ██║   ██║██████╔╝██╔██╗ ██║██║ █╗ ██║███████║██████╔╝██║   ██║
# ██╔══██╗██╔══╝  ██║   ██║██╔══██╗██║╚██╗██║██║███╗██║██╔══██║██╔══██╗██║   ██║
# ██║  ██╝███████╗╚██████╔╝██████╔╝██║ ╚████║╚███╔███╔╝██║  ██║██║  ██║╚██████╔╝
# ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝ ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ 

**HERO** — CLI Multi-Agent Orchestration System

> Manage AI soldier agents across project sandboxes using token-efficient
> TOON state format, Graphify code navigation, and automated pipelines.

---

## Quick Start

```bash
# Install (from repo)
./scripts/install-hero.sh

# Discover projects
hero scan

# Check status  
hero status

# Spawn a soldier
hero spawn --sandbox sook-pro --task "fix theme switcher lag"

# Deploy to multiple targets
hero deploy --targets sook-pro,freya,hoppy-backend --task "update deps"

# Full pipeline (one command)
hero go --sandbox qlearner --task "fix all issues"

# Auto-execute pipeline
hero go --sandbox fury-os --task "Phase 2 polish" --auto
hero go --sandbox fury-os --task "Phase 2 polish" --no-self-review  # Skip self-review

# Live dashboard
hero viewport
```

---

## All Commands

| Command | Description |
|---------|-------------|
| `hero scan` | Discover projects in `~/Development/` → create sandbox entries |
| `hero spawn` | Launch a soldier agent with TOON state injection |
| `hero status` | Show all sandbox states in compact TOON format |
| `hero deploy` | Deploy soldier armies to multiple sandboxes in parallel |
| `hero graph query <query> [--sandbox X]` | Query Graphify for code-aware navigation |
| `hero graph dependencies [--sandbox X]` | Show cross-project dependency graph (imports, pubspec, Cargo) |
| `hero katana` | Manage katana priorities and known issues |
| `hero heartbeat` | Check and report HERO system health |
| `hero budget [--query ...]` | Query/filter sandbox budgets |
| `hero budget summary` | Table of all sandbox budgets with color-coded utilization |
| `hero budget top --limit 10` | Top N token consumers |
| `hero budget alert --threshold 2000` | List sandboxes with remaining tokens below threshold |
| `hero budget history --sandbox X` | Show recent budget events (spawn/complete/compact) |
| `hero tell --sandbox X --message M` | Direct message / instruction to a sandbox's soldier |
| `hero eval --sandbox X [--phase N]` | Run eval phases on a sandbox (up to 9) |
| `hero dispatch list` | Show all dispatched tasks in the queue |
| `hero orchestrate --sandbox X --goal G` | Plan and generate subtasks for a goal |
| `hero assemble --sandbox X --goal G` | Assemble and deploy a full plan to a sandbox |
| `hero go --sandbox X --task Y` | Full pipeline: navigate → pre-commit → build → self_review → harden → legal → cipr → verify → archive |
| `hero go --sandbox X --task Y --mode quick` | Quick mode: navigate + pre-commit + build + self-review + verify |
| `hero go --sandbox X --task Y --mode ci` | CI mode: pre-commit + build + self-review + cipr + verify |
| `hero go --sandbox X --task Y --mode audit` | Audit mode: harden + legal only |
| `hero go --sandbox X --task Y --from navigate --to build` | Stage range: runs navigate through build |
| `hero go --sandbox X --task Y --stage harden` | Single stage: runs exactly one stage |
| `hero go --sandbox X --task Y --auto` | Same but auto-executes via PipelineExecutor |
| `hero pipeline run <id>` | Execute a pipeline manifest |
| `hero pipeline status <id>` | Show current pipeline state from manifest |
| `hero pipeline list` | List all pipeline manifests sorted by creation time |
| `hero pipeline rollback <id>` | Rollback git changes from a pipeline (switch back, delete branch) |
| `hero dlq list` | List dead letter queue (failed tasks) |
| `hero dlq retry <id>` | Re-enqueue a failed task from the dead letter queue |
| `hero dlq clear --older-than 7` | Clear dead letters older than N days |
| `hero check --sandbox X` | 6-point health check (budget, heartbeat, git, build, circuit, dispatch) |
| `hero viewport [--once] [--sandbox X]` | Live Rich-based TUI dashboard with army-level and per-sandbox metrics |

### Examples

```bash
# Scan for projects
hero scan

# Spawn a soldier in a specific sandbox
hero spawn --sandbox sook-pro --task "implement dark mode"

# Show all sandbox statuses
hero status

# Deploy to multiple sandboxes at once
hero deploy --targets sook-pro,freya,her --task "run tests"

# Query code relationships via Graphify
hero graph query "flutter debugging" --sandbox sook-pro

# Show cross-project dependency graph
hero graph dependencies

# Budget overview
hero budget summary
hero budget top --limit 10
hero budget alert --threshold 2000
hero budget history --sandbox sook-pro

# Full pipeline (plan + dispatch manual)
hero go --sandbox qlearner --task "rewrite solver"

# Full pipeline with auto-execution
hero go --sandbox fury-os --task "Phase 2 polish" --auto

# Pipeline lifecycle
hero pipeline list
hero pipeline status abc123
hero pipeline run abc123
hero pipeline rollback abc123

# Dead letter queue management
hero dlq list
hero dlq retry abc123
hero dlq clear --older-than 7

# Health check
hero check --sandbox sook-pro

# Live dashboard
hero viewport
hero viewport --sandbox sook-pro
hero viewport --once
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                              HERO                                    │
│                      (CLI Orchestration Layer)                      │
├──────────┬──────────┬──────────┬──────────┬──────────┬─────────────┤
│  scan    │  spawn   │  status  │  deploy  │  go      │  viewport   │
│  budget  │  tell    │  eval    │ dispatch │ pipeline │   (TUI)     │
│  check   │  dlq     │ graph    │  katana  │ assemble │             │
│          │          │          │ heartbeat│  orchest.│             │
├──────────┴──────────┴──────────┴──────────┴──────────┴─────────────┤
│                         System Modules                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────────┐   │
│  │  State   │  │ Soldier  │  │ Pipeline │  │  Reliability    │   │
│  │ (TOON)   │  │ (Spawn)  │  │(Executor)│  │ (CircuitBreaker)│   │
│  ├──────────┤  ├──────────┤  ├──────────┤  ├─────────────────┤   │
│  │  Git     │  │  QA Gate │  │ Logging  │  │  Graphify/Deps  │   │
│  │(Branch,  │  │(Scope,   │  │(JSONL,   │  │  (Code Nav)     │   │
│  │ Commit,  │  │ Diff,    │  │ Rotation)│  │                 │   │
│  │ Rollback)│  │ Semantic)│  │          │  │                 │   │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
     │         │          │          │           │          │
     ▼         ▼          ▼          ▼           ▼          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          ~/.hero/                                   │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│   │  sandboxes/  │    │  pipeline/   │    │      logging/        │  │
│   │  INDEX.toon  │    │  *.json      │    │   hero.jsonl (rot.)  │  │
│   │  {sandbox}/  │    │  manifests   │    │                      │  │
│   │  BUDGET/     │    │              │    ├──────────────────────┤  │
│   │  HEARTBEAT   │    │  dispatch/   │    │   dead_letter/       │  │
│   │  KATANA      │    │  *.toon      │    │   {task_id}.json     │  │
│   └──────────────┘    └──────────────┘    └──────────────────────┘  │
│   ┌──────────────┐    ┌──────────────┐                              │
│   │  budget_hist │    │dependencies  │                              │
│   │  .jsonl      │    │ .toon        │                              │
│   └──────────────┘    └──────────────┘                              │
└──────────────────────────────────────────────────────────────────────┘
```

**Components:**
- **CLI** — Click-based commands (19 registered command groups)
- **State** — TOON-format files for token-efficient storage; JSON for pipeline manifests
- **Soldier** — Wraps Hermes `delegate_task` for agent spawning with dynamic budget allocation
- **PipelineExecutor** — Drives pipeline state: polls dispatch queue, runs QA gate, commits, archives
- **Git Workflow** — Auto-branch (`hero/<pipeline_id>`), auto-commit, and rollback safety net
- **QA Gate** — File-scope and diff-size checks on soldier output before merge
- **Reliability** — Circuit breaker (3 fails → quarantine), Dead Letter Queue, Model Fallback
- **Logging** — Structured JSONL with 10MB rotation (keep last 3 files)
- **Graphify** — Code navigation via relationship queries; dependency graph via import parsing
- **Context Cache** — Shared dedup cache across pipeline soldiers (avoids re-reading README/PLAN)

---

## System Features

### Structured JSONL Logging
Every CLI command, soldier spawn, completion, and error writes a JSON line to `~/.hero/logs/hero.jsonl`. Log files rotate at 10MB, keeping the last 3 rotated files.

### Dynamic Budget Allocation
Budget is auto-estimated from task complexity (1-10 scale): complexity 1-3 → 1k tokens, 4-6 → 5k, 7-10 → 20k. Override with explicit `--budget` flag.

### TOON Format Dispatch Queue
Dispatch tasks are stored as `.toon` files instead of `.json`, saving ~37% tokens when the queue is injected into LLM context.

### Circuit Breaker
Tracks failures per sandbox. After 3 consecutive failures, the sandbox is quarantined (skipped in `hero deploy` and `hero go`) with a 10-minute auto-cooldown.

### Model Fallback
If the primary model fails (model-specific error), auto-retries with the next model in the role's `models` list. Fallback events are logged.

### QA Gate
Runs file-scope (every changed file must be in the allowed list) and diff-size (no single file exceeds 200 lines changed) checks on soldier output after each pipeline soldier completes.

### Git Workflow
`PipelineExecutor` creates a feature branch (`hero/<pipeline_id>`) before spawning soldiers. On success, auto-commits with `[hero]`-prefixed message. On failure, `hero pipeline rollback <id>` switches back to the original branch and deletes the feature branch.

### Context Dedup
`ContextCache` caches repeated project context across pipeline soldiers, avoiding re-reading the same README, PLAN.md, or config files per soldier.

### Dead Letter Queue
When a soldier task fails, the full dispatch payload + error is saved to `~/.hero/dead_letter/<task_id>.json`. Use `hero dlq list` to inspect, `hero dlq retry` to re-enqueue, and `hero dlq clear` to purge old entries.

### Dependency Graph
Parses `package.json`, `pubspec.yaml`, and `Cargo.toml` across sandboxes to build an inter-project dependency graph stored in `~/.hero/dependencies.toon`.

### External Prompt Templates
All agent prompts (soldier, architect, verify, fix, archive) are external `.md` files loaded at runtime. User templates in `~/.hero/prompts/` override bundled defaults. Templates use `string.Template` syntax (`$variable`). Composable rule blocks (TDD, context budget) can be injected per template. Edit prompts without touching Python code.

---

## TOON Format

HERO uses **TOON** (Token-optimized Object Notation) for all state files. TOON is designed for efficient LLM injection — same information as JSON at a fraction of the token cost.

**Example TOON state:**
```
sandbox: sook-pro
budget{bootstrap_max,compactions_used,tokens_remaining}: 10000,0,9500
katana:
  pending[1]: perf-regression-fix
  known_issues[0]: 
```

vs equivalent JSON:
```json
{
  "sandbox": "sook-pro",
  "budget": {
    "bootstrap_max": 10000,
    "compactions_used": 0,
    "tokens_remaining": 9500
  },
  "katana": {
    "pending": ["perf-regression-fix"],
    "known_issues": []
  }
}
```

---

## Configuration

| Path | Description |
|------|-------------|
| `~/.hero/` | HERO home directory |
| `~/.hero/prompts/` | User prompt template overrides (roles, phases, rules) |
| `~/.hero/sandboxes/` | Sandbox state files (.toon) |
| `~/.hero/sandboxes/INDEX.toon` | Master sandbox registry |
| `~/.hero/dispatch/` | Dispatch queue (.toon tasks) |
| `~/.hero/pipeline/` | Pipeline manifests (.json) |
| `~/.hero/logs/hero.jsonl` | Structured JSONL log (rotated) |
| `~/.hero/dead_letter/` | Failed task archives (.json) |
| `~/.hero/dependencies.toon` | Inter-sandbox dependency graph |
| `~/.hero/budget_history.jsonl` | Budget event history |
| `~/Development/` | Default project discovery path |

---

## Documentation

- [SPEC.md](./SPEC.md) — Full specification and design decisions
- [PLAN.md](./PLAN.md) — Implementation plan and progress

---

## Development

```bash
# Install in development mode
uv pip install -e .

# Run tests
uv run --project . pytest tests/ -v

# Lint
uv run --project . ruff check .

# Format
uv run --project . ruff format .
```

---

**Last updated:** 2026-05-24
