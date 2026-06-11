"""hero cipr — Run CI/PR stage checks on a sandbox.

Checks:
1. Test runner — run project-appropriate test suite, count passed/failed
2. Trivy scan — dependency CVE scan (CRITICAL only)
3. Build artifact verification — check build/ or dist/ exists and is non-empty
4. Brakeman scan — Rails security scan (if Gemfile detected)

Part of the HERO pipeline: PRE-COMMIT → BUILD → HARDEN → LEGAL → CI/PR → VERIFY → ARCHIVE
"""

from __future__ import annotations

import json
import re
import shutil
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

# ── Helpers ──────────────────────────────────────────────────────────────


def _is_rails_project(sandbox_path: Path) -> bool:
    """Detect a Ruby on Rails project by the presence of Gemfile with rails."""
    gemfile = sandbox_path / "Gemfile"
    if not gemfile.exists():
        return False
    try:
        content = gemfile.read_text(errors="ignore")
        return "rails" in content.lower()
    except OSError:
        return False


def _count_test_failures(output: str) -> tuple[int, int]:
    """Parse test runner output for failure indicators.

    Returns (failure_count, error_line_count).
    Tries to extract explicit counts first, falls back to keyword counting.
    """
    failure_count = 0
    error_line_count = 0

    # Try common "N failed, M passed" patterns
    # Flutter: "12345 tests passed, 2 failed"
    m = re.search(r'(\d+)\s+failed', output, re.IGNORECASE)
    if m:
        failure_count = max(failure_count, int(m.group(1)))

    # pytest: "= 5 failed, 45 passed"
    m = re.search(r'=\s+(\d+)\s+failed', output, re.IGNORECASE)
    if m:
        failure_count = max(failure_count, int(m.group(1)))

    # Count lines containing failure keywords
    for line in output.splitlines():
        ls = line.strip()
        if not ls:
            continue
        if any(kw in ls.upper() for kw in ["FAILED", "FAILURE", "ERROR:"]):
            error_line_count += 1

    return failure_count, error_line_count


def _run_tests(sandbox_path: Path, project_type: str) -> tuple[bool, str, int]:
    """Run the project's test suite.

    Returns (all_passed, summary, failure_count).
    """
    if project_type == "unknown":
        return True, "no project type detected (skipped)", 0

    cmd: list[str] | None = None
    cmd_label = ""

    if project_type == "flutter":
        cmd = ["flutter", "test"]
        cmd_label = "flutter test"
    elif project_type == "node":
        cmd = ["npm", "test"]
        cmd_label = "npm test"
    elif project_type == "python":
        cmd = ["pytest", "-q"]
        cmd_label = "pytest"
    elif project_type == "rust":
        cmd = ["cargo", "test"]
        cmd_label = "cargo test"
    else:
        return True, f"no test runner for {project_type} (skipped)", 0

    result, err = _safe_run(cmd, cwd=sandbox_path, timeout=120)
    if result is None:
        return True, f"{cmd_label} unavailable: {err} (skipped)", 0

    output = (result.stdout or "") + (result.stderr or "")
    all_passed = result.returncode == 0
    failure_count, _ = _count_test_failures(output)

    if all_passed and failure_count == 0:
        summary = f"all tests passed ({cmd_label})"
    elif all_passed:
        summary = f"passed (exit 0) but {failure_count} failure indicator(s) found"
    else:
        summary = f"{failure_count} test(s) failed (exit {result.returncode})" if failure_count else f"tests failed (exit {result.returncode})"

    return all_passed, summary, failure_count


def _run_trivy(sandbox_path: Path) -> tuple[list[str], str]:
    """Run trivy fs against sandbox_path, return (critical_findings, status_note).

    status_note is empty on success, or a skip/missing message.
    """
    if shutil.which("trivy") is None:
        # Try pre-generated report
        report = sandbox_path / "trivy-report.json"
        if report.exists():
            try:
                data = json.loads(report.read_text())
                findings: list[str] = []
                results = data.get("Results", [])
                for res in results:
                    for vuln in res.get("Vulnerabilities", []):
                        sev = vuln.get("Severity", "").upper()
                        if sev == "CRITICAL":
                            findings.append(
                                f"{vuln.get('PkgID', '?')} — {vuln.get('Title', 'CVE')}"
                            )
                return findings, ""
            except (json.JSONDecodeError, OSError):
                pass
        return [], "trivy not installed (skipped)"

    result, err = _safe_run(
        ["trivy", "fs", "--severity", "CRITICAL", "--no-progress", str(sandbox_path)],
        cwd=sandbox_path,
        timeout=120,
    )
    if result is None:
        return [], err or "trivy execution failed"

    output = result.stdout or ""
    findings: list[str] = []
    for line in output.splitlines():
        line_s = line.strip()
        if not line_s:
            continue
        if "CRITICAL" in line_s.upper():
            findings.append(line_s[:200])

    return findings, ""


