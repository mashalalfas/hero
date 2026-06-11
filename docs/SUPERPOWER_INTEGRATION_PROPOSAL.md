# Superpower → HERO Integration Proposal

> **Date:** 2026-05-26  
> **Author:** Claw (subagent)  
> **Purpose:** Extract high-value patterns from the Superpower workflow system and integrate them into the HERO army pipeline.

---

## Executive Summary

The Superpower system (by the opencode team) enforces three mechanisms that HERO currently lacks:

1. **TDD strict enforcement** — Red-Green-Refactor with mandatory "watch it fail" verification
2. **Git worktree isolation** — Detect existing isolation → native tools → git fallback → baseline verification
3. **Brainstorm gate** — Hard gate: no code until design is approved by the user

HERO already has partial infrastructure for each. The integration plan below maps Superpower patterns onto HERO's existing modules with minimal disruption.

---

## 1. TDD Strict Enforcement

### What Superpower Does

- **Iron Law:** "NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST"
- Code written before tests must be **DELETED**, not adapted
- "Watch it fail" is **MANDATORY** — if you didn't see the test fail, you don't know it tests the right thing
- Verification checklist: 8 items, 100% required or restart
- Anti-pattern tables that bust rationalizations ("too simple to test", "tests after achieve the same")

### Where It Goes in HERO

**Integration point: `hero/qa/gate.py`** — the QA Gate already checks file-scope and diff-size. Add a **TDD compliance gate** that runs after soldier completion.

**Integration point: Soldier brief templates** — the task prompt sent to each soldier must include TDD rules.

**Integration point: `PipelineExecutor.run()`** — add a TDD verification stage after the verify phase.

### Implementation

#### A. TDD Gate (`hero/qa/tdd_gate.py` — new file)

```python
"""TDD Gate — verifies soldiers followed Red-Green-Refactor.

Checks (all must pass):
1. Every new/modified source file has a corresponding test file
2. Test file contains at least one test that calls the changed function
3. git log shows test commit before implementation commit (if auto-commit)
4. No "TODO" or "FIXME" placeholders in test files
"""

import subprocess
from pathlib import Path
from dataclasses import dataclass

@dataclass
class TDDResult:
    passed: bool
    violations: list[str]

class TDDGate:
    def __init__(self, sandbox_path: Path, project_type: str = "auto"):
        self.sandbox_path = sandbox_path
        self.project_type = project_type

    def run(self) -> TDDResult:
        violations = []
        changed = self._get_changed_source_files()
        for src_file in changed:
            test_file = self._find_test_for(src_file)
            if not test_file:
                violations.append(f"No test file for {src_file}")
            elif not self._test_has_assertions(test_file):
                violations.append(f"Test file {test_file} has no assertions")

        # Check commit ordering (test before impl)
        if not self._verify_commit_order():
            violations.append("Test commit not before implementation commit")

        return TDDResult(passed=len(violations) == 0, violations=violations)
```

#### B. Soldier Brief Update (`hero/soldier/spawner.py`)

The `build_context()` function constructs the task prompt sent to soldiers. Add a TDD block:

```python
TDD_RULES = """
## MANDATORY: Test-Driven Development

You MUST follow Red-Green-Refactor for every change:

1. **Write the failing test FIRST** — no implementation code without a test
2. **Watch it fail** — run the test and confirm it fails for the right reason
3. **Write minimal code** — just enough to pass the test
4. **Watch it pass** — run the test and confirm it passes
5. **Refactor** — clean up while tests stay green

RULES:
- Code written before tests? DELETE it. Start over from step 1.
- No "I'll add tests later" — that's not TDD, that's after-the-fact verification
- No mocks unless absolutely unavoidable — test real behavior
- One test per behavior — if "and" is in the test name, split it
- Every commit must be: test → implementation → green

VIOLATIONS → task restart from step 1
"""
```

#### C. Pipeline Integration (`hero/pipeline/executor.py`)

Add to `PipelineExecutor.run()` after Stage 3 (verify):

```python
# ── Stage 3b: TDD compliance check ─────────────────────
from hero.qa.tdd_gate import TDDGate
if self.soldiers and not soldier_failures:
    tdd_gate = TDDGate(sandbox_path, self.manifest.get("project_type", "auto"))
    tdd_result = tdd_gate.run()
    if not tdd_result.passed:
        # Send failing soldiers to DLQ
        for v in tdd_result.violations:
            logger.error("TDD violation: %s", v)
        status = "tdd_failed"
```

