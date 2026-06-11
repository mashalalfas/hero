"""hero score — Evaluate and score each stage of the HERO pipeline."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import click

from hero.commands.check import detect_project_type, EMOJI_PASS, EMOJI_WARN, EMOJI_FAIL, EMOJI_INFO

HERO_HOME = Path.home() / ".hero"
SANDBOX_DIR = HERO_HOME / "sandboxes"


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


def _run(cmd: list[str], cwd: Path, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    """Run a subprocess, returning the CompletedProcess."""
    return subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout
    )


def _safe_run(cmd: list[str], cwd: Path, timeout: int = 60) -> tuple[subprocess.CompletedProcess[str] | None, str | None]:
    """Run a subprocess with error handling. Returns (result, error_reason)."""
    try:
        return _run(cmd, cwd=cwd, timeout=timeout), None
    except FileNotFoundError:
        return None, f"{cmd[0]} not found"
    except subprocess.TimeoutExpired:
        return None, f"{cmd[0]} timed out after {timeout}s"
    except Exception as exc:
        return None, str(exc)


def _detect_project_type(sandbox_path: Path) -> str:
    """Detect project type from config files."""
    if (sandbox_path / "pubspec.yaml").exists():
        return "flutter"
    if (sandbox_path / "Cargo.toml").exists():
        return "rust"
    if (sandbox_path / "package.json").exists():
        return "node"
    if (sandbox_path / "pyproject.toml").exists():
        return "python"
    return "unknown"


def _count_lines(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text, re.IGNORECASE))


# ── Secret scan (gitleaks or fallback) ───────────────────────────────────

_SECRET_PATTERNS = [
    re.compile(r'(api[_-]?key|apikey)\s*[:=]\s*["\']?[A-Za-z0-9_\-]{16,}'),
    re.compile(r'(token|access[_-]?token)\s*[:=]\s*["\']?[A-Za-z0-9_\-]{16,}'),
    re.compile(r'(secret|password)\s*[:=]\s*["\']?[A-Za-z0-9_\-]{8,}'),
    re.compile(r'(aws|AKIA)[A-Z0-9]{16}'),
    re.compile(r'xox[baprs]-[0-9a-zA-Z-]+'),
    re.compile(r'gh[ops]_[A-Za-z0-9_]{36,}'),
]


def _scan_secrets_gitleaks(path: Path) -> int:
    """Run gitleaks if available. Returns count of secrets found, -1 if unavailable."""
    result, err = _safe_run(
        ["gitleaks", "detect", "--source", str(path), "--no-git", "-v"],
        cwd=path,
        timeout=30,
    )
    if result is None:
        return -1  # tool unavailable
    # gitleaks returns non-zero if secrets found
    output = result.stdout + result.stderr
    matches = re.findall(r'\bsecret\b|\bfinding\b|\bLEAK\b', output, re.IGNORECASE)
    # Better: count actual finding lines
    findings = _count_lines(output, r'^\s*\[')
    return max(findings, result.returncode)


def _scan_secrets_fallback(path: Path, file_patterns: list[str] | None = None) -> int:
    """Fallback: scan files for common secret patterns."""
    count = 0
    exts = file_patterns or [".dart", ".ts", ".js", ".py", ".json", ".yaml", ".yml", ".env", ".toml"]
    for f in path.rglob("*"):
        if not f.is_file():
            continue
        if any(f.suffix == e or str(f).endswith(e) for e in exts):
            # Skip common non-source directories
            if any(part in f.parts for part in ["node_modules", ".git", "build", "__pycache__", "dist"]):
                continue
            try:
                text = f.read_text(errors="ignore")[:500_000]
                for pat in _SECRET_PATTERNS:
                    matches = pat.findall(text)
                    if matches:
                        count += len(matches)
                        break  # one hit per file is enough
            except OSError:
                continue
    return count


def _count_copyright_headers(path: Path) -> int:
    """Count files missing copyright/SPDX headers in first 5 lines."""
    exts = [".dart", ".ts", ".js", ".py", ".java", ".kt", ".swift", ".rs", ".go"]
    missing = 0
    checked = 0
    for f in path.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix not in exts:
            continue
        if any(part in f.parts for part in ["node_modules", ".git", "build", "__pycache__", "dist"]):
            continue
        try:
            lines = f.read_text(errors="ignore").splitlines()[:5]
            header = " ".join(lines).lower()
            has_copyright = "copyright" in header or "spdx" in header
            checked += 1
            if not has_copyright:
                missing += 1
        except OSError:
            continue
    return missing, checked


# ── Stage scorers ─────────────────────────────────────────────────────────

def _score_pre_commit(sandbox_path: Path) -> dict[str, Any]:
    """Score the pre-commit stage (0-100, starts at 100)."""
    score = 100
    notes: list[str] = []
    secrets_count = 0

    # Secret scan
    gitleaks_count = _scan_secrets_gitleaks(sandbox_path)
    if gitleaks_count == -1:
        # fallback
        secrets_count = _scan_secrets_fallback(sandbox_path)
        notes.append("gitleaks not available (fallback scan)")
    else:
        secrets_count = gitleaks_count

    if secrets_count > 0:
        deduction = min(score, secrets_count * 30)
        score -= deduction
        notes.append(f"{secrets_count} secret(s) found (-{deduction})")

    # Lint errors
    project_type = _detect_project_type(sandbox_path)
    lint_cmd = None
    if project_type == "flutter":
        lint_cmd = ["flutter", "analyze"]
    elif project_type == "node":
        lint_cmd = ["npx", "eslint", "."]
    elif project_type == "python":
        lint_cmd = ["ruff", "check", "."]

    lint_errors = 0
    lint_warnings = 0
    if lint_cmd:
        result, err = _safe_run(lint_cmd, cwd=sandbox_path, timeout=60)
        if result is not None:
            output = result.stdout + result.stderr
            # Flutter analyze: lines with "error:" and "warning:"
            lint_errors = output.lower().count("error:")
            lint_warnings = output.lower().count("warning:")
            # ruff format: lines with "error" or "E/W" codes
            if project_type == "python":
                lint_errors = _count_lines(output, r'\b[EWRF]\d{4}\b')
        else:
            notes.append(f"lint unavailable: {err}")

    if lint_errors > 0:
        deduction = min(score, lint_errors * 10)
        score -= deduction
        notes.append(f"{lint_errors} lint error(s) (-{deduction})")

    if lint_warnings > 0:
        deduction = min(score, lint_warnings * 5)
        score -= deduction
        notes.append(f"{lint_warnings} warning(s) (-{deduction})")

    # Copyright headers
    missing_headers, total_checked = _count_copyright_headers(sandbox_path)
    if total_checked > 0:
        header_deduction = min(score, missing_headers * 2)
        score -= header_deduction
        if missing_headers > 0:
            notes.append(f"{missing_headers} files missing headers (-{header_deduction})")

    score = max(0, score)
    status = "pass" if score >= 70 else ("warn" if score >= 50 else "fail")
    details = ", ".join(notes) if notes else "clean"
    return {"score": score, "status": status, "details": details}


def _score_build(sandbox_path: Path) -> dict[str, Any]:
    """Score the build stage (0-100)."""
    score = 100
    notes: list[str] = []
    project_type = _detect_project_type(sandbox_path)

    if project_type == "unknown":
        notes.append("no project detected")
        return {"score": 100, "status": "pass", "details": "no project detected (skipped)"}

    # Run analyze first
    analyze_ok = True
    if project_type == "flutter":
        result, err = _safe_run(["flutter", "analyze"], cwd=sandbox_path, timeout=120)
        if result is None:
            notes.append(f"flutter analyze unavailable: {err}")
            analyze_ok = False
        elif result.returncode != 0:
            analyze_ok = False
            errors = _count_lines(result.stdout, r'error:')
            score = max(0, score - 10)
            notes.append(f"flutter analyze failed (-10)")
    elif project_type == "node":
        result, err = _safe_run(["npx", "tsc", "--noEmit"], cwd=sandbox_path, timeout=60)
        if result is None:
            notes.append(f"tsc unavailable: {err}")
            analyze_ok = False
        elif result.returncode != 0:
            analyze_ok = False
            score = max(0, score - 10)
            notes.append("tsc failed (-10)")
    elif project_type == "python":
        result, err = _safe_run(["python", "-m", "pytest", "-q"], cwd=sandbox_path, timeout=120)
        if result is None:
            notes.append(f"pytest unavailable: {err}")
            analyze_ok = False
        elif result.returncode != 0:
            analyze_ok = False
            score = max(0, score - 10)
            notes.append("pytest failed (-10)")
    elif project_type == "rust":
        result, err = _safe_run(["cargo", "check"], cwd=sandbox_path, timeout=120)
        if result is None:
            notes.append(f"cargo unavailable: {err}")
            analyze_ok = False
        elif result.returncode != 0:
            analyze_ok = False
            score = max(0, score - 10)
            notes.append("cargo check failed (-10)")

    # Build attempt
    build_ok = True
    obfuscated = False
    if project_type == "flutter":
        build_result, err = _safe_run(
            ["flutter", "build", "apk", "--obfuscate", "--split-debug-info=build/debug-info"],
            cwd=sandbox_path,
            timeout=300,
        )
        if build_result is None:
            build_ok = False
            notes.append(f"build unavailable: {err}")
            score = max(0, score - 20)
            notes.append("build failed entirely (-20)")
        elif build_result.returncode != 0:
            build_ok = False
            score = max(0, score - 20)
            notes.append("flutter build failed (-20)")
        else:
            # Check for obfuscation flag in build output or check for debug-info dir
            build_output = build_result.stdout + build_result.stderr
            if "--obfuscate" in build_output or "obfuscate" in build_output.lower():
                obfuscated = True
            debug_dir = sandbox_path / "build" / "debug-info"
            obfuscated = obfuscated or debug_dir.exists()
    elif project_type == "node":
        build_result, err = _safe_run(["npm", "run", "build"], cwd=sandbox_path, timeout=120)
        if build_result is None:
            build_ok = False
            score = max(0, score - 20)
            notes.append("build failed entirely (-20)")
        elif build_result.returncode != 0:
            build_ok = False
            score = max(0, score - 20)
            notes.append("npm build failed (-20)")
    elif project_type == "python":
        build_result, err = _safe_run(
            ["python", "-m", "build"], cwd=sandbox_path, timeout=120
        )
        if build_result is None:
            build_ok = False
            score = max(0, score - 20)
            notes.append("python build failed (-20)")
        elif build_result.returncode != 0:
            build_ok = False
            score = max(0, score - 20)
            notes.append("python build failed (-20)")
    elif project_type == "rust":
        build_result, err = _safe_run(["cargo", "build", "--release"], cwd=sandbox_path, timeout=300)
        if build_result is None:
            build_ok = False
            score = max(0, score - 20)
            notes.append("cargo build failed (-20)")
        elif build_result.returncode != 0:
            build_ok = False
            score = max(0, score - 20)
            notes.append("cargo build failed (-20)")

    if build_ok and not obfuscated and project_type == "flutter":
        score = max(0, score - 15)
        notes.append("obfuscation not detected (-15)")

    score = max(0, score)
    status = "pass" if score >= 70 else ("warn" if score >= 50 else "fail")
    if build_ok:
        notes.append("build succeeded")
    details = ", ".join(notes) if notes else "no issues"
    return {"score": score, "status": status, "details": details}


def _score_harden(sandbox_path: Path) -> dict[str, Any]:
    """Score the hardening stage (0-100)."""
    score = 100
    notes: list[str] = []
    project_type = _detect_project_type(sandbox_path)

    # Obfuscation check
    obfuscated = False
    if project_type == "flutter":
        # Check for --obfuscate in build.gradle or build output indicators
        build_gradle = sandbox_path / "android" / "app" / "build.gradle"
        if build_gradle.exists():
            try:
                content = build_gradle.read_text()
                obfuscated = "--obfuscate" in content or "minifyEnabled" in content
            except OSError:
                pass
        if not obfuscated:
            debug_info = sandbox_path / "build" / "debug-info"
            obfuscated = debug_info.exists()
    elif project_type == "android":
        build_gradle = sandbox_path / "android" / "app" / "build.gradle"
        if build_gradle.exists():
            try:
                content = build_gradle.read_text()
                obfuscated = "minifyEnabled" in content or "proguard" in content.lower()
            except OSError:
                pass

    if not obfuscated:
        score = max(0, score - 20)
        notes.append("obfuscation not verified (-20)")

    # Debug symbols check
    has_debug_symbols = False
    build_dir = sandbox_path / "build"
    if build_dir.exists():
        # Check for .symtab in APK/AAR or debug-info dirs
        for f in build_dir.rglob("*"):
            if f.is_file() and (f.suffix == ".symtab" or "debug-info" in str(f)):
                has_debug_symbols = True
                break
        # Check for unstripped binaries in release dir
        release_dir = build_dir / "app" / "intermediates" / "merged_native_libs" / "release" if project_type == "flutter" else None
        if release_dir and release_dir.exists():
            has_debug_symbols = True

    if has_debug_symbols:
        score = max(0, score - 15)
        notes.append("debug symbols present in build output (-15)")

    # Secrets in compiled output
    secrets_in_build = 0
    if build_dir.exists():
        secrets_in_build = _scan_secrets_fallback(build_dir, [".dex", ".so", ".js", ".dart", ".json"])
    if secrets_in_build > 0:
        deduction = min(score, secrets_in_build * 25)
        score -= deduction
        notes.append(f"{secrets_in_build} secret(s) in build output (-{deduction})")

    # Root detection
    has_root_detection = False
    lib_dir = sandbox_path / "lib" if project_type == "flutter" else None
    android_dir = sandbox_path / "android"
    check_dirs = [d for d in [lib_dir, android_dir] if d and d.exists()]
    for d in check_dirs:
        for f in d.rglob("*.dart"):
            try:
                content = f.read_text(errors="ignore").lower()
                if any(term in content for term in ["rootdetector", "jailbreak", "isrooted", "root_check", "jailbreak"]):
                    has_root_detection = True
                    break
            except OSError:
                continue
        if has_root_detection:
            break
        # Check android native
        for f in d.rglob("*.kt"):
            try:
                content = f.read_text(errors="ignore").lower()
                if "root" in content and "detect" in content:
                    has_root_detection = True
                    break
            except OSError:
                continue
        if has_root_detection:
            break

    if not has_root_detection:
        score = max(0, score - 10)
        notes.append("root detection not found (-10)")

    # Certificate pinning
    has_cert_pinning = False
    for d in check_dirs:
        for f in d.rglob("*"):
            if not f.is_file():
                continue
            try:
                content = f.read_text(errors="ignore").lower()
                if "certificate" in content and ("pin" in content or "pinning" in content):
                    has_cert_pinning = True
                    break
            except OSError:
                continue
        if has_cert_pinning:
            break

    if not has_cert_pinning:
        score = max(0, score - 10)
        notes.append("certificate pinning not found (-10)")

    score = max(0, score)
    status = "pass" if score >= 70 else ("warn" if score >= 50 else "fail")
    details = ", ".join(notes) if notes else "all checks passed"
    return {"score": score, "status": status, "details": details}


def _score_legal(sandbox_path: Path) -> dict[str, Any]:
    """Score the legal stage (0-100)."""
    score = 100
    notes: list[str] = []

    # EULA check
    eula_files = list(sandbox_path.rglob("*EULA*")) + list(sandbox_path.rglob("*eula*"))
    eula_files += [sandbox_path / "legal" / "EULA.md", sandbox_path / "EULA.md",
                   sandbox_path / "LEGAL.md", sandbox_path / "legal.md"]
    has_eula = any(f.exists() for f in eula_files)
    if not has_eula:
        score = max(0, score - 20)
        notes.append("no EULA found (-20)")

    # Privacy policy check
    privacy_files = [sandbox_path / "PRIVACY.md", sandbox_path / "privacy-policy.md",
                     sandbox_path / "legal" / "privacy.md"]
    has_privacy = any(f.exists() for f in privacy_files)
    if not has_privacy:
        score = max(0, score - 15)
        notes.append("no Privacy Policy found (-15)")

    # SBOM check
    sbom_files = list(sandbox_path.rglob("*.sbom*")) + list(sandbox_path.rglob("SBOM*"))
    has_sbom = len(sbom_files) > 0
    if not has_sbom:
        score = max(0, score - 15)
        notes.append("no SBOM generated (-15)")

    # License risk check
    risky_licenses = {"gpl", "agpl", "sspl"}
    risky_found = []
    project_type = _detect_project_type(sandbox_path)
    lock_files = {
        "flutter": sandbox_path / "pubspec.lock",
        "node": sandbox_path / "package-lock.json",
        "rust": sandbox_path / "Cargo.lock",
        "python": sandbox_path / "poetry.lock",
    }
    lock_file = lock_files.get(project_type)
    if lock_file and lock_file.exists():
        try:
            content = lock_file.read_text(errors="ignore").lower()
            for lic in risky_licenses:
                if lic in content:
                    risky_found.append(lic.upper())
        except OSError:
            pass
    if risky_found:
        deduction = min(score, 25 * len(risky_found))
        score -= deduction
        notes.append(f"risky license(s) {risky_found} found (-{deduction})")

    # Copyright headers
    missing_headers, total_checked = _count_copyright_headers(sandbox_path)
    if missing_headers > 0:
        deduction = min(score, missing_headers * 10)
        score -= deduction
        notes.append(f"{missing_headers} files missing copyright headers (-{deduction})")

    # legal-config.json check
    legal_config = sandbox_path / "legal-config.json"
    if not legal_config.exists():
        score = max(0, score - 15)
        notes.append("legal-config.json missing (-15)")

    score = max(0, score)
    status = "pass" if score >= 70 else ("warn" if score >= 50 else "fail")
    details = ", ".join(notes) if notes else "all docs generated"
    return {"score": score, "status": status, "details": details}


def _score_cipr(sandbox_path: Path) -> dict[str, Any]:
    """Score the CI/PR stage (0-100)."""
    score = 100
    notes: list[str] = []
    project_type = _detect_project_type(sandbox_path)

    # Run tests
    test_cmds = {
        "flutter": ["flutter", "test"],
        "node": ["npm", "test"],
        "python": ["python", "-m", "pytest", "-q"],
        "rust": ["cargo", "test"],
    }
    test_cmd = test_cmds.get(project_type)
    passed_tests = 0
    total_tests = 0
    if test_cmd:
        result, err = _safe_run(test_cmd, cwd=sandbox_path, timeout=120)
        if result is None:
            score = max(0, score - 30)
            notes.append(f"tests unavailable: {err} (-30)")
        elif result.returncode != 0:
            # Count passed/failed
            output = result.stdout + result.stderr
            passed_match = re.search(r'(\d+)\s+passed', output, re.IGNORECASE)
            failed_match = re.search(r'(\d+)\s+failed', output, re.IGNORECASE)
            passed_tests = int(passed_match.group(1)) if passed_match else 0
            failed_count = int(failed_match.group(1)) if failed_match else 1
            total_tests = passed_tests + failed_count
            deduction = min(score, 30 + max(0, failed_count - 1) * 10)
            score -= deduction
            notes.append(f"{failed_count} test(s) failed (-{deduction})")
        else:
            output = result.stdout + result.stderr
            passed_match = re.search(r'(\d+)\s+passed', output, re.IGNORECASE)
            passed_tests = int(passed_match.group(1)) if passed_match else 0
            total_tests = passed_tests
    else:
        notes.append("no test command detected")

    # Security scan artifacts
    security_artifacts = list(sandbox_path.rglob(".trivy*")) + list(sandbox_path.rglob("osv-scanner*"))
    if not security_artifacts:
        score = max(0, score - 15)
        notes.append("no security scan artifacts found (-15)")

    # Build artifacts
    build_dir = sandbox_path / "build"
    if not build_dir.exists() or not any(build_dir.iterdir()):
        score = max(0, score - 10)
        notes.append("no build artifacts (-10)")

    score = max(0, score)
    status = "pass" if score >= 70 else ("warn" if score >= 50 else "fail")
    test_detail = f"{passed_tests}/{total_tests} tests passed" if total_tests > 0 else "no tests detected"
    details = f"{test_detail}"
    if notes:
        details += ", " + ", ".join(notes)
    return {"score": score, "status": status, "details": details}


def _score_verify(all_scores: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Composite VERIFY score — average of all other stage scores."""
    stage_scores = [v["score"] for k, v in all_scores.items() if k != "verify"]
    if not stage_scores:
        return {"score": 100, "status": "pass", "details": "no stages scored"}

    avg = sum(stage_scores) / len(stage_scores)
    score = round(avg)
    # Penalties
    any_below_50 = any(s < 50 for s in stage_scores)
    any_below_70 = any(s < 70 for s in stage_scores)
    if any_below_50:
        score = max(0, score - 10)
    elif any_below_70:
        score = max(0, score - 5)

    status = "pass" if score >= 70 else ("warn" if score >= 50 else "fail")
    details = "composite"
    return {"score": score, "status": status, "details": details}


