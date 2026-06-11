"""hero sweep — Full system sweep: kill zombies, clean errors, restart fresh.

A comprehensive cleanup that:
1. Kills all stale sub-agent sessions >1m old
2. Cleans zombie dispatch tasks and pipeline manifests
3. Removes stale session lock files
4. Deletes old session transcripts from disk
5. Reports errored cron jobs and dead agent spawns
6. Reports memory/disk health
7. Restarts the OpenClaw gateway for clean RSS

Run manually:  hero sweep
For automation: hero sweep --auto
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

import click

from hero.commands.clean import clean as clean_dispatch
from hero.commands.kill import (
    _list_subagent_sessions,
    _remove_session_by_key,
    _cleanup_all_sessions,
    SESSION_DIR as SESSION_DIR_SRC,
)
from hero.state.toon import toon_read

# ── Paths ──────────────────────────────────────────────────────────────

SESSION_DIR = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
SESSIONS_JSON = Path.home() / ".openclaw" / "agents" / "main" / "sessions" / "sessions.json"
DISPATCH_DIR = Path.home() / ".hero" / "dispatch"
PIPELINE_DIR = Path.home() / ".hero" / "pipeline"
CRON_STORE = Path.home() / ".openclaw" / "cron"
GATEWAY_LOGS = Path.home() / ".openclaw" / "logs"


# ── Helpers ────────────────────────────────────────────────────────────


def _size_human(bytes_val: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if bytes_val < 1024:
            return f"{bytes_val:.1f}{unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f}TB"


def _disk_usage(path: Path) -> tuple[int, str]:
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return total, _size_human(total)


def _run_openclaw(args: list[str], timeout: int = 30) -> tuple[str, str]:
    """Run openclaw CLI and return (stdout, stderr)."""
    try:
        result = subprocess.run(
            ["openclaw"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return "", "timeout"
    except FileNotFoundError:
        return "", "openclaw not found"


# ── Sweep phases ──────────────────────────────────────────────────────


def _phase_clean_sessions(dry_run: bool = False) -> tuple[int, list[str]]:
    """Phase 1: Kill all stale sub-agent sessions.
    
    Returns (removed_count, report_lines).
    """
    report: list[str] = ["─ Phase 1: Stale sub-agent sessions"]
    sessions = _list_subagent_sessions(max_age_minutes=99999)
    
    if not sessions:
        report.append("  No sub-agent sessions found.")
        return 0, report

    # Filter to sessions older than 1 minute (everything completed)
    now = time.time()
    old_sessions = []
    for s in sessions:
        age_str = s.get("age", "0m")
        try:
            if "h" in age_str:
                age_min = float(age_str.replace("h", "")) * 60
            elif "m" in age_str:
                age_min = float(age_str.replace("m", ""))
            else:
                age_min = 0
        except (ValueError, TypeError):
            age_min = 0
        if age_min > 1:
            old_sessions.append(s)

    if not old_sessions:
        report.append("  No sessions older than 1m.")
        return 0, report

    removed = 0
    for s in old_sessions:
        key = s.get("key", "")
        sid = s.get("id", s.get("system_id", ""))
        age_str = s.get("age", "?")
        status = s.get("status", "?")
        if not dry_run:
            if _remove_session_by_key(key, sid):
                removed += 1
                report.append(f"  🧹 [{age_str}] {status} — {key.split(':')[-1][:30]}...")
        else:
            report.append(f"  🗑 Would remove [{age_str}] {status} — {key.split(':')[-1][:30]}...")
            removed += 1

    # Also run openclaw cleanup
    if not dry_run:
        _cleanup_all_sessions()

    report.append(f"  Result: {removed} session(s) cleaned.")
    return removed, report


def _phase_clean_session_files(dry_run: bool = False) -> tuple[int, list[str]]:
    """Phase 2: Delete old session transcript files from disk."""
    report: list[str] = ["─ Phase 2: Session transcript files"]
    
    if not SESSION_DIR.exists():
        report.append("  Session directory not found.")
        return 0, report

    cutoff = time.time() - (3 * 86400)  # 3 days
    removed = 0
    total_size = 0

    for f in sorted(SESSION_DIR.glob("*.jsonl")):
        if f.stat().st_mtime < cutoff:
            total_size += f.stat().st_size
            if not dry_run:
                f.unlink(missing_ok=True)
                removed += 1

    # Also clean locks
    for f in SESSION_DIR.glob("*.lock"):
        if f.stat().st_mtime < cutoff:
            if not dry_run:
                f.unlink(missing_ok=True)

    report.append(f"  Removed: {removed} files ({_size_human(total_size)} freed)" if not dry_run
                  else f"  Would remove: {removed} files ({_size_human(total_size)})")
    return removed, report


def _phase_clean_dispatch(dry_run: bool = False) -> tuple[int, list[str]]:
    """Phase 3: Clean zombie dispatch tasks and pipeline manifests."""
    report: list[str] = ["─ Phase 3: Dispatch tasks + pipeline manifests"]
    removed = 0

    # Dispatch tasks
    if DISPATCH_DIR.exists():
        for f in sorted(DISPATCH_DIR.glob("*.toon"), key=lambda p: p.stat().st_mtime):
            status = "unknown"
            try:
                data = toon_read(f)
                status = data.get("status", "unknown")
            except Exception:
                pass

            if status in ("completed", "failed", "timeout") or status == "unknown":
                if not dry_run:
                    f.unlink(missing_ok=True)
                    removed += 1

    # Pipeline manifests
    if PIPELINE_DIR.exists():
        for f in PIPELINE_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                status = data.get("status", "")
                if status in ("completed", "failed", "verify_failed", "cancelled"):
                    if not dry_run:
                        f.unlink(missing_ok=True)
                        removed += 1
            except (json.JSONDecodeError, OSError):
                if not dry_run:
                    f.unlink(missing_ok=True)
                    removed += 1

    report.append(f"  Removed: {removed} stale entries" if not dry_run
                  else f"  Would remove: {removed} stale entries")
    return removed, report


def _phase_clean_locks(dry_run: bool = False) -> tuple[int, list[str]]:
    """Phase 4: Clean stale session lock files."""
    report: list[str] = ["─ Phase 4: Stale session locks"]
    removed = 0

    lock_dir = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
    if not lock_dir.exists():
        report.append("  No lock directory found.")
        return 0, report

    import os

    for lock_file in sorted(lock_dir.glob("*.lock")):
        try:
            lock_data = json.loads(lock_file.read_text())
        except (json.JSONDecodeError, OSError):
            if not dry_run:
                lock_file.unlink(missing_ok=True)
                removed += 1
            continue

        pid = lock_data.get("pid")
        pid_alive = False
        if pid is not None:
            try:
                os.kill(pid, 0)
                pid_alive = True
            except (OSError, ProcessLookupError):
                pid_alive = False

        if not pid_alive:
            if not dry_run:
                lock_file.unlink(missing_ok=True)
                removed += 1

    report.append(f"  Removed: {removed} stale locks" if not dry_run
                  else f"  Would remove: {removed} stale locks")
    return removed, report


def _phase_check_crons() -> list[str]:
    """Phase 5: Report errored cron jobs."""
    report: list[str] = ["─ Phase 5: Cron job health"]

    cron_dir = Path.home() / ".openclaw" / "cron"
    if not cron_dir.exists():
        report.append("  No cron store found.")
        return report

    errored = 0
    total = 0
    for f in sorted(cron_dir.rglob("*.json")):
        try:
            data = json.loads(f.read_text())
            total += 1
            name = data.get("name", f.stem)
            state = data.get("state", {})
            errs = state.get("consecutiveErrors", 0)
            last_status = state.get("lastStatus", "ok")
            last_error = state.get("lastErrorReason", "")

            if errs > 0 or last_status == "error":
                errored += 1
                report.append(f"  ⚠ [{errs}x err] {name} — {last_error or last_status}")
        except (json.JSONDecodeError, OSError):
            pass

    if errored == 0:
        report.append("  ✅ All crons healthy.")
    else:
        report.append(f"  Result: {errored}/{total} cron(s) with errors.")
    return report


def _phase_health() -> list[str]:
    """Phase 6: Report memory and disk health."""
    report: list[str] = ["─ Phase 6: System health"]

    # Disk usage for key directories
    for label, path in [
        ("Sessions", SESSION_DIR),
        ("Cron", CRON_STORE),
        ("Logs", GATEWAY_LOGS),
        (".openclaw", Path.home() / ".openclaw"),
        (".hero", Path.home() / ".hero"),
    ]:
        if path and path.exists():
            total, human = _disk_usage(path)
            report.append(f"  {label}: {human}")

    # Memory via ps
    try:
        result = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(subprocess.getpid())],
            capture_output=True, text=True, timeout=5,
        )
        # Also check gateway
        gw = subprocess.run(
            ["pgrep", "-f", "openclaw.*gateway"],
            capture_output=True, text=True, timeout=5,
        )
        if gw.stdout.strip():
            mem = subprocess.run(
                ["ps", "-o", "rss=", "-p", gw.stdout.strip().split("\n")[0]],
                capture_output=True, text=True, timeout=5,
            )
            gw_rss = int(mem.stdout.strip()) if mem.stdout.strip() else 0
            report.append(f"  Gateway RSS: {_size_human(gw_rss * 1024)}")
    except Exception:
        pass

    return report


def _phase_gateway_restart(dry_run: bool = False) -> list[str]:
    """Phase 7: Restart the OpenClaw gateway."""
    report: list[str] = ["─ Phase 7: Gateway restart"]
    
    if dry_run:
        report.append("  ⚡ Would restart gateway (dry-run, skipped).")
        return report

    report.append("  ⚡ Restarting gateway...")
    stdout, stderr = _run_openclaw(["gateway", "restart"], timeout=15)
    if stderr and "timeout" not in stderr:
        report.append(f"  ⚠ Partial restart: {stderr[:100]}")
    else:
        report.append("  ✅ Gateway restart initiated.")
    return report


# ── CLI command ────────────────────────────────────────────────────────


@click.command("sweep")
@click.option(
    "--auto",
    is_flag=True,
    default=False,
    help="Non-interactive mode — skip confirmations, restart gateway.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be done without making changes.",
)
@click.option(
    "--skip-restart",
    is_flag=True,
    default=False,
    help="Run all cleanup phases but do NOT restart the gateway.",
)
def sweep(auto: bool, dry_run: bool, skip_restart: bool) -> None:
    """Full system sweep: kill zombies, clean errors, restart fresh.

    Runs all cleanup phases:
      1. Kill stale sub-agent sessions
      2. Delete old session transcripts
      3. Clean zombie dispatch tasks
      4. Remove stale session locks
      5. Check cron job health
      6. Report system health
      7. Restart gateway (unless --skip-restart)

    Examples:
        hero sweep                    # Interactive full sweep + restart
        hero sweep --auto             # Non-interactive, restart included
        hero sweep --dry-run          # Preview only
        hero sweep --skip-restart     # Clean without bouncing gateway
    """
    if not dry_run and not auto:
        click.echo("\n⚠  This will kill all sessions and restart the gateway.")
        click.echo("   Currently running work will be interrupted.")
        if not click.confirm("\nContinue?"):
            click.echo("Aborted.")
            return

    start = time.time()
    all_reports: list[list[str]] = []

    # Run all phases
    _, r1 = _phase_clean_sessions(dry_run)
    all_reports.append(r1)

    _, r2 = _phase_clean_session_files(dry_run)
    all_reports.append(r2)

    _, r3 = _phase_clean_dispatch(dry_run)
    all_reports.append(r3)

    _, r4 = _phase_clean_locks(dry_run)
    all_reports.append(r4)

    all_reports.append(_phase_check_crons())
    all_reports.append(_phase_health())

    if not skip_restart and not dry_run:
        all_reports.append(_phase_gateway_restart(dry_run))
    elif skip_restart or dry_run:
        report = ["─ Phase 7: Gateway restart"]
        if skip_restart:
            report.append("  ⏭ Skipped (--skip-restart).")
        if dry_run:
            report.append("  ⏭ Skipped (dry-run).")
        all_reports.append(report)

    # Print full report
    elapsed = time.time() - start
    click.echo("\n" + "═" * 50)
    click.echo("  HERO SWEEP REPORT")
    click.echo("═" * 50)
    for phase_report in all_reports:
        click.echo("")
        for line in phase_report:
            click.echo(f"  {line}")

    click.echo("")
    click.echo("─" * 50)
    click.echo(f"  Completed in {elapsed:.1f}s")
    if dry_run:
        click.echo("  Mode: DRY RUN — no changes made")
    click.echo("═" * 50)


if __name__ == "__main__":
    sweep()
