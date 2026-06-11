# Implementation Plan: HERO CLI

**Based on:** SPEC.md (v1.0.0) + Kimi K2.6 External Review  
**Date:** 2025-05-24  
**Status:** Phase 3 Complete — improvement plan below

---

## Architecture Decisions

1. **Click over Typer** — lighter framework, better shell autocomplete, no TypeScript-style type noise in CLI
2. **TOON native, JSON on read** — store TOON on disk, convert to JSON/dict in memory for processing, convert back for writing
3. **State files, not database** — no SQLite; sandboxes are `.toon` files under `~/.hero/`
4. **Graphify as library** — wrap `graphify` CLI subprocess, don't import it as a module
5. **Hermes delegate_task via subprocess** — not a direct Python import; HERO shell-outs to `hermes subagent` for isolation

---

## What Exists (Phase 3 Complete)

| Module | Files | Status |
|--------|-------|--------|
| CLI | `cli.py`, 15 command modules | ✅ Done |
| State | `toon.py`, `sandbox.py`, `budget.py`, `index.py`, `cache.py` | ✅ Done |
| Soldier | `spawner.py`, `dispatch.py`, `heartbeat.py`, `context.py` | ✅ Done |
| Commands | scan, spawn, status, deploy, graph, katana, heartbeat, budget, tell, eval, dispatch, orchestrate, assemble, go, viewport | ✅ Done |
| Viewport | `renderer.py`, `metrics.py` | ✅ Done |
| Eval | `engine.py`, 9 phases | ✅ Done |
| Analysis | `analysis_cache.py` | ✅ Done |

---

## Improvement Plan (Kimi K2.6 Review)

### Priority Order & Dependencies

```
Phase 5a: Reliability Foundation
  ↓
Phase 5b: PipelineExecutor
  ↓
Phase 5c: Soldier Output QA Gate
  ↓
Phase 5d: Git Workflow Integration
  ↓
Phase 5e: Token Efficiency
  ↓
Phase 5f: Cross-Sandbox Budget Queries
  ↓
Phase 5g: Developer Experience
  ↓
Phase 5h: Architecture Refinements
```

---

### Phase 5a: Reliability & Observability Foundation
**Priority: CRITICAL — blocks PipelineExecutor**

Everything else depends on reliable infrastructure. Build this first.

#### Subtask 5a.1: Structured JSONL Logging
- **Files:** Create `src/hero/logging/__init__.py`, `src/hero/logging/handler.py`
- **What:** Replace ad-hoc `click.echo` with structured JSONL logging. Every CLI command, soldier spawn, completion, and error writes a JSON line to `~/.hero/logs/hero.jsonl`. Each line: `{"ts": "...", "level": "INFO", "cmd": "spawn", "sandbox": "sook-pro", "task_id": "abc123", "detail": "..."}`.
- **Complexity:** Small
- **Dependencies:** None

#### Subtask 5a.2: Dead Letter Queue
- **Files:** Create `src/hero/reliability/dlq.py`
- **What:** `~/.hero/dead_letter/` directory. When a soldier fails (dispatch task status="failed"), write the full dispatch JSON + error to `dead_letter/<task_id>.json`. Add `hero dlq list` and `hero dlq retry <task_id>` commands. `dlq retry` re-enqueues the original task via `enqueue()`.
- **Complexity:** Small
- **Dependencies:** 5a.1 (log DLQ events)

#### Subtask 5a.3: Circuit Breaker
- **Files:** Create `src/hero/reliability/circuit_breaker.py`, modify `src/hero/soldier/spawner.py`
- **What:** Track failures per sandbox. After 3 consecutive failures on the same sandbox, quarantine it (set status="quarantined" in HEARTBEAT.toon, skip it in `hero deploy` and `hero go`). Auto-reset after 10 minutes or manual `hero sandbox unquarantine <name>`. Integrate into `SoldierSpawner.launch()` — check quarantine before spawning.
- **Complexity:** Medium
- **Dependencies:** 5a.1 (log circuit breaker events)

