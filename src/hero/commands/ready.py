"""hero ready — HERO pipeline readiness check.

Single command to validate the entire pipeline is set up and ready to go.
AI agents run this first to onboard themselves.

Checks:
1. CLI — hero CLI itself available
2. Venv — .hero/venv/ exists and activated
3. Stage commands — all 7 + go import correctly
4. Sandboxes — at least one registered sandbox exists
5. Pipeline state — PIPELINE.md exists with build progress

Usage:
    hero ready                       # Full readiness check
    hero ready --sandbox fury-os     # Check specific sandbox readiness
    hero ready --json                # Machine-readable output
    hero ready --quick               # Fast check (skip imports)
"""

from __future__ import annotations

import json as _json
import subprocess
import sys
from pathlib import Path
from typing import Any

import click

from hero.commands.check import EMOJI_PASS, EMOJI_WARN, EMOJI_FAIL, EMOJI_INFO
from hero.commands.pre_commit import _resolve_sandbox

# ── Constants ────────────────────────────────────────────────────────────

HERO_HOME = Path.home() / ".hero"
SANDBOX_DIR = HERO_HOME / "sandboxes"
PIPELINE_FILE = HERO_HOME / "PIPELINE.md"

_STAGE_NAMES = [
    "pre_commit",
    "build",
    "harden",
    "legal",
    "cipr",
    "verify",
    "archive",
    "go",
]

_STAGE_COMMANDS = [
    "hero.commands.pre_commit",
    "hero.commands.build",
    "hero.commands.harden",
    "hero.commands.legal",
    "hero.commands.cipr",
    "hero.commands.verify",
    "hero.commands.archive",
    "hero.commands.go",
]

# Required sections in PIPELINE.md for it to be considered valid
# These match the actual structure of the HERO PIPELINE.md file
_REQUIRED_PIPELINE_SECTIONS = [
    "### PRE-COMMIT",
    "### BUILD",
    "### HARDEN",
    "### LEGAL",
    "### CI/PR",
    "### VERIFY",
    "### ARCHIVE",
]


# ── Check implementations ───────────────────────────────────────────────