# ── Pipeline dispatch ─────────────────────────────────────────────────────

_PIPELINE_STAGES = {
    "pre-commit": _score_pre_commit,
    "precommit": _score_pre_commit,
    "build": _score_build,
    "harden": _score_harden,
    "legal": _score_legal,
    "cipr": _score_cipr,
    "ci/pr": _score_cipr,
    "verify": None,  # composite — handled separately
    "all": None,  # handled separately
}


def _score_pipeline(pipeline: str, sandbox_path: Path) -> dict[str, dict[str, Any]]:
    """Run scoring for the given pipeline stage(s)."""
    pipeline = pipeline.strip().lower()
    scores: dict[str, dict[str, Any]] = {}

    if pipeline in ("all",):
        stages = ["pre-commit", "build", "harden", "legal", "cipr"]
    elif pipeline in _PIPELINE_STAGES and _PIPELINE_STAGES[pipeline] is not None:
        stages = [pipeline]
    elif pipeline == "verify":
        # VERIFY alone needs all other stages first
        stages = ["pre-commit", "build", "harden", "legal", "cipr"]
        scores["verify"] = None  # placeholder
    else:
        raise click.ClickException(
            f"Unknown pipeline '{pipeline}'. Valid: "
            f"{', '.join(k for k, v in _PIPELINE_STAGES.items() if v is not None or k in ('verify', 'all'))}"
        )

    for stage in stages:
        scorer = _PIPELINE_STAGES.get(stage)
        if scorer:
            scores[stage] = scorer(sandbox_path)

    # Handle verify / all composite
    if pipeline in ("all", "verify"):
        scores["verify"] = _score_verify(scores)

    return scores


