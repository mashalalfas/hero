# HERO — CLI Multi-Agent Orchestration System

> **Spec Version:** 2.1.0  
> **Date:** 2026-05-26  
> **Status:** IMPLEMENTED — Phase 5 (Reliability, Pipeline, QA, Git, DX) complete + Prompt Templates

---

## ASSUMPTIONS I'M MAKING

1. Python CLI (not Go/Rust) — leverage existing venv, faster to prototype
2. TOON as native format for all internal state files — JSON on disk for humans, TOON for LLM injection
3. Graphify for code knowledge (HERO navigates project code via graphify)
4. Hermes `delegate_task` as the soldier spawning mechanism — HERO wraps it
5. Sandboxes are project directories under `~/Development/` — auto-discovered via `hero scan`
6. No database — sandboxes/state stored as `.toon` files in `~/.hero/`
7. User is the only operator — no multi-user auth needed

→ **Correct any of these and I'll update the spec.**

---

## Objective

HERO is a CLI orchestration tool that manages a team of AI agents (soldiers) working in parallel sandboxes (project directories). It uses TOON format for token-efficient state injection and Graphify for code-aware navigation.

**Who uses it:** A single developer (you) managing multiple agent workstreams across 21+ projects in `~/Development/`.

**What it does:**
- `hero scan` — Auto-discover projects in `~/Development/` → create sandbox entries
- `hero spawn` — Launch soldier agents with TOON state injection and graphify context
- `hero status` — Show all sandbox states in compact TOON
- `hero deploy` — Deploy soldier armies to target sandboxes with role-based delegation
- `hero go` — Full pipeline: navigate → pre-commit → build → harden → legal → cipr → verify → archive → report
  - `--mode quick` — navigate + pre-commit + build + verify (fast dev loop)
  - `--mode ci` — pre-commit + build + cipr + verify (CI simulation)
  - `--mode audit` — harden + legal only (security/legal review)
  - `--mode full` — all 8 stages (production deploy)
  - `--stage X` — run exactly one stage (e.g. `--stage harden`)
  - `--from X --to Y` — run a stage range (e.g. `--from navigate --to build`)
- `hero pipeline run` — Execute existing pipeline manifest or create new one with same flags as above
- `hero budget` — Query, summarize, alert, and history-track sandbox token budgets
- `hero dlq` — Dead letter queue management (list, retry, clear)
- `hero check` — 6-point health diagnostic for any sandbox
- `hero viewport` — Live TUI dashboard with army-level and per-sandbox metrics
- `hero graph dependencies` — Cross-project dependency graph parsing

**What success looks like:**
- One `hero spawn --sandbox sook-pro --task "fix theme switcher lag"` spins up a focused soldier with full context
- Soldiers consume ~40% fewer tokens via TOON state injection vs JSON
- Parallel spawning works: `hero deploy --targets sook-pro,freya,hoppy-backend` dispatches to 3 sandboxes simultaneously
- `hero go --sandbox X --task Y --auto` runs a full pipeline from navigation to archive automatically
- Graphify integration: soldiers can query "how does X relate to Y" without manual codebase scanning, and archivist rebuilds NAVIGATION_TREE.md post-mission
- PipelineExecutor drives pipeline state with integrated QA Gate, Git workflow, and context dedup
- Circuit breaker automatically quarantines sandboxes after 3 consecutive failures
- Dead Letter Queue preserves failed tasks for manual retry or recovery

---

## Tech Stack

- **Language:** Python 3.11 (active venv at `~/.hermes/hermes-agent/venv/`)
- **CLI Framework:** Click (lighter than typer, better shell autocomplete)
- **State Format:** TOON (via `npx @toon-format/cli` for conversion, Python parser for reading)
- **Code Navigation:** Graphify (existing at `~/Development/Taurus/sook_pro/lib/graphify-out/`)
- **Agent Delegation:** Hermes `delegate_task` (wraps AIAgent.spawn_subagent / hermes subagent)
- **Config:** YAML for HERO config (`~/.hero/config.yaml`), TOON for state

**Key Dependencies:**
```
click>=8.1.0
pyyaml>=6.0
graphify (existing installation)
@toon-format/cli (npm, already installed)
hermes (existing installation, via subprocess)
```

---

## Commands