---

## 2. Git Worktree Isolation

### What Superpower Does

- **Step 0:** Detect existing isolation (linked worktree vs normal repo)
- **Step 1a:** Prefer native worktree tools (e.g., `EnterWorktree`)
- **Step 1b:** Git worktree fallback with `.worktrees/` directory
- **Safety:** Verify `.worktrees` is in `.gitignore` before creating
- **Step 3:** Auto-detect project type → run setup (npm install, cargo build, etc.)
- **Step 4:** Verify clean baseline — run tests before starting

### Where It Goes in HERO

**Integration point: `hero/git/branch.py`** — already has `create_pipeline_branch()`. Extend it with worktree isolation.

**Integration point: `PipelineExecutor.run()` Stage 1a** — before soldiers are dispatched, create an isolated worktree.

**Integration point: `hero go --sandbox X`** — add `--isolate` flag (default: on for `--auto`).

### Implementation

#### A. Worktree Manager (`hero/git/worktree.py` — new file)

```python
"""Git worktree isolation for HERO pipelines.

Detects existing isolation, creates worktrees for pipeline branches,
and verifies clean baselines before work begins.
"""

from pathlib import Path
import subprocess

class WorktreeManager:
    def __init__(self, sandbox_path: Path):
        self.sandbox_path = sandbox_path

    def detect_existing_isolation(self) -> dict:
        """Step 0: Check if already in a linked worktree."""
        git_dir = self._run("git", "rev-parse", "--git-dir")
        git_common = self._run("git", "rev-parse", "--git-common-dir")
        is_submodule = bool(self._run("git", "rev-parse", "--show-superproject-working-tree"))

        return {
            "in_worktree": git_dir != git_common and not is_submodule,
            "in_submodule": is_submodule,
            "git_dir": git_dir,
            "git_common_dir": git_common,
        }

    def create_isolated_workspace(self, branch_name: str) -> Path:
        """Step 1: Create worktree with proper safety checks."""
        # Check if .worktrees is gitignored
        worktrees_dir = self.sandbox_path / ".worktrees"
        if not self._is_gitignored(".worktrees"):
            self._add_to_gitignore(".worktrees")
            self._commit_gitignore()

        worktree_path = worktrees_dir / branch_name
        self._run(
            "git", "worktree", "add", str(worktree_path),
            "-b", branch_name,
            cwd=str(self.sandbox_path)
        )
        return worktree_path

    def verify_clean_baseline(self, path: Path) -> dict:
        """Step 4: Run tests to verify workspace starts clean."""
        result = self._run_project_tests(path)
        return {"tests_pass": result["exit_code"] == 0, "output": result["stdout"]}

    def _is_gitignored(self, pattern: str) -> bool:
        result = subprocess.run(
            ["git", "check-ignore", "-q", pattern],
            cwd=str(self.sandbox_path),
            capture_output=True
        )
        return result.returncode == 0
```

#### B. PipelineExecutor Integration

```python
# ── Stage 0b: Worktree isolation ──────────────────────────
from hero.git.worktree import WorktreeManager

wm = WorktreeManager(sandbox_path)
isolation = wm.detect_existing_isolation()

if not isolation["in_worktree"]:
    worktree_path = wm.create_isolated_workspace(f"hero/{self.pipeline_id}")
    # Update sandbox_path for all subsequent operations
    sandbox_path = worktree_path
    self.manifest["worktree_path"] = str(worktree_path)

    # Verify clean baseline
    baseline = wm.verify_clean_baseline(sandbox_path)
    if not baseline["tests_pass"]:
        raise RuntimeError(
            f"Baseline tests fail in new worktree: {baseline['output'][:200]}"
        )
```

#### C. CLI Flag

```python
@click.option("--isolate/--no-isolate", default=True,
              help="Create git worktree isolation (default: on)")
```

---

## 3. Brainstorm Phase (Hard Gate)

### What Superpower Does

