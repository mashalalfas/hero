"""hero verify — Run VERIFY stage on a sandbox.

Composite gate: averages all pipeline stage scores and makes pass/fail decision.

Part of the HERO pipeline: PRE-COMMIT → BUILD → HARDEN → LEGAL → CI/PR → VERIFY → ARCHIVE

Scoring:
  - Computed as composite average of pre-commit, build, harden, legal, cipr scores
  - -10 penalty if any stage < 50 (failed)
  - -5 penalty if any stage < 70 (warning)
  - ≥70 PASS (proceed), 50-69 WARN (proceed with caution), <50 FAIL (block pipeline)
"""

from __future__ import annotations

import json as _json
import re
import subprocess
from pathlib import Path
from typing import Any

import click

from hero.commands.check import EMOJI_PASS, EMOJI_WARN, EMOJI_FAIL, EMOJI_INFO
from hero.commands.pre_commit import (
    _detect_project_type,
    _resolve_sandbox,
    _safe_run,
)
from hero.commands.score import _score_pipeline, _score_verify


# ── Main API ────────────────────────────────────────────────────────────


def run_verify(sandbox_path: str | Path, verbose: bool = False, **kwargs: Any) -> dict[str, Any]:
    """Run VERIFY composite gate and return structured results.

    Scores all pipeline stages (pre-commit, build, harden, legal, cipr)
    and computes the composite VERIFY score with penalty modifiers.

    Parameters
    ----------
    sandbox_path : str or Path
        Path to the sandbox/project directory.
    verbose : bool, default=False
        Include detailed output in each check result.

    Returns
    -------
    dict
        Results dict with structure:

        .. code-block:: python

            {
                "sandbox": str,
                "passed": bool,
                "score": int,            # 0-100
                "status": str,           # "pass" | "warn" | "fail"
                "stage_scores": {
                    "pre-commit": {...},
                    "build": {...},
                    "harden": {...},
                    "legal": {...},
                    "cipr": {...},
                },
                "findings": [...],
            }
    """
    path = Path(sandbox_path).resolve()

    # Score all pipeline stages
    scores = _score_pipeline("all", path)

    # Extract stage scores (exclude the composite verify entry)
    stage_scores = {k: v for k, v in scores.items() if k != "verify"}

    # Get the composite verify result
    verify_result = scores.get("verify", _score_verify(stage_scores))

    score = verify_result["score"]
    status = verify_result["status"]
    passed = status == "pass" or status == "warn"

    # Build findings from all stage scores
    findings: list[dict[str, str]] = []
    for stage_name, stage_data in stage_scores.items():
        if stage_data["status"] == "fail":
            findings.append({
                "severity": "error",
                "stage": stage_name,
                "message": f"{stage_name.replace('-', '/').upper()} stage failed (score: {stage_data['score']}/100)",
            })
        elif stage_data["status"] == "warn":
            findings.append({
                "severity": "warning",
                "stage": stage_name,
                "message": f"{stage_name.replace('-', '/').upper()} stage warning (score: {stage_data['score']}/100)",
            })

    # Add penalty findings
    stage_score_values = [s["score"] for s in stage_scores.values()]
    any_below_50 = any(s < 50 for s in stage_score_values)
    any_below_70 = any(s < 70 for s in stage_score_values)

    if any_below_50:
        findings.append({
            "severity": "error",
            "stage": "verify",
            "message": "Stage(s) below 50: -10 penalty applied",
        })
    elif any_below_70:
        findings.append({
            "severity": "warning",
            "stage": "verify",
            "message": "Stage(s) below 70: -5 penalty applied",
        })

    return {
        "sandbox": str(path),
        "passed": passed,
        "score": score,
        "status": status,
        "stage_scores": stage_scores,
        "findings": findings,
    }


# ── Click command ───────────────────────────────────────────────────────