```bash
# Build & Install
pip install -e ~/.hero/  # Install HERO as a CLI tool

# Development
cd ~/Development/HERO
python -m hero --help

# Core Commands
hero scan                              # Discover projects in ~/Development/, create INDEX.toon
hero status                            # Show all sandboxes as TOON table
hero spawn --sandbox <name> --task "..."  # Launch soldier agent

# Pipeline Commands
hero go --sandbox <name> --task "..."                   # Full pipeline: 8 stages
hero go --sandbox <name> --task "..." --mode quick          # Quick: navigate + pre-commit + build + verify
hero go --sandbox <name> --task "..." --mode ci             # CI: pre-commit + build + cipr + verify
hero go --sandbox <name> --task "..." --mode audit          # Audit: harden + legal only
hero go --sandbox <name> --task "..." --stage navigate       # Single stage
hero go --sandbox <name> --task "..." --from build --to cipr  # Stage range
hero go --sandbox <name> --task "..." --auto                # Auto-execute via PipelineExecutor
hero pipeline run <id>                 # Execute a pipeline manifest
hero pipeline status <id>              # Show pipeline state
hero pipeline list                     # List all pipeline manifests
hero pipeline rollback <id>            # Rollback git changes from a pipeline

# Advanced Commands
hero deploy --targets <s1>,<s2>        # Deploy to multiple sandboxes in parallel
hero graph query <query> [--sandbox X] # Query graphify for code knowledge
hero graph dependencies [--sandbox X]  # Show cross-project dependency graph

# Budget & Heartbeat Management
hero katana --sandbox <name>           # Compact budget, manage pending/known_issues
hero heartbeat --sandbox <name>        # Show/update heartbeat checkpoint state

# Budget Commands
hero budget [--query "..."]           # Query/filter budgets
hero budget summary                    # Table of all budgets with color-coded utilization
hero budget top --limit 10             # Top N token consumers
hero budget alert --threshold 2000     # Sandboxes below threshold
hero budget history --sandbox X        # Recent budget events

# Reliability Commands
hero dlq list                          # List dead letter queue
hero dlq retry <id>                    # Re-enqueue a failed task
hero dlq clear --older-than 7          # Clear old dead letters

# Utility Commands
hero check --sandbox X                 # 6-point health check
hero viewport [--once] [--sandbox X]   # Live TUI dashboard

# Eval & Planning
hero tell --sandbox X --message M      # Direct message to a sandbox soldier
hero eval --sandbox X [--phase N]      # Run eval phases on a sandbox
hero dispatch list                     # Show all dispatched tasks
hero orchestrate --sandbox X --goal G  # Plan and generate subtasks
hero assemble --sandbox X --goal G     # Assemble and deploy a full plan

# Run tests
python -m pytest tests/ -v

# Lint
python -m ruff check .

# Format
python -m ruff format .
```

---

## Project Structure

