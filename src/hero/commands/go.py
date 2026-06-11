"""hero go — One-command full pipeline.

Queues soldiers, outputs sessions_spawn manifest, runs pipeline execution
line inline (pre-commit → build → harden → legal → cipr → verify → archive),
writes pipeline file for the Communicator to execute: spawn → report.

Pipeline phases:
    0.  Brainstorm      (OPTIONAL — only for open-ended tasks)
    0b. Worktree        (ALWAYS — creates git worktree before code changes)
    1.  Analysis        (detect project type, run linter)
    2.  Lead            (break task into focused subtasks)
    3.  Dispatch        (queue soldiers)
    3b. Spawn           (generate sessions_spawn commands)
    4.  Pipeline        (direct inline: pre-commit → build → harden → legal → cipr → verify → archive)
    5.  Report          (communicator summary)

Usage:
    hero go --sandbox qlearner --task "fix all issues"
    hero go --sandbox fury-os --task "Phase 2 polish" --dry-run

Output:
    - Console: sessions_spawn commands + pipeline instructions
    - File: ~/.hero/pipeline/<task_id>.json — structured manifest
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

import click

from hero.analysis_cache import cached_analyze, invalidate as invalidate_cache
from hero.soldier.dispatch import enqueue, mark_dispatched, get_sessions_spawn_command
from hero.soldier.spawner import estimate_budget, get_model_for_role, load_army_config
from hero.core.locks import FileLock
from hero.state.index import IndexState
from hero.commands.pre_commit import run_pre_commit
from hero.commands.build import run_build
from hero.commands.harden import run_harden
from hero.commands.legal import run_legal
from hero.commands.cipr import run_cipr
from hero.commands.verify import run_verify
from hero.commands.archive import run_archive

# ── New core/stages layer (graceful fallback if not yet installed) ─────
try:
    from hero.core.project import detect_project_type as _core_detect
except ImportError:  # pragma: no cover — optional dependency
    _core_detect = None

try:
    import hero.stages as _stages
    _stages_run = _stages.run_stage
    _stages_resolve = _stages.resolve_mode
except ImportError:  # pragma: no cover — optional dependency
    _stages = None
    _stages_run = None
    _stages_resolve = None


# ── Default stage ordering (used when stages module unavailable) ───────
_DEFAULT_STAGE_ORDER = [
    "navigate",
    "pre_commit",
    "build",
    "harden",
    "legal",
    "cipr",
    "verify",
    "archive",
]

# ── Mode → stage list (fallback when hero.stages.resolve_mode is missing)
_MODE_STAGES = {
    "smart": ["navigate", "pre_commit", "build", "verify", "archive"],
    "quick": ["navigate", "pre_commit", "build"],
    "full": _DEFAULT_STAGE_ORDER,
    "ci": ["pre_commit", "build", "cipr"],
    "audit": ["navigate", "pre_commit", "harden", "legal"],
}


def _resolve_mode(mode: str) -> list[str]:
    """Resolve a mode name to an ordered stage list."""
    if _stages_resolve:
        try:
            return _stages_resolve(mode)
        except (ValueError, KeyError) as exc:
            raise click.ClickException(str(exc))
    stages = _MODE_STAGES.get(mode)
    if stages is None:
        raise click.ClickException(
            f"Unknown mode '{mode}'. Choose from: {', '.join(sorted(_MODE_STAGES.keys()))}"
        )
    return list(stages)


def _run_stage_safe(name: str, sandbox_path, verbose: bool = False, **kwargs):
    """Run a stage via hero.stages if available, else direct function call."""
    if _stages_run:
        return _stages_run(name, sandbox_path, verbose=verbose, **kwargs)
    # Fallback: use old direct imports
    _FALLBACKS = {
        "navigate": None,   # no old navigate function exists
        "pre_commit": (
            run_pre_commit,
            lambda sp, v, **kw: run_pre_commit(sp, verbose=v),
        ),
        "build": (
            run_build,
            lambda sp, v, **kw: run_build(sp, verbose=v, bump=kw.get("bump", False)),
        ),
        "harden": (
            run_harden,
            lambda sp, v, **kw: run_harden(sp, verbose=v),
        ),
        "legal": (
            run_legal,
            lambda sp, v, **kw: run_legal(sp, verbose=v),
        ),
        "cipr": (
            run_cipr,
            lambda sp, v, **kw: run_cipr(sp, verbose=v),
        ),
        "verify": (
            run_verify,
            lambda sp, v, **kw: run_verify(sp, verbose=v),
        ),
        "archive": (
            run_archive,
            lambda sp, v, **kw: run_archive(
                sp, verbose=v,
                pipeline_id=kwargs.get("pipeline_id"),
                task=kwargs.get("task", ""),
                stage_scores=kwargs.get("stage_scores"),
            ),
        ),
    }
    entry = _FALLBACKS.get(name)
    if entry is None:
        raise click.ClickException(f"Unknown stage: {name}")
    _, fn = entry
    return fn(sandbox_path, verbose, **kwargs)


PIPELINE_DIR = Path.home() / ".hero" / "pipeline"
BRAINSTORM_DIR = Path.home() / ".hero" / "brainstorm"
WORKTREE_BASE = Path.home() / "Development" / "worktrees"


def _ensure_brainstorm_dir() -> None:
    BRAINSTORM_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_worktree_base() -> None:
    WORKTREE_BASE.mkdir(parents=True, exist_ok=True)


def _detect_main_branch(repo_path: Path) -> str:
    """Detect the default branch name (main, master, or develop)."""
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        ref = result.stdout.strip()
        if ref:
            branch = ref.rsplit("/", 1)[-1]
            if branch in ("main", "master", "develop"):
                return branch
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["git", "branch", "--list"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        for branch in ("main", "master", "develop"):
            if branch in result.stdout:
                return branch
    except Exception:
        pass
    return "main"


def _create_worktree(
    sandbox: str,
    sandbox_path: Path,
    pipeline_id: str,
    soldier_id: str | None = None,
) -> str | None:
    """Create a git worktree for the pipeline.

    When *soldier_id* is provided the branch and path include the
    soldier identifier:

        hero/<pipeline_id>/<soldier_id>
        ~/Development/worktrees/<sandbox>/<pipeline_id>/<soldier_id>/

    Returns the worktree path on success, None on failure.
    """
    try:
        main_branch = _detect_main_branch(sandbox_path)
        suffix = f"{pipeline_id}/{soldier_id}" if soldier_id else pipeline_id
        branch_name = f"hero/{suffix}"
        worktree_path = str(WORKTREE_BASE / sandbox / suffix)
        Path(worktree_path).parent.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            [
                "git", "worktree", "add",
                "-b", branch_name,
                worktree_path,
                main_branch,
            ],
            cwd=str(sandbox_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return worktree_path
        else:
            stderr = result.stderr.lower()
            if "already" in stderr or "exists" in stderr:
                if Path(worktree_path).exists():
                    return worktree_path
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=str(sandbox_path),
                capture_output=True,
                timeout=10,
            )
            return None
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None


def _prune_worktree(sandbox_path: Path, pipeline_id: str) -> None:
    """Remove a pipeline worktree and prune stale refs."""
    try:
        subprocess.run(
            ["git", "worktree", "remove", f"hero/{pipeline_id}"],
            cwd=str(sandbox_path),
            capture_output=True,
            timeout=10,
        )
    except Exception:
        pass
    try:
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=str(sandbox_path),
            capture_output=True,
            timeout=10,
        )
    except Exception:
        pass


def _is_open_ended_task(task: str) -> bool:
    """Detect if a task is open-ended/ambiguous and needs brainstorming.

    Keywords: design, idea, brainstorm, research, explore, what if, should we
    """
    keywords = [
        "design", "idea", "brainstorm", "research", "explore",
        "what if", "should we", "architecture", "spec", "proposal",
        "investigate", "analyze options", "compare", "approach",
    ]
    task_lower = task.lower()
    for kw in keywords:
        if kw in task_lower:
            return True
    return False


def _run_brainstorm(pipeline_id: str, task: str, sandbox: str, sandbox_path: Path) -> dict:
    """Phase 0: Quick brainstorm for open-ended tasks.

    Produces a short brief (2-5 lines) saved to ~/.hero/brainstorm/<pipeline_id>.md.
    Returns dict with status and brief path.
    """
    brief_path = BRAINSTORM_DIR / f"{pipeline_id}.md"
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    brief = (
        f"# Brainstorm Brief — {pipeline_id}\n\n"
        f"**Sandbox:** {sandbox}\n"
        f"**Task:** {task}\n\n"
        f"## What's Known\n"
        f"- Working directory: {sandbox_path}\n\n"
        f"## What's Unknown\n"
        f"- Scope and requirements to be clarified\n\n"
        f"## Quick Research Direction\n"
        f"- Read PLAN.md if it exists\n"
        f"- Check existing code patterns\n"
        f"- Identify key files and modules\n\n"
        f"## Recommended Next Steps\n"
        f"1. Run project analysis (Phase 1)\n"
        f"2. Break into focused subtasks (Phase 2)\n"
    )
    with FileLock("pipeline_brainstorm"):
        brief_path.write_text(brief)
    return {"status": "completed", "brief_path": str(brief_path)}


def _write_journal_entry(journal_path: Path, phase: str, content: str) -> None:
    """Append an entry to the running journal (incremental archive)."""
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n## {phase} — {timestamp}\n\n{content}\n"
    with open(journal_path, "a") as f:
        f.write(entry)


def _consolidate_journal(journal_path: Path, sandbox_path: Path, task: str,
                          pipeline_id: str, verify_result: str) -> None:
    """Consolidate journal.md into sandbox memory file (Phase 6 Archive)."""
    if not journal_path.exists():
        return
    journal_content = journal_path.read_text()
    if not journal_content.strip():
        return
    today = datetime.now().strftime("%Y-%m-%d")
    memory_dir = sandbox_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    memory_file = memory_dir / f"{today}.md"
    header = f"\n# Pipeline {pipeline_id} — {task[:80]}\n\n"
    if memory_file.exists():
        existing = memory_file.read_text()
        if header not in existing:
            memory_file.write_text(existing + header + journal_content)
    else:
        memory_file.write_text(header + journal_content)
    with open(journal_path, "a") as f:
        f.write("\n## Consolidated — " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
        f.write(f"_Archived to {memory_file}_\n")


def _check_circuit_breaker(current_errors: list[str], previous_errors: list[str],
                           iteration: int) -> bool:
    """Check if circuit breaker should trigger.

    Triggers if the same error persists for 2 consecutive iterations.
    """
    if iteration < 2:
        return False
    if set(current_errors) == set(previous_errors) and current_errors:
        return True
    return False


def _diff_errors(new_errors: list[str], old_errors: list[str]) -> list[str]:
    """Return errors that are new or changed since last iteration."""
    old_set = set(old_errors)
    return [e for e in new_errors if e not in old_set]


def _ensure_pipeline_dir() -> None:
    PIPELINE_DIR.mkdir(parents=True, exist_ok=True)


def _detect_project_type(path: Path) -> dict:
    """Detect project type and return analysis commands.

    Delegates to hero.core.project.detect_project_type when available;
    falls back to inline detection otherwise.
    """
    if _core_detect:
        return _core_detect(path)

    # ── Fallback: inline project detection ─────────────────────────
    result = {
        "type": "unknown",
        "analyze_cmd": None,
        "build_cmd": None,
        "analyzer": None,
        "source_globs": None,
    }

    if (path / "project.godot").exists() or (path / "engine.cfg").exists():
        result["type"] = "godot"
        result["source_globs"] = ["**/*.gd", "**/*.tscn", "**/*.tres", "**/*.json"]
    elif (path / "pubspec.yaml").exists():
        result["type"] = "flutter"
        result["analyze_cmd"] = ["flutter", "analyze"]
        result["build_cmd"] = ["flutter", "build", "apk", "--debug"]
        result["analyzer"] = "flutter"
        result["source_globs"] = ["lib/**/*.dart"]
    elif (path / "package.json").exists():
        result["type"] = "node"
        # Check for specific frameworks
        pkg = path / "package.json"
        try:
            pkg_data = json.loads(pkg.read_text())
            deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
            if "electron" in deps:
                result["type"] = "electron"
                result["analyze_cmd"] = ["npx", "tsc", "--noEmit"]
                result["build_cmd"] = ["npx", "vite", "build"]
                result["analyzer"] = "tsc"
                result["source_globs"] = ["src/**/*.ts", "src/**/*.tsx", "**/*.ts", "**/*.tsx"]
            else:
                result["analyze_cmd"] = ["npm", "run", "lint"] if "lint" in (pkg_data.get("scripts") or {}) else None
                result["build_cmd"] = ["npm", "run", "build"]
                result["analyzer"] = "npm"
                result["source_globs"] = ["src/**/*.js", "src/**/*.jsx", "**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx"]
        except (json.JSONDecodeError, OSError):
            pass

    elif (path / "pyproject.toml").exists():
        result["type"] = "python"
        result["analyze_cmd"] = ["ruff", "check", "."]
        result["build_cmd"] = ["python", "-m", "compileall", "."]
        result["source_globs"] = ["src/**/*.py", "**/*.py"]

    return result


def _run_analysis(analyze_cmd: list[str], cwd: Path,
                   source_globs: list[str] | None = None) -> dict:
    """Run analysis and return results (delegates to cached_analyze)."""
    return cached_analyze(analyze_cmd, cwd, source_globs=source_globs)


def _build_verify_task(project: dict, sandbox: str, original_task: str) -> str:
    """Build a verify task prompt that runs analyze + build after soldiers."""
    from hero.prompts import render_template

    checks = []
    if project.get("analyze_cmd"):
        checks.append(f"1. Analyze: {' '.join(project['analyze_cmd'])}")
    if project.get("build_cmd"):
        checks.append(f"2. Build: {' '.join(project['build_cmd'])}")
    if project["type"] == "flutter":
        checks.append("3. Tests: flutter test")
    elif project["type"] in ("electron", "node"):
        checks.append("3. Tests: npm test (if script exists)")

    return render_template(
        "phases/verify.md",
        sandbox=sandbox,
        original_task=original_task,
        checks="\n".join(checks),
    )


def _build_archive_task(sandbox: str, task: str, sandbox_path: Path) -> str:
    """Build an archivist task prompt to document results in memory."""
    from hero.prompts import render_template

    return render_template(
        "phases/archive.md",
        sandbox=sandbox,
        task=task,
        sandbox_path=sandbox_path,
        date=datetime.now().strftime("%Y-%m-%d"),
        date_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
        task_short=task[:80],
    )


def _get_escalation_model(tier: str = "tier1_to_tier2") -> str:
    """Get the full model name for an escalation tier from army.yaml.

    Args:
        tier: Escalation tier name (e.g. "tier1_to_tier2", "tier2_to_tier3")

    Returns:
        Full model string in "provider/model" format, or empty string if not found.
    """
    army = load_army_config()
    esc = army.get("escalation", {})
    t = esc.get(tier, {})
    provider = t.get("provider", "")
    model = t.get("model", "")
    if provider and model:
        return f"{provider}/{model}"
    if model:
        return model
    return ""

def _build_fix_task(sandbox: str, task: str, verify_task_id: str) -> str:
    """Build a fix task prompt that reads verify results and fixes issues.

    Uses Kimi K2.6 (escalation tier 1) for agent reasoning.
    If the verify step found issues, this task analyzes the errors
    and attempts to fix them.
    """
    from hero.prompts import render_template

    return render_template(
        "phases/fix.md",
        sandbox=sandbox,
        task=task,
        verify_task_id=verify_task_id,
    )



def _get_ts_errors(sandbox_path: Path) -> list[str]:
    """Run tsc --noEmit and return TypeScript error lines."""
    try:
        result = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            cwd=str(sandbox_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    if result.returncode == 0:
        return []
    errors = []
    for line in result.stderr.strip().splitlines():
        if "error TS" in line:
            errors.append(line.strip())
    return errors[:10]



@click.command()
@click.option("--sandbox", required=True, type=str, help="Target sandbox name.")
@click.option("--task", required=True, type=str, help="High-level task description.")
@click.option("--budget", type=int, default=None, help="Budget per soldier (auto-estimated from task complexity if not set).")
@click.option("--dry-run", is_flag=True, help="Plan without dispatching.")
@click.option("--verify/--no-verify", default=True, help="Run verify step after soldiers (default: yes)")
@click.option("--archive/--no-archive", default=True, help="Update memory after completion (default: yes)")
@click.option(
    "--viewport",
    is_flag=True,
    default=False,
    help="Open the HERO viewport dashboard after pipeline planning.",
)
@click.option("--full-pipeline", is_flag=True, default=False,
              help="Run ALL planning phases (Council, Research, PE, Architect, Lead)")
@click.option("--skip", type=str, multiple=True,
              help="Skip specific stages: pre-commit, build, harden, legal, cipr, verify, archive")
@click.option("--legacy-verify", is_flag=True, default=False,
              help="Use legacy verify\u21d4fix loop instead of direct pipeline execution")
@click.option("--verbose", "-v", is_flag=True, default=False,
              help="Verbose output for pipeline stages.")
@click.option("--mode", type=click.Choice(["smart", "quick", "full", "ci", "audit"]),
              default=None,
              help="Pipeline mode: smart (default), quick, full, ci, audit.")
@click.option("--from", "from_stage", type=str, default=None,
              help="Start stage (e.g. navigate, pre-commit, build). Exclusive with --mode and --stage.")
@click.option("--to", "to_stage", type=str, default=None,
              help="End stage (e.g. build, verify, archive). Requires --from. Exclusive with --mode and --stage.")
@click.option("--stage", "single_stage", type=str, default=None,
              help="Run a single stage (e.g. pre_commit). Exclusive with --mode and --from/--to.")
def go(sandbox: str, task: str, budget: int, dry_run: bool, verify: bool,
       archive: bool, viewport: bool, full_pipeline: bool = False,
       skip: tuple[str, ...] = (), legacy_verify: bool = False,
       verbose: bool = False, mode: str | None = None,
       from_stage: str | None = None, to_stage: str | None = None,
       single_stage: str | None = None) -> None:
    """One-command full pipeline: plan → dispatch → spawn → verify → archive.

    Queues soldiers, writes a pipeline manifest file at ~/.hero/pipeline/,
    and outputs sessions_spawn commands for the Communicator to execute.

    Typical flow:
        1. hero go --sandbox X --task "Y"             (this command)
        2. Plans → dispatches soldiers → runs pipeline execution line
        3. Pipeline stages: pre-commit → build → harden → legal → cipr → verify → archive
        4. PipelineExecutor monitors soldier completion
        5. Reports to user
    """
    _ensure_pipeline_dir()

    click.echo("")
    click.echo("=" * 60)
    click.echo("HERO GO — Full Pipeline")
    click.echo("=" * 60)
    click.echo(f"  Sandbox:   {sandbox}")
    click.echo(f"  Task:      {task}")
    click.echo(f"  Budget:    {budget if budget is not None else 'auto'} tokens")
    click.echo(f"  Verify:    {'yes' if verify else 'no'}")
    click.echo(f"  Archive:   {'yes' if archive else 'no'}")
    click.echo(f"  Mode:      {'DRY RUN' if dry_run else 'LIVE'}")
    click.echo("=" * 60)
    click.echo("")

    # Resolve sandbox
    index = IndexState()
    entry = index.get_sandbox(sandbox)
    if not entry:
        raise click.ClickException(f"Sandbox '{sandbox}' not found.")
    sandbox_path = Path(entry["path"])
    if not sandbox_path.exists():
        raise click.ClickException(f"Path does not exist: {sandbox_path}")

    # Generate pipeline ID early (used by brainstorm and worktree phases)
    pipeline_id = f"{sandbox}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Write manifest early so it always exists even if pipeline crashes
    PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
    early_manifest = {
        "pipeline_id": pipeline_id,
        "sandbox": sandbox,
        "task": task,
        "created_at": datetime.now().isoformat(),
        "status": "created",
        "steps": {},
    }
    manifest_path = PIPELINE_DIR / f"{pipeline_id}.json"
    with FileLock("pipeline_manifest"):
        manifest_path.write_text(json.dumps(early_manifest, indent=2))

    # Phase 0: Brainstorm — OPTIONAL for open-ended tasks
    click.echo("── Phase 0: Brainstorm ─────────────────────────")
    _ensure_brainstorm_dir()
    brainstorm_result = None
    if _is_open_ended_task(task):
        click.echo(f"  Open-ended task detected — running brainstorm")
        if not dry_run:
            brainstorm_result = _run_brainstorm(pipeline_id, task, sandbox, sandbox_path)
            click.echo(f"  ✅ Brief written: {brainstorm_result['brief_path']}")
        else:
            click.echo(f"  (would write brainstorm brief)")
    else:
        click.echo(f"  Mechanical task — skipping brainstorm")
    click.echo("")

    # Phase 0b: Worktree — ALWAYS create before any code changes
    click.echo("── Phase 0b: Worktree ──────────────────────────")
    _ensure_worktree_base()
    worktree_path = None
    if not dry_run:
        worktree_path = _create_worktree(sandbox, sandbox_path, pipeline_id)
        if worktree_path:
            click.echo(f"  ✅ Worktree: {worktree_path}")
            click.echo(f"     Branch: hero/{pipeline_id}")
            click.echo(f"     All subsequent phases run inside worktree")
        else:
            click.echo(f"  ⚠ Worktree creation failed — proceeding in original sandbox")
    else:
        click.echo(f"  (would create worktree at {WORKTREE_BASE / sandbox / pipeline_id})")
    click.echo("")

    # Phase 1: Detect project + run analysis
    click.echo("── Phase 1: Analysis ──────────────────────────")
    project = _detect_project_type(sandbox_path)
    click.echo(f"  Project type: {project['type']}")

    analysis_result = None
    if project["analyze_cmd"]:
        click.echo(f"  Running: {' '.join(project['analyze_cmd'])}")
        if not dry_run:
            import time as _time
            analysis_result = _run_analysis(
                project["analyze_cmd"],
                sandbox_path,
                source_globs=project.get("source_globs"),
            )
            if analysis_result.get("cached"):
                age = _time.time() - analysis_result.get("cached_at", 0)
                click.echo(f"  ⚡ Analysis: cached ({age:.0f}s old)")
            elif analysis_result["success"]:
                click.echo(f"  ✅ Analysis: clean")
            else:
                click.echo(f"  ⚠ Analysis: {analysis_result['exit_code']} issues")
        else:
            click.echo(f"  (would run analysis)")
    click.echo("")

    # Get model for soldier (needed by Lead for subtask assignment and fallback)
    soldier_model, _ = get_model_for_role("soldier")

    # ── Dynamic budget estimation ──────────────────────────────────────
    if budget is None:
        # Count source files for project_size
        src_globs = project.get("source_globs") or []
        project_size = 0
        for glob_pattern in src_globs:
            project_size += len(list(sandbox_path.glob(glob_pattern)))
        if project_size == 0:
            # Fallback: count files in src/ or just all files
            src_dir = sandbox_path / "src"
            if src_dir.exists():
                project_size = sum(1 for _ in src_dir.rglob("*"))
            else:
                project_size = sum(1 for _ in sandbox_path.rglob("*"))
        budget = estimate_budget(task, files=[], project_size=project_size)
        click.echo(f"  Auto-estimated budget: {budget} tokens (project size: {project_size} files)")
    click.echo("")

    # Phase 2: LEAD — analyze sandbox, break task into focused subtasks
    click.echo("── Phase 2: Lead Analysis ─────────────────────")
    lead_model, _ = get_model_for_role("lead")
    click.echo(f"  Lead: {lead_model}")

    subtasks = []
    try:
        from hero.commands.orchestrate import _analyze_task, _read_plan, _get_src_map, _estimate_tokens  # type: ignore
        plan_content = _read_plan(sandbox_path)
        src_map = _get_src_map(sandbox_path)
        ts_errors = _get_ts_errors(sandbox_path) if project["type"] in ("electron", "node") else []
        subtasks = _analyze_task(task, ts_errors, sandbox, sandbox_path, soldier_model)
        click.echo(f"  PLAN.md: {'found' if plan_content else 'not found'}")
        click.echo(f"  Source files: {sum(len(v) for v in src_map.values())}")
    except Exception as exc:
        click.echo(f"  ⚠ Lead analysis: {exc}")
        subtasks = []

    if not subtasks:
        # Fallback: one subtask for the whole thing
        click.echo(f"  (no subtasks derived — using whole task)")
        subtasks = [{
            "title": f"[{sandbox}] Execute task",
            "goal": task,
            "files": "auto-detected",
            "model": soldier_model,
        }]

    for i, st in enumerate(subtasks, 1):
        desc = st["goal"][:80] + ("..." if len(st["goal"]) > 80 else "")
        click.echo(f"  [{i}] {st['title']}")
        click.echo(f"      Files: {st['files']}")
        click.echo(f"      Goal: {desc}")
    click.echo("")

    # Phase 3: Dispatch soldiers — one per subtask
    click.echo("── Phase 3: Dispatch ──────────────────────────")
    task_ids = []
    # Use worktree as workdir if available, else original sandbox
    active_workdir = worktree_path if worktree_path else str(sandbox_path)
    if not dry_run:
        for i, st in enumerate(subtasks):
            st_budget = max(1000, budget // len(subtasks))
            st_id = enqueue(
                sandbox=sandbox,
                task=st["goal"],
                model=st.get("model", soldier_model),
                budget=st_budget,
                workdir=active_workdir,
                timeout=600,
                max_tokens=min(st_budget, 20000),
                label=f"{sandbox}-soldier-{i+1}",
            )
            task_ids.append(st_id)
            click.echo(f"  [\u2713] {st_id} — soldier {i+1} queued for '{st['title']}'")
    else:
        click.echo(f"  (would queue {len(subtasks)} soldier(s) for {sandbox})")
    click.echo("")

    # Phase 3b: Generate spawn commands
    click.echo("── Phase 3b: Spawn Commands ────────────────────")
    spawn_entries = []
    if not dry_run:
        from hero.soldier.dispatch import get_task
        for st_id in task_ids:
            t = get_task(st_id)
            if t:
                cmd = get_sessions_spawn_command(t)
                spawn_entries.append({
                    "task_id": st_id,
                    "sandbox": sandbox,
                    "role": "soldier",
                    "model": cmd["model"],
                    "workdir": active_workdir,
                    "sessions_spawn": cmd,
                })
                click.echo(f"  sessions_spawn")
                click.echo(f"    taskName: \"{sandbox}_soldier_{st_id}\"")
                click.echo(f"    model: \"{cmd['model']}\"")
                click.echo(f"    runTimeoutSeconds: {cmd['runTimeoutSeconds']}")

    # ── Mode / stage selection (new flags) ───────────────────────────
    use_new_stage_selection = bool(mode or from_stage or single_stage)

    if use_new_stage_selection:
        # Validate exclusivity
        if mode and (from_stage or to_stage):
            raise click.ClickException("--mode and --from/--to are mutually exclusive")
        if mode and single_stage:
            raise click.ClickException("--mode and --stage are mutually exclusive")
        if single_stage and (from_stage or to_stage):
            raise click.ClickException("--stage and --from/--to are mutually exclusive")

        # Resolve stage ordering
        if mode:
            stage_order = _resolve_mode(mode)
        elif from_stage:
            # Use full stage order, slice from→to
            full_order = _resolve_mode("full")
            try:
                start_idx = full_order.index(from_stage)
            except ValueError:
                raise click.ClickException(
                    f"Unknown stage '{from_stage}'. Known stages: {', '.join(full_order)}"
                )
            if to_stage:
                try:
                    end_idx = full_order.index(to_stage)
                except ValueError:
                    raise click.ClickException(
                        f"Unknown stage '{to_stage}'. Known stages: {', '.join(full_order)}"
                    )
                if end_idx < start_idx:
                    raise click.ClickException(
                        f"--to stage '{to_stage}' comes before --from stage '{from_stage}'"
                    )
                stage_order = full_order[start_idx : end_idx + 1]
            else:
                stage_order = full_order[start_idx:]
        elif single_stage:
            # Run exactly one stage (handle hyphen→underscore alias from CLI)
            full_order = _resolve_mode("full")
            stage_name = single_stage.replace("-", "_")
            if stage_name not in full_order:
                raise click.ClickException(
                    f"Unknown stage '{single_stage}'. Known stages: {', '.join(full_order)}"
                )
            stage_order = [stage_name]
        else:
            stage_order = _resolve_mode("smart")

        click.echo(f"  Mode: {mode or 'custom'} → stages: {' → '.join(stage_order)}")
        click.echo("")
        # --skip operates relative to the resolved stage list
    else:
        # Backward-compatible: traditional stage list
        stage_order = None  # signals "use the old behaviour below"

    # Phase 4: Pipeline Execution Line — direct inline execution
    pipeline_results = {}
    pipeline_passed = True
    skip_set = set(skip)
    if not verify:
        skip_set.add("verify")
    if not archive:
        skip_set.add("archive")

    click.echo("── Phase 4: Pipeline Execution ───────────────")

    if legacy_verify:
        # Legacy Phase 4↔5: Verify⇄Fix loop (preserved for backward compat)
        max_iterations = 3
        verify_task_id = None
        fix_task_id = None
        fix_model = _get_escalation_model("tier1_to_tier2") or soldier_model
        verify_fix_loop_info = {
            "iterations": 0,
            "circuit_breaker_triggered": False,
            "final_status": "pending",
            "tasks": [],
        }
        click.echo("── Phase 4: Legacy Verify⇄Fix Loop ─" + "─" * 32)
        click.echo(f"  Max iterations: {max_iterations}")
        click.echo(f"  Circuit breaker: same errors persist across 2 consecutive iterations")
        click.echo(f"  Fix model: {fix_model}")
        for iteration in range(max_iterations):
            click.echo(f"")
            click.echo(f"  Iteration {iteration+1}/{max_iterations}")
            if verify and not dry_run:
                it_verify_id = enqueue(
                    sandbox=sandbox,
                    task=_build_verify_task(project, sandbox, task),
                    role="utility",
                    model=soldier_model,
                    budget=min(budget, 2000),
                    workdir=active_workdir,
                    timeout=300,
                    label=f"{sandbox}-verify-iter{iteration+1}",
                )
                click.echo(f"    [\u2713] {it_verify_id} — verify queued")
                if project.get("analyze_cmd"):
                    click.echo(f"      Analyze: {' '.join(project['analyze_cmd'])}")
                if project.get("build_cmd"):
                    click.echo(f"      Build: {' '.join(project['build_cmd'])}")

                it_fix_id = enqueue(
                    sandbox=sandbox,
                    task=_build_fix_task(sandbox, task, it_verify_id),
                    role="utility",
                    model=fix_model,
                    budget=min(budget, 3000),
                    workdir=active_workdir,
                    timeout=300,
                    label=f"{sandbox}-fix-iter{iteration+1}",
                )
                click.echo(f"    [\u2713] {it_fix_id} — fix queued")

                verify_fix_loop_info["tasks"].append({
                    "iteration": iteration + 1,
                    "verify_task_id": it_verify_id,
                    "fix_task_id": it_fix_id,
                })

                # Keep last iteration IDs for backward compatibility
                verify_task_id = it_verify_id
                fix_task_id = it_fix_id
                verify_fix_loop_info["iterations"] = iteration + 1

            elif verify:
                click.echo(f"    (would queue verify+fix iteration {iteration+1})")

        verify_fix_loop_info["final_status"] = (
            "queued" if verify_task_id else "dry_run"
        )
        click.echo("")
        click.echo(f"  → Planned {verify_fix_loop_info['iterations']} iteration(s) in manifest")

        # Legacy Phase 5: Archive — enqueue an Archivist task
        archive_task_id = None
        journal_path = PIPELINE_DIR / pipeline_id / "journal.md"
        click.echo("── Phase 5: Archive (legacy) ──────────────")
        if archive and not dry_run:
            _write_journal_entry(journal_path, "Pipeline Start",
                                 f"Task: {task}\nSandbox: {sandbox}")
            _write_journal_entry(journal_path, "Phase 0 — Brainstorm",
                                 brainstorm_result.get("status", "skipped") if brainstorm_result else "skipped")
            if brainstorm_result:
                _write_journal_entry(journal_path, "  Brief", brainstorm_result.get("brief_path", ""))
            _write_journal_entry(journal_path, "Phase 0b — Worktree",
                                 f"Path: {worktree_path}" if worktree_path else "Skipped (dry-run or failed)")
            _write_journal_entry(journal_path, "Phase 1 — Analysis",
                                 f"Project type: {project['type']}" + ("\n" + str(analysis_result) if analysis_result else ""))
            _write_journal_entry(journal_path, "Phase 2 — Lead",
                                 f"Subtasks generated: {len(subtasks)}")
            _write_journal_entry(journal_path, "Phase 3 — Dispatch",
                                 f"Soldiers queued: {len(task_ids)}")
            archive_prompt = _build_archive_task(sandbox, task, sandbox_path)
            archive_task_id = enqueue(
                sandbox=sandbox,
                task=archive_prompt,
                role="archivist",
                model=get_model_for_role("archivist")[0],
                budget=min(budget, 1000),
                workdir=str(sandbox_path),
                timeout=120,
                label=f"{sandbox}-archive",
            )
            click.echo(f"  [\u2713] {archive_task_id} — archivist queued")
            click.echo(f"    - Journal: {journal_path}")
            click.echo(f"    - Consolidates into sandbox memory on completion")
        elif archive:
            click.echo(f"  (would queue archivist task)")
        else:
            click.echo(f"  Skipped")
        click.echo("")
    else:
        # ── Pipeline execution line — direct inline stages ─────────
        # Build the stage list: use custom order if set, else fallback
        if stage_order:
            _stage_list = [(s,) for s in stage_order]
        else:
            _stage_list = [
                ("navigate",),
                ("pre_commit",),
                ("build",),
                ("harden",),
                ("legal",),
                ("cipr",),
                ("verify",),
                ("archive",),
            ]

        if dry_run:
            click.echo(f"  Pipeline stages (dry-run):")
            for (stage_name,) in _stage_list:
                skipped = stage_name in skip_set
                marker = "\u23ED" if skipped else "\u00B7"
                click.echo(f"    {marker} {stage_name}")
        else:
            for (stage_name,) in _stage_list:
                if stage_name in skip_set:
                    click.echo(f"  \u23ED [skip] {stage_name}")
                    continue

                click.echo(f"  Running {stage_name}...")
                try:
                    if stage_name == "archive":
                        result = _run_stage_safe(
                            stage_name, sandbox_path, verbose=verbose,
                            pipeline_id=pipeline_id, task=task,
                            stage_scores=pipeline_results,
                        )
                    else:
                        result = _run_stage_safe(
                            stage_name, sandbox_path, verbose=verbose,
                        )
                except Exception as e:
                    click.echo(f"  \U0001f534 {stage_name}: EXCEPTION — {e}")
                    pipeline_results[stage_name] = {
                        "score": 0, "status": "fail", "passed": False,
                        "error": str(e),
                    }
                    pipeline_passed = False
                    break

                pipeline_results[stage_name] = result
                score = result.get("score", 0)
                status = result.get("status", "fail")

                if status == "fail":
                    click.echo(f"  \U0001f534 {stage_name}: {score}/100 — FAILED (blocking pipeline)")
                    pipeline_passed = False
                    break
                elif status == "warn":
                    click.echo(f"  \U0001f7e1 {stage_name}: {score}/100 — WARN (continuing)")
                else:
                    click.echo(f"  \U0001f7e2 {stage_name}: {score}/100 — PASS")

        click.echo("")
        if not dry_run:
            overall = "PASSED" if pipeline_passed else "FAILED"
            click.echo(f"  Pipeline: {overall}")
            click.echo("")

    # Phase 5: Report
    click.echo("── Phase 5: Report ────────────────────────────")
    click.echo(f"  Communicator summarises to user:")
    click.echo(f"  - Files changed (git diff --stat)")
    click.echo(f"  - Build status")
    click.echo(f"  - Issues found")
    click.echo("")

    # Build and write pipeline manifest
    manifest = {
        "pipeline_id": pipeline_id,
        "sandbox": sandbox,
        "task": task,
        "project_type": project["type"],
        "created_at": datetime.now().isoformat(),
        "dry_run": dry_run,
        "full_pipeline": full_pipeline,
        "steps": {
            "brainstorm": {
                "status": "completed" if brainstorm_result else "skipped",
                "brief_path": brainstorm_result.get("brief_path") if brainstorm_result else None,
            },
            "worktree": {
                "status": "created" if worktree_path else "skipped",
                "path": worktree_path,
                "branch": f"hero/{pipeline_id}" if worktree_path else None,
            },
            "analysis": {
                "status": "done" if not dry_run else "dry_run",
                "result": analysis_result,
            },
            "dispatch": {
                "status": "done" if task_ids else "dry_run",
                "task_ids": task_ids,
            },
            "spawn": {
                "status": "ready",
                "commands": spawn_entries,
            },
            "pipeline_execution": {
                "status": ("completed" if pipeline_passed else "failed") if not dry_run else "planned",
                "passed": pipeline_passed,
                "stages": {
                    stage_name: {
                        "score": r.get("score", 0),
                        "status": r.get("status", "fail"),
                        "passed": r.get("passed", r.get("status", "") in ("pass", "warn")),
                        "stage_scores": r.get("stage_scores", {}),
                    }
                    for stage_name, r in pipeline_results.items()
                },
            },
            "report": {
                "status": "pending",
            },
        },
        "pipeline_execution": {
            "status": ("completed" if pipeline_passed else "failed") if not dry_run else "planned",
            "passed": pipeline_passed,
            "stages": {
                stage_name: {
                    "score": r.get("score", 0),
                    "status": r.get("status", "fail"),
                    "passed": r.get("passed", r.get("status", "") in ("pass", "warn")),
                    "stage_scores": r.get("stage_scores", {}),
                }
                for stage_name, r in pipeline_results.items()
            },
        },
        "communicator_instructions": (
            f"Soldier tasks: {len(task_ids)}\n"
            f"Pipeline execution: {'completed' if pipeline_passed else 'failed'}\n"
            "\n"
            "EXECUTION ORDER:\n"
            "1. → spawn soldiers (one per subtask)\n"
            "2. WAIT for soldiers to complete\n"
            "3. Report results to user"
        ),
    }

    # In legacy-verify mode, also include old manifest fields
    if legacy_verify:
        manifest["steps"].setdefault("verify", {
            "status": "queued" if verify_task_id else "dry_run",
            "enabled": verify,
            "analyze_cmd": project.get("analyze_cmd"),
            "analyzer": project.get("analyzer"),
            "build_cmd": project.get("build_cmd"),
        })
        manifest["steps"].setdefault("fix", {
            "status": "queued" if fix_task_id else "dry_run",
            "enabled": bool(fix_task_id),
            "task_id": fix_task_id,
            "model": fix_model if fix_task_id else None,
            "escalation": _get_escalation_model("tier1_to_tier2"),
        })
        manifest["steps"].setdefault("verify_fix_loop", {
            "iterations": verify_fix_loop_info["iterations"],
            "circuit_breaker_triggered": verify_fix_loop_info["circuit_breaker_triggered"],
            "final_status": verify_fix_loop_info["final_status"],
            "tasks": verify_fix_loop_info["tasks"],
        })
        manifest["archive"] = {
            "status": "queued" if archive_task_id else "dry_run",
            "enabled": archive,
            "journal_path": str(journal_path) if archive_task_id else None,
        }

    if not dry_run:
        # Update the early manifest with final status
        with FileLock("pipeline_manifest"):
            manifest_path.write_text(json.dumps(manifest, indent=2))
        click.echo(f"  Pipeline manifest: {manifest_path}")

        # ── Auto-clean: remove zombie dispatch tasks ──────────────
        from hero.commands.clean import clean as clean_cmd
        try:
            clean_cmd.callback(sandbox=None, age=120, dry_run=False)
        except Exception:
            pass  # Non-fatal

        # ── Run pipeline executor for soldier-phase monitoring ──────────
        try:
            from hero.pipeline.executor import PipelineExecutor
            executor = PipelineExecutor(manifest_path)
            result = executor.run(poll_interval=5, max_wait=600)
            click.echo(f"  Pipeline result: {result.status}")
        except Exception as e:
            click.echo(f"  Pipeline executor error: {e}")

    click.echo("")

    # Summary
    click.echo("=" * 60)
    if dry_run:
        click.echo("DRY RUN — no changes made. Run without --dry-run to execute.")
    else:
        click.echo(f"PIPELINE READY — {pipeline_id}")
        click.echo("Communicator: read manifest and execute spawn/verify/archive/report")
    click.echo("=" * 60)

    # ── Optional: open viewport dashboard after pipeline setup ────────
    if viewport:
        click.echo("\nOpening HERO Viewport…")
        from hero.viewport.renderer import render_live
        try:
            render_live(console=None, sandbox_filter=sandbox)
        except Exception as exc:  # pragma: no cover — interactive only
            click.echo(f"  [warn] Viewport exited: {exc}")