@click.command()
@click.option("--sandbox", required=True, help="Sandbox path or name.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed findings.")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
@click.option("--dry-run", is_flag=True, help="Show what would be checked without running.")
def verify(sandbox: str, verbose: bool, json_output: bool, dry_run: bool) -> None:
    """Run VERIFY composite gate on a sandbox.

    Averages all pipeline stage scores (pre-commit, build, harden, legal, cipr)
    and applies penalties to produce the final VERIFY score and pass/fail decision.

    \b
    Scoring rubric:
        Start at 100 (average of all stage scores)
        -10 if any stage < 50 (failed)
        -5 if any stage < 70 (warning)
        ≥70 PASS (proceed), 50-69 WARN (proceed with caution), <50 FAIL (block pipeline)

    \b
    Pipeline stages scored:
        PRE-COMMIT — secrets, lint errors, missing headers
        BUILD      — analyze pass, build success, obfuscation
        HARDEN     — trivy CVEs, secrets, root detection, cert pinning, debug symbols
        LEGAL      — EULA, privacy policy, SBOM, license risk, legal-config.json
        CI/PR      — tests pass, security scan, build artifacts

    Examples:

        hero verify --sandbox ~/Development/MyApp

        hero verify --sandbox HERO --verbose

        hero verify --sandbox MyApp --dry-run

        hero verify --sandbox MyApp --json
    """
    sandbox_path = _resolve_sandbox(sandbox)
    project_type = _detect_project_type(sandbox_path)

    # ── Dry-run mode ─────────────────────────────────────────────────
    if dry_run:
        click.echo(f"\nhero verify --sandbox {sandbox_path.name} (dry run)\n")
        click.echo(f"  Project type: {project_type}")
        click.echo(f"  {EMOJI_INFO} Would score: PRE-COMMIT stage (secrets, lint, headers)")
        click.echo(f"  {EMOJI_INFO} Would score: BUILD stage (analyze, build, obfuscation)")
        click.echo(f"  {EMOJI_INFO} Would score: HARDEN stage (trivy, secrets, root detection, cert pinning, debug symbols)")
        click.echo(f"  {EMOJI_INFO} Would score: LEGAL stage (EULA, privacy, SBOM, license, legal-config)")
        click.echo(f"  {EMOJI_INFO} Would score: CI/PR stage (tests, security scan, build artifacts)")
        click.echo(f"  {EMOJI_INFO} Would compute: composite VERIFY score with penalty modifiers")
        click.echo(f"\n  No stages scored (dry run).")
        click.echo("")
        return

    # ── Run verify checks ────────────────────────────────────────────
    result = run_verify(sandbox_path, verbose=verbose)

    # ── JSON output ──────────────────────────────────────────────────
    if json_output:
        json_result = {
            "sandbox": result["sandbox"],
            "passed": result["passed"],
            "score": result["score"],
            "status": result["status"],
            "stage_scores": {
                k: {
                    "score": v["score"],
                    "status": v["status"],
                    "details": v["details"],
                }
                for k, v in result["stage_scores"].items()
            },
            "findings": result["findings"],
        }
        click.echo(_json.dumps(json_result, indent=2))
        return

    # ── Pretty output ────────────────────────────────────────────────
    click.echo(f"\nhero verify --sandbox {sandbox_path.name}\n")

    # Stage score lines
    for stage_name in ["pre-commit", "build", "harden", "legal", "cipr"]:
        s = result["stage_scores"].get(stage_name, {"score": 0, "status": "fail", "details": "not scored"})
        if s["status"] == "pass":
            icon = EMOJI_PASS
        elif s["status"] == "warn":
            icon = EMOJI_WARN
        else:
            icon = EMOJI_FAIL
        stage_label = stage_name.replace("-", "/").upper()
        click.echo(f"  {icon} {stage_label:<14} {s['score']:>3}/100  ({s['status']})  — {s['details']}")

    # Verbose details
    if verbose:
        for stage_name, label in [
            ("pre-commit", "Pre-commit"),
            ("build", "Build"),
            ("harden", "Harden"),
            ("legal", "Legal"),
            ("cipr", "CI/PR"),
        ]:
            s = result["stage_scores"].get(stage_name, {"details": "", "score": 0})
            if s.get("details") and s["details"] != "clean" and s["details"] != "no issues":
                click.echo(f"\n  {label} details:")
                click.echo(f"    {s['details']}")
                if verbose > 0:
                    # Score breakdown is implicit in details
                    pass

    # Score line
    score = result["score"]
    status = result["status"]
    if status == "pass":
        score_icon = EMOJI_PASS
        status_label = "PASS"
    elif status == "warn":
        score_icon = EMOJI_WARN
        status_label = "WARN"
    else:
        score_icon = EMOJI_FAIL
        status_label = "FAIL"

    click.echo(f"\n  Score: {score}/100 — {score_icon} {status_label}")
    click.echo(f"  {EMOJI_INFO} Verified stage scores from all pipeline stages")

    # Findings summary
    if result["findings"]:
        error_count = sum(1 for f in result["findings"] if f["severity"] == "error")
        warning_count = sum(1 for f in result["findings"] if f["severity"] == "warning")
        parts = []
        if error_count:
            parts.append(f"{EMOJI_FAIL} {error_count} error(s)")
        if warning_count:
            parts.append(f"{EMOJI_WARN} {warning_count} warning(s)")
        click.echo(f"  {' '.join(parts)}")

    click.echo("")
