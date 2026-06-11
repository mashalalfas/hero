"""hero heartbeat — Monitor soldier heartbeats.

Shows heartbeat status for soldiers, including:
- Active soldiers and their last ping time
- Stale soldiers (missed 3+ heartbeats)
- Watch mode for continuous monitoring every 10 seconds
"""

from __future__ import annotations

import time
from pathlib import Path

import click

from hero.soldier.heartbeat import HeartbeatState


DEFAULT_POLL_INTERVAL = 10  # seconds


@click.command()
@click.option(
    "--watch",
    is_flag=True,
    default=False,
    help="Continuously poll every 10 seconds (Ctrl+C to stop).",
)
@click.option(
    "--stale",
    is_flag=True,
    default=False,
    help="Show only stale soldiers (3+ missed heartbeats).",
)
@click.option(
    "--sandbox",
    type=str,
    default=None,
    help="Show heartbeat for a specific sandbox only.",
)
def heartbeat(watch: bool, stale: bool, sandbox: str | None) -> None:
    """Monitor soldier heartbeat status.

    Shows soldiers that are:
    - active: pinging normally
    - stale: missed 3+ consecutive heartbeats
    - completed: finished their task

    Examples:
        hero heartbeat              # Show all soldiers
        hero heartbeat --stale      # Show only stale soldiers
        hero heartbeat --sandbox my-sandbox  # Show specific sandbox
        hero heartbeat --watch      # Continuous monitoring
    """
    if watch:
        _watch_heartbeats(stale, sandbox)
    elif sandbox:
        _show_sandbox_heartbeat(sandbox)
    else:
        _show_all_heartbeats(stale)


def _show_sandbox_heartbeat(sandbox_name: str) -> None:
    """Show heartbeat status for a single sandbox."""
    state = HeartbeatState(sandbox_name)
    hb = state.get_heartbeat()

    if hb is None:
        click.echo(f"No heartbeat found for sandbox: {sandbox_name}")
        return

    _print_heartbeat(sandbox_name, hb)


def _show_all_heartbeats(stale_only: bool = False) -> None:
    """Show heartbeat status for all sandboxes."""
    all_heartbeats = HeartbeatState.get_all_heartbeats()

    if not all_heartbeats:
        click.echo("No soldier heartbeats found. Spawn a soldier first.")
        return

    active = []
    stale_sandboxes = []
    completed = []

    for name, hb in all_heartbeats.items():
        if hb.status == "stale":
            stale_sandboxes.append((name, hb))
        elif hb.status == "completed":
            completed.append((name, hb))
        else:
            active.append((name, hb))

    if stale_only:
        if not stale_sandboxes:
            click.echo("No stale soldiers found.")
            return
        click.echo(f"Stale soldiers: {len(stale_sandboxes)}\n")
        for name, hb in stale_sandboxes:
            _print_heartbeat(name, hb)
    else:
        click.echo(f"Soldiers: {len(active)} active, {len(stale_sandboxes)} stale, {len(completed)} completed\n")

        if active:
            click.echo("=== Active ===")
            for name, hb in active:
                _print_heartbeat(name, hb)
            click.echo()

        if stale_sandboxes:
            click.echo("=== Stale ===")
            for name, hb in stale_sandboxes:
                _print_heartbeat(name, hb)
            click.echo()

        if completed:
            click.echo("=== Completed ===")
            for name, hb in completed:
                _print_heartbeat(name, hb)


def _watch_heartbeats(stale_only: bool, sandbox_name: str | None) -> None:
    """Continuously poll and display heartbeat status."""
    click.echo("Watching soldier heartbeats (Ctrl+C to stop)...\n")

    try:
        while True:
            if sandbox_name:
                _show_sandbox_heartbeat(sandbox_name)
            else:
                _show_all_heartbeats(stale_only)
            time.sleep(DEFAULT_POLL_INTERVAL)
    except KeyboardInterrupt:
        click.echo("\nStopped watching.")


def _print_heartbeat(name: str, hb) -> None:
    """Print a single heartbeat in a formatted style."""
    status_icon = "✅" if hb.status == "active" else "⚠️" if hb.status == "stale" else "🏁"
    click.echo(f"  {status_icon} {name}")
    click.echo(f"      soldier_id: {hb.soldier_id}")
    click.echo(f"      status: {hb.status}")
    click.echo(f"      last_ping: {hb.last_ping}")
    click.echo(f"      missed_count: {hb.missed_count}")


if __name__ == "__main__":
    heartbeat()