def _check_build_artifacts(sandbox_path: Path, project_type: str) -> tuple[bool, str, int]:
    """Check that build output directory exists and is non-empty.

    Returns (exists_and_non_empty, summary, file_count).
    """
    candidates: list[Path] = []
    if project_type == "flutter":
        candidates = [sandbox_path / "build"]
    elif project_type == "node":
        candidates = [sandbox_path / "dist", sandbox_path / "build"]
    elif project_type == "python":
        candidates = [sandbox_path / "dist", sandbox_path / "build"]
    elif project_type == "rust":
        candidates = [sandbox_path / "target" / "release", sandbox_path / "target" / "debug"]

    for d in candidates:
        if d.exists() and d.is_dir():
            try:
                files = list(d.rglob("*"))
                file_count = sum(1 for f in files if f.is_file())
                if file_count > 0:
                    return True, f"{d.name}/ exists ({file_count} file(s))", file_count
                else:
                    return False, f"{d.name}/ exists but is empty", 0
            except OSError:
                return False, f"{d.name}/ exists but unreadable", 0

    dir_names = ", ".join(d.name + "/" for d in candidates) if candidates else "build/ or dist/"
    return False, f"{dir_names} not found", 0


def _run_brakeman(sandbox_path: Path) -> tuple[list[str], str]:
    """Run brakeman security scan on a Rails project.

    Returns (high_findings, status_note).
    status_note is empty on success, or a skip/missing message.
    """
    if not _is_rails_project(sandbox_path):
        return [], "not a Rails project"

    if shutil.which("brakeman") is None:
        return [], "brakeman not installed (skipped)"

    # Try to write report to security/ subdirectory
    report_dir = sandbox_path / "security"
    report_dir.mkdir(exist_ok=True)
    report_file = report_dir / "brakeman-report.json"

    result, err = _safe_run(
        ["brakeman", "-q", "-o", str(report_file)],
        cwd=sandbox_path,
        timeout=120,
    )
    if result is None:
        return [], err or "brakeman execution failed"

    # Parse the JSON report for high-severity findings
    try:
        if report_file.exists():
            data = json.loads(report_file.read_text())
        else:
            # brakeman -q may write to stdout on failure
            data = {}
    except (json.JSONDecodeError, OSError):
        data = {}

    findings: list[str] = []
    warnings = data.get("warnings", [])
    for w in warnings:
        confidence = w.get("confidence", "").lower()
        warning_type = w.get("warning_type", "")
        file_path = w.get("file", "")
        # Treat "High" confidence as high severity
        if confidence == "high":
            findings.append(f"{warning_type} in {file_path} (confidence: high)")

    if not findings and warnings:
        return [], f"brakeman ran, {len(warnings)} warning(s) (none high confidence)"

    return findings, ""


# ── Scoring ─────────────────────────────────────────────────────────────


def _compute_cipr_score(
    test_failures: int,
    test_all_passed: bool,
    trivy_findings: list[str],
    artifacts_ok: bool,
    brakeman_high: list[str],
) -> tuple[int, list[dict[str, str]]]:
    """Compute CI/PR score.

    Rubric:
        Start at 100
        -30 if tests fail entirely, -10 per additional failure
        -25 per CRITICAL CVE
        -10 if build artifacts missing
        -20 per brakeman high finding (Rails only)
        Floor at 0
    """
    score = 100
    findings: list[dict[str, str]] = []

    # Test failures
    if not test_all_passed:
        score = max(0, score - 30)
        findings.append({
            "severity": "error",
            "check": "tests",
            "message": f"Tests failed (-30)",
        })

    if test_failures > 1:
        additional = test_failures - 1
        deduction = additional * 10
        score = max(0, score - deduction)
        findings.append({
            "severity": "error",
            "check": "tests",
            "message": f"{additional} additional test failure(s) (-{deduction})",
        })
    elif test_failures == 1 and test_all_passed:
        # One failure but still exit 0 (partial failure)
        score = max(0, score - 10)
        findings.append({
            "severity": "warning",
            "check": "tests",
            "message": "1 test failure indicator found (-10)",
        })

    # Trivy CVEs
    cve_count = len(trivy_findings)
    if cve_count > 0:
        deduction = cve_count * 25
        score = max(0, score - deduction)
        findings.append({
            "severity": "critical",
            "check": "trivy",
            "message": f"{cve_count} CRITICAL CVE(s) found (-{deduction})",
        })

    # Build artifacts
    if not artifacts_ok:
        score = max(0, score - 10)
        findings.append({
            "severity": "error",
            "check": "artifacts",
            "message": "Build artifacts missing (-10)",
        })

    # Brakeman high findings
    high_count = len(brakeman_high)
    if high_count > 0:
        deduction = high_count * 20
        score = max(0, score - deduction)
        findings.append({
            "severity": "critical",
            "check": "brakeman",
            "message": f"{high_count} high-severity brakeman finding(s) (-{deduction})",
        })

    return score, findings