- **HARD GATE:** "Do NOT invoke any implementation skill, write any code, scaffold any project, or take any implementation action until you have presented a design and the user has approved it."
- Flow: explore context → clarify questions (one at a time, multiple choice) → 2-3 approaches → present design → write spec → user reviews → only THEN implement
- Anti-pattern: "This is too simple to need a design" — every project goes through this
- Spec self-review for placeholders/contradictions before user review

### Where It Goes in HERO

**Integration point: `hero go` command** — add a `--brainstorm` flag (default: on for `--auto`). Before dispatching soldiers, run a brainstorm phase.

**Integration point: New command `hero think`** — standalone brainstorm command that produces a spec file.

**Integration point: Soldier brief** — include the approved spec in every soldier's context.

### Implementation

#### A. Brainstorm Module (`hero/brainstorm/gate.py` — new file)

```python
"""Brainstorm Gate — forces design review before implementation.

The gate ensures:
1. Project context is explored (files, docs, recent commits)
2. Clarifying questions are asked (one at a time)
3. 2-3 approaches are proposed with trade-offs
4. Design is presented and approved by user
5. Spec is written and self-reviewed
6. User reviews spec before proceeding
"""

from pathlib import Path
from dataclasses import dataclass

@dataclass
class BrainstormResult:
    approved: bool
    spec_path: Path | None = None
    design_summary: str = ""

class BrainstormGate:
    HARD_GATE = (
        "Do NOT write any code until you have presented a design "
        "and the user has approved it. This applies to EVERY project "
        "regardless of perceived simplicity."
    )

    def __init__(self, sandbox_path: Path, task: str):
        self.sandbox_path = sandbox_path
        self.task = task

    def run_interactive(self) -> BrainstormResult:
        """Run the brainstorm phase interactively.

        This is called by the Communicator before hero go --auto.
        Returns the approved spec path.
        """
        # 1. Explore context
        context = self._explore_project_context()

        # 2. Ask clarifying questions (communicator handles this)
        questions = self._generate_clarifying_questions(context)

        # 3. Propose approaches (communicator presents to user)
        approaches = self._propose_approaches(questions, context)

        # 4. Present design (communicator presents to user)
        design = self._present_design(approaches)

        # 5. Write spec (after user approves design)
        spec_path = self._write_spec(design)

        # 6. Self-review spec
        self._self_review_spec(spec_path)

        return BrainstormResult(
            approved=True,  # Only returns after user approves
            spec_path=spec_path,
            design_summary=design["summary"]
        )

    def _explore_project_context(self) -> dict:
        """Read PLAN.md, README.md, src structure, recent git log."""
        # ... reads project files, returns context dict

    def _generate_clarifying_questions(self, context: dict) -> list[str]:
        """Generate questions based on task + context gaps."""
        # ... returns list of questions to ask user

    def _propose_approaches(self, questions: dict, context: dict) -> list[dict]:
        """Propose 2-3 approaches with trade-offs."""
        # ... returns list of approach dicts

    def _present_design(self, approaches: list[dict]) -> dict:
        """Present the recommended design."""
        # ... returns design dict with summary, components, data flow

    def _write_spec(self, design: dict) -> Path:
        """Write spec to docs/specs/YYYY-MM-DD-<topic>-design.md."""
        spec_dir = self.sandbox_path / "docs" / "specs"
        spec_dir.mkdir(parents=True, exist_ok=True)
        # ... write spec file

    def _self_review_spec(self, spec_path: Path) -> list[str]:
        """Check spec for placeholders, contradictions, ambiguity."""
        violations = []
        content = spec_path.read_text()
        if "TBD" in content or "TODO" in content:
            violations.append("Placeholder found in spec")
        # ... more checks
        return violations
```

#### B. `hero think` Command (`hero/commands/think.py` — new file)

```python
"""hero think — Brainstorm phase before implementation.

Usage:
    hero think --sandbox qlearner --task "add spaced repetition"
    hero think --sandbox qlearner --task "add spaced repetition" --auto
"""

@click.command()
@click.option("--sandbox", required=True)
@click.option("--task", required=True)
@click.option("--auto", is_flag=True, help="Auto-run brainstorm, write spec")
def think(sandbox: str, task: str, auto: bool):
    """Brainstorm gate: design before code."""
    gate = BrainstormGate(sandbox_path, task)

    if auto:
        result = gate.run_interactive()
        click.echo(f"Spec written to: {result.spec_path}")
    else:
        # Interactive mode — Communicator drives the conversation
        click.echo(gate.HARD_GATE)
        click.echo("\nAsk clarifying questions one at a time.")
        click.echo("Propose 2-3 approaches with trade-offs.")
        click.echo("Present design and get user approval.")
        click.echo("Write spec and self-review.")
```