#### Subtask 5a.4: Model Fallback in Spawner
- **Files:** Modify `src/hero/soldier/spawner.py`
- **What:** In `SoldierSpawner.launch()`, if primary model fails (dispatch task fails with model-specific error), auto-retry with the next model in the role's `models` list. Add `model_fallbacks: ["deepseek-v4-flash"]` field to army.yaml roles. Log fallback events.
- **Complexity:** Medium
- **Dependencies:** 5a.1, 5a.3 (circuit breaker should track model-specific failures)

---

### Phase 5b: PipelineExecutor
**Priority: CRITICAL — automates the manual orchestration gap**

The `hero go` command currently generates a pipeline manifest and tells the Communicator to execute it manually. PipelineExecutor automates steps 3-5: spawn → poll → verify → archive.

#### Subtask 5b.1: PipelineExecutor Core
- **Files:** Create `src/hero/pipeline/executor.py`, `src/hero/pipeline/__init__.py`
- **What:** `PipelineExecutor` class that reads a pipeline manifest from `~/.hero/pipeline/<id>.json` and:
  1. Reads all dispatched task_ids from manifest
  2. Polls `~/.hero/dispatch/<task_id>.json` for status changes (completed/failed) with configurable interval (default 5s)
  3. Tracks which tasks are done, which are still running
  4. Once all soldiers complete → auto-enqueues verify task (reuses `go.py` logic)
  5. Once verify completes → auto-enqueues archive task
  6. Updates manifest status at each stage
  7. Returns final PipelineResult with all outcomes
- **Complexity:** Large
- **Dependencies:** 5a.1 (structured logging), 5a.3 (circuit breaker checks before spawn)

#### Subtask 5b.2: `hero pipeline run` Command
- **Files:** Create `src/hero/commands/pipeline.py`, modify `src/hero/cli.py`
- **What:** `hero pipeline run <task_id>` — takes a pipeline ID (from `hero go` output), creates a `PipelineExecutor`, and runs the full pipeline with live progress output via Rich. `hero pipeline status <task_id>` — shows current pipeline state from manifest. `hero pipeline list` — lists all pipelines.
- **Complexity:** Medium
- **Dependencies:** 5b.1

#### Subtask 5b.3: `hero go` Integration
- **Files:** Modify `src/hero/commands/go.py`
- **What:** After writing the pipeline manifest (Phase 6 of `go`), if `--auto` flag is passed, immediately invoke `PipelineExecutor` on the new manifest. Default behavior stays the same (manifest only). Add `--auto` flag.
- **Complexity:** Small
- **Dependencies:** 5b.1, 5b.2

---

### Phase 5c: Soldier Output QA Gate
**Priority: HIGH — prevents garbage-in-garbage-out**

#### Subtask 5c.1: File-Scope Check
- **Files:** Create `src/hero/qa/scope_check.py`
- **What:** After a soldier completes, verify that modified files (via `git diff --name-only`) are within the assigned file list. If soldier was assigned `src/components/Foo.tsx` and it modified `src/utils/bar.ts`, flag as scope violation. Returns `QAResult(passed, violations[])`.
- **Complexity:** Small
- **Dependencies:** 5b.1 (integrate into pipeline after soldier completes)

#### Subtask 5c.2: Diff-Size Check
- **Files:** Create `src/hero/qa/diff_check.py`
- **What:** After a soldier completes, run `git diff --stat` and check that no single file exceeds 200 lines changed. Flag as oversized diff. Configurable threshold via `~/.hero/config.yaml` (new file).
- **Complexity:** Small
- **Dependencies:** 5b.1

#### Subtask 5c.3: Semantic Sanity Check
- **Files:** Create `src/hero/qa/semantic_check.py`
- **What:** Lightweight prompt-based check: send the diff to a fast model (step-3.5-flash) with "Does this diff look correct for the task? Answer YES/NO and brief reason." Parse response. Flag if NO. Optional — can be disabled via config.
- **Complexity:** Medium
- **Dependencies:** 5b.1 (needs soldier output), 5a.4 (uses model with fallback)