# ── Output formatting ─────────────────────────────────────────────────────

def _format_score_line(stage: str, data: dict[str, Any]) -> str:
    icon_map = {"pass": EMOJI_PASS, "warn": EMOJI_WARN, "fail": EMOJI_FAIL}
    icon = icon_map.get(data["status"], EMOJI_INFO)
    return f"  {icon} {stage.upper().replace('-', '/'):<14} {data['score']:>3}/100  ({data['status']})  — {data['details']}"


def _print_scores(pipeline: str, sandbox: str, sandbox_path: Path, scores: dict[str, dict[str, Any]]) -> None:
    click.echo(f"\nhero score — pipeline: {pipeline}")
    click.echo("─" * 42)
    for stage, data in scores.items():
        click.echo(_format_score_line(stage, data))
    if len(scores) > 1:
        click.echo("─" * 42)
        # If verify wasn't computed (e.g. single stage without all), show average
        if "verify" not in scores and len(scores) > 1:
            verify = _score_verify(scores)
            scores["verify"] = verify
        if "verify" in scores:
            click.echo(_format_score_line("verify", scores["verify"]))
    click.echo("")


# ── Click command ─────────────────────────────────────────────────────────

@click.command()
@click.option(
    "--pipeline",
    required=True,
    type=click.Choice(
        ["pre-commit", "build", "harden", "legal", "cipr", "verify", "all"],
        case_sensitive=False,
    ),
    help="Pipeline stage to score.",
)
@click.option("--sandbox", "sandbox_arg", default=None,
              help="Sandbox name or path (defaults to current project).")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
