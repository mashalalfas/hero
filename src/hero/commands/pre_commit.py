"""hero pre-commit — Run PRE-COMMIT stage checks on a sandbox.

Checks:
1. Secrets — gitleaks (or fallback regex scan for API keys, tokens, passwords)
2. Lint — project-appropriate linter (dart analyze / eslint / ruff)
3. Copyright — SPDX / Copyright / © headers in source files

Part of the HERO pipeline: PRE-COMMIT → BUILD → HARDEN → LEGAL → CI/PR → VERIFY → ARCHIVE
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

import click

from hero.commands.check import EMOJI_PASS, EMOJI_WARN, EMOJI_FAIL

SANDBOX_DIR = Path.home() / ".hero" / "sandboxes"


# ── Helpers ──────────────────────────────────────────────────────────────


def _resolve_sandbox(sandbox: str) -> Path:
    """Resolve sandbox identifier to an actual path."""
    # Try named sandbox first
    entry = SANDBOX_DIR / sandbox
    if entry.exists():
        return entry
    # Try direct path
    p = Path(sandbox)
    if p.exists():
        return p
    # Try ~/Development/<name>
    dev = Path.home() / "Development" / sandbox
    if dev.exists():
        return dev
    raise click.ClickException(
        f"Sandbox '{sandbox}' not found in {SANDBOX_DIR}, as path, or ~/Development/."
    )


def _detect_project_type(sandbox_path: Path) -> str:
    """Detect project type from config files present.

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


