"""hero pipeline — Execute and monitor deployment pipelines.

Subcommands:

- ``hero pipeline run <id>`` — execute a pipeline via PipelineExecutor
- ``hero pipeline status <id>`` — show current state from manifest
- ``hero pipeline list`` — list all pipeline manifests

Pipelines are created by ``hero go`` and stored as JSON manifests at
``~/.hero/pipeline/<pipeline_id>.json``.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import click

from hero.pipeline.executor import PIPELINE_DIR, PipelineExecutor

# ── New stages layer imports (graceful fallback) ──────────────────────
try:
    import hero.stages as _stages
    _stages_run = _stages.run_stage
    _stages_resolve = _stages.resolve_mode
except ImportError:  # pragma: no cover — optional dependency
    _stages = None
    _stages_run = None
    _stages_resolve = None

# ── Mode → stage mapping (fallback when hero.stages unavailable) ─────
_PIPELINE_MODE_STAGES = {
    "smart": ["navigate", "pre_commit", "build", "verify", "archive"],
    "quick": ["navigate", "pre_commit", "build"],
    "full": [
        "navigate", "pre_commit", "build", "harden",
        "legal", "cipr", "verify", "archive",
    ],
    "ci": ["pre_commit", "build", "cipr"],
    "audit": ["navigate", "pre_commit", "harden", "legal"],
}


def _resolve_pipeline_mode(mode: str) -> list[str]:
    """Resolve a mode name to an ordered stage list."""
    if _stages_resolve:
        try:
            return _stages_resolve(mode)
        except (ValueError, KeyError) as exc:
            raise click.ClickException(str(exc))
    stages = _PIPELINE_MODE_STAGES.get(mode)
    if stages is None:
        raise click.ClickException(
            f"Unknown mode '{mode}'. Choose from: {', '.join(sorted(_PIPELINE_MODE_STAGES.keys()))}"
        )
    return list(stages)

# ── Helpers ─────────────────────────────────────────────────────────────


def _render_progress(
    soldiers: list[dict],
    status: str,
    sandbox: str,
    pipeline_id: str,
    elapsed: float,
) -> None:
    """Render a live progress table to stdout."""
    status_icon = {"running": "▶", "completed": "✅", "failed": "❌", "verify_failed": "⚠"}.get(
        status, "⏳"
    )

    click.echo(f"\n{status_icon} Pipeline {pipeline_id[:8]} ({sandbox}) — {status}")
    click.echo(f"  Elapsed: {elapsed:.0f}s")
    click.echo("  " + "─" * 50)

    icons = {
        "completed": "✅",
        "failed": "❌",
        "running": "▶",
        "dispatched": "⏳",
        "pending": "⬜",
        "unknown": "❓",
    }

    for s in soldiers:
        icon = icons.get(s["status"], "❓")
        label = s.get("label", s["task_id"])[:50]
        click.echo(f"  {icon} {s['task_id'][:8]} ({label}): {s['status']}")

    click.echo("")


def _load_manifest(pipeline_id: str) -> dict | None:
    """Load a pipeline manifest by ID (with or without .json suffix)."""
    path = PIPELINE_DIR / pipeline_id
    if not path.suffix:
        path = path.with_suffix(".json")
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    # Try with full path as given
    alt = Path(pipeline_id)
    if alt.exists() and alt.suffix == ".json":
        try:
            return json.loads(alt.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _collect_all_pipelines() -> list[dict]:
    """Return all pipeline manifests sorted by creation time (newest first)."""
    if not PIPELINE_DIR.exists():
        return []

    manifests = []
    for f in sorted(PIPELINE_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            data["_path"] = str(f)
            manifests.append(data)
        except (json.JSONDecodeError, OSError):
            pass

    manifests.sort(
        key=lambda m: m.get("created_at", ""),
        reverse=True,
    )
    return manifests


# ── Inline pipeline execution (--sandbox + --task) ────────────────────


def _run_inline(
    sandbox: str,
    task: str,
    mode: str | None = None,
    from_stage: str | None = None,
    to_stage: str | None = None,
    single_stage: str | None = None,
    verbose: bool = False,
    dry_run: bool = False,
) -> None:
    """Run pipeline stages inline — no soldier dispatch.

    Like ``hero go`` but skips planning/dispatch phases.
    Resolves the stage list from mode/from-to/stage flags, then runs each
    stage sequentially using ``hero.stages.run_stage()`` (or fallback).
    """
    from hero.state.index import IndexState

    # Resolve sandbox path
    index = IndexState()
    entry = index.get_sandbox(sandbox)
    if not entry:
        raise click.ClickException(f"Sandbox '{sandbox}' not found.")
    sandbox_path = Path(entry["path"])
    if not sandbox_path.exists():
        raise click.ClickException(f"Path does not exist: {sandbox_path}")

    # Resolve stage ordering
    if mode:
        if from_stage or to_stage:
            raise click.ClickException("--mode and --from/--to are mutually exclusive")
        if single_stage:
            raise click.ClickException("--mode and --stage are mutually exclusive")
        stage_order = _resolve_pipeline_mode(mode)
    elif from_stage:
        if single_stage:
            raise click.ClickException("--stage and --from/--to are mutually exclusive")
        full_order = _resolve_pipeline_mode("full")
        try:
            start_idx = full_order.index(from_stage)
        except ValueError:
            raise click.ClickException(
                f"Unknown stage '{from_stage}'. Known: {', '.join(full_order)}"
            )
        if to_stage:
            try:
                end_idx = full_order.index(to_stage)
            except ValueError:
                raise click.ClickException(
                    f"Unknown stage '{to_stage}'. Known: {', '.join(full_order)}"
                )
            if end_idx < start_idx:
                raise click.ClickException(
                    f"--to stage '{to_stage}' comes before --from stage '{from_stage}'"
                )
            stage_order = full_order[start_idx : end_idx + 1]
        else:
            stage_order = full_order[start_idx:]
    elif single_stage:
        full_order = _resolve_pipeline_mode("full")
        stage_name = single_stage.replace("-", "_")
        if stage_name not in full_order:
            raise click.ClickException(
                f"Unknown stage '{single_stage}'. Known: {', '.join(full_order)}"
            )
        stage_order = [stage_name]
    else:
        stage_order = _resolve_pipeline_mode("smart")

    # Display
    click.echo("")
    click.echo("=" * 60)
    click.echo("HERO PIPELINE RUN (inline)")
    click.echo("=" * 60)
    click.echo(f"  Sandbox:   {sandbox}")
    click.echo(f"  Task:      {task}")
    click.echo(f"  Mode:      {mode or 'custom'}")
    click.echo(f"  Stages:    {' → '.join(stage_order)}")
    click.echo(f"  Dry run:   {'yes' if dry_run else 'no'}")
    click.echo("=" * 60)
    click.echo("")

    if dry_run:
        click.echo("Pipeline stages (dry-run):")
        for s in stage_order:
            click.echo(f"  · {s}")
        click.echo("\nDRY RUN — no changes made.")
        return

    # Run stages sequentially
    pipeline_results: dict = {}
    pipeline_passed = True

    for stage_name in stage_order:
        click.echo(f"  Running {stage_name}...")
        try:
            if stage_name == "archive":
                if _stages_run:
                    result = _stages_run(
                        stage_name, sandbox_path, verbose=verbose,
                        pipeline_id=None, task=task,
                        stage_scores=pipeline_results,
                    )
                else:
                    from hero.commands.archive import run_archive as _arc
                    result = _arc(
                        sandbox_path, verbose=verbose,
                        pipeline_id=None, task=task,
                        stage_scores=pipeline_results,
                    )
            else:
                if _stages_run:
                    result = _stages_run(stage_name, sandbox_path, verbose=verbose)
                else:
                    # Fallback through per-stage commands
                    result = _run_fallback_stage(stage_name, sandbox_path, verbose)
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
            click.echo(f"  \U0001f534 {stage_name}: {score}/100 — FAILED (blocking)")
            pipeline_passed = False
            break
        elif status == "warn":
            click.echo(f"  \U0001f7e1 {stage_name}: {score}/100 — WARN (continuing)")
        else:
            click.echo(f"  \U0001f7e2 {stage_name}: {score}/100 — PASS")

    click.echo("")
    overall = "PASSED" if pipeline_passed else "FAILED"
    click.echo(f"  Pipeline: {overall}")
    click.echo(f"  Stages completed: {len(pipeline_results)}/{len(stage_order)}")
    click.echo("")

    if not pipeline_passed:
        raise SystemExit(1)


def _run_fallback_stage(name: str, sandbox_path: Path, verbose: bool) -> dict:
    """Run a single stage via direct import when hero.stages is unavailable."""
    # Navigate doesn't exist as a standalone command yet — skip silently
    if name == "navigate":
        return {"score": 100, "status": "pass", "passed": True}
    if name == "pre_commit":
        from hero.commands.pre_commit import run_pre_commit
        return run_pre_commit(sandbox_path, verbose=verbose)
    if name == "build":
        from hero.commands.build import run_build
        return run_build(sandbox_path, verbose=verbose)
    if name == "harden":
        from hero.commands.harden import run_harden
        return run_harden(sandbox_path, verbose=verbose)
    if name == "legal":
        from hero.commands.legal import run_legal
        return run_legal(sandbox_path, verbose=verbose)
    if name == "cipr":
        from hero.commands.cipr import run_cipr
        return run_cipr(sandbox_path, verbose=verbose)
    if name == "verify":
        from hero.commands.verify import run_verify
        return run_verify(sandbox_path, verbose=verbose)
    if name == "archive":
        from hero.commands.archive import run_archive
        return run_archive(sandbox_path, verbose=verbose)
    raise click.ClickException(f"Unknown stage: {name}")


# ── CLI Group ───────────────────────────────────────────────────────────


@click.group()
def pipeline() -> None:
    """Execute and monitor deployment pipelines."""


# ── hero pipeline run ───────────────────────────────────────────────────


@pipeline.command()
@click.argument("pipeline_id", required=False)
@click.option("--sandbox", type=str, default=None, help="Target sandbox name (for inline execution).")
@click.option("--task", type=str, default=None, help="Task description (for inline execution).")
@click.option("--mode", type=click.Choice(["smart", "quick", "full", "ci", "audit"]),
              default=None, help="Pipeline mode: smart, quick, full, ci, audit.")
@click.option("--from", "from_stage", type=str, default=None,
              help="Start stage. Exclusive with --mode and --stage.")
@click.option("--to", "to_stage", type=str, default=None,
              help="End stage. Requires --from. Exclusive with --mode and --stage.")
@click.option("--stage", "single_stage", type=str, default=None,
              help="Run a single stage. Exclusive with --mode and --from/--to.")
@click.option(
    "--poll-interval",
    default=5,
    show_default=True,
    help="Seconds between dispatch queue polls.",
)
@click.option(
    "--max-wait",
    default=3600,
    show_default=True,
    help="Maximum seconds to wait before timeout.",
)
@click.option("--no-progress", is_flag=True, help="Suppress live progress output.")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Verbose output for pipeline stages.")
@click.option("--dry-run", is_flag=True, help="Plan without executing.")
def run(
    pipeline_id: str | None,
    sandbox: str | None,
    task: str | None,
    mode: str | None,
    from_stage: str | None,
    to_stage: str | None,
    single_stage: str | None,
    poll_interval: int,
    max_wait: int,
    no_progress: bool,
    verbose: bool,
    dry_run: bool,
) -> None:
    """Run a pipeline by ID, or execute stages inline via --sandbox/--task.

    \b
    Two modes:
    1. ``hero pipeline run <pipeline_id>`` — execute a manifest (existing behaviour)
    2. ``hero pipeline run --sandbox X --task Y`` — inline execution, no soldiers

    With --sandbox/--task, runs stages directly (like hero go but without
    the planning/soldier dispatch phases).
    """
    # ── Inline execution mode (--sandbox + --task) ──────────────────
    if sandbox and task:
        _run_inline(
            sandbox=sandbox,
            task=task,
            mode=mode,
            from_stage=from_stage,
            to_stage=to_stage,
            single_stage=single_stage,
            verbose=verbose,
            dry_run=dry_run,
        )
        return

    # ── Existing pipeline run behaviour (pipeline_id required) ──────
    if not pipeline_id:
        raise click.ClickException(
            "Either provide a PIPELINE_ID or use --sandbox + --task for inline execution."
        )

    # Resolve manifest path
    manifest_path = PIPELINE_DIR / pipeline_id
    if not manifest_path.suffix:
        manifest_path = manifest_path.with_suffix(".json")
    if not manifest_path.exists():
        raise click.ClickException(
            f"Pipeline manifest not found: {manifest_path}\n"
            f"   Run `hero go --sandbox X --task Y` first to create one."
        )

    # Load and validate
    manifest = json.loads(manifest_path.read_text())
    click.echo("")
    click.echo("=" * 60)
    click.echo("HERO PIPELINE RUN")
    click.echo("=" * 60)
    click.echo(f"  Pipeline:  {manifest.get('pipeline_id', '?')[:12]}")
    click.echo(f"  Sandbox:   {manifest.get('sandbox', '?')}")
    click.echo(f"  Task:      {manifest.get('task', '?')[:80]}")
    click.echo(f"  Poll:      every {poll_interval}s (max {max_wait}s)")
    auto_commit = manifest.get("auto_commit", False)
    click.echo(f"  Git:       {'auto-commit ON' if auto_commit else 'auto-commit OFF'}")
    click.echo("=" * 60)
    click.echo("")

    # Create executor and run
    executor = PipelineExecutor(manifest_path)

    if no_progress:
        result = executor.run(poll_interval=poll_interval, max_wait=max_wait)
    else:
        click.echo("Pipeline running — poll interval every {poll_interval}s")
        click.echo("")
        start_ts = time.time()

        # Initial display
        _render_progress(
            executor.soldiers,
            "running",
            executor.sandbox,
            executor.pipeline_id,
            0,
        )

        result = executor.run(poll_interval=min(poll_interval, 2), max_wait=max_wait)

        elapsed = time.time() - start_ts
        _render_progress(
            result.soldiers,
            result.status,
            result.sandbox,
            result.pipeline_id,
            elapsed,
        )

    # ── Summary ─────────────────────────────────────────────────────────
    click.echo("")
    click.echo("─" * 60)
    click.echo("SUMMARY")
    click.echo("─" * 60)

    status_icons = {
        "completed": "✅",
        "failed": "❌",
        "verify_failed": "⚠",
        "running": "▶",
    }
    icon = status_icons.get(result.status, "❓")
    click.echo(f"  Status:     {icon} {result.status}")
    click.echo(f"  Pipeline:   {result.pipeline_id[:12]}")
    click.echo(f"  Sandbox:    {result.sandbox}")
    click.echo(f"  Task:       {result.task[:80]}")

    if result.soldiers:
        total = len(result.soldiers)
        done = sum(1 for s in result.soldiers if s["status"] == "completed")
        failed = sum(1 for s in result.soldiers if s["status"] == "failed")
        click.echo(f"  Soldiers:   {done}/{total} completed")
        if failed:
            click.echo(f"  Failures:   {failed}")

    if result.verify_status:
        verify_icon = "✅" if result.verify_status == "passed" else "❌"
        click.echo(f"  Verify:     {verify_icon} {result.verify_status}")

    if result.archive_status:
        archive_icon = "✅" if result.archive_status == "completed" else "⏭"
        click.echo(f"  Archive:    {archive_icon} {result.archive_status}")

    if result.completed_at:
        click.echo(f"  Completed:  {result.completed_at}")

    click.echo(f"  Manifest:   {result.manifest_path}")
    click.echo("")

    # ── Exit code ───────────────────────────────────────────────────────
    if result.status == "completed":
        click.echo("✅ Pipeline completed successfully.")
    elif result.status == "verify_failed":
        click.echo("⚠ Pipeline completed with verify failures.")
        raise SystemExit(2)
    else:
        click.echo("❌ Pipeline failed.")
        raise SystemExit(1)


# ── hero pipeline status ────────────────────────────────────────────────


@pipeline.command()
@click.argument("pipeline_id")
def status(pipeline_id: str) -> None:
    """Show current state of a pipeline from its manifest."""
    manifest = _load_manifest(pipeline_id)
    if manifest is None:
        raise click.ClickException(
            f"Pipeline manifest not found for id '{pipeline_id}'.\n"
            f"  Looked in: {PIPELINE_DIR / pipeline_id}.json"
        )

    status_val = manifest.get("status", "unknown")
    status_icons = {
        "running": "▶",
        "completed": "✅",
        "failed": "❌",
        "verify_failed": "⚠",
        "dispatched": "⏳",
    }
    icon = status_icons.get(status_val, "❓")

    click.echo("")
    click.echo(f"{icon} Pipeline {manifest.get('pipeline_id', '?')[:12]}")
    click.echo("  " + "─" * 50)
    click.echo(f"  Status:    {status_val}")
    click.echo(f"  Sandbox:   {manifest.get('sandbox', '?')}")
    click.echo(f"  Task:      {manifest.get('task', '?')[:80]}")

    soldiers = manifest.get("soldiers", [])
    if soldiers:
        total = len(soldiers)
        done = sum(1 for s in soldiers if s.get("status") == "completed")
        failed = sum(1 for s in soldiers if s.get("status") == "failed")
        click.echo(f"  Soldiers:  {done}/{total} completed", nl=False)
        if failed:
            click.echo(f", {failed} failed")
        else:
            click.echo("")

    if manifest.get("verify_status"):
        click.echo(f"  Verify:    {manifest['verify_status']}")
    if manifest.get("archive_status"):
        click.echo(f"  Archive:   {manifest['archive_status']}")
    if manifest.get("started_at"):
        click.echo(f"  Started:   {manifest['started_at']}")
    if manifest.get("completed_at"):
        click.echo(f"  Completed: {manifest['completed_at']}")
    if manifest.get("original_branch"):
        click.echo(f"  Orig br:   {manifest['original_branch']}")
    if manifest.get("pipeline_branch"):
        click.echo(f"  Pipe br:   {manifest['pipeline_branch']}")
    click.echo(f"  Created:   {manifest.get('created_at', '?')}")
    click.echo(f"  Path:      {manifest.get('_path', PIPELINE_DIR / pipeline_id)}")
    click.echo("")

    # Show soldier detail
    if soldiers:
        click.echo("Soldiers:")
        for s in soldiers:
            icon = {"completed": "✅", "failed": "❌", "running": "▶", "pending": "⬜"}.get(
                s.get("status", ""), "❓"
            )
            tid = s.get("task_id", "?")[:8]
            label = s.get("label", "")[:40]
            result_preview = ""
            if s.get("result") and isinstance(s["result"], str):
                result_preview = s["result"][:60]
            click.echo(f"  {icon} {tid} ({label}): {s.get('status', '?')}")
            if result_preview:
                click.echo(f"      ↳ {result_preview}")
        click.echo("")


# ── hero pipeline list ──────────────────────────────────────────────────


@pipeline.command(name="list")
def list_pipelines() -> None:
    """List all pipeline manifests in ~/.hero/pipeline/."""
    manifests = _collect_all_pipelines()

    if not manifests:
        click.echo("No pipeline manifests found.")
        click.echo(f"  Looked in: {PIPELINE_DIR}")
        click.echo("  Run `hero go --sandbox X --task Y` to create one.")
        return

    click.echo("")
    click.echo("─" * 70)
    click.echo(f"{'PIPELINE':<14} {'SANDBOX':<14} {'STATUS':<14} {'TASK':<28}")
    click.echo("─" * 70)

    for m in manifests:
        pid = m.get("pipeline_id", "?")[:12]
        sandbox = m.get("sandbox", "?")[:13]
        status = m.get("status", "created")[:12]
        task = m.get("task", "?")[:27]

        status_icons = {
            "running": "▶",
            "completed": "✅",
            "failed": "❌",
            "verify_failed": "⚠",
            "dispatched": "⏳",
        }
        icon = status_icons.get(status, " ")
        click.echo(f"  {icon} {pid:<11} {sandbox:<13} {status:<13} {task}")

    click.echo("─" * 70)
    click.echo(f"  {len(manifests)} pipeline(s) total")
    click.echo("")


# ── hero pipeline rollback ────────────────────────────────────────────────


@pipeline.command()
@click.argument("pipeline_id")
def rollback(pipeline_id: str) -> None:
    """Rollback a pipeline: switch to original branch and delete pipeline branch.

    Reads the pipeline manifest for git branch info, then switches back
    to the original branch and removes the pipeline branch.
    """
    manifest = _load_manifest(pipeline_id)
    if manifest is None:
        raise click.ClickException(
            f"Pipeline manifest not found for id '{pipeline_id}'.\n"
            f"  Looked in: {PIPELINE_DIR / pipeline_id}.json"
        )

    original_branch = manifest.get("original_branch")
    pipeline_branch = manifest.get("pipeline_branch")

    if not original_branch or not pipeline_branch:
        raise click.ClickException(
            f"Pipeline '{pipeline_id}' has no git branch information.\n"
            f"  Only pipelines run with auto-commit enabled can be rolled back."
        )

    sandbox_path = Path(manifest.get("sandbox", ""))
    if not sandbox_path.is_absolute():
        sandbox_path = Path.cwd() / sandbox_path

    if not sandbox_path.exists():
        raise click.ClickException(
            f"Sandbox path not found: {sandbox_path}"
        )

    from hero.git.branch import rollback_pipeline

    try:
        rollback_pipeline(sandbox_path, original_branch, pipeline_branch)
    except Exception as exc:
        raise click.ClickException(
            f"Rollback failed: {exc}"
        )

    click.echo(f"\n✅ Rolled back to original branch: {original_branch}\n")