```
~/Development/HERO/
├── SPEC.md                        # This file
├── README.md                      # User-facing docs
├── pyproject.toml                 # Package config
├── src/
│   └── hero/
│       ├── __init__.py            # __version__
│       ├── cli.py                 # Click CLI entry point (main command group)
│       ├── commands/
│       │   ├── __init__.py
│       │   ├── scan.py            # hero scan — discover + index projects
│       │   ├── spawn.py           # hero spawn — launch soldier agent
│       │   ├── status.py          # hero status — show sandbox states
│       │   ├── deploy.py          # hero deploy — parallel multi-sandbox dispatch
│       │   ├── graph.py           # hero graph — graphify queries + deps
│       │   ├── katana.py          # hero katana — budget compaction/state
│       │   ├── heartbeat.py       # hero heartbeat — KATANA checkpoint
│       │   ├── budget.py          # hero budget — summary/top/alert/history
│       │   ├── tell.py            # hero tell — direct message soldier
│       │   ├── eval.py            # hero eval — run eval phases
│       │   ├── dispatch.py        # hero dispatch — task queue management
│       │   ├── orchestrate.py     # hero orchestrate — plan subtasks
│       │   ├── assemble.py        # hero assemble — deploy full plan
│       │   ├── go.py              # hero go — full pipeline command
│       │   ├── pipeline.py        # hero pipeline — run/status/list/rollback
│       │   ├── viewport.py        # hero viewport — live TUI dashboard
│       │   ├── dlq.py             # hero dlq — dead letter queue management
│       │   ├── check.py           # hero check — 6-point health diagnostic
│       │   └── viewport_audit.py  # Viewport audit decorators
│       ├── state/
│       │   ├── __init__.py
│       │   ├── toon.py            # TOON read/write utilities
│       │   ├── index.py           # INDEX.toon management
│       │   ├── sandbox.py         # Per-sandbox state files
│       │   ├── budget.py          # Budget tracking (Katana-style)
│       │   ├── budget_history.py  # Budget event JSONL history
│       │   └── cache.py           # State caching helpers
│       ├── soldier/
│       │   ├── __init__.py
│       │   ├── spawner.py         # Wraps Hermes delegate_task
│       │   ├── context.py         # TOON context blocks + ContextCache
│       │   ├── dispatch.py        # TOON dispatch queue management
│       │   └── heartbeat.py       # KATANA checkpoint + heartbeat tracking
│       ├── graphify/
│       │   ├── __init__.py
│       │   ├── client.py          # Wrapper around graphify CLI
│       │   └── query.py           # Query building + parsing
│       ├── graph/
│       │   ├── __init__.py
│       │   └── dependencies.py    # Cross-project dependency graph parser
│       ├── pipeline/
│       │   ├── __init__.py
│       │   └── executor.py        # PipelineExecutor — polls, verifies, archives
│       ├── qa/
│       │   ├── __init__.py
│       │   └── gate.py            # QA Gate — file-scope + diff-size checks
│       ├── reliability/
│       │   ├── __init__.py
│       │   ├── circuit_breaker.py # Circuit breaker (3 fails → quarantine)
│       │   └── dlq.py             # Dead letter queue I/O
│       ├── git/
│       │   ├── __init__.py
│       │   └── branch.py          # Git branch/commit/rollback
│       ├── logging/
│       │   ├── __init__.py
│       │   └── handler.py         # Structured JSONL logging with rotation
│       ├── eval/
│       │   ├── __init__.py
│       │   └── engine.py          # Eval engine (9 phases)
│       ├── viewport/
│       │   ├── __init__.py
│       │   ├── renderer.py        # Rich TUI renderer
│       │   └── metrics.py         # Dashboard metric collection
│       └── analysis_cache.py      # Cached project analysis results
├── tests/
│   ├── __init__.py
│   ├── test_cli.py
│   ├── test_toon.py
│   ├── test_spawn.py
│   ├── test_state.py
│   └── test_graphify.py
├── scripts/
│   └── install-hero.sh            # Install script
└── .hero/                         # Runtime state (created at runtime)
    └── sandboxes/
        ├── INDEX.toon             # Master sandbox registry
        ├── {sandbox}/
        │   ├── BUDGET.toon        # Per-sandbox budget tracking
        │   ├── KATANA.toon        # Katana state (pending, known_issues)
        │   └── HEARTBEAT.toon     # Heartbeat tracking state
```

---

## Code Style

**Python formatting:** Ruff, line length 100, trailing commas.

**Example — TOON state file writer:**
```python
def write_toon(path: Path, data: dict) -> None:
    """Write dict as TOON to path, with trailing comma style."""
    lines = ["{"]
    for key, val in data.items():
        if isinstance(val, list):
            lines.append(f"  {key}[{len(val)}]: {', '.join(str(v) for v in val)}")
        elif isinstance(val, dict):
            lines.append(f"  {key}{{...}}")  # truncated for brevity
        else:
            lines.append(f"  {key}: {val}")
    lines.append("}")
    path.write_text("\n".join(lines) + "\n")
```

**Example — Click command:**
```python
@click.command()
@click.option("--sandbox", required=True, help="Sandbox name")
@click.option("--task", required=True, help="Task description")
def spawn(sandbox: str, task: str):
    """Launch a soldier agent in a sandbox."""
    sandbox_path = resolve_sandbox(sandbox)
    if not sandbox_path.exists():
        raise click.ClickException(f"Sandbox '{sandbox}' not found.")
    soldier = SoldierSpawner(sandbox_path)
    soldier.launch(task=task, budget=BudgetConfig.default())
```

**Example — TOON context block for agent injection:**
```python
def build_context(sandbox: Sandbox, task: str) -> str:
    """Build TOON context block for soldier agent."""
    return f"""sandbox: {sandbox.name}
budget{{bootstrap_max,compactions_used,tokens_remaining}}: {sandbox.budget.bootstrap_max},{sandbox.budget.compactions_used},{sandbox.budget.tokens_remaining}
task: {task}
katana:
  pending[{len(sandbox.katana.pending)}]: {', '.join(sandbox.katana.pending)}
  known_issues[{len(sandbox.katana.known_issues)}]: {', '.join(sandbox.katana.known_issues)}
"""
```