#### Subtask 5c.4: QA Gate Integration
- **Files:** Create `src/hero/qa/gate.py`, modify `src/hero/pipeline/executor.py`
- **What:** `QAGate` class that runs all three checks (scope, diff-size, semantic) after each soldier completes in the pipeline. If any check fails: mark task as "qa_failed" in dispatch queue, move to DLQ. If all pass: proceed normally. Add `--no-qa` flag to `hero pipeline run` and `hero go`.
- **Complexity:** Medium
- **Dependencies:** 5c.1, 5c.2, 5c.3, 5b.1

---

### Phase 5d: Git Workflow Integration
**Priority: HIGH — safety net for all soldier work**

#### Subtask 5d.1: Auto-Branch on Pipeline Start
- **Files:** Create `src/hero/git/branch.py`
- **What:** Before spawning soldiers, `PipelineExecutor` creates a feature branch `hero/<pipeline_id>` from the current branch. All soldier work happens on this branch. If pipeline fails → offer `hero pipeline rollback <id>` to switch back to original branch and delete the feature branch.
- **Complexity:** Small
- **Dependencies:** 5b.1 (integrate into pipeline executor)

#### Subtask 5d.2: Auto-Commit on Success
- **Files:** Modify `src/hero/pipeline/executor.py`, create `src/hero/git/commit.py`
- **What:** After all soldiers + verify pass, auto-commit with message: `hero(<sandbox>): <task summary>`. Include files changed in commit. If verify fails → don't commit, leave dirty state for manual fix.
- **Complexity:** Small
- **Dependencies:** 5d.1, 5b.1

#### Subtask 5d.3: Rollback on Failure
- **Files:** Create `src/hero/commands/pipeline.py` (add rollback subcommand)
- **What:** `hero pipeline rollback <task_id>` — switches back to the original branch (stored in pipeline manifest), deletes the feature branch, resets any uncommitted changes. Safety mechanism.
- **Complexity:** Small
- **Dependencies:** 5d.1

---

### Phase 5e: Token Efficiency
**Priority: HIGH — cost reduction**

#### Subtask 5e.1: Dynamic Budget Allocation
- **Files:** Modify `src/hero/soldier/spawner.py`, `src/hero/commands/go.py`
- **What:** Replace static `--budget 5000` with dynamic allocation: estimate task complexity (1-10 scale) from task description length, number of files involved, and project size. Map to budget: complexity 1-3 → 1k, 4-6 → 5k, 7-10 → 20k. Override with explicit `--budget` flag.
- **Complexity:** Medium
- **Dependencies:** None

#### Subtask 5e.2: Dispatch Queue TOON Format
- **Files:** Modify `src/hero/soldier/dispatch.py`
- **What:** Store dispatch tasks as `.toon` files instead of `.json`. Keep JSON export for backward compat via `hero dispatch list --json`. TOON saves ~37% tokens when the dispatch queue is injected into LLM context.
- **Complexity:** Small
- **Dependencies:** None

#### Subtask 5e.3: Context Deduplication
- **Files:** Modify `src/hero/soldier/context.py`
- **What:** When building soldier context, detect repeated project context (same README, same PLAN.md across soldiers in the same pipeline). Include once with a reference marker, not duplicated per soldier. Track in pipeline manifest.
- **Complexity:** Small
- **Dependencies:** 5b.1 (pipeline context sharing)

---

### Phase 5f: Cross-Sandbox Budget Queries
**Priority: MEDIUM — visibility across the army**

#### Subtask 5f.1: Budget Summary Aggregation
- **Files:** Modify `src/hero/commands/budget.py`
- **What:** Add `hero budget summary` subcommand: total tokens used vs budget across all sandboxes, average utilization, sandboxes below threshold. Add `hero budget top --limit 10` to show top consumers. Add `hero budget alert --threshold 2000` to show sandboxes below threshold.
- **Complexity:** Small
- **Dependencies:** None (budget.py already loads all budgets)

