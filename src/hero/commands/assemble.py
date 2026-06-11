"""hero assemble — Full army pipeline: orchestrate → dispatch → spawn.

Runs the Lead agent to break the task into subtasks, queues soldiers,
then outputs sessions_spawn JSON ready for execution.

Usage:
    hero assemble --sandbox qlearner --task "fix all broken things"
    
Outputs a JSON array of sessions_spawn commands that the
OpenClaw Communicator can execute directly.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import click

from hero.soldier.dispatch import list_pending, get_sessions_spawn_command, mark_dispatched, enqueue
from hero.soldier.spawner import get_model_for_role
from hero.state.index import IndexState


@click.command()
@click.option("--sandbox", required=True, type=str, help="Target sandbox name.")
@click.option("--task", required=True, type=str, help="High-level task description.")
@click.option("--budget", type=int, default=5000, help="Budget per soldier.")
@click.option("--dry-run", is_flag=True, help="Plan without executing.")
def assemble(sandbox: str, task: str, budget: int, dry_run: bool) -> None:
    """Full army pipeline: orchestrate → dispatch → spawn-ready output.

    Runs the Lead agent to analyze the task and sandbox, generates
    focused subtasks, queues soldiers, and outputs sessions_spawn
    commands for OpenClaw execution.
    """
    # Step 1: Orchestrate (plan & queue)
    click.echo("")
    click.echo("=" * 60)
    click.echo("HERO ARMY ASSEMBLY")
    click.echo("=" * 60)
    click.echo(f"  Sandbox:   {sandbox}")
    click.echo(f"  Task:      {task}")
    click.echo(f"  Budget:    {budget} tokens per soldier")
    click.echo(f"  Mode:      {'DRY RUN' if dry_run else 'LIVE'}")
    click.echo("=" * 60)
    click.echo("")

    # Resolve sandbox path
    index = IndexState()
    entry = index.get_sandbox(sandbox)
    if not entry:
        raise click.ClickException(f"Sandbox '{sandbox}' not found.")
    sandbox_path = Path(entry["path"])
    if not sandbox_path.exists():
        raise click.ClickException(f"Path does not exist: {sandbox_path}")

    # Detect project type
    has_pubspec = (sandbox_path / "pubspec.yaml").exists()
    has_package_json = (sandbox_path / "package.json").exists()
    has_cargo = (sandbox_path / "Cargo.toml").exists()

    # Run project-type-specific analysis
    if has_pubspec:
        click.echo("  Detected: Flutter/Dart project")
        _analyze_flutter(sandbox_path, dry_run)
    elif has_package_json:
        click.echo("  Detected: Node/JS project")
        _analyze_node(sandbox_path, dry_run)
    elif has_cargo:
        click.echo("  Detected: Rust project")
    else:
        click.echo("  Project type: unknown")

    # Step 2: Queue the task as a soldier task
    click.echo("")
    click.echo("Queuing task...")
    
    soldier_model, _ = get_model_for_role("soldier")
    task_id = enqueue(
        sandbox=sandbox,
        task=task,
        model=soldier_model,
        budget=budget,
        workdir=str(sandbox_path),
        timeout=600,
        max_tokens=min(budget, 20000),
    )
    click.echo(f"  [\u2713] {task_id} — soldier queued for {sandbox}")
    click.echo("")

    # Step 3: Display queued tasks  
    pending = list_pending()
    if not pending:
        click.echo("  ⚠ No tasks found after queuing.")
        return

    click.echo(f"\n  Army assembled — {len(pending)} soldier(s) ready:")
    for i, t in enumerate(pending, 1):
        click.echo(f"    {i}. [{t['task_id']}] {t['sandbox']}/{t['role']} — {t['model']}")

    # Step 4: Output sessions_spawn commands
    click.echo("")
    click.echo("=" * 60)
    click.echo("DISPATCH ORDERS — sessions_spawn commands")
    click.echo("=" * 60)
    click.echo("")

    spawn_commands = []
    for t in pending:
        cmd = get_sessions_spawn_command(t)
        entry = {
            "task_id": t["task_id"],
            "sandbox": t["sandbox"],
            "role": t["role"],
            "sessions_spawn": cmd,
        }
        spawn_commands.append(entry)

        click.echo(f"  --- {t['task_id']} ---")
        click.echo(f"  sessions_spawn")
        click.echo(f"    label: \"{cmd['label']}\"")
        click.echo(f"    model: \"{cmd['model']}\"")
        click.echo(f"    mode: \"{cmd['mode']}\"")
        click.echo(f"    runtime: \"{cmd['runtime']}\"")
        click.echo(f"    runTimeoutSeconds: {cmd['runTimeoutSeconds']}")
        click.echo(f"    taskName: \"{t['sandbox']}_{t['role']}_{t['task_id']}\"")
        click.echo("")

        if not dry_run:
            mark_dispatched(t["task_id"])

    if not dry_run:
        click.echo(f"  → {len(pending)} task(s) marked as dispatched.")
    click.echo("")
    click.echo("=" * 60)
    click.echo("ARMY ASSEMBLED — deploy with sessions_spawn above")
    click.echo("=" * 60)


def _analyze_flutter(path: Path, dry_run: bool) -> None:
    """Run flutter analyze and report issues."""
    try:
        result = subprocess.run(
            ["flutter", "analyze"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=120,
        )
        lines = result.stdout.strip().splitlines() if result.stdout else []
        err_lines = result.stderr.strip().splitlines() if result.stderr else []

        # Count by severity
        errors = [l for l in lines if l.startswith("error")]
        warnings = [l for l in lines if l.startswith("warning")]
        infos = [l for l in lines if l.startswith("info")]

        click.echo(f"  flutter analyze: {len(errors)} errors, {len(warnings)} warnings, {len(infos)} infos")
        
        if errors and not dry_run:
            click.echo(f"  First error: {errors[0][:80]}")
        elif errors:
            click.echo(f"  (would fix {len(errors)} error(s))")
            
    except subprocess.TimeoutExpired:
        click.echo("  flutter analyze timed out (120s)")
    except FileNotFoundError:
        click.echo("  flutter not found in PATH")


def _analyze_node(path: Path, dry_run: bool) -> None:
    """Run npm check and report issues."""
    try:
        result = subprocess.run(
            ["npm", "run", "build", "--", "--noEmit"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            click.echo("  Build: clean")
        else:
            errors = [l for l in (result.stderr or "").splitlines() if "error" in l.lower()]
            click.echo(f"  Build: {len(errors)} issue(s)")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        click.echo("  Node analysis skipped")
