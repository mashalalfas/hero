"""hero validate_output — Post-build output validation stage.

Runs AFTER build and BEFORE verify. Validates that the soldier produced
the expected output artifacts for the declared TARGET platform, not just
that the build command exited with code 0.

This is the gate that catches:
- Soldiers who built nothing (missing output files)
- Soldiers who built the wrong thing (forbidden outputs present)
- Stale/empty builds (output files suspiciously small)

Part of the HERO pipeline:
  PRE-COMMIT → BUILD → VALIDATE_OUTPUT → SELF_REVIEW → HARDEN → VERIFY → ARCHIVE

Usage:
    from hero.stages.validate_output import run_validate_output

    result = run_validate_output(
        sandbox_path=Path("/path/to/sandbox"),
        target={
            "platform": "static_website",
            "build_tool": "npm",
            "output_dir": "dist/",
            "output_files": ["index.html"],
            "validation": "static_site",
        },
        verbose=True,
    )
    # Returns: {"passed": bool, "score": int, "status": str, "findings": list[dict]}
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


# ── Forbidden output globs by platform ─────────────────────────────────
# These are patterns that should NOT exist after a build for a given target
# platform. The presence of these indicates the soldier built the wrong thing.
_FORBIDDEN_OUTPUTS: dict[str, list[str]] = {
    "static_website": ["build/app/outputs/**", "*.apk", "*.aab"],
    "flutter_app":    ["dist/**", "site/**"],
    "documentation":  [],
    "backend_api":    [],
}


# ── Scoring rubric ─────────────────────────────────────────────────────
# Start at 100, deduct for each finding. Pass >= 70.
_MISSING_OUTPUT_PENALTY = 40   # per missing required file
_FORBIDDEN_OUTPUT_PENALTY = 30  # per forbidden pattern matched
_SMALL_FILE_PENALTY = 20       # per suspiciously small file (< 100 bytes)
_PASS_THRESHOLD = 70
_WARN_THRESHOLD = 50


def _check_output_file_exists(sandbox_path: Path, output_dir: str,
                               output_file: str) -> Path | None:
    """Check if a specific output file exists under the sandbox.

    Resolves the file relative to sandbox_path/output_dir. Supports
    exact filenames and simple glob patterns (e.g. ``assets/**``).

    Returns the first matching path, or None if not found.
    """
    base = sandbox_path / output_dir

    # Simple filename — check directly
    target = base / output_file
    if target.exists() and target.is_file():
        return target

    # Glob pattern — try to find matches
    matches = list(base.glob(output_file))
    if matches:
        return matches[0]

    # Also try from sandbox root if the file has no directory prefix
    # (handles cases like "index.html" where the build tool puts it in a
    #  different sub-path than expected)
    root_matches = list(sandbox_path.glob(output_file))
    if root_matches:
        return root_matches[0]

    return None


def _check_forbidden_outputs(sandbox_path: Path,
                              platform: str) -> list[dict[str, Any]]:
    """Check that no forbidden outputs exist for this platform.

    For each forbidden glob pattern registered for the platform, glob
    the sandbox path and report any matches.

    Returns a list of finding dicts, one per matched pattern.
    """
    findings: list[dict[str, Any]] = []
    forbidden = _FORBIDDEN_OUTPUTS.get(platform, [])

    for pattern in forbidden:
        matches = list(sandbox_path.glob(pattern))
        if matches:
            # Collapse to unique paths (deduplicate)
            matched_files = sorted(set(
                str(m.relative_to(sandbox_path)) for m in matches
            ))
            findings.append({
                "severity": "error",
                "check": "forbidden_output",
                "message": (
                    f"Forbidden output detected for platform '{platform}': "
                    f"pattern '{pattern}' matched {len(matched_files)} file(s). "
                    f"Example: {matched_files[0]} (-{_FORBIDDEN_OUTPUT_PENALTY})"
                ),
                "files": matched_files[:10],  # limit to avoid huge reports
                "score_impact": -_FORBIDDEN_OUTPUT_PENALTY,
            })

    return findings


def _check_output_sizes(sandbox_path: Path, output_dir: str,
                         output_files: list[str],
                         verbose: bool = False) -> list[dict[str, Any]]:
    """Check that output files aren't suspiciously small (< 100 bytes).

    Iterates over all output files produced in the output directory and
    checks each file's size.

    Returns a list of finding dicts for files below the threshold.
    """
    findings: list[dict[str, Any]] = []
    base = sandbox_path / output_dir

    if not base.exists():
        return findings

    # Check all files in output dir (not just declared output_files)
    # to catch accidentally small artifacts
    for f in base.rglob("*"):
        if not f.is_file():
            continue
        try:
            size = f.stat().st_size
        except OSError:
            continue

        if size < 100:
            rel = str(f.relative_to(sandbox_path))
            findings.append({
                "severity": "warning",
                "check": "output_size",
                "message": (
                    f"Output file suspiciously small ({size} bytes < 100): "
                    f"{rel} (-{_SMALL_FILE_PENALTY})"
                ),
                "file": rel,
                "size_bytes": size,
                "score_impact": -_SMALL_FILE_PENALTY,
            })

            if verbose:
                try:
                    content_preview = f.read_text(errors="replace")[:200]
                    findings[-1]["content_preview"] = content_preview
                except OSError:
                    pass

    return findings


def run_validate_output(sandbox_path: Path | str,
                         target: dict[str, Any] | None = None,
                         verbose: bool = False) -> dict[str, Any]:
    """Post-build output validation — did we build the RIGHT thing?

    This stage runs AFTER the build stage and BEFORE verify. Its sole
    purpose is to confirm the soldier produced the expected output
    artifacts for the declared target platform.

    Parameters
    ----------
    sandbox_path : Path or str
        Path to the sandbox / project directory.
    target : dict or None
        Target platform profile dict with keys:

        - ``platform`` (str): Target platform name
          (e.g. ``"static_website"``, ``"flutter_app"``).
        - ``build_tool`` (str): Build tool used.
        - ``output_dir`` (str): Directory where build artifacts land.
        - ``output_files`` (list[str]): Expected output files/glob patterns.
        - ``validation`` (str): Validation strategy name.

        If None or empty, validation is skipped (returns pass).
    verbose : bool, default=False
        Include detailed output (content previews, etc.).

    Returns
    -------
    dict
        Results dict with keys:

        - ``passed`` (bool): Overall pass/fail.
        - ``score`` (int): Score 0-100.
        - ``status`` (str): ``"pass"``, ``"warn"``, or ``"fail"``.
        - ``findings`` (list[dict]): Individual check findings.

    Scoring rubric
    --------------
    Start at 100:

    - Missing required output file: **-40** per file
    - Forbidden output detected: **-30** per pattern
    - Output file < 100 bytes: **-20** per file

    - ``pass``: >= 70
    - ``warn``: >= 50
    - ``fail``: < 50

    Example
    -------
    >>> result = run_validate_output(
    ...     sandbox_path=Path("/tmp/my-sandbox"),
    ...     target={
    ...         "platform": "static_website",
    ...         "build_tool": "npm",
    ...         "output_dir": "dist/",
    ...         "output_files": ["index.html", "assets/"],
    ...         "validation": "static_site",
    ...     },
    ... )
    >>> result["passed"]
    True
    >>> result["status"]
    'pass'
    """
    path = Path(sandbox_path).resolve()

    # ── Fast path: no target → nothing to validate ──
    if not target:
        return {
            "passed": True,
            "score": 100,
            "status": "pass",
            "findings": [],
        }

    platform = target.get("platform", "unknown")
    output_dir = target.get("output_dir", "")
    output_files = target.get("output_files", []) or []
    score = 100
    findings: list[dict[str, Any]] = []

    # ── Check 1: Required output files exist ─────────────────────────
    for output_file in output_files:
        match = _check_output_file_exists(path, output_dir, output_file)
        if match is None:
            score -= _MISSING_OUTPUT_PENALTY
            findings.append({
                "severity": "error",
                "check": "output_exists",
                "message": (
                    f"Required output missing: "
                    f"{output_dir}{output_file} (-{_MISSING_OUTPUT_PENALTY})"
                ),
                "expected": f"{output_dir}{output_file}",
                "score_impact": -_MISSING_OUTPUT_PENALTY,
            })
            if verbose:
                # List what IS in the output dir to help debug
                base = path / output_dir
                if base.exists():
                    actual_files = [
                        str(f.relative_to(path))
                        for f in base.rglob("*")
                        if f.is_file()
                    ]
                    if actual_files:
                        findings[-1]["actual_files"] = actual_files[:20]
                else:
                    findings[-1]["output_dir_missing"] = str(base)
        else:
            if verbose:
                findings.append({
                    "severity": "info",
                    "check": "output_exists",
                    "message": f"Required output found: {str(match.relative_to(path))}",
                    "file": str(match.relative_to(path)),
                    "score_impact": 0,
                })

    # ── Check 2: Forbidden outputs absent ────────────────────────────
    forbidden_findings = _check_forbidden_outputs(path, platform)
    for ff in forbidden_findings:
        score -= _FORBIDDEN_OUTPUT_PENALTY
    findings.extend(forbidden_findings)

    # ── Check 3: Output files not suspiciously small ─────────────────
    size_findings = _check_output_sizes(path, output_dir, output_files,
                                         verbose=verbose)
    for sf in size_findings:
        score -= _SMALL_FILE_PENALTY
    findings.extend(size_findings)

    # ── Final score & status ─────────────────────────────────────────
    score = max(0, score)

    if score >= _PASS_THRESHOLD:
        status = "pass"
        passed = True
    elif score >= _WARN_THRESHOLD:
        status = "warn"
        passed = True
    else:
        status = "fail"
        passed = False

    return {
        "passed": passed,
        "score": score,
        "status": status,
        "findings": findings,
    }