#### Subtask 5f.2: Budget History
- **Files:** Create `src/hero/state/budget_history.py`
- **What:** Append budget snapshots to `~/.hero/budget_history.jsonl` on every spawn/complete event. Each line: `{"ts": "...", "sandbox": "...", "event": "spawn|complete", "tokens_before": N, "tokens_after": N}`. Enables trending over time.
- **Complexity:** Small
- **Dependencies:** None

---

### Phase 5g: Developer Experience
**Priority: MEDIUM — quality of life**

#### Subtask 5g.1: `hero plan --interactive`
- **Files:** Modify `src/hero/commands/orchestrate.py`
- **What:** Add `--interactive` flag to `hero orchestrate`. Instead of auto-generating subtasks, present each proposed subtask and let user confirm/edit/skip before queuing. Uses `click.confirm` and `click.prompt`.
- **Complexity:** Small
- **Dependencies:** None

#### Subtask 5g.2: `hero check --sandbox X`
- **Files:** Create `src/hero/commands/check.py`
- **What:** Quick health check for a sandbox: run analyzer, check budget, check heartbeat status, verify no stale soldiers, show last eval score. Single-command diagnostic.
- **Complexity:** Small
- **Dependencies:** None

#### Subtask 5g.3: `hero watch --sandbox X`
- **Files:** Modify `src/hero/viewport/renderer.py`
- **What:** `hero watch <sandbox>` — focused live dashboard for a single sandbox, showing real-time token usage, active soldiers, and recent events. Subset of the full viewport.
- **Complexity:** Small
- **Dependencies:** None

---

### Phase 5h: Architecture Refinements
**Priority: LOW — long-term health**

#### Subtask 5h.1: TOON-ify Remaining JSON
- **Files:** Modify `src/hero/soldier/dispatch.py` (after 5e.2), `src/hero/analysis_cache.py`, `src/hero/eval/engine.py`
- **What:** Convert remaining JSON files to TOON: analysis cache metadata, eval scorecards, dispatch history. Keep backward-compat JSON read.
- **Complexity:** Medium
- **Dependencies:** 5e.2

#### Subtask 5h.2: Sandbox Dependency Graph
- **Files:** Create `src/hero/graph/dependencies.py`, modify `src/hero/commands/graph.py`
- **What:** Parse `package.json` imports, `pubspec.yaml` dependencies, and `Cargo.toml` to build inter-sandbox dependency graph. Store in `~/.hero/dependencies.toon`. `hero graph dependencies` shows which sandboxes depend on which. Useful for `hero deploy --cascade` (deploy dependents too).
- **Complexity:** Large
- **Dependencies:** None

#### Subtask 5h.3: Task Complexity Estimator
- **Files:** Create `src/hero/analysis/complexity.py`
- **What:** Estimate task complexity (1-10) from: task description length, number of files mentioned, project size (src file count), whether it involves architecture vs. bugfix, presence of tests. Used by dynamic budget (5e.1) and subtask generation.
- **Complexity:** Medium
- **Dependencies:** None

---

## Execution Order (Recommended)

### Wave 1 — Foundation (parallelizable)
| # | Subtask | Can parallel with |
|---|---------|-------------------|
| 1 | 5a.1 Structured Logging | 5e.1, 5e.2, 5f.1, 5f.2 |
| 2 | 5e.1 Dynamic Budget | 5a.1, 5e.2, 5f.1 |
| 3 | 5e.2 Dispatch TOON | 5a.1, 5e.1, 5f.1 |
| 4 | 5f.1 Budget Summary | 5a.1, 5e.1, 5e.2 |
| 5 | 5f.2 Budget History | 5a.1, 5e.1, 5e.2 |

### Wave 2 — Reliability (sequential after Wave 1)
| # | Subtask | Depends on |
|---|---------|------------|
| 6 | 5a.2 Dead Letter Queue | 5a.1 |
| 7 | 5a.3 Circuit Breaker | 5a.1 |
| 8 | 5a.4 Model Fallback | 5a.1, 5a.3 |

