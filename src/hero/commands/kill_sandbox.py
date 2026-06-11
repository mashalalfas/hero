"""hero kill — Stop a sandbox and put it to sleep.

Safely stops a sandbox by:
1. Setting HEARTBEAT.toon status to "dead"
2. Cancelling pending dispatch tasks (move to DLQ)
3. Preserving sandbox directory and plan.md
4. Saving budget state
5. Updating INDEX.toon

The sandbox remains on disk but won't burn tokens or show as active.
Use 'hero spawn' to wake it up again later.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import click

from hero.state.index import IndexState
from hero.state.sandbox import SandboxState, invalidate_cache
from hero.soldier.dispatch import list_all, mark_failed, DISPATCH_DIR


@click.command()
@click.argument("sandbox")
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt.",
)
@click.option(
    "--archive-tasks",
    is_flag=True,
    default=True,
    help="Move pending tasks to DLQ (default: true).",
)
def kill(sandbox: str, force: bool, archive_tasks: bool) -> None:
    """Put a sandbox to sleep.

    Stops all activity for SANDBOX without deleting it. The sandbox
    directory and plan.md are preserved so it can be resumed later.

    Also cleans up:
    - All dispatch files for the sandbox (any status) → DLQ
    - Pipeline manifests for the sandbox → DLQ

    Examples:
        hero kill galaxy_oblivion       # Put galaxy_oblivion to sleep
        hero kill Melody_MD --force     # Skip confirmation
        hero kill qlearner --no-archive-tasks  # Keep tasks in queue
    """
    # Check if sandbox exists in index
    index = IndexState()
    entry = index.get_sandbox(sandbox)

    if not entry:
        raise click.ClickException(
            f"Sandbox '{sandbox}' not found in INDEX. "
            f"Run 'hero status' to see registered sandboxes."
        )

    # Check current status
    sandbox_state = SandboxState(sandbox)
    state = sandbox_state.load(use_cache=False, include_katana=False)
    current_status = state.get("status", "unknown")

    if current_status == "dead":
        click.echo(f"Sandbox '{sandbox}' is already dead/sleeping.")
        return

    # Collect ALL dispatch tasks for this sandbox (any status)
    all_tasks = [t for t in list_all() if t.get("sandbox") == sandbox]

    # Confirmation
    if not force:
        click.echo(f"\n  Sandbox: {sandbox}")
        click.echo(f"  Path: {entry.get('path', 'unknown')}")
        click.echo(f"  Current status: {current_status}")
        click.echo(f"  Dispatch tasks to archive: {len(all_tasks)}")
        click.echo()

        if archive_tasks and all_tasks:
            click.echo(f"  These tasks will be moved to Dead Letter Queue:")
            for t in all_tasks[:5]:  # Show max 5
                status = t.get("status", "?")
                click.echo(f"    - [{status}] {t.get('task_id', '?')}: {t.get('task', '')[:60]}...")
            if len(all_tasks) > 5:
                click.echo(f"    ... and {len(all_tasks) - 5} more")
            click.echo()

        if not click.confirm(f"Put '{sandbox}' to sleep?"):
            click.echo("Aborted.")
            return

    # 1. Archive ALL dispatch tasks for this sandbox (any status) to DLQ
    cancelled_count = 0
    if archive_tasks:
        for task in all_tasks:
            task_id = task.get("task_id")
            if task_id:
                status = task.get("status", "unknown")
                mark_failed(
                    task_id,
                    error=f"Archived by hero kill: sandbox '{sandbox}' put to sleep (was {status})"
                )
                cancelled_count += 1

    # 2. Archive pipeline manifests for this sandbox
    pipeline_dir = Path.home() / ".hero" / "pipeline"
    pipeline_archived = 0
    dlq_dir = Path.home() / ".hero" / "dlq"
    dlq_dir.mkdir(parents=True, exist_ok=True)
    if pipeline_dir.exists():
        for f in sorted(pipeline_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                if data.get("sandbox") == sandbox:
                    f.rename(dlq_dir / f.name)
                    pipeline_archived += 1
            except (json.JSONDecodeError, OSError):
                pass
    
    # 3. Update HEARTBEAT.toon to dead
    sandbox_state.update_status("dead")
    
    # 4. Update INDEX.toon
    index.add_sandbox(
        name=sandbox,
        path=entry.get("path", ""),
        budget_max=entry.get("budget_max", 5000),
    )
    # Force status to dead in index
    index_data = index.load()
    for sb in index_data.get("sandboxes", []):
        if sb.get("name") == sandbox:
            sb["status"] = "dead"
            sb["last_seen"] = datetime.utcnow().isoformat()
            break
    index.save(index_data)
    
    # 5. Invalidate cache
    invalidate_cache(sandbox)
    
    # Report
    click.echo(f"\n  ✅ Sandbox '{sandbox}' is now sleeping")
    click.echo(f"     Status: dead")
    if cancelled_count > 0:
        click.echo(f"     Tasks archived: {cancelled_count} (moved to DLQ)")
    if pipeline_archived > 0:
        click.echo(f"     Pipeline manifests archived: {pipeline_archived}")
    click.echo(f"     Budget preserved: {state.get('budget', {}).get('tokens_remaining', '?')} tokens remaining")
    click.echo(f"     Directory: {entry.get('path', 'unknown')}")
    click.echo()
    click.echo(f"  To wake up: hero spawn {sandbox} <task>")


if __name__ == "__main__":
    kill()