# ── Main API ────────────────────────────────────────────────────────────


def run_cipr(sandbox_path: str | Path, verbose: bool = False) -> dict[str, Any]:
    """Run CI/PR checks on a sandbox.

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
                "passed": bool,
                "score": int,            # 0-100
                "status": str,           # "pass" | "warn" | "fail"
                "project_type": str,
                "checks": {
                    "tests": {...},
                    "trivy": {...},
                    "artifacts": {...},
                    "brakeman": {...},
                },
                "findings": [...],
                "sandbox": str,
            }
    """
    path = Path(sandbox_path).resolve()
    project_type = _detect_project_type(path)
    is_rails = _is_rails_project(path)

    # 1. Test runner
    tests_passed, tests_summary, test_failures = _run_tests(path, project_type)

    # 2. Trivy scan
    trivy_findings, trivy_note = _run_trivy(path)
    trivy_ok = len(trivy_findings) == 0
    if trivy_note:
        trivy_summary = trivy_note
        trivy_detail = trivy_note if verbose else ""
    elif trivy_ok:
        trivy_summary = "0 CRITICAL CVEs"
        trivy_detail = ""
    else:
        trivy_summary = f"{len(trivy_findings)} CRITICAL CVE(s) found"
        trivy_detail = "\n".join(f"    - {f}" for f in trivy_findings[:5]) if verbose else ""
        if len(trivy_findings) > 5:
            trivy_detail += f"\n    ... and {len(trivy_findings) - 5} more"

    # 3. Build artifact verification
    artifacts_ok, artifacts_summary, artifact_count = _check_build_artifacts(path, project_type)

    # 4. Brakeman scan (Rails only)
    brakeman_high, brakeman_note = _run_brakeman(path)
    brakeman_skipped = brakeman_note == "not a Rails project" or brakeman_note == "brakeman not installed (skipped)"
    if brakeman_skipped:
        brakeman_summary = "Skipped (not a Rails project)" if not is_rails else "Skipped (brakeman not installed)"
        brakeman_detail = ""
    elif brakeman_note and "no high confidence" in brakeman_note.lower():
        brakeman_summary = f"0 high-severity findings ({brakeman_note})"
        brakeman_detail = ""
    elif brakeman_ok := len(brakeman_high) == 0:
        brakeman_summary = "0 high-severity findings"
        brakeman_detail = ""
    else:
        brakeman_summary = f"{len(brakeman_high)} high-severity finding(s)"
        brakeman_detail = "\n".join(f"    - {f}" for f in brakeman_high[:5]) if verbose else ""
        if len(brakeman_high) > 5:
            brakeman_detail += f"\n    ... and {len(brakeman_high) - 5} more"

    # ── Score ─────────────────────────────────────────────────────────
    score, findings = _compute_cipr_score(
        test_failures=test_failures if not tests_passed else 0,
        test_all_passed=tests_passed,
        trivy_findings=trivy_findings,
        artifacts_ok=artifacts_ok,
        brakeman_high=brakeman_high,
    )

    # Handle partial failure case (1 failure, still exit 0)
    if tests_passed and test_failures == 1:
        score, findings = _compute_cipr_score(
            test_failures=1,
            test_all_passed=True,
            trivy_findings=trivy_findings,
            artifacts_ok=artifacts_ok,
            brakeman_high=brakeman_high,
        )

    if score >= 70:
        status = "pass"
        passed = True
    elif score >= 50:
        status = "warn"
        passed = True
    else:
        status = "fail"
        passed = False

    return {
        "sandbox": str(path),
        "project_type": project_type,
        "passed": passed,
        "score": score,
        "status": status,
        "checks": {
            "tests": {
                "passed": tests_passed,
                "summary": tests_summary,
                "detail": "",
            },
            "trivy": {
                "passed": trivy_ok,
                "summary": trivy_summary,
                "detail": trivy_detail,
            },
            "artifacts": {
                "passed": artifacts_ok,
                "summary": artifacts_summary,
                "detail": "",
            },
            "brakeman": {
                "passed": len(brakeman_high) == 0,
                "summary": brakeman_summary,
                "detail": brakeman_detail,
            },
        },
        "findings": findings,
    }


# ── Click command ───────────────────────────────────────────────────────


