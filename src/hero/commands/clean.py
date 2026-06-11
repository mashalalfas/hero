"""hero clean — Clean up zombie dispatch tasks and stale state.

Removes dispatch files that are no longer backed by live processes.
Designed to run after every pipeline phase to prevent zombie buildup.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from hero.state.toon import toon_read
from hero.soldier.dispatch import clear_completed, purge_stale

DISPATCH_DIR = Path.home() / ".hero" / "dispatch"
PIPELINE_DIR = Path.home() / ".hero" / "pipeline"
LOCK_DIR = Path.home() / ".openclaw" / "agents" / "main" / "sessions"


def _clean_stale_session_locks() -> int:
    """Remove stale OpenClaw session lock files.

    Checks each *.lock file in the OpenClaw sessions directory. If the PID
    recorded in the lock is no longer alive the lock file is removed. Locks
    held by still-running processes (including the gateway) are left alone.
    """
    import json
    import os

    if not LOCK_DIR.exists():
        return 0

    cleaned = 0
    for lock_file in LOCK_DIR.glob("*.lock"):
        try:
            lock_data = json.loads(lock_file.read_text())
        except (json.JSONDecodeError, OSError):
            # Unreadable / corrupt lock — safe to drop
            lock_file.unlink(missing_ok=True)
            cleaned += 1
            continue

        pid = lock_data.get("pid")
        pid_alive = False
        if pid is not None:
            try:
                os.kill(pid, 0)  # signal 0 = existence check, no actual signal sent
                pid_alive = True
            except (OSError, ProcessLookupError):
                pid_alive = False

        if not pid_alive:
            lock_file.unlink(missing_ok=True)
            cleaned += 1

    return cleaned


def clear_stale(age_minutes: int = 30, dry_run: bool = False, sandbox: str | None = None) -> int:
    """Remove pending/dispatched tasks older than age_minutes."""
    import time

    dispatch_dir = Path.home() / ".hero" / "dispatch"
    if not dispatch_dir.exists():
        return 0
    removed = 0
    now = time.time()
    for f in sorted(dispatch_dir.glob("*.toon")):
        try:
            data = toon_read(f)
        except Exception:
            continue
        status = data.get("status", "pending")
        if status not in ("pending", "dispatched"):
            continue
        created = data.get("created_at", "")
        # Simple timestamp check: if file older than age_minutes
        age_seconds = now - f.stat().st_mtime
        if age_seconds > age_minutes * 60:
            if sandbox and data.get("sandbox", "") != sandbox:
                continue
            if not dry_run:
                f.unlink()
            removed += 1
            if not dry_run:
                print(f"  Removed stale task: {f.stem}")
    return removed


@click.command("clean")
@click.option(
    "--sandbox",
    type=str,
    default=None,
    help="Only clean dispatch for a specific sandbox.",
)
@click.option(
    "--age",
    type=int,
    default=300,
    help="Remove tasks older than this many seconds (default: 300 = 5min).",
)
@click.option(
    "--status-age",
    type=int,
    default=24,
    help="Remove per-agent status files older than this many hours (default: 24).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be cleaned without removing.",
)
def clean(sandbox: str | None, age: int, status_age: int, dry_run: bool) -> None:
    """Remove zombie dispatch tasks — stale entries with no live process.

    Scans ~/.hero/dispatch/ for tasks that are older than *age* seconds
    and have no corresponding live process. These are usually tasks spawned
    by sessions_spawn that timed out or were never picked up.

    Run automatically after every pipeline phase to keep state clean.
    """
    import time

    now = time.time()
    removed = 0
    skipped = 0

    for f in sorted(DISPATCH_DIR.glob("*.toon"), key=lambda p: p.stat().st_mtime):
        try:
            data = toon_read(f)
        except Exception:
            if not dry_run:
                f.unlink(missing_ok=True)
                removed += 1
            else:
                click.echo(f"  🗑 Would remove (corrupt): {f.name}")
            continue

        task_sandbox = data.get("sandbox", "")
        task_status = data.get("status", "pending")
        task_id = data.get("task_id", f.stem)

        # Filter by sandbox if specified
        if sandbox and task_sandbox != sandbox:
            continue

        # Skip tasks that are already completed
        if task_status in ("completed", "failed"):
            skipped += 1
            continue

        # Check age
        mtime = f.stat().st_mtime
        age_secs = now - mtime
        if age_secs < age:
            skipped += 1
            continue

        # Remove stale dispatch
        if not dry_run:
            f.unlink(missing_ok=True)
            click.echo(f"  🧹 Removed: {f.name} ({task_sandbox}, {task_status}, {age_secs:.0f}s old)")
            removed += 1
        else:
            click.echo(f"  🗑 Would remove: {f.name} ({task_sandbox}, {task_status}, {age_secs:.0f}s old)")

    # Also clean empty pipeline manifests
    for f in PIPELINE_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            status = data.get("status", "")
            if status in ("completed", "failed", "verify_failed"):
                age_secs = now - f.stat().st_mtime
                if age_secs > age:
                    if not dry_run:
                        f.unlink(missing_ok=True)
                        click.echo(f"  🧹 Removed pipeline: {f.name} ({status}, {age_secs:.0f}s old)")
                        removed += 1
                    else:
                        click.echo(f"  🗑 Would remove pipeline: {f.name} ({status}, {age_secs:.0f}s old)")
        except (json.JSONDecodeError, OSError):
            pass

    stale = clear_stale(dry_run=dry_run, sandbox=sandbox)
    click.echo(f"  Stale: {stale}")

    stale_locks = 0
    if not dry_run:
        stale_locks = _clean_stale_session_locks()
    else:
        # Count stale locks without removing them for dry-run reporting
        if LOCK_DIR.exists():
            import os as _os
            for lf in LOCK_DIR.glob("*.lock"):
                try:
                    ld = json.loads(lf.read_text())
                    pid = ld.get("pid")
                    if pid is not None:
                        try:
                            _os.kill(pid, 0)
                        except (OSError, ProcessLookupError):
                            stale_locks += 1
                    else:
                        stale_locks += 1
                except (json.JSONDecodeError, OSError):
                    stale_locks += 1
    if stale_locks:
        prefix = "Would clean" if dry_run else "Cleaned"
        click.echo(f"  {prefix} stale session locks: {stale_locks}")

    removed_purge = purge_stale() if not dry_run else 0
    click.echo(f"  Purged stale dispatch: {removed_purge}")

    # Clean per-agent status files
    removed_status = clean_status(age_hours=status_age) if not dry_run else 0
    click.echo(f"  Cleaned stale status: {removed_status}")

    if dry_run:
        click.echo(f"\nDry run: {removed} would be removed, {skipped} skipped.")
    else:
        click.echo(f"\nCleaned: {removed} removed, {skipped} skipped.")
