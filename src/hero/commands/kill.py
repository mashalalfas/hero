"""hero kill — Stop a sandbox or kill sub-agent sessions."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

import click

from hero.state.sandbox import invalidate_cache

# ── Constants ──────────────────────────────────────────────────────────

SESSIONS_JSON = Path.home() / ".openclaw" / "agents" / "main" / "sessions" / "sessions.json"
SESSION_DIR = Path.home() / ".openclaw" / "agents" / "main" / "sessions"


# ── Internal helpers ──────────────────────────────────────────────────


def _run_openclaw(args: list[str], timeout: int = 30) -> str:
    """Run openclaw CLI and return stdout."""
    result = subprocess.run(
        ["openclaw"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise click.ClickException(
            f"openclaw {' '.join(args)} failed: {result.stderr}"
        )
    return result.stdout


def _list_subagent_sessions(max_age_minutes: int = 120) -> list[dict]:
    """List spawn-child sessions within max_age_minutes."""
    try:
        out = _run_openclaw([
            "sessions", "list",
            "--json",
            "--limit", "200",
            "--active", str(max_age_minutes),
        ])
        data = json.loads(out)
        sessions = data.get("sessions", []) if isinstance(data, dict) else data
    except (json.JSONDecodeError, click.ClickException):
        return []

    subagents: list[dict] = []
    for s in sessions:
        if s.get("kind") == "spawn-child":
            subagents.append(s)
    return subagents


def _remove_session_by_key(session_key: str, system_id: str) -> bool:
    """Remove a session from the session store and delete its transcript file."""
    if not SESSIONS_JSON.exists():
        return False

    # Remove from sessions.json
    try:
        data = json.loads(SESSIONS_JSON.read_text())
        original = len(data.get("sessions", []))
        data["sessions"] = [
            s
            for s in data.get("sessions", [])
            if s.get("key") != session_key and s.get("sessionId") != system_id
        ]
        if len(data["sessions"]) < original:
            SESSIONS_JSON.write_text(json.dumps(data, indent=2))
        else:
            return False  # Session not found
    except (json.JSONDecodeError, OSError):
        return False

    # Delete transcript file
    transcript_file = SESSION_DIR / f"{system_id}.jsonl"
    if transcript_file.exists():
        transcript_file.unlink(missing_ok=True)

    # Delete lock file
    lock_file = SESSION_DIR / f"{system_id}.jsonl.lock"
    if lock_file.exists():
        lock_file.unlink(missing_ok=True)

    return True


def _cleanup_all_sessions() -> int:
    """Run openclaw sessions cleanup --enforce. Returns count or -1."""
    try:
        _run_openclaw(["sessions", "cleanup", "--enforce"])
        return 0
    except click.ClickException:
        return -1


# ── Subcommand: sandbox ───────────────────────────────────────────────
# Re-export the existing sandbox-killing logic so callers of
# `hero kill <sandbox>` continue to work unchanged.

from hero.commands.kill_sandbox import kill as kill_sandbox_fn  # noqa: E402


# ── CLI group ─────────────────────────────────────────────────────────


@click.group()
def kill() -> None:
    """Stop a sandbox or kill sub-agent sessions."""
    pass


# Register the sandbox subcommand under the group.
# The original logic lives in kill_sandbox.py (renamed from kill.py);
# we import its `kill` function and invoke it directly to avoid recursion.
from hero.commands.kill_sandbox import kill as _original_kill_fn  # noqa: E402


@kill.command("sandbox")
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
def kill_sandbox(sandbox: str, force: bool, archive_tasks: bool) -> None:
    """Put a sandbox to sleep.

    Stops all activity for SANDBOX without deleting it. The sandbox
    directory and plan.md are preserved so it can be resumed later.

    Also cleans up:
    - All dispatch files for the sandbox (any status) → DLQ
    - Pipeline manifests for the sandbox → DLQ

    Examples:
        hero kill sandbox galaxy_oblivion       # Put galaxy_oblivion to sleep
        hero kill sandbox Melody_MD --force     # Skip confirmation
        hero kill sandbox qlearner --no-archive-tasks  # Keep tasks in queue
    """
    # Delegate to the original implementation directly — no CLI round-trip.
    _original_kill_fn(
        sandbox,
        force=force,
        archive_tasks=archive_tasks,
    )


# ── Subcommand: session ───────────────────────────────────────────────


@kill.command("session")
@click.argument("session_key")
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt.",
)
def kill_session(session_key: str, force: bool) -> None:
    """Kill a specific sub-agent session by session key.

    SESSION_KEY can be the full key (e.g. main:spawn-child:abc123)
    or just the short suffix.

    Example:
        hero kill session main:spawn-child:abc123
        hero kill session abc123 --force
    """
    if not SESSIONS_JSON.exists():
        raise click.ClickException(
            f"No sessions store found at {SESSIONS_JSON}"
        )

    try:
        data = json.loads(SESSIONS_JSON.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise click.ClickException(f"Failed to read sessions store: {exc}")

    # Match by full key or short suffix
    matched = [
        s for s in data.get("sessions", [])
        if s.get("key") == session_key
        or s.get("key", "").endswith(session_key)
    ]

    if not matched:
        raise click.ClickException(
            f"No sub-agent session matching '{session_key}' found. "
            f"Run 'hero kill list' to see active sessions."
        )

    if len(matched) > 1:
        click.echo(f"  Ambiguous key '{session_key}' — matched {len(matched)} sessions:")
        for s in matched:
            click.echo(f"    {s.get('key', '?')}")
        raise click.ClickException("Use the full session key to disambiguate.")

    target = matched[0]
    full_key = target.get("key", session_key)
    system_id = target.get("id", target.get("system_id", ""))

    if not force:
        click.echo(f"\n  Session:    {full_key}")
        click.echo(f"  System ID:  {system_id}")
        if not click.confirm("Kill this sub-agent session?"):
            click.echo("Aborted.")
            return

    if _remove_session_by_key(full_key, system_id):
        click.echo(f"\n  ✅ Killed session: {full_key.split(':')[-1][:20]}...")
        click.echo(f"     Run 'openclaw sessions list' to confirm")
    else:
        raise click.ClickException(
            f"Failed to remove session '{full_key}'. "
            "It may have already been deleted."
        )


# ── Subcommand: clean ─────────────────────────────────────────────────


@kill.command("clean")
@click.option(
    "--age",
    default=120,
    help="Max age in minutes to keep (default: 120).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be removed without making changes.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt.",
)
def kill_clean(age: int, dry_run: bool, force: bool) -> None:
    """List and optionally kill old sub-agent sessions.

    Finds all spawn-child sessions and removes those older than AGE minutes.

    Examples:
        hero kill clean --age 60 --dry-run   # Preview sessions older than 1h
        hero kill clean --age 30 --force     # Remove sessions older than 30m
    """
    sessions = _list_subagent_sessions(max_age_minutes=9999)

    if not sessions:
        click.echo("No sub-agent sessions found.")
        return

    now = time.time()
    old_sessions: list[dict] = []
    for s in sessions:
        age_str = s.get("age", "0m")
        try:
            if "h" in age_str:
                session_age_minutes = float(age_str.replace("h", "")) * 60
            elif "m" in age_str:
                session_age_minutes = float(age_str.replace("m", ""))
            else:
                session_age_minutes = 0
        except (ValueError, TypeError):
            session_age_minutes = 0

        if session_age_minutes > age:
            old_sessions.append(s)

    if not old_sessions:
        click.echo(f"No sub-agent sessions older than {age} minutes.")
        return

    click.echo(f"\n  Found {len(old_sessions)} sub-agent sessions older than {age}m:")
    for s in old_sessions:
        key = s.get("key", "?")
        age_str = s.get("age", "?")
        click.echo(f"    [{age_str}] {key.split(':')[-1][:20]}...")

    click.echo("")

    if dry_run:
        click.echo(
            f"  Dry-run: would remove {len(old_sessions)} sessions. "
            "Use --force to actually remove."
        )
        return

    if not force:
        if not click.confirm(f"Kill {len(old_sessions)} sub-agent sessions?"):
            click.echo("Aborted.")
            return

    removed = 0
    for s in old_sessions:
        key = s.get("key", "")
        sid = s.get("id", s.get("system_id", ""))
        if _remove_session_by_key(key, sid):
            removed += 1

    # Also run openclaw cleanup for any remaining stragglers
    _cleanup_all_sessions()

    click.echo(f"\n  ✅ Removed {removed} sub-agent sessions")
    click.echo(f"     Run 'openclaw sessions list --active 120' to confirm")


if __name__ == "__main__":
    kill()
