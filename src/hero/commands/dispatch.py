"""hero dispatch — List and manage tasks for OpenClaw sessions_spawn.

The OpenClaw agent reads this queue and executes tasks via sessions_spawn
with per-task model selection (unlike Hermes which ignores model overrides).
"""

from __future__ import annotations

import json

import click

from hero.soldier.dispatch import (
    list_pending, list_all, clear_completed, 
    get_sessions_spawn_command, get_task
)


@click.group(invoke_without_command=True)
@click.option("--spawn", "-s", is_flag=True, help="Show ready-to-spawn commands.")
@click.option("--count", "-c", type=int, default=0, help="Max tasks to show (0 = all).")
@click.pass_context
def dispatch(ctx: click.Context, spawn: bool, count: int) -> None:
    """Manage the dispatch queue for OpenClaw execution.

    Tasks include per-model assignments for sessions_spawn.
    
    Run without subcommands to list pending tasks with spawn info.
    """
    if ctx.invoked_subcommand is not None:
        return
    
    if spawn:
        _show_spawn_ready(count)
    else:
        _show_pending(count)


@dispatch.command("list")
@click.option("--spawn", "-s", is_flag=True, help="Show sessions_spawn commands.")
def list_cmd(spawn: bool) -> None:
    """List all pending tasks."""
    if spawn:
        _show_spawn_ready()
    else:
        _show_pending()


@dispatch.command("all")
def all_cmd() -> None:
    """List all tasks (any status)."""
    tasks = list_all()
    if not tasks:
        click.echo("No tasks in dispatch queue.")
        return

    click.echo(f"\nDispatch Queue ({len(tasks)} tasks):")
    click.echo("=" * 60)
    for t in tasks:
        status_icon = {
            "pending": "⏳",
            "dispatched": "🔄",
            "completed": "✅",
            "failed": "❌",
        }.get(t["status"], "❓")
        click.echo(f"  {status_icon} {t['task_id']}  {t['sandbox']:15s}  {t['role']:12s}  {t['model'][:25]}")
        click.echo(f"     Task: {t['task'][:80]}")
        if t.get("result"):
            click.echo(f"     Result: {t['result'][:80]}")
        click.echo()


@dispatch.command("spawn")
@click.option("--dry-run", is_flag=True, help="Show what would be spawned without executing.")
def spawn_cmd(dry_run: bool) -> None:
    """Read pending tasks and output sessions_spawn commands as JSON.

    Output is a JSON array of objects, each with:
      - task_id: the dispatch task ID
      - sandbox: sandbox name
      - role: army role
      - sessions_spawn: dict ready for OpenClaw sessions_spawn tool

    Pipe this to the OpenClaw agent for execution.
    """
    pending = list_pending()
    if not pending:
        click.echo('[]')
        click.echo("No pending tasks.", err=True)
        return

    spawn_commands = []
    for t in pending:
        cmd = get_sessions_spawn_command(t)
        spawn_commands.append({
            "task_id": t["task_id"],
            "sandbox": t["sandbox"],
            "role": t["role"],
            "sessions_spawn": cmd,
        })
        if not dry_run:
            # Mark as dispatched
            from hero.soldier.dispatch import mark_dispatched
            mark_dispatched(t["task_id"])

    click.echo(json.dumps(spawn_commands, indent=2))

    if not dry_run:
        click.echo(f"\n{len(pending)} task(s) marked as dispatched.", err=True)
        click.echo(f"Execute with: hero dispatch list --spawn", err=True)


@dispatch.command("clear")
def clear_cmd() -> None:
    """Remove completed/failed tasks from queue."""
    removed = clear_completed()
    click.echo(f"Cleared {removed} completed/failed tasks.")


def _show_pending(max_count: int = 0) -> None:
    """Display pending tasks with model info for OpenClaw."""
    pending = list_pending()
    if not pending:
        click.echo("No pending tasks. Queue is empty.")
        return

    if max_count > 0:
        pending = pending[:max_count]

    click.echo(f"\n{'=' * 60}")
    click.echo(f"PENDING TASKS ({len(pending)}) — OpenClaw-ready:")
    click.echo(f"{'=' * 60}")

    for i, t in enumerate(pending, 1):
        click.echo(f"\n[{i}] {t['task_id']} — {t['sandbox']} / {t['role']}")
        click.echo(f"    Model: {t['model']}")
        click.echo(f"    Label: {t['label']}")
        click.echo(f"    Timeout: {t['timeout']}s")
        click.echo(f"    Task: {t['task']}")
        click.echo()
        click.echo(f"    → sessions_spawn ready:")
        cmd = get_sessions_spawn_command(t)
        click.echo(f"      sessions_spawn")
        click.echo(f"        label: \"{cmd['label']}\"")
        click.echo(f"        model: \"{cmd['model']}\"")
        click.echo(f"        mode: \"{cmd['mode']}\"")
        click.echo(f"        runtime: \"{cmd['runtime']}\"")
        click.echo(f"        runTimeoutSeconds: {cmd['runTimeoutSeconds']}")

    click.echo(f"\n{'=' * 60}")
    click.echo("To execute via OpenClaw, use the sessions_spawn parameters above.")
    click.echo(f"{'=' * 60}\n")


def _show_spawn_ready(max_count: int = 0) -> None:
    """Show tasks formatted as sessions_spawn JSON commands."""
    pending = list_pending()
    if not pending:
        click.echo("[]")
        return

    if max_count > 0:
        pending = pending[:max_count]

    spawn_commands = []
    for t in pending:
        cmd = get_sessions_spawn_command(t)
        spawn_commands.append({
            "task_id": t["task_id"],
            "sandbox": t["sandbox"],
            "role": t["role"],
            "sessions_spawn": cmd,
        })

    click.echo(json.dumps(spawn_commands, indent=2))


if __name__ == "__main__":
    dispatch()