def score(pipeline: str, sandbox_arg: str | None, json_output: bool) -> None:
    """Evaluate and score each stage of the HERO pipeline.

    Scoring rubrics:

    \b
    PRE-COMMIT  — secrets, lint errors, missing headers
    BUILD       — analyze pass, build success, obfuscation
    HARDEN      — obfuscation, debug symbols, root detection, cert pinning
    LEGAL       — EULA, privacy policy, SBOM, license risk, legal-config.json
    CI/PR       — tests pass, security scan, build artifacts
    VERIFY      — composite average of all stages

    Examples:

        hero score --pipeline all

        hero score --pipeline pre-commit --sandbox my-project

        hero score --pipeline build --sandbox ~/Development/MyApp --json
    """
    # Resolve sandbox
    if sandbox_arg:
        sandbox_path = _resolve_sandbox(sandbox_arg)
        sandbox_display = str(sandbox_path)
    else:
        sandbox_path = Path.cwd()
        sandbox_display = str(sandbox_path)

    try:
        scores = _score_pipeline(pipeline, sandbox_path)
    except click.ClickException:
        raise
    except Exception as exc:
        raise click.ClickException(f"Scoring failed: {exc}") from exc

    if json_output:
        output = {
            "pipeline": pipeline,
            "sandbox": sandbox_display,
            "scores": {
                stage: data for stage, data in scores.items()
            },
        }
        click.echo(json.dumps(output, indent=2))
        return

    _print_scores(pipeline, sandbox_arg or sandbox_path.name, sandbox_path, scores)