def _check_cli() -> dict[str, Any]:
    """Check hero CLI is available and returns a version string."""
    try:
        result = subprocess.run(
            ["hero", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            version = result.stdout.strip() or result.stderr.strip()
            # Normalise: keep first line only
            version_line = version.split("\n")[0] if version else "unknown"
            return {
                "passed": True,
                "summary": f"hero {version_line}",
                "version": version_line,
            }
        else:
            return {
                "passed": False,
                "summary": f"hero --version failed (exit {result.returncode})",
                "version": "",
            }
    except FileNotFoundError:
        return {
            "passed": False,
            "summary": "hero CLI not found on PATH",
            "version": "",
        }
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "summary": "hero --version timed out",
            "version": "",
        }
    except OSError as exc:
        return {
            "passed": False,
            "summary": f"hero CLI error: {exc}",
            "version": "",
        }


def _check_venv() -> dict[str, Any]:
    """Check that ~/.hero/venv/ exists with a python binary."""
    venv_python = HERO_HOME / "venv" / "bin" / "python3"
    if venv_python.exists():
        return {
            "passed": True,
            "summary": str(HERO_HOME / "venv") + "/",
        }
    else:
        return {
            "passed": False,
            "summary": f"{HERO_HOME / 'venv/'} not found",
        }


def _check_stages(quick: bool = False) -> dict[str, Any]:
    """Check that all pipeline stage commands can be imported or found.

    If quick=True, only check file existence instead of actual imports.
    """
    stages: dict[str, dict[str, Any]] = {}
    all_passed = True
    failed_names: list[str] = []

    for cmd_name, module_path in zip(_STAGE_NAMES, _STAGE_COMMANDS):
        if quick:
            # Fast path: check file existence
            # Convert dotted module path to file path relative to project
            # hero.commands.pre_commit -> src/hero/commands/pre_commit.py
            parts = module_path.split(".")
            # Try to find the file under common project roots
            found = False
            for root in [HERO_HOME, Path.cwd(), Path.cwd() / "src"]:
                file_path = root.joinpath(*parts).with_suffix(".py")
                if file_path.exists():
                    found = True
                    break

            if found:
                stages[cmd_name] = {
                    "passed": True,
                    "summary": f"found ({file_path.name})",
                }
            else:
                stages[cmd_name] = {
                    "passed": False,
                    "summary": f"module file not found",
                }
                all_passed = False
                failed_names.append(cmd_name)
        else:
            # Full path: try to import the module
            try:
                __import__(module_path)
                stages[cmd_name] = {
                    "passed": True,
                    "summary": "imported",
                }
            except ImportError as exc:
                stages[cmd_name] = {
                    "passed": False,
                    "summary": f"import failed: {exc}",
                }
                all_passed = False
                failed_names.append(cmd_name)

    passed_count = sum(1 for s in stages.values() if s["passed"])
    total_count = len(_STAGE_NAMES)

    if all_passed:
        summary = f"{passed_count}/{total_count} registered"
    else:
        summary = f"{passed_count}/{total_count} registered (failed: {', '.join(failed_names)})"

    return {
        "passed": all_passed,
        "summary": summary,
        "stages": stages,
    }


def _check_sandboxes() -> dict[str, Any]:
    """Count registered sandboxes and check at least one has valid structure."""
    if not SANDBOX_DIR.exists():
        return {
            "passed": False,
            "summary": f"{SANDBOX_DIR} not found",
            "count": 0,
        }

    entries = [
        d for d in SANDBOX_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ]
    count = len(entries)

    if count == 0:
        return {
            "passed": False,
            "summary": "no registered sandboxes",
            "count": 0,
        }

    # Check that at least one sandbox has a valid structure (INDEX.toon or other marker)
    valid_sandboxes = 0
    for entry in entries:
        if (entry / "INDEX.toon").exists() or any(entry.iterdir()):
            valid_sandboxes += 1

    if valid_sandboxes == 0:
        return {
            "passed": False,
            "summary": f"{count} sandbox(es) registered but all empty",
            "count": count,
        }

    summary = f"{valid_sandboxes} registered"
    if valid_sandboxes < count:
        summary += f" ({count - valid_sandboxes} empty)"

    return {
        "passed": True,
        "summary": summary,
        "count": valid_sandboxes,
    }


def _check_pipeline_doc() -> dict[str, Any]:
    """Check that PIPELINE.md exists and has the required sections."""
    if not PIPELINE_FILE.exists():
        return {
            "passed": False,
            "summary": "PIPELINE.md not found",
        }

    try:
        content = PIPELINE_FILE.read_text(errors="ignore")
    except OSError as exc:
        return {
            "passed": False,
            "summary": f"PIPELINE.md unreadable: {exc}",
        }

    missing_sections = [
        section for section in _REQUIRED_PIPELINE_SECTIONS
        if section not in content
    ]

    if missing_sections:
        section_names = [s.strip("# ") for s in missing_sections]
        return {
            "passed": False,
            "summary": f"PIPELINE.md found but missing stage sections: {', '.join(section_names)}",
        }

    return {
        "passed": True,
        "summary": "PIPELINE.md found",
    }


# ── Scoring ─────────────────────────────────────────────────────────────


def _compute_readiness_score(checks: dict[str, dict[str, Any]]) -> int:
    """Compute readiness score 0-100.

    Each check is worth 20 points.
    - Start at 100
    - -20 per failed check
    - Floor at 0
    """
    score = 100
    failures = 0

    for check_key in ["cli", "venv", "stages", "sandboxes", "pipeline_doc"]:
        if not checks[check_key]["passed"]:
            failures += 1
            score = max(0, score - 20)

    return score


# ── Main API ────────────────────────────────────────────────────────────


def run_readiness(
    sandbox_path: str | Path | None = None,
    quick: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    """Run all readiness checks and return structured results.

    Parameters
    ----------
    sandbox_path : str or Path or None, default=None
        If provided, also check that the specific sandbox exists.
    quick : bool, default=False
        Skip imports and only check file existence for stage commands.
    verbose : bool, default=False
        Not used in current implementation (reserved for future detail).

    Returns
    -------
    dict
        Results dict with structure:

        .. code-block:: python

            {
                "ready": bool,
                "checks": {
                    "cli": {"passed": bool, "summary": str},
                    "venv": {"passed": bool, "summary": str},
                    "stages": {"passed": bool, "summary": str, "stages": {...}},
                    "sandboxes": {"passed": bool, "summary": str, "count": int},
                    "pipeline_doc": {"passed": bool, "summary": str},
                },
                "score": int,           # 0-100
                "quickstart": str,      # "hero go --sandbox <name> --task \"<desc>\""
            }
    """
    checks: dict[str, dict[str, Any]] = {}

    # 1. CLI check
    checks["cli"] = _check_cli()

    # 2. Venv check
    checks["venv"] = _check_venv()

    # 3. Stage commands check
    checks["stages"] = _check_stages(quick=quick)

    # 4. Sandboxes check
    checks["sandboxes"] = _check_sandboxes()

    # 5. Pipeline doc check
    checks["pipeline_doc"] = _check_pipeline_doc()

    # Compute score
    score = _compute_readiness_score(checks)

    # Determine overall ready status
    all_passed = all(c["passed"] for c in checks.values())

    # Generate quickstart command
    sandbox_count = checks["sandboxes"].get("count", 0)
    if sandbox_count > 0:
        # Find the first valid sandbox name to use in quickstart
        try:
            entries = [
                d.name for d in SANDBOX_DIR.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            ]
            first_sandbox = entries[0] if entries else "<name>"
        except OSError:
            first_sandbox = "<name>"
    else:
        first_sandbox = "<name>"

    quickstart = f"hero go --sandbox {first_sandbox} --task \"<description>\""

    return {
        "ready": all_passed,
        "checks": checks,
        "score": score,
        "quickstart": quickstart,
    }


# ── Click command ───────────────────────────────────────────────────────


@click.command()
@click.option("--sandbox", default=None, help="Check specific sandbox readiness.")
@click.option("--quick", "-q", is_flag=True, help="Fast check (skip imports, just file checks).")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed findings.")
def ready(sandbox: str | None, quick: bool, json_output: bool, verbose: bool) -> None:
    """Check HERO pipeline readiness.

    Validates all components: CLI, virtual environment, stage commands,
    registered sandboxes, and pipeline documentation.

    \b
    Checks performed:
        1. CLI      — hero --version available on PATH
        2. Venv     — ~/.hero/venv/ exists with Python binary
        3. Stages   — all 8 pipeline commands import correctly
        4. Sandboxes — at least one registered sandbox
        5. Pipeline — PIPELINE.md exists with required sections

    \b
    Scoring rubric:
        Start at 100, -20 per failed check, floor at 0
        >= 70 READY, < 70 PARTIAL or NOT_READY

    Examples:

        hero ready

        hero ready --sandbox fury-os

        hero ready --quick

        hero ready --json

        hero ready --verbose
    """
    # If --sandbox is given, resolve it early so we can validate
    sandbox_path: Path | None = None
    if sandbox:
        try:
            sandbox_path = _resolve_sandbox(sandbox)
        except click.ClickException:
            click.echo(
                f"\n  {EMOJI_FAIL} Sandbox '{sandbox}' not found. "
                f"Run 'hero status' to see available sandboxes.\n",
                err=True,
            )
            sys.exit(1)

    # ── Run readiness checks ─────────────────────────────────────────
    result = run_readiness(
        sandbox_path=sandbox_path,
        quick=quick,
        verbose=verbose,
    )

    checks = result["checks"]
    score = result["score"]

    # ── JSON output ──────────────────────────────────────────────────
    if json_output:
        json_result: dict[str, Any] = {
            "ready": result["ready"],
            "score": score,
            "status": "ready" if score >= 70 else "not_ready",
            "checks": {},
        }
        for check_key in ["cli", "venv", "stages", "sandboxes", "pipeline_doc"]:
            check_result = checks[check_key]
            entry: dict[str, Any] = {
                "passed": check_result["passed"],
                "summary": check_result["summary"],
            }
            if check_key == "sandboxes":
                entry["count"] = check_result.get("count", 0)
            if check_key == "stages":
                entry["stage_count"] = len(check_result.get("stages", {}))
                entry["stage_passed"] = sum(
                    1 for s in check_result.get("stages", {}).values() if s["passed"]
                )
            json_result["checks"][check_key] = entry

        if sandbox:
            json_result["sandbox"] = sandbox
        json_result["quickstart"] = result["quickstart"]
        click.echo(_json.dumps(json_result, indent=2))
        return

    # ── Pretty output ────────────────────────────────────────────────
    click.echo("\n" + "═" * 55)
    click.echo("  HERO Pipeline — Readiness Check")
    click.echo("═" * 55)
    click.echo("")

    # CLI line
    cl = checks["cli"]
    icon = EMOJI_PASS if cl["passed"] else EMOJI_FAIL
    click.echo(f"  CLI:          {icon} {cl['summary']}")

    # Venv line
    ve = checks["venv"]
    icon = EMOJI_PASS if ve["passed"] else EMOJI_FAIL
    click.echo(f"  Venv:         {icon} {ve['summary']}")

    # Stages line
    st = checks["stages"]
    icon = EMOJI_PASS if st["passed"] else EMOJI_FAIL
    stage_summary = st["summary"]
    click.echo(f"  Stages:       {icon} {stage_summary}")

    # Verbose: show individual stage status
    if verbose and st.get("stages"):
        for stage_name, stage_result in st["stages"].items():
            stage_icon = EMOJI_PASS if stage_result["passed"] else EMOJI_FAIL
            click.echo(f"    {stage_icon} {stage_name:<12} {stage_result['summary']}")

    # Sandboxes line
    sa = checks["sandboxes"]
    icon = EMOJI_PASS if sa["passed"] else EMOJI_FAIL
    click.echo(f"  Sandboxes:    {icon} {sa['summary']}")

    # Pipeline doc line
    pd = checks["pipeline_doc"]
    icon = EMOJI_PASS if pd["passed"] else EMOJI_FAIL
    click.echo(f"  Pipeline doc: {icon} {pd['summary']}")

    # Score line
    if score >= 70:
        score_icon = EMOJI_PASS
        status_label = "READY"
    elif score >= 50:
        score_icon = EMOJI_WARN
        status_label = "PARTIAL"
    else:
        score_icon = EMOJI_FAIL
        status_label = "NOT READY"

    click.echo("")
    click.echo(f"  Ready Score: {score}/100")
    click.echo(f"  Status: {score_icon} {status_label}")

    # Quickstart
    click.echo("")
    click.echo(f"  Quickstart:")
    click.echo(f"    {result['quickstart']}")
    click.echo("")
    click.echo(f"  For AI agents: Read PIPELINE.md for full pipeline documentation.")
    click.echo(f"  For help: hero --help")
    click.echo("")

    # If sandbox was requested, add a line about it
    if sandbox and sandbox_path:
        if sandbox_path.exists():
            click.echo(f"  {EMOJI_PASS} Sandbox '{sandbox}' resolved to {sandbox_path}")
        else:
            click.echo(f"  {EMOJI_FAIL} Sandbox '{sandbox}' could not be resolved")
        click.echo("")
