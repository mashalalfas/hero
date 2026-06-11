"""hero dlq — Inspect, retry, and purge dead letters.

Failed dispatch tasks are automatically sent to the Dead Letter Queue.
Use these commands to view failures, retry them, or clean up old entries.
"""

from __future__ import annotations

import click

from hero.reliability.dlq import list_dlq, retry_from_dlq, clear_dlq


@click.group()
def dlq() -> None:
    """Manage the dead letter queue for failed dispatch tasks.

    View failed tasks, retry them in a new dispatch entry, or
    purge entries that are older than a configurable threshold.
    """


@dlq.command("list")
def list_cmd() -> None:
    """List all tasks currently in the dead letter queue."""
    entries = list_dlq()

    if not entries:
        click.echo("Dead letter queue is empty.")
        return

    click.echo(f"\nDead Letter Queue ({len(entries)} entries):")
    click.echo("=" * 70)
    for e in entries:
        click.echo(f"  ❌ {e['task_id']}  {e['sandbox']:20s}  {e['timestamp']}")
        error_preview = e['error'][:100] if e['error'] else "(no error)"
        click.echo(f"     Error: {error_preview}")
    click.echo()


@dlq.command("retry")
@click.argument("task_id")
def retry_cmd(task_id: str) -> None:
    """Re-enqueue a task from the dead letter queue.

    TASK_ID is the ID of the dead-lettered task to retry.
    """
    new_id = retry_from_dlq(task_id)
    if new_id:
        click.echo(f"✅ Re-enqueued {task_id} as new task {new_id}")
    else:
        click.echo(f"❌ Could not retry {task_id} — entry not found or invalid.")


@dlq.command("clear")
@click.option(
    "--older-than",
    default=7,
    show_default=True,
    help="Remove entries older than N days.",
    type=int,
)
def clear_cmd(older_than: int) -> None:
    """Remove dead letter entries older than N days (default 7)."""
    removed = clear_dlq(older_than_days=older_than)
    if removed:
        click.echo(f"Removed {removed} old dead letter entr{'y' if removed == 1 else 'ies'}.")
    else:
        click.echo("No matching entries to remove.")