@click.command()
@click.option("--sandbox", required=True, help="Sandbox path or name.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed findings.")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
@click.option("--dry-run", is_flag=True, help="Show what would be checked without running.")
def cipr(sandbox: str, verbose: bool, json_output: bool, dry_run: bool) -> None:
    """Run CI/PR checks on a sandbox.

    Runs tests, dependency CVE scan, build artifact verification, and
    (for Rails projects) Brakeman security scan.

    \b
    Scoring rubric:
        Start at 100
        -30 if tests fail, -10 per additional failure
        -25 per CRITICAL CVE
        -10 if build artifacts missing
        -20 per high-severity brakeman finding (Rails only)
        Floor at 0, pass >= 70, warn >= 50, fail < 50

    \b
    Examples:

        hero cipr --sandbox ~/Development/MyApp

        hero cipr --sandbox HERO --verbose

        hero cipr --sandbox MyApp --dry-run

        hero cipr --sandbox MyApp --json
    """
    sandbox_path = _resolve_sandbox(sandbox)
    project_type = _detect_project_type(sandbox_path)

    # ── Dry-run mode ─────────────────────────────────────────────────
    if dry_run:
        click.echo(f"\nhero cipr --sandbox {sandbox_path.name} (dry run)\n")
        click.echo(f"  Project type: {project_type}")
        click.echo(f"  {EMOJI_INFO} Would run: {_test_cmd_label(project_type)}")
        click.echo(f"  {EMOJI_INFO} Would scan: dependency CVEs via trivy fs")
        click.echo(f"  {EMOJI_INFO} Would check: build/ or dist/ artifacts")
        if _is_rails_project(sandbox_path):
            click.echo(f"  {EMOJI_INFO} Would run: brakeman security scan")
        else:
            click.echo(f"  {EMOJI_INFO} Would skip: brakeman (not a Rails project)")
        click.echo(f"\n  No scans executed (dry run).")
        click.echo("")
        return

    # ── Run CI/PR checks ─────────────────────────────────────────────
    result = run_cipr(sandbox_path, verbose=verbose)

    # ── JSON output ──────────────────────────────────────────────────
    if json_output:
        import json as _json

        json_result = {
            "sandbox": result["sandbox"],
            "project_type": result["project_type"],
            "passed": result["passed"],
            "score": result["score"],
            "status": result["status"],
            "checks": {
                k: {
                    "passed": v["passed"],
                    "summary": v["summary"],
                }
                for k, v in result["checks"].items()
            },
            "findings": result["findings"],
        }
        click.echo(_json.dumps(json_result, indent=2))
        return

    # ── Pretty output ────────────────────────────────────────────────
    click.echo(f"\nhero cipr --sandbox {sandbox_path.name}\n")

    checks = result["checks"]

    # Tests line
    t = checks["tests"]
    if t["passed"]:
        icon = EMOJI_PASS
    else:
        icon = EMOJI_FAIL
    click.echo(f"  {icon} Tests:      {t['summary']}")

    # Trivy line
    tv = checks["trivy"]
    icon = EMOJI_PASS if tv["passed"] else EMOJI_FAIL
    click.echo(f"  {icon} Trivy:      {tv['summary']}")

    # Artifacts line
    a = checks["artifacts"]
    icon = EMOJI_PASS if a["passed"] else EMOJI_FAIL
    click.echo(f"  {icon} Artifacts:  {a['summary']}")

    # Brakeman line
    b = checks["brakeman"]
    if b["passed"] or b["summary"].startswith("Skipped"):
        icon = EMOJI_PASS if b["passed"] else EMOJI_INFO
    else:
        icon = EMOJI_FAIL
    click.echo(f"  {icon} Brakeman:   {b['summary']}")

    # Verbose details
    if verbose:
        for check_key, label in [
            ("tests", "Tests"),
            ("trivy", "Trivy"),
            ("artifacts", "Artifacts"),
            ("brakeman", "Brakeman"),
        ]:
            detail = result["checks"][check_key].get("detail", "")
            if detail:
                click.echo(f"\n  {label} details:")
                click.echo(detail)

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

    # Findings summary
    if result["findings"]:
        critical_count = sum(1 for f in result["findings"] if f["severity"] == "critical")
        error_count = sum(1 for f in result["findings"] if f["severity"] == "error")
        warning_count = sum(1 for f in result["findings"] if f["severity"] == "warning")
        parts = []
        if critical_count:
            parts.append(f"{EMOJI_FAIL} {critical_count} critical")
        if error_count:
            parts.append(f"{EMOJI_FAIL} {error_count} error(s)")
        if warning_count:
            parts.append(f"{EMOJI_WARN} {warning_count} warning(s)")
        click.echo(f"  {' '.join(parts)}")

    click.echo("")


def _test_cmd_label(project_type: str) -> str:
    """Return human-readable label for the test command."""
    return {
        "flutter": "flutter test",
        "node": "npm test",
        "python": "pytest -q",
        "rust": "cargo test",
    }.get(project_type, "unknown")