### Wave 3 — Pipeline (sequential after Wave 2)
| # | Subtask | Depends on |
|---|---------|------------|
| 9 | 5b.1 PipelineExecutor Core | 5a.1, 5a.3 |
| 10 | 5b.2 `hero pipeline` command | 5b.1 |
| 11 | 5b.3 `hero go --auto` | 5b.1, 5b.2 |

### Wave 4 — QA & Git (parallel after Wave 3)
| # | Subtask | Depends on |
|---|---------|------------|
| 12 | 5c.1 File-scope check | 5b.1 |
| 13 | 5c.2 Diff-size check | 5b.1 |
| 14 | 5c.3 Semantic check | 5b.1, 5a.4 |
| 15 | 5d.1 Auto-branch | 5b.1 |
| 16 | 5e.3 Context dedup | 5b.1 |

### Wave 5 — Integration (sequential after Wave 4)
| # | Subtask | Depends on |
|---|---------|------------|
| 17 | 5c.4 QA Gate integration | 5c.1, 5c.2, 5c.3, 5b.1 |
| 18 | 5d.2 Auto-commit | 5d.1, 5b.1 |
| 19 | 5d.3 Rollback | 5d.1 |

### Wave 6 — DX & Architecture (parallel, last)
| # | Subtask | Depends on |
|---|---------|------------|
| 20 | 5g.1 Interactive plan | — |
| 21 | 5g.2 Hero check | — |
| 22 | 5g.3 Hero watch | — |
| 23 | 5h.1 TOON-ify remaining | 5e.2 |
| 24 | 5h.2 Dependency graph | — |
| 25 | 5h.3 Complexity estimator | — |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| PipelineExecutor polling is too slow | MEDIUM | Configurable poll interval; event-driven alternative via filesystem watcher |
| QA Gate semantic check costs too many tokens | LOW | Make it opt-in, use cheapest model, cache results |
| Git auto-commit on dirty state | HIGH | Always check `git status` clean before branching; rollback command is safety net |
| TOON dispatch migration breaks existing workflows | MEDIUM | Dual-mode: read both .toon and .json, write only .toon after migration |
| Circuit breaker false positives | MEDIUM | Configurable threshold, manual unquarantine, cooldown timer |

---

## Open Questions (Answered)

1. **PipelineExecutor as subprocess or library?** → **Library (in-process).** Pipeline runs are synchronous CLI commands. User runs `hero go --auto` or `hero pipeline run` and waits. No need for process management overhead.

2. **QA Gate model cost budget** → **Acceptable.** 5k tokens per pipeline is ~$0.0005 on Step 3.5 Flash. Make semantic check configurable via `--no-qa` and `~/.hero/config.yaml` `qa.semantic: true|false`.

3. **Git auto-commit scope** → **Sandbox-scoped.** For monorepos, `git add <sandbox_path>/` to commit only the sandbox files. Store sandbox path in the pipeline manifest.

4. **Dead Letter Queue retention** → **7 days.** Auto-cleanup runs on `hero dlq list` and `hero dlq retry`. Also add `hero dlq clear --older-than 7d`.

---

## Execution Log

### Wave 1 — Foundation (2026-05-24)
- ✅ 5a.1 Structured Logging — soldier deployed in parallel
- ✅ 5e.1 Dynamic Budget — soldier deployed in parallel
- ✅ 5e.2 Dispatch TOON — soldier deployed in parallel
- ✅ 5f.1 Budget Summary — soldier deployed in parallel
- ✅ 5f.2 Budget History — soldier deployed in parallel
- Status: ⏳ Waiting for all 5 soldiers to complete...

### Lead Keyword Bug Fix (2026-05-25)
**Challenge:** `orchestrate.py` Phase 3 matched `"agent config"` as substring in task text, causing hallucinated Agent Config tasks for non-Agent projects (e.g., Godot game builds).
**Fix:** Full phrase matching (`"agent config window"`) + added Godot keywords to Phase 1.
**Result:** Galaxy & Oblivion Phase 1 deployed successfully via soldier after fix.