---

## Testing Strategy

**Framework:** pytest

**Test locations:**
- `tests/test_cli.py` — CLI argument parsing, command routing, error handling
- `tests/test_toon.py` — TOON read/write round-trip (JSON → TOON → parse)
- `tests/test_state.py` — INDEX and sandbox state file CRUD
- `tests/test_spawn.py` — SoldierSpawner unit (mock Hermes delegate)
- `tests/test_graphify.py` — Graphify query builder and response parsing
- `tests/test_pipeline.py` — PipelineExecutor core logic
- `tests/test_qa_gate.py` — QA Gate file-scope and diff-size checks
- `tests/test_git_workflow.py` — Git branch/commit/rollback logic
- `tests/test_circuit_breaker.py` — Circuit breaker state management
- `tests/test_dlq.py` — Dead letter queue I/O operations
- `tests/test_budget.py` — Budget queries, summary, history
- `tests/test_logging.py` — JSONL logging format and rotation
- `tests/test_context.py` — ContextCache dedup
- `tests/test_dependencies.py` — Dependency graph parsing
- `tests/test_viewport.py` — Viewport renderer and metrics
- `tests/test_check.py` — Health check diagnostics

**Coverage expectations:**
- CLI commands: 100% coverage
- State management: 90%+
- TOON utilities: 95%+
- Soldier spawning: 80%+ (mock external dependencies)
- Pipeline executor: 80%+
- QA Gate: 90%+
- Reliability modules: 85%+

