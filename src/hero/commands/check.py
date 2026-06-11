"""hero check — Run health diagnostics on a sandbox.

Checks:
1. Budget health — read BUDGET.toon, show remaining/used
2. Heartbeat — read HEARTBEAT.toon, check last activity
3. Git status — check if working tree is clean
4. Build status — run project-appropriate build/analyze command
5. Circuit breaker — check is_quarantined(sandbox)
6. Stale dispatch tasks — check ~/.hero/dispatch/ for this sandbox's incomplete tasks
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

import click

from hero.reliability.circuit_breaker import is_quarantined
from hero.soldier.dispatch import DISPATCH_DIR, list_all as list_all_tasks
from hero.state.toon import toon_read

SANDBOX_DIR = Path.home() / ".hero" / "sandboxes"
HERO_HOME = Path.home() / ".hero"


EMOJI_PASS = "🟢"
EMOJI_WARN = "🟡"
EMOJI_FAIL = "🔴"
EMOJI_INFO = "🔵"


def _status_icon(passed: bool) -> str:
    """Return colour emoji for pass/fail status."""
    return EMOJI_PASS if passed else EMOJI_FAIL


def _warn_icon(something: bool) -> str:
    return EMOJI_WARN if something else EMOJI_PASS


def detect_project_type(sandbox_path: Path) -> str:
    """Detect the project type based on config files present.

    Checks are ordered by specificity: Flutter, Rust, Node, Python.
    Returns ``\"unknown\"`` if nothing matches.
    """
    if (sandbox_path / "pubspec.yaml").exists():
        return "flutter"
    if (sandbox_path / "Cargo.toml").exists():
        return "rust"
    if (sandbox_path / "package.json").exists():
        return "node"
    if (sandbox_path / "pyproject.toml").exists():
        return "python"
    return "unknown"


def _check_budget(sandbox: str, verbose: bool) -> dict[str, Any]:
    """Check budget health. Returns check result dict."""
    budget_file = SANDBOX_DIR / sandbox / "BUDGET.toon"
    if not budget_file.exists():
        return {
            "label": "Budget",
            "passed": False,
            "summary": "No BUDGET.toon found",
            "detail": "Run 'hero scan' or 'hero budget' to initialise.",
        }

    budget = toon_read(budget_file)
    bootstrap_max = budget.get("bootstrap_max", 5000)
    tokens_remaining = budget.get("tokens_remaining", bootstrap_max)
    compactions_used = budget.get("compactions_used", 0)
    tokens_used = bootstrap_max - tokens_remaining
    util_pct = (tokens_used / bootstrap_max * 100) if bootstrap_max > 0 else 0.0

    critical = tokens_remaining < 500
    low = tokens_remaining < 2000
    passed = not critical

    if tokens_remaining == bootstrap_max:
        summary = f"{tokens_remaining:,} / {bootstrap_max:,} remaining (unused)"
    elif critical:
        summary = f"⚠ CRITICAL — {tokens_remaining:,} / {bootstrap_max:,} remaining"
    elif low:
        summary = f"⚠ LOW — {tokens_remaining:,} / {bootstrap_max:,} remaining ({util_pct:.0f}% used)"
    else:
        summary = f"{tokens_remaining:,} / {bootstrap_max:,} remaining ({util_pct:.0f}% used)"

    detail = ""
    if verbose:
        detail = f"  tokens_used: {tokens_used:,}\n  compactions: {compactions_used}"

    return {
        "label": "Budget",
        "passed": passed,
        "summary": summary,
        "detail": detail,
        "warn": low and not critical,
    }


def _check_heartbeat(sandbox: str, verbose: bool) -> dict[str, Any]:
    """Check heartbeat status. Returns check result dict."""
    heartbeat_file = SANDBOX_DIR / sandbox / "HEARTBEAT.toon"
    if not heartbeat_file.exists():
        return {
            "label": "Heartbeat",
            "passed": True,
            "summary": "No heartbeat yet (sandbox never spawned)",
            "detail": "",
        }

    hb = toon_read(heartbeat_file)
    status = hb.get("status", "idle")
    last_ping_str = hb.get("last_ping", "")
    now = time.time()

    # Determine staleness
    stale = False
    elapsed_str = ""
    if last_ping_str:
        try:
            from datetime import datetime
            last_ping_dt = datetime.fromisoformat(last_ping_str)
            elapsed = now - last_ping_dt.timestamp()
            if elapsed < 60:
                elapsed_str = f"{int(elapsed)}s ago"
            elif elapsed < 3600:
                elapsed_str = f"{int(elapsed // 60)}m ago"
            else:
                elapsed_str = f"{elapsed / 3600:.1f}h ago"
            stale = elapsed > 180  # 3 minutes = stale
        except (ValueError, OSError):
            elapsed_str = last_ping_str

    status_text = {
        "active": "active",
        "stale": "stale",
        "completed": "completed",
        "idle": "idle",
    }.get(status, status)

    if status == "active" and not stale:
        summary = f"active, last seen {elapsed_str}" if elapsed_str else "active"
        passed = True
    elif stale and status == "active":
        summary = f"stale — last ping {elapsed_str}" if elapsed_str else "stale"
        passed = False
    elif status == "stale":
        summary = f"stale (flagged)"
        passed = False
    elif status == "completed":
        summary = f"completed"
        passed = True
    else:
        summary = status_text
        passed = True

    detail = ""
    if verbose and status in ("active", "stale"):
        detail = f"  soldier_id: {hb.get('soldier_id', 'N/A')}\n  missed_count: {hb.get('missed_count', 0)}"

    return {
        "label": "Heartbeat",
        "passed": passed,
        "summary": summary,
        "detail": detail,
        "warn": stale,
    }


def _check_git(sandbox_path: Path, verbose: bool) -> dict[str, Any]:
    """Check git status. Returns check result dict."""
    if not (sandbox_path / ".git").exists():
        return {
            "label": "Git",
            "passed": True,
            "summary": "no git repo",
            "detail": "",
        }

    try:
        # Check branch
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(sandbox_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"

        # Check clean status
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(sandbox_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        changes = status_result.stdout.strip()
        dirty = bool(changes)
        change_count = len([l for l in changes.split("\n") if l.strip()]) if changes else 0

        if dirty:
            summary = f"dirty ({change_count} changed files, branch: {branch})"
        else:
            summary = f"clean (branch: {branch})"

        detail = ""
        if verbose and dirty:
            detail = f"  Changes:\n" + "\n".join(f"    {l}" for l in changes.split("\n")[:15])
            if change_count > 15:
                detail += f"\n    ... and {change_count - 15} more"

        return {
            "label": "Git",
            "passed": not dirty,
            "summary": summary,
            "detail": detail,
            "warn": dirty,
        }
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return {
            "label": "Git",
            "passed": False,
            "summary": f"git check failed: {exc}",
            "detail": "",
        }


def _check_build(sandbox_path: Path, verbose: bool) -> dict[str, Any]:
    """Run project-appropriate build/analyze command. Returns check result dict."""
    project_type = detect_project_type(sandbox_path)
    if project_type == "unknown":
        return {
            "label": "Build",
            "passed": True,
            "summary": "no project detected (unknown type)",
            "detail": "",
        }

    cmd: list[str] | None = None
    cmd_name = ""
    if project_type == "flutter":
        cmd = ["flutter", "analyze"]
        cmd_name = "flutter analyze"
    elif project_type == "node":
        cmd = ["npx", "tsc", "--noEmit"]
        cmd_name = "tsc --noEmit"
    elif project_type == "python":
        cmd = ["python", "-m", "pytest", "-q", "--tb=short"]
        cmd_name = "pytest"
    elif project_type == "rust":
        cmd = ["cargo", "check"]
        cmd_name = "cargo check"

    if not cmd:
        return {
            "label": "Build",
            "passed": True,
            "summary": "no build command available",
            "detail": "",
        }

    try:
        result = subprocess.run(
            cmd,
            cwd=str(sandbox_path),
            capture_output=True,
            text=True,
            timeout=120,
        )
        passed = result.returncode == 0

        # Parse output for a meaningful summary
        stdout_lines = result.stdout.strip().split("\n") if result.stdout else []
        stderr_lines = result.stderr.strip().split("\n") if result.stderr else []

        if passed:
            # Flutter analyze
            if project_type == "flutter" and stdout_lines:
                last_line = stdout_lines[-1]
                summary = last_line
            elif project_type == "node" and stdout_lines:
                summary = f"passed — {len(stdout_lines)} lines of output"
            elif project_type == "python":
                # py.test summary line
                summary_lines = [l for l in stdout_lines if "passed" in l.lower() or "failed" in l.lower()]
                summary = summary_lines[-1] if summary_lines else "passed"
            elif project_type == "rust":
                summary_lines = [l for l in stderr_lines if "error" not in l.lower()]
                summary = summary_lines[-1].strip() if summary_lines else "passed"
            else:
                summary = "passed"
        else:
            # Collect first few errors
            error_lines: list[str] = []
            if project_type == "flutter":
                error_lines = [l.strip() for l in stdout_lines if "error" in l.lower() or "warning" in l.lower()]
            elif project_type == "node":
                error_lines = [l.strip() for l in stdout_lines if "error" in l.lower()]
                error_lines.extend(l.strip() for l in stderr_lines if "error" in l.lower())
            elif project_type == "python":
                # Get test count from pytest output
                error_lines = [l.strip() for l in stdout_lines if "failed" in l.lower()]
                if not error_lines:
                    error_lines = stdout_lines[-3:] if stdout_lines else stderr_lines[-3:]
            elif project_type == "rust":
                error_lines = [l.strip() for l in stderr_lines if "error" in l.lower()]

            error_summary = "; ".join(error_lines[:5])
            if len(error_lines) > 5:
                error_summary += f" ... and {len(error_lines) - 5} more"
            summary = error_summary if error_summary else f"failed (exit code {result.returncode})"

        detail = ""
        if verbose and not passed:
            out = "\n".join(stdout_lines[:20]) if stdout_lines else ""
            err = "\n".join(stderr_lines[:20]) if stderr_lines else ""
            if out:
                detail += f"  stdout:\n" + "\n".join(f"    {l}" for l in out.split("\n")[:20])
            if err:
                detail += f"  stderr:\n" + "\n".join(f"    {l}" for l in err.split("\n")[:20])

        return {
            "label": "Build",
            "passed": passed,
            "summary": f"{cmd_name}: {summary}" if summary else f"{cmd_name}: {'passed' if passed else 'failed'}",
            "detail": detail,
        }
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return {
            "label": "Build",
            "passed": False,
            "summary": f"build check failed: {exc}",
            "detail": "",
        }


def _check_circuit_breaker(sandbox: str, verbose: bool) -> dict[str, Any]:
    """Check circuit breaker status. Returns check result dict."""
    quarantined = is_quarantined(sandbox)
    return {
        "label": "Circuit",
        "passed": not quarantined,
        "summary": "quarantined" if quarantined else "active (0 failures)",
        "detail": "",
        "warn": quarantined,
    }


def _check_dispatch(sandbox: str, verbose: bool) -> dict[str, Any]:
    """Check for stale dispatch tasks for this sandbox. Returns check result dict."""
    if not DISPATCH_DIR.exists():
        return {
            "label": "Dispatch",
            "passed": True,
            "summary": "no dispatch directory",
            "detail": "",
        }

    all_tasks = list_all_tasks()
    stale_tasks = [
        t for t in all_tasks
        if t.get("sandbox") == sandbox and t.get("status") in ("pending", "dispatched", "running")
    ]

    count = len(stale_tasks)
    passed = count == 0
    if passed:
        summary = "no stale tasks"
    else:
        task_labels = []
        for t in stale_tasks[:5]:
            tid = t.get("task_id", "?")
            status = t.get("status", "?")
            label = t.get("label", tid)
            task_labels.append(f"{label} ({status})")
        summary = f"{count} stale task(s): {', '.join(task_labels)}"
        if count > 5:
            summary += f" ... and {count - 5} more"

    detail = ""
    if verbose and stale_tasks:
        for t in stale_tasks:
            tid = t.get("task_id", "?")
            status = t.get("status", "?")
            created = t.get("created_at", "")[:19]
            detail += f"  {tid}: {status} (created {created})\n"

    return {
        "label": "Dispatch",
        "passed": passed,
        "summary": summary,
        "detail": detail,
        "warn": not passed,
    }


CHECK_FUNCTIONS = [
    _check_budget,
    _check_heartbeat,
    _check_git,
    _check_build,
    _check_circuit_breaker,
    _check_dispatch,
]


@click.command()
@click.option("--sandbox", required=True, help="Sandbox name to check.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output.")
@click.option("--skip", type=str, multiple=True,
              help="Skip specific checks (budget, heartbeat, git, build, circuit, dispatch).")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
def check(sandbox: str, verbose: bool, skip: tuple[str, ...], json_output: bool) -> None:
    """Run health diagnostics on a sandbox.

    Runs up to 6 checks:

    \b
    \b
    1. BUDGET    — remaining tokens vs bootstrap max
    2. HEARTBEAT — last ping time and staleness
    3. GIT       — working tree clean/dirty
    4. BUILD     — flutter analyze / tsc / pytest / cargo check
    5. CIRCUIT   — circuit breaker quarantine status
    6. DISPATCH  — stale (pending/running) dispatch tasks

    Example:

        hero check --sandbox HERO

        hero check --sandbox HERO --verbose

        hero check --sandbox HERO --skip build --skip circuit
    """
    skip_set = set(skip)

    # Resolve sandbox path
    entry = SANDBOX_DIR / sandbox
    if not entry.exists():
        # Try as a project path directly
        sandbox_path = Path(sandbox)
        if not sandbox_path.exists():
            # Try ~/Development/<sandbox>
            sandbox_path = Path.home() / "Development" / sandbox
            if not sandbox_path.exists():
                raise click.ClickException(
                    f"Sandbox '{sandbox}' not found in {SANDBOX_DIR} "
                    f"or ~/Development/. Run 'hero status' first."
                )
    else:
        sandbox_path = entry

    # Build check args
    check_args = {"sandbox": sandbox, "verbose": verbose, "sandbox_path": sandbox_path}

    results: list[dict[str, Any]] = []
    all_passed = True

    for check_fn in CHECK_FUNCTIONS:
        label = check_fn.__name__.replace("_check_", "")
        if label in skip_set:
            continue

        if check_fn in (_check_git, _check_build):
            result = check_fn(sandbox_path, verbose)
        else:
            result = check_fn(sandbox, verbose)

        results.append(result)
        if not result["passed"]:
            all_passed = False

    # ── Output ──────────────────────────────────────────────────────
    if json_output:
        import json as _json

        output = {
            "sandbox": sandbox,
            "passed": all_passed,
            "checks": {},
        }
        for r in results:
            output["checks"][r["label"].lower()] = {
                "passed": r["passed"],
                "summary": r["summary"],
            }
        click.echo(_json.dumps(output, indent=2))
        return

    # Pretty output
    click.echo(f"\nhero check --sandbox {sandbox}\n")

    for r in results:
        if r["passed"]:
            icon = EMOJI_PASS
        elif r.get("warn"):
            icon = EMOJI_WARN
        else:
            icon = EMOJI_FAIL

        click.echo(f"  {icon} {r['label']}: {r['summary']}")

        if verbose and r.get("detail"):
            click.echo(r["detail"])

    click.echo("")
    if all_passed:
        click.echo(f"  {EMOJI_PASS} All checks passed — sandbox '{sandbox}' is healthy.")
    else:
        failures = [r["label"] for r in results if not r["passed"]]
        click.echo(f"  {EMOJI_FAIL} {len(failures)} check(s) failed: {', '.join(failures)}")