#### C. `hero go` Integration

```python
@click.option("--brainstorm/--no-brainstorm", default=False,
              help="Run brainstorm phase before dispatching soldiers.")
def go(sandbox, task, brainstorm, auto, ...):
    # Phase 0: Brainstorm (if --brainstorm or --auto)
    if brainstorm or auto:
        click.echo("── Phase 0: Brainstorm ──────────────────────")
        gate = BrainstormGate(sandbox_path, task)
        result = gate.run_interactive()
        click.echo(f"  Spec: {result.spec_path}")
        # Include spec in soldier context
        task = f"{task}\n\nSpec: {result.spec_path.read_text()}"
```

---

## Integration Map

```
SUPERPOWER PATTERN          → HERO MODULE                      → PIPELINE STAGE
─────────────────────────────────────────────────────────────────────────────────
TDD Iron Law                → hero/qa/tdd_gate.py              → Stage 3b (after verify)
Soldier TDD rules           → hero/soldier/spawner.py          → Soldier brief template
Brainstorm hard gate        → hero/brainstorm/gate.py          → Stage 0 (before dispatch)
  ├─ explore context        │   └── _explore_project_context()
  ├─ clarifying questions   │   └── _generate_clarifying_questions()
  ├─ propose approaches     │   └── _propose_approaches()
  ├─ present design         │   └── _present_design()
  ├─ write spec             │   └── _write_spec()
  └─ self-review            │   └── _self_review_spec()
Worktree isolation          → hero/git/worktree.py             → Stage 0b (before soldiers)
  ├─ detect existing        │   └── detect_existing_isolation()
  ├─ create worktree        │   └── create_isolated_workspace()
  └─ verify baseline        │   └── verify_clean_baseline()
Verification before claims  → hero/qa/gate.py (existing)      → Stage 4 (existing verify)
```

---

## Pipeline Stages (Updated)

```
Stage 0:  Brainstorm          ← NEW (Superpower brainstorm gate)
Stage 0b: Worktree Isolation  ← NEW (Superpower git worktrees)
Stage 1:  Analysis             (existing)
Stage 2:  Lead / Orchestrate   (existing)
Stage 3:  Dispatch / Spawn     (existing)
Stage 3b: TDD Compliance       ← NEW (Superpower TDD gate)
Stage 4:  Verify               (existing QA gate)
Stage 5:  Fix                  (existing)
Stage 6:  Archive              (existing)
Stage 7:  Report               (existing)
```

---

## New Files

| File | Purpose |
|------|---------|
| `src/hero/qa/tdd_gate.py` | TDD compliance verification |
| `src/hero/git/worktree.py` | Git worktree isolation manager |
| `src/hero/brainstorm/gate.py` | Brainstorm phase gate |
| `src/hero/commands/think.py` | `hero think` CLI command |
| `tests/test_tdd_gate.py` | TDD gate tests |
| `tests/test_worktree.py` | Worktree manager tests |
| `tests/test_brainstorm.py` | Brainstorm gate tests |

## Modified Files

| File | Change |
|------|--------|
| `src/hero/pipeline/executor.py` | Add Stages 0, 0b, 3b |
| `src/hero/commands/go.py` | Add `--brainstorm`, `--isolate` flags |
| `src/hero/qa/gate.py` | Import TDD gate integration |
| `src/hero/soldier/spawner.py` | Add TDD rules to soldier brief |
| `src/hero/cli.py` | Register `think` command |

---

## Rollout Priority

1. **TDD Gate** — highest value, catches the most costly mistakes (code without tests)
2. **Brainstorm Gate** — prevents wasted work on wrong implementations
3. **Worktree Isolation** — nice-to-have, protects main branch during pipeline runs

---

## Success Metrics

- **TDD Gate:** 100% of new source files have corresponding test files with assertions
- **Brainstorm Gate:** 0 implementations that required rework due to unclear requirements
- **Worktree Isolation:** 0 accidental commits to main during pipeline runs
