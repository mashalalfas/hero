"""hero watch — Start the pipeline watcher daemon.

Monitors dispatch files and automatically syncs pipeline manifest state
when subagent sessions complete.  Solves the "stale dispatch" problem
where dispatch files stay at ``"dispatched"`` forever because nobody
calls ``mark_completed()`` after a ``sessions_spawn`` finishes.

Usage:
    hero watch                  # start in background (default)
    hero watch --foreground     # run in foreground (blocking)
    hero watch --status         # check if watcher is running
    hero watch --stop           # stop the background watcher

How it works:
    1. Reads all dispatch files every 3 seconds
    2. For "dispatched" tasks older than 15s, checks session liveness
    3. If the session ended → infers outcome and updates state
    4. Syncs completed/failed tasks to pipeline manifests
    5. Advances pipeline steps (spawn → verify → archive → completed)
"""

from __future__ import annotations

import json
import os
import signal
import sys
from pathlib import Path

import click

from hero.logging import get_logger

PID_FILE = Path.home() / ".hero" / "watcher.pid"
logger = get_logger("watch")


def _write_pid(pid: int) -> None:
    """Write PID to the lock file."""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(pid))


def _read_pid() -> int | None:
    """Read PID from the lock file.  Returns None if file missing or stale."""
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
        # Check if process is still alive
        os.kill(pid, 0)
        return pid
    except (ValueError, OSError, ProcessLookupError):
        # Stale PID file — clean up
        PID_FILE.unlink(missing_ok=True)
        return None


def _stop_existing() -> bool:
    """Stop an existing watcher process.  Returns True if one was stopped."""
    pid = _read_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink(missing_ok=True)
        click.echo(f"Stopped watcher (PID {pid})")
        return True
    except (OSError, ProcessLookupError):
        PID_FILE.unlink(missing_ok=True)
        return False


@click.command()
@click.option(
    "--foreground/--background",
    "-f/-b",
    default=False,
    help="Run in foreground (blocking) or background (daemon). Default: background.",
)
@click.option(
    "--status",
    "show_status",
    is_flag=True,
    default=False,
    help="Show watcher status and exit.",
)
@click.option(
    "--stop",
    "do_stop",
    is_flag=True,
    default=False,
    help="Stop the running watcher.",
)
@click.option(
    "--interval",
    type=int,
    default=3,
    help="Poll interval in seconds (default: 3).",
)
def watch(foreground: bool, show_status: bool, do_stop: bool, interval: int) -> None:
    """Start the pipeline watcher for live dispatch → pipeline sync.

    The watcher monitors ``~/.hero/dispatch/`` for completed subagent
    sessions and automatically updates ``~/.hero/pipeline/`` manifests
    so the viewport always shows current state.

    \b
    Examples:
        hero watch                     # start in background
        hero watch -f                  # foreground (see logs)
        hero watch --status            # is it running?
        hero watch --stop              # kill the watcher
    """
    # ── Status check ──────────────────────────────────────────────────
    if show_status:
        pid = _read_pid()
        if pid:
            click.echo(f"Watcher is running (PID {pid})")
        else:
            click.echo("Watcher is not running")
        return

    # ── Stop ──────────────────────────────────────────────────────────
    if do_stop:
        if not _stop_existing():
            click.echo("No watcher is running")
        return

    # ── Kill existing if any ──────────────────────────────────────────
    _stop_existing()

    # ── Import here to avoid circular deps at module load ─────────────
    from hero.pipeline.watcher import PipelineWatcher, WATCH_INTERVAL

    watcher = PipelineWatcher()

    if foreground:
        click.echo("Pipeline Watcher starting (foreground)…")
        click.echo(f"  Poll interval: {WATCH_INTERVAL}s")
        click.echo(f"  Dispatch dir:  {Path.home() / '.hero' / 'dispatch'}")
        click.echo(f"  Pipeline dir:  {Path.home() / '.hero' / 'pipeline'}")
        click.echo("  Press Ctrl+C to stop")
        click.echo("")
        try:
            _write_pid(os.getpid())
            watcher.run()
        except KeyboardInterrupt:
            click.echo("\nWatcher stopped.")
        finally:
            PID_FILE.unlink(missing_ok=True)
    else:
        # Background mode — fork
        pid = os.fork()
        if pid > 0:
            # Parent
            _write_pid(pid)
            click.echo(f"Pipeline Watcher started (PID {pid})")
            click.echo(f"  Logs: ~/.hero/logs/hero.jsonl")
            click.echo(f"  Stop: hero watch --stop")
        else:
            # Child — detach and run
            os.setsid()
            watcher.run()
            PID_FILE.unlink(missing_ok=True)
            sys.exit(0)