**Test levels:**
- Unit: pure functions, state file operations
- Integration: CLI commands with temporary state dirs
- Mock: Hermes delegate_task (don't actually spawn agents in tests)

---

## Boundaries

### Always Do
- Run `pytest tests/ -q` before any commit
- Format with `ruff format .` before commit
- Store internal state as `.toon` files (not `.json`)
- Use Graphify for code navigation queries
- Inject TOON context blocks to soldiers (not JSON)
- Keep budget tracking on every spawn/spawn-complete cycle
- Check circuit breaker before spawning soldiers in `hero deploy` and `hero go`
- Run QA Gate after each pipeline soldier completes (unless `--no-qa`)
- Append budget history events on every spawn/complete
- Create git feature branch in PipelineExecutor before spawning
- Log every CLI command and soldier event to structured JSONL
- Dispatch queue: prefer `.toon` storage over `.json` (token savings)

### Ask First
- Adding new CLI commands (may affect UX design)
- Changing TOON schema (affects all state files)
- Adding dependencies beyond click/pyyaml
- Modifying `~/.hero/config.yaml` structure
- Changing sandbox discovery path (`~/Development/` default)
- Changing QA Gate threshold or enforcing semantic check by default
- Modifying circuit breaker threshold from 3-failure default

### Never Do
- Commit secrets or API keys to repo
- Use JSON for internal state (TOON only)
- Spawn soldiers without budget tracking
- Bypass graphify for manual codebase scanning
- Modify other projects' files directly (HERO only manages its own state)
- Auto-commit without running QA Gate first
- Spawn soldiers on a quarantined sandbox

---

## Success Criteria

### Phase 0-3 (Core)
- [x] `hero scan` discovers all projects in `~/Development/` and creates `~/.hero/sandboxes/INDEX.toon`
- [x] `hero spawn --sandbox sook-pro --task "fix lag"` creates a soldier context with TOON state
- [x] `hero status` shows all sandboxes as compact TOON output
- [x] `hero deploy --targets sook-pro,her,freya` spawns soldiers in parallel to all three
- [x] TOON state files are 50%+ smaller than equivalent JSON
- [x] Budget is tracked: spawn decrements, completion increments, compaction resets
- [x] `hero graph "flutter debugging" sook-pro` queries graphify and returns results
- [x] All tests pass: `pytest tests/ -q`
- [x] HERO installs as a CLI tool: `hero --version` works

### Phase 5 — Reliability
- [x] Structured JSONL logging writes every CLI command and soldier event to `~/.hero/logs/hero.jsonl`
- [x] Log rotation at 10MB, keeping last 3 rotated files
- [x] Dead Letter Queue captures failed dispatch tasks to `~/.hero/dead_letter/`
- [x] `hero dlq list`, `hero dlq retry`, `hero dlq clear` commands work
- [x] Circuit breaker quarantines sandboxes after 3 consecutive failures
- [x] Quarantine auto-resets after 10-minute cooldown (or manual `hero sandbox unquarantine`)
- [x] Model fallback retries with alternate model on model-specific errors

### Phase 5 — PipelineExecutor
- [x] `PipelineExecutor` reads pipeline manifest and polls dispatch queue
- [x] `hero pipeline run <id>` executes a pipeline with live progress
- [x] `hero pipeline status <id>` shows current pipeline state
- [x] `hero pipeline list` shows all pipeline manifests
- [x] `hero pipeline rollback <id>` reverts git branch to original
- [x] `hero go --auto` invokes PipelineExecutor inline

### Phase 5 — QA Gate & Git
- [x] File-scope check: every changed file must be in the allowed list
- [x] Diff-size check: no single file exceeds 200 lines changed
- [x] QA Gate runs after each soldier in pipeline; `--no-qa` flag to skip
- [x] Pipeline creates feature branch `hero/<pipeline_id>` before spawning
- [x] Auto-commit on success with `[hero]`-prefixed message
- [x] Rollback command switches back to original branch, deletes feature branch

### Phase 5 — Token Efficiency & DX
- [x] Dynamic budget allocation (1k/5k/20k based on complexity 1-10)
- [x] Dispatch queue uses `.toon` format (~37% token savings vs JSON)
- [x] ContextCache deduplicates project context across pipeline soldiers
- [x] `hero budget summary`, `hero budget top`, `hero budget alert`, `hero budget history`
- [x] `hero check --sandbox X` 6-point health diagnostic
- [x] `hero viewport` live TUI dashboard with keyboard shortcuts
- [x] `hero graph dependencies` cross-project dependency graph

---

---

## PipelineExecutor

> Implements automatic pipeline execution: reads a manifest, polls the dispatch queue,
> verifies output, archives results, and manages the full lifecycle.

### Design

`PipelineExecutor` (in `src/hero/pipeline/executor.py`) is an in-process library — no subprocess
overhead. Pipeline runs are synchronous CLI commands. The executor:

1. Reads all dispatched `task_ids` from the manifest
2. Polls `~/.hero/dispatch/<task_id>.json` at a configurable interval (default 5s)
3. Tracks per-soldier status: pending → dispatched → running → completed/failed
4. Once all soldiers complete → auto-enqueues verify task
5. Once verify completes → auto-enqueues archive task
6. Updates manifest status at each stage
7. Returns `PipelineResult` with all outcomes

### Pipeline Manifest

Pipelines are created by `hero go` and stored as JSON at `~/.hero/pipeline/<pipeline_id>.json`.
Each manifest contains:

```json
{
  "pipeline_id": "abc123",
  "sandbox": "sook-pro",
  "task": "fix theme switcher lag",
  "created_at": "2026-05-24T20:30:00",
  "status": "running",
  "original_branch": "main",
  "feature_branch": "hero/abc123",
  "soldiers": [{"task_id": "...", "label": "...", "status": "completed"}, ...],
  "verify_status": "completed",
  "archive_status": "completed"
}
```

### Commands

- `hero pipeline run <id>` — Execute with live Rich progress output
- `hero pipeline status <id>` — Show current state from manifest
- `hero pipeline list` — List all manifests sorted by creation time (newest first)
- `hero pipeline rollback <id>` — Revert git changes, delete feature branch
- `hero go --sandbox X --task Y --auto` — Create manifest + auto-execute inline

### Dependencies

- Structured logging (5a.1) for pipeline lifecycle events
- Circuit breaker (5a.3) — prevents spawning on quarantined sandboxes
- Git workflow (5d) — branch management per pipeline
- QA Gate (5c) — output verification per soldier
- Context dedup (5e.3) — shared context cache across pipeline soldiers

---

## QA Gate

> Quality verification of soldier output before merging. Prevents garbage-in-garbage-out
> by checking file scope and diff size of every soldier's changes.

### Design

`QAGate` (in `src/hero/qa/gate.py`) runs after each soldier completes in a pipeline.
It performs two checks:

1. **File-Scope Check** — Runs `git diff --name-only` and verifies that every changed
   file is within the soldier's assigned file list. If a soldier was assigned
   `src/components/Foo.tsx` and it modified `src/utils/bar.ts`, it's flagged as a
   scope violation.

2. **Diff-Size Check** — Runs `git diff --stat` and checks that no single file exceeds
   200 lines changed (configurable via `~/.hero/config.yaml` `qa.max_diff_lines`).

### Check Results

```python
@dataclass
class QAResult:
    passed: bool
    violations: list[str]
```

If any check fails, the task is marked `qa_failed` in the dispatch queue and moved
 to the Dead Letter Queue. If all pass, the pipeline proceeds normally.

### Usage

- Integrated into `PipelineExecutor` — runs automatically per soldier
- Skip with `hero pipeline run --no-qa` or `hero go --no-qa`
- Configure threshold via `~/.hero/config.yaml`:
  ```yaml
  qa:
    max_diff_lines: 200
    semantic: false   # opt-in semantic check (not yet implemented)
  ```

---

## Git Workflow

> Safety net for all soldier work. Every pipeline gets its own feature branch,
> auto-commits on success, and provides rollback on failure.

### Design

Managed by `src/hero/git/branch.py` with three operations:

1. **Auto-Branch** — Before spawning soldiers, `PipelineExecutor` verifies the working
   tree is clean, then creates a feature branch `hero/<pipeline_id>` from current HEAD.
   All soldier work happens on this branch.

2. **Auto-Commit** — After all soldiers + verify pass, runs `git add -A` and commits
   with a `[hero]`-prefixed message:
   ```
   [hero] sook-pro: fix theme switcher lag
   ```
   Commits only sandbox-scoped files (for monorepos, `git add <sandbox_path>/`).

3. **Rollback** — `hero pipeline rollback <pipeline_id>`:
   - Switches back to the original branch (stored in pipeline manifest)
   - Deletes the feature branch
   - Resets any uncommitted changes

### Error States

| State | Behaviour |
|-------|-----------|
| Working tree dirty | Pipeline refuses to start — user must commit/stash first |
| Verify fails | Don't commit — leave dirty state for manual inspection |
| Pipeline run cancelled | Use `hero pipeline rollback` to clean up |
| Auto-commit fails | Error logged, state left dirty for manual fix |

---

## Phase Plan

### Phase 0: Foundation (completed)
- [x] Project scaffold: pyproject.toml, src/hero/, CLI entry point
- [x] TOON utilities: read, write, convert from JSON
- [x] State management: INDEX.toon CRUD
- [x] `hero --version` and `hero --help`

### Phase 1: Core Commands (completed)
- [x] `hero scan` — discover + index
- [x] `hero status` — show all sandboxes in TOON
- [x] `hero spawn` — single soldier launch

### Phase 2: Advanced Commands (completed)
- [x] `hero deploy` — parallel multi-sandbox
- [x] `hero graph` — graphify integration
- [x] Budget tracking (spawn/complete/compact cycle)

### Phase 3: Polish (completed)
- [x] Install script (`scripts/install-hero.sh`)
- [x] README.md documentation
- [x] Full test suite

### Phase 5: Reliability, Pipeline, QA, Git & DX (completed)

#### Wave 1 — Foundation
- [x] 5a.1 Structured JSONL logging with 10MB rotation (keep last 3)
- [x] 5e.1 Dynamic budget allocation (1k/5k/20k based on complexity 1-10)
- [x] 5e.2 Dispatch queue TOON format (~37% token savings)
- [x] 5f.1 Budget summary, top, alert subcommands
- [x] 5f.2 Budget history JSONL append on every spawn/complete

#### Wave 2 — Reliability
- [x] 5a.2 Dead Letter Queue (`~/.hero/dead_letter/`) with dlq list/retry/clear
- [x] 5a.3 Circuit breaker (3 fails → quarantine, 10min cooldown)
- [x] 5a.4 Model fallback auto-retry with alternate model

#### Wave 3 — PipelineExecutor
- [x] 5b.1 PipelineExecutor core (read manifest, poll queue, track state)
- [x] 5b.2 `hero pipeline` command group (run/status/list/rollback)
- [x] 5b.3 `hero go --auto` integration (`PipelineExecutor` inline)

#### Wave 4 — QA & Git
- [x] 5c.1 File-scope check (changed files must be in allowed list)
- [x] 5c.2 Diff-size check (no file exceeds 200 lines changed)
- [x] 5c.4 QA Gate integration into PipelineExecutor (`--no-qa` flag)
- [x] 5d.1 Auto-branch (`hero/<pipeline_id>`) on pipeline start
- [x] 5d.2 Auto-commit on success with `[hero]`-prefixed message
- [x] 5d.3 Rollback command (switch + delete branch)
- [x] 5e.3 ContextCache dedup across pipeline soldiers

#### Wave 6 — DX & Architecture
- [x] 5g.2 `hero check --sandbox X` 6-point health diagnostic
- [x] 5g.3 `hero viewport` live Rich TUI dashboard
- [x] 5h.2 Dependency graph (`hero graph dependencies`)

### Phase 4: Future Work
- [ ] TOON schema auto-migration for state file versioning
- [ ] Semantic sanity check in QA Gate (optional LLM-based diff review)
- [ ] `hero plan --interactive` — approve/edit subtasks before queuing
- [ ] `hero watch --sandbox X` — focused single-sandbox TUI dashboard
- [ ] TOON-ify remaining JSON files (analysis cache, eval scorecards)
- [ ] Task complexity estimator in `src/hero/analysis/complexity.py`
- [ ] `hero deploy --cascade` — deploy to sandbox + dependents
- [ ] Token usage trends and cost projections from budget history

---

## Open Questions

1. **Storage backend:** TOON files on disk is simple but do you want a lightweight SQLite layer for querying across sandboxes (e.g., "find all sandboxes with budget < 2000")? **Partly addressed** by `hero budget summary` and `hero budget alert` — these aggregate from all BUDGET.toon files in-memory. For larger-scale queries, SQLite may still be worth it.
2. **Delegation depth:** Should HERO support soldier → sub-soldier spawning, or flat (soldiers cannot spawn more agents)? **Currently flat.** Soldiers do not spawn sub-agents. PipelineExecutor handles multi-step orchestration at the CLI level.
3. **TOON schema versioning:** When TOON schema evolves, should HERO auto-migrate old state files? **Not yet implemented.** Manual migration on schema changes for now. JSON files used for pipeline manifests (not TOON) due to richer structure.
4. **QA Gate model cost:** Semantic check would cost ~5k tokens per pipeline (~$0.0005 on Step 3.5 Flash). **Opt-in only** via config. File-scope + diff-size checks are free (git-based).
5. **Git auto-commit scope:** **Sandbox-scoped.** For monorepos, `git add <sandbox_path>/` to commit only the sandbox files. Sandbox path stored in pipeline manifest.

---

## Challenges Faced

### Lead Keyword Matching Bug (2026-05-25)

**The Problem:**
`orchestrate.py` used substring matching (`any(w in task_lower for w in [...])`) to detect which Phase rules apply. Phase 3 checked for `"agent config"` — but this substring appeared in both goal text *and* task titles like `"Build Agent Config window"`. Result: Lead always generated 2 tasks — the hallucinated Agent Config task + the correct Godot Phase 1 task.

**Root Cause:**
No distinction between title text and goal text at the keyword level. Any Phase that matched on short substrings was prone to false positives when task descriptions contained similar words.

**Fix Applied:**
- Phase 3 keywords changed from `"agent config"` (substring) → full phrase match: `"agent config window"`, `"build agent config window"`, `"create agent config window"`
- Phase 1 gained explicit keywords for Godot/scaffold tasks: `godot`, `scaffold`, `placeholder`, `autoload`, `collision`, `damage calculator`
- Added explanatory comment in `orchestrate.py` documenting why full phrase matching is required

**Lesson:** Short substring matching in orchestration rules causes false positives. Use full phrase matches for Phase detection, and avoid generic single-word triggers.

**Workaround Used:**
During the fix window, Lead's stale output (containing both agent config + correct task) was handled by manually dispatching the correct task to soldiers. The agent config ghost task sat unused in the dispatch queue.

---

## Step 3.5 — Parallel Soldier Execution

> Per your instruction: after planning but before implementation, parallelize independent work.

**Parallel opportunities:**
- Phase 0 tasks 1-4 can run simultaneously (different files/modules)
- Phase 1 commands can be built in parallel (scan, status, spawn are independent)
- Tests can be written alongside implementation (TDD)
- Phase 5 Wave 1 subtasks (logging, dynamic budget, TOON dispatch, budget commands) execute in parallel

**Pattern:** Use `delegate_task` for Phase 0 tasks 1-4 simultaneously — each subagent owns one module (cli.py, toon.py, state/, soldier/).

**Checkpoint after Phase 0:** All Phase 0 tests pass before proceeding to Phase 1.