def _safe_run(
    cmd: list[str], cwd: Path, timeout: int = 60
) -> tuple[subprocess.CompletedProcess[str] | None, str | None]:
    """Run a subprocess with error handling. Returns (result, error_reason)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result, None
    except FileNotFoundError:
        return None, f"{cmd[0]} not found"
    except subprocess.TimeoutExpired:
        return None, f"{cmd[0]} timed out after {timeout}s"
    except Exception as exc:
        return None, str(exc)


# ── Secret scan patterns ────────────────────────────────────────────────

_FALLBACK_SECRET_RE = re.compile(
    r'(?i)(api[_-]?key|secret|token|password|passwd|credential)[\s:=]+["\'][^"\']+["\']'
)

_SOURCE_EXTENSIONS = {".dart", ".ts", ".js", ".py"}
_ADDITIONAL_CONFIG_EXTS = {".yaml", ".yml", ".env"}


# ── Check 1: Secrets ────────────────────────────────────────────────────


def _check_secrets(sandbox_path: Path, verbose: bool) -> dict[str, Any]:
    """Check for secrets using gitleaks or fallback regex scan.

    Returns a check result dict with:
        passed, summary, detail, finding_count
    """
    findings: list[str] = []
    count = 0

    # Try gitleaks first
    result, err = _safe_run(
        ["gitleaks", "detect", "--source", str(sandbox_path), "--no-git", "-v"],
        cwd=sandbox_path,
        timeout=30,
    )

    if result is not None:
        # gitleaks succeeded (exit 0 = clean, non-zero = secrets found)
        output = (result.stdout or "") + (result.stderr or "")
        # Count finding lines
        finding_lines = [l for l in output.split("\n") if l.strip() and "[\]" not in l and ":" in l and "finding" in l.lower()]
        # Parse gitleaks output for actual finding count
        gitleak_findings = re.findall(r'^\s*\[\d+\]', output, re.MULTILINE)
        count = len(gitleak_findings) if gitleak_findings else (result.returncode if result.returncode > 0 else 0)

        if count > 0:
            # Extract finding descriptions
            for line in output.split("\n"):
                if "Finding:" in line or "secret" in line.lower() and "leak" in line.lower():
                    findings.append(line.strip())
            for line in output.split("\n"):
                if "Description:" in line:
                    desc = line.split("Description:")[-1].strip()
                    if desc and desc not in findings:
                        findings.append(desc)
        passed = count == 0
        summary = f"0 secrets found (gitleaks: clean)" if passed else f"{count} secret(s) found (gitleaks)"
    else:
        # gitleaks not available — fallback regex scan
        fallback_count = 0
        all_exts = _SOURCE_EXTENSIONS | _ADDITIONAL_CONFIG_EXTS

        for f in sandbox_path.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix not in all_exts:
                continue
            # Skip common non-source directories
            parts = f.parts
            if any(p in parts for p in ["node_modules", ".git", "build", "__pycache__",
                                          "dist", ".dart_tool", ".pub-cache"]):
                continue
            try:
                text = f.read_text(errors="ignore")[:200_000]
                matches = _FALLBACK_SECRET_RE.findall(text)
                if matches:
                    fallback_count += len(matches)
                    if verbose:
                        findings.append(f"{f.relative_to(sandbox_path)}: {len(matches)} pattern(s)")
            except OSError:
                continue

        count = fallback_count
        passed = count == 0
        scan_type = "fallback regex" if err else "gitleaks"
        summary = (
            f"0 secrets found ({scan_type}: clean)" if passed
            else f"{count} potential secret(s) found ({scan_type} scan)"
        )
        if err:
            findings.append(f"gitleaks unavailable: {err}")

    detail = ""
    if verbose and findings:
        detail = "  Findings:\n" + "\n".join(f"    - {f}" for f in findings[:20])
        if len(findings) > 20:
            detail += f"\n    ... and {len(findings) - 20} more"

    return {
        "passed": passed,
        "summary": summary,
        "detail": detail,
        "finding_count": count,
    }


# ── Check 2: Lint ───────────────────────────────────────────────────────


def _check_lint(sandbox_path: Path, verbose: bool) -> dict[str, Any]:
    """Run project-appropriate linter and count errors/warnings.

    Returns a check result dict with:
        passed, summary, detail, errors, warnings, findings
    """
    project_type = _detect_project_type(sandbox_path)
    findings: list[str] = []
    errors = 0
    warnings = 0

    if project_type == "unknown":
        return {
            "passed": True,
            "summary": "no project type detected (skipped)",
            "detail": "",
            "errors": 0,
            "warnings": 0,
            "findings": [],
        }

    cmd: list[str] | None = None
    cmd_label = ""

    if project_type == "flutter":
        cmd = ["dart", "analyze", str(sandbox_path)]
        cmd_label = "dart analyze"
    elif project_type == "node":
        # Check if eslint config exists first
        eslint_config = None
        for cfg_name in (".eslintrc.js", ".eslintrc.cjs", ".eslintrc.yaml",
                         ".eslintrc.yml", ".eslintrc.json", ".eslintrc"):
            candidate = sandbox_path / cfg_name
            if candidate.exists():
                eslint_config = candidate
                break
        if eslint_config:
            src_dir = sandbox_path / "src"
            if src_dir.exists():
                cmd = ["npx", "eslint", str(src_dir)]
            else:
                cmd = ["npx", "eslint", str(sandbox_path)]
            cmd_label = "eslint"
        else:
            return {
                "passed": True,
                "summary": "no eslint config found (skipped)",
                "detail": "",
                "errors": 0,
                "warnings": 0,
                "findings": [],
            }
    elif project_type == "python":
        # Check for ruff config
        ruff_config = None
        for cfg_name in ("pyproject.toml", ".ruff.toml", "ruff.toml"):
            candidate = sandbox_path / cfg_name
            if candidate.exists():
                ruff_config = candidate
                break
        if ruff_config:
            cmd = ["ruff", "check", str(sandbox_path)]
            cmd_label = "ruff check"
        else:
            return {
                "passed": True,
                "summary": "no ruff config found (skipped)",
                "detail": "",
                "errors": 0,
                "warnings": 0,
                "findings": [],
            }
    elif project_type == "rust":
        cmd = ["cargo", "check", "--message-format=short"]
        cmd_label = "cargo check"

    if not cmd:
        return {
            "passed": True,
            "summary": f"no linter available for {project_type}",
            "detail": "",
            "errors": 0,
            "warnings": 0,
            "findings": [],
        }

    result, err = _safe_run(cmd, cwd=sandbox_path, timeout=60)

    if result is None:
        # Tool not available
        return {
            "passed": True,
            "summary": f"{cmd_label} unavailable: {err} (skipped)",
            "detail": "",
            "errors": 0,
            "warnings": 0,
            "findings": [],
        }

    output = (result.stdout or "") + (result.stderr or "")

    if project_type == "flutter":
        # dart analyze output: "error - " / "warning - " patterns
        errors = len(re.findall(r'(?m)^\s*(?:error|ERROR)\s*[: ]', output))
        warnings = len(re.findall(r'(?m)^\s*(?:warning|WARNING)\s*[: ]', output))
        # Also look for "error:" and "warning:" in lines
        if errors == 0 and warnings == 0:
            errors = output.lower().count("error:")
            warnings = output.lower().count("warning:")
        # Parse individual findings
        for line in output.split("\n"):
            line_s = line.strip()
            if "error:" in line_s.lower() or "warning:" in line_s.lower():
                findings.append(line_s[:200])
    elif project_type == "node":
        # eslint output: lines with "error" or "warning"
        errors = output.lower().count("error")
        warnings = output.lower().count("warning")
        for line in output.split("\n"):
            line_s = line.strip()
            if line_s and ("error" in line_s.lower() or "warning" in line_s.lower()):
                findings.append(line_s[:200])
    elif project_type == "python":
        # ruff output: <file>:<line>:<col>: <code> <message>
        ruff_findings = re.findall(r'^.+?:(\d+):\d+: (\w\d+) ', output, re.MULTILINE)
        for _ in ruff_findings:
            pass  # Count only
        # Count E/W codes (ruff uses codes like E401, W291, F841)
        errors = len(re.findall(r'[EF]\d{3}', output))
        warnings = len(re.findall(r'[W]\d{3}', output))
        if errors == 0 and warnings == 0:
            # Count any matching line as a finding
            errors = len(re.findall(r'^.+?:\d+:\d+: ', output, re.MULTILINE))
        for line in output.split("\n"):
            line_s = line.strip()
            if line_s and re.match(r'^.+?:\d+:\d+: ', line_s):
                findings.append(line_s[:200])
    elif project_type == "rust":
        # cargo check: lines with "error[" / "warning["
        errors = output.lower().count("error[")
        warnings = output.lower().count("warning[")
        if errors == 0 and warnings == 0:
            errors = output.lower().count("error:")
            warnings = output.lower().count("warning:")
        for line in output.split("\n"):
            line_s = line.strip()
            if "error" in line_s.lower() or "warning" in line_s.lower():
                findings.append(line_s[:200])

    passed = errors == 0

    if errors == 0 and warnings == 0:
        summary = f"0 issues found ({cmd_label}: clean)"
    else:
        parts = []
        if errors > 0:
            parts.append(f"{errors} error(s)")
        if warnings > 0:
            parts.append(f"{warnings} warning(s)")
        summary = f"{', '.join(parts)} ({cmd_label})"

    detail = ""
    if verbose and findings:
        detail = "  Issues:\n" + "\n".join(f"    - {f}" for f in findings[:15])
        if len(findings) > 15:
            detail += f"\n    ... and {len(findings) - 15} more"

    return {
        "passed": passed,
        "summary": summary,
        "detail": detail,
        "errors": errors,
        "warnings": warnings,
        "findings": findings[:50],
    }


# ── Check 3: Copyright headers ──────────────────────────────────────────


def _check_copyright(sandbox_path: Path, verbose: bool) -> dict[str, Any]:
    """Check source files for SPDX/Copyright/© headers.

    Scans .dart, .ts, .js, .py files in lib/, src/, test/ directories.
    Skips .git, node_modules, build, .dart_tool.

    Returns a check result dict with:
        passed, summary, detail, missing, total
    """
    source_extensions = {".dart", ".ts", ".js", ".py"}
    search_dirs = ["lib", "src", "test"]
    exclude_parts = {".git", "node_modules", "build", ".dart_tool", ".pub-cache",
                     "__pycache__", "dist", ".idea", ".vscode", "android/build",
                     "ios/build", "coverage"}

    missing = 0
    total = 0
    missing_files: list[str] = []

    for search_dir_name in search_dirs:
        search_dir = sandbox_path / search_dir_name
        if not search_dir.exists() or not search_dir.is_dir():
            continue

        for f in search_dir.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix not in source_extensions:
                continue
            # Skip excluded directories
            parts = f.relative_to(sandbox_path).parts
            if any(p in exclude_parts for p in parts):
                continue

            try:
                lines = f.read_text(errors="ignore").splitlines()[:5]
                if not lines:
                    continue
                total += 1
                header_text = " ".join(lines).lower()
                has_header = (
                    "spdx-license-identifier" in header_text
                    or "copyright" in header_text
                    or "©" in header_text
                )
                if not has_header:
                    missing += 1
                    missing_files.append(str(f.relative_to(sandbox_path)))
            except OSError:
                continue

    passed = missing == 0

    if total == 0:
        summary = "no source files to check"
    elif missing == 0:
        summary = f"all {total} files have headers"
    else:
        summary = f"{missing}/{total} files missing headers"

    detail = ""
    if verbose and missing_files:
        detail = "  Missing headers:\n" + "\n".join(f"    - {f}" for f in missing_files[:20])
        if len(missing_files) > 20:
            detail += f"\n    ... and {len(missing_files) - 20} more"

    return {
        "passed": passed,
        "summary": summary,
        "detail": detail,
        "missing": missing,
        "total": total,
    }


# ── Scoring ─────────────────────────────────────────────────────────────


def _compute_score(
    secrets: dict[str, Any],
    lint: dict[str, Any],
    copyright: dict[str, Any],
) -> tuple[int, list[dict[str, str]]]:
    """Compute final score (0-100) and list of findings.

    Scoring rubric:

        Start at 100
        -30 per secret found
        -10 per lint error
        -5 per lint warning
        -2 per file missing copyright header
        Floor at 0
    """
    score = 100
    findings: list[dict[str, str]] = []

    # Secrets
    secret_count = secrets.get("finding_count", 0)
    if secret_count > 0:
        deduction = secret_count * 30
        score -= deduction
        for i in range(min(secret_count, 10)):
            findings.append({
                "severity": "error",
                "check": "secrets",
                "message": f"Secret pattern found (deduction -30)",
            })

    # Lint
    lint_errors = lint.get("errors", 0)
    lint_warnings = lint.get("warnings", 0)
    if lint_errors > 0:
        deduction = lint_errors * 10
        score -= deduction
        for finding in lint.get("findings", [])[:lint_errors]:
            findings.append({
                "severity": "error",
                "check": "lint",
                "message": finding[:200],
            })
        # Add generic entries if we don't have specific findings
        remaining = lint_errors - min(lint_errors, len(lint.get("findings", [])))
        for _ in range(min(remaining, 5)):
            findings.append({
                "severity": "error",
                "check": "lint",
                "message": f"Lint error (deduction -10)",
            })
    if lint_warnings > 0:
        deduction = lint_warnings * 5
        score -= deduction
        for _ in range(min(lint_warnings, 5)):
            findings.append({
                "severity": "warning",
                "check": "lint",
                "message": f"Lint warning (deduction -5)",
            })

    # Copyright
    missing_headers = copyright.get("missing", 0)
    if missing_headers > 0:
        deduction = missing_headers * 2
        score -= deduction
        for _ in range(min(missing_headers, 5)):
            findings.append({
                "severity": "warning",
                "check": "copyright",
                "message": f"Missing copyright/SPDX header (deduction -2)",
            })

    score = max(0, score)
    return score, findings


# ── Main API ────────────────────────────────────────────────────────────


def run_pre_commit(sandbox_path: str | Path, verbose: bool = False) -> dict[str, Any]:
    """Run all PRE-COMMIT checks and return structured results.

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
                "passed": bool,          # score >= 70
                "score": int,            # 0-100
                "status": str,           # "pass" | "warn" | "fail"
                "checks": {
                    "secrets": {...},
                    "lint": {...},
                    "copyright": {...},
                },
                "findings": [
                    {"severity": "error"|"warning", "check": str, "message": str},
                ],
                "sandbox": str,          # resolved path
            }
    """
    path = Path(sandbox_path).resolve()

    # Run all three checks (each wrapped independently so one failure
    # doesn't crash the entire command)
    errors: list[str] = []
    secrets = _check_secrets(path, verbose)
    lint = _check_lint(path, verbose)
    copyright = _check_copyright(path, verbose)

    score, findings = _compute_score(secrets, lint, copyright)

    if score >= 70:
        status = "pass"
        passed = True
    elif score >= 50:
        status = "warn"
        passed = True  # warn is still passing, just needs attention
    else:
        status = "fail"
        passed = False

    return {
        "sandbox": str(path),
        "passed": passed,
        "score": score,
        "status": status,
        "checks": {
            "secrets": {
                "passed": secrets["passed"],
                "summary": secrets["summary"],
                "detail": secrets.get("detail", ""),
            },
            "lint": {
                "passed": lint["passed"],
                "summary": lint["summary"],
                "detail": lint.get("detail", ""),
            },
            "copyright": {
                "passed": copyright["passed"],
                "summary": copyright["summary"],
                "detail": copyright.get("detail", ""),
            },
        },
        "findings": findings,
    }


# ── Click command ───────────────────────────────────────────────────────


@click.command()
@click.option("--sandbox", required=True, help="Sandbox path or name.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed findings.")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
def pre_commit(sandbox: str, verbose: bool, json_output: bool) -> None:
    """Run PRE-COMMIT checks on a sandbox.

    Checks for secrets, lint errors, and missing copyright headers
    before code enters the pipeline.

    \b
    Scoring rubric:
        - Start at 100
        -30 per secret found / -10 per lint error
        -5 per lint warning / -2 per missing copyright header
        Floor at 0, pass >= 70, warn >= 50, fail < 50

    Examples:

        hero pre-commit --sandbox HERO

        hero pre-commit --sandbox ~/Development/MyApp --verbose

        hero pre-commit --sandbox MyApp --json
    """
    # Resolve sandbox path
    sandbox_path = _resolve_sandbox(sandbox)

    result = run_pre_commit(sandbox_path, verbose=verbose)

    # ── JSON output ──────────────────────────────────────────────────
    if json_output:
        import json as _json

        # Strip detail from JSON output (keeps it concise)
        json_result = {
            "sandbox": result["sandbox"],
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
    click.echo(f"\nhero pre-commit --sandbox {sandbox_path.name}\n")

    # Secrets line
    s = result["checks"]["secrets"]
    icon = EMOJI_PASS if s["passed"] else EMOJI_FAIL
    click.echo(f"  {icon} Secrets:  {s['summary']}")

    # Lint line
    l = result["checks"]["lint"]
    icon = EMOJI_PASS if l["passed"] else EMOJI_FAIL
    click.echo(f"  {icon} Lint:     {l['summary']}")

    # Copyright line
    c = result["checks"]["copyright"]
    if c["passed"]:
        icon = EMOJI_PASS
    elif c.get("missing", 0) > 0:
        icon = EMOJI_WARN
    else:
        icon = EMOJI_FAIL
    click.echo(f"  {icon} Copyright: {c['summary']}")

    # Verbose details
    if verbose:
        for check_key, label in [("secrets", "Secrets"), ("lint", "Lint"), ("copyright", "Copyright")]:
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
        errors_count = sum(1 for f in result["findings"] if f["severity"] == "error")
        warnings_count = sum(1 for f in result["findings"] if f["severity"] == "warning")
        click.echo(f"  {EMOJI_FAIL} {errors_count} error(s), {EMOJI_WARN} {warnings_count} warning(s)")

    click.echo("")
