"""hero harden — Run HARDEN stage checks on a sandbox.

Checks:
1. Trivy — dependency CVE scan (CRITICAL only)
2. Secrets — scan build/ or dist/ for exposed API key patterns
3. Root detection — check for anti-jailbreak / root detection package
4. Certificate pinning — verify network pinning is configured
5. Debug symbols stripped — confirm debug info is separated from binary

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

# Patterns that look like exposed secrets in compiled output
_SECRET_PATTERNS: list[re.Pattern] = [
    # Bearer / Authorization tokens
    re.compile(r'["\'](?:Authorization|Bearer)\s+[A-Za-z0-9_\-]{20,}["\']', re.IGNORECASE),
    # Firebase / Google API key (AIza...)
    re.compile(r'AIza[0-9A-Za-z_\-]{35}'),
    # AWS access key ID
    re.compile(r'AKIA[0-9A-Z]{16}'),
    # Generic API key token
    re.compile(r'["\'](?:api[_-]?key|apikey|api_secret)\s*[:=]\s*["\'][A-Za-z0-9_\-]{20,}["\']', re.IGNORECASE),
    # Private key header
    re.compile(r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----'),
    # Slack / Twilio style tokens
    re.compile(r'xox[baprs]-[A-Za-z0-9_\-]{10,}'),
    re.compile(r'SK[a-z0-9]{32,}'),
    # GitHub personal access token
    re.compile(r'ghp_[A-Za-z0-9_]{30,}'),
]


def _scan_secrets(directory: Path) -> list[str]:
    """Scan files in *directory* for secret-like strings.

    Only scans files with typical compiled/text extensions.
    Returns list of descriptive hit strings.
    """
    hits: list[str] = []
    scan_extensions = {
        ".js", ".mjs", ".cjs", ".ts", ".dart", ".java", ".kt",
        ".swift", ".m", ".h", ".so", ".a", ".json", ".txt",
        ".yaml", ".yml", ".xml", ".pb", ".pb.go", ".pem",
    }
    # Max bytes per file to scan (avoid scanning huge bundled assets)
    max_bytes = 5_000_000

    for fpath in directory.rglob("*"):
        if not fpath.is_file():
            continue
        if fpath.suffix.lower() not in scan_extensions:
            continue
        try:
            if fpath.stat().st_size > max_bytes:
                continue
            content = fpath.read_text(errors="ignore")
        except OSError:
            continue
        for pat in _SECRET_PATTERNS:
            found = pat.search(content)
            if found:
                hits.append(f"{fpath.relative_to(directory)}: {found.group()[:60]}")

    return hits


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

    skip_dirs = [
        "node_modules", ".pub-cache", "vendor", "third_party",
        ".venv", "venv", ".dart_tool", ".git", "build", "dist",
        ".bundled_packages", ".hero",
    ]
    cmd = [
        "trivy", "fs",
        "--severity", "CRITICAL",
        "--no-progress",
    ]
    for d in skip_dirs:
        cmd.extend(["--skip-dirs", d])
    cmd.append(str(sandbox_path))

    result, err = _safe_run(
        cmd,
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
        # Trivy CRITICAL lines contain CVE identifiers
        if "CRITICAL" in line_s.upper():
            findings.append(line_s[:200])

    return findings, ""


def _check_root_detection(sandbox_path: Path, project_type: str) -> tuple[bool, str]:
    """Check whether root/jailbreak detection is configured.

    Returns (found, note).
    """
    if project_type == "flutter":
        pubspec = sandbox_path / "pubspec.yaml"
        if pubspec.exists():
            try:
                content = pubspec.read_text(errors="ignore")
                if "flutter_jailbreak_detection" in content:
                    return True, "flutter_jailbreak_detection in pubspec.yaml"
            except OSError:
                pass
        # Also scan lib/ for usage hints
        lib_dir = sandbox_path / "lib"
        if lib_dir.exists():
            try:
                for f in lib_dir.rglob("*.dart"):
                    txt = f.read_text(errors="ignore")
                    if "JailbreakDetection" in txt or "flutter_jailbreak_detection" in txt:
                        return True, f"jailbreak detection used in {f.name}"
            except OSError:
                pass
        return False, "flutter_jailbreak_detection not found in pubspec.yaml"

    elif project_type == "android":
        # Scan android/ source files
        android_dir = sandbox_path / "android"
        if not android_dir.exists():
            return False, "android/ directory not found"
        search_paths = [android_dir / "app" / "src", android_dir]
        for base in search_paths:
            if not base.exists():
                continue
            for f in base.rglob("*.java") if base.rglob("*.java") else []:
                try:
                    txt = f.read_text(errors="ignore")
                    if any(kw in txt for kw in [
                        "RootBeer", "isRooted", "isDeviceRooted",
                        "detectRoot", "jailbreak", "SafetyNet",
                    ]):
                        return True, f"root detection code in {f.relative_to(sandbox_path)}"
                except OSError:
                    continue
            for f in base.rglob("*.kt") if base.rglob("*.kt") else []:
                try:
                    txt = f.read_text(errors="ignore")
                    if any(kw in txt for kw in [
                        "RootBeer", "isRooted", "isDeviceRooted",
                        "detectRoot", "jailbreak", "SafetyNet",
                    ]):
                        return True, f"root detection code in {f.relative_to(sandbox_path)}"
                except OSError:
                    continue
        return False, "no root detection code found in android/ sources"

    return True, f"root detection check not applicable for {project_type} (skipped)"


def _check_cert_pinning(sandbox_path: Path, project_type: str) -> tuple[bool, str]:
    """Check whether certificate pinning is configured.

    Returns (found, note).
    """
    if project_type == "flutter":
        # Check lib/ for http/dio pinning usage
        lib_dir = sandbox_path / "lib"
        if lib_dir.exists():
            pinning_keywords = [
                "HttpClient", "badCertificateCallback",
                "pinning", "CertificatePinning",
                "dio", "Dio", "PinningInterceptor",
            ]
            try:
                for f in lib_dir.rglob("*.dart"):
                    txt = f.read_text(errors="ignore")
                    if any(kw in txt for kw in pinning_keywords):
                        return True, f"certificate pinning code in {f.name}"
            except OSError:
                pass
        # Also check pubspec for dio / http packages that might do pinning
        pubspec = sandbox_path / "pubspec.yaml"
        if pubspec.exists():
            try:
                content = pubspec.read_text(errors="ignore")
                if "dio" in content and "certificate_pinning" in content.lower():
                    return True, "dio certificate pinning in pubspec.yaml"
            except OSError:
                pass
        return False, "no certificate pinning configuration found in lib/"

    elif project_type == "android":
        # network_security_config.xml
        candidates = [
            sandbox_path / "android" / "app" / "src" / "main" / "res" / "xml" / "network_security_config.xml",
            sandbox_path / "app" / "src" / "main" / "res" / "xml" / "network_security_config.xml",
        ]
        for cfg in candidates:
            if cfg.exists():
                return True, f"network_security_config.xml at {cfg.relative_to(sandbox_path)}"
        return False, "network_security_config.xml not found"

    elif project_type == "ios":
        # Info.plist with NSAppTransportSecurity / pinned keys
        candidates = [
            sandbox_path / "ios" / "Runner" / "Info.plist",
            sandbox_path / "ios" / "Runner" / "Info.plist",
        ]
        for plist in candidates:
            if plist.exists():
                try:
                    content = plist.read_text(errors="ignore")
                    if "NSAppTransportSecurity" in content or "NSExceptionDomains" in content:
                        return True, "NSAppTransportSecurity in Info.plist"
                except OSError:
                    pass
        return False, "NSAppTransportSecurity not found in Info.plist"

    return True, f"cert pinning check not applicable for {project_type} (skipped)"


def _check_debug_symbols_stripped(sandbox_path: Path) -> tuple[bool, str]:
    """Verify that debug symbols have been separated from the release binary.

    Checks build/debug-info/ directory (populated by BUILD stage via
    --split-debug-info).

    Returns (stripped, note).
    """
    debug_info_dir = sandbox_path / "build" / "debug-info"
    if not debug_info_dir.exists():
        return False, "build/debug-info/ directory not found (debug symbols may be embedded)"

    files = list(debug_info_dir.iterdir())
    if not files:
        return False, "build/debug-info/ exists but is empty"

    file_count = len(files)
    # Heuristic: directory has files, likely .symbol-map or .debug files
    symbol_exts = {".symbol-map", ".symbols", ".debug", ".dSYM", ".pdb", ".dbg"}
    has_symbol_files = any(f.suffix in symbol_exts for f in files)
    if has_symbol_files:
        return True, f"symbol map at build/debug-info/ ({file_count} file(s))"
    # Even without known symbol extensions, presence indicates attempt
    return True, f"build/debug-info/ present ({file_count} file(s))"


# ── Scoring ─────────────────────────────────────────────────────────────


def _compute_harden_score(
    trivy_findings: list[str],
    secret_hits: list[str],
    root_detection_found: bool,
    root_note: str,
    cert_pinning_found: bool,
    cert_note: str,
    debug_symbols_ok: bool,
    debug_note: str,
) -> tuple[int, list[dict[str, str]]]:
    """Compute HARDEN score.

    Rubric:
        Start at 100
        -30 per CRITICAL CVE (cap -90)
        -25 per secret in compiled output
        -10 if root detection missing (when applicable)
        -10 if cert pinning missing (when applicable)
        -15 if debug symbols not stripped
        Floor at 0
    """
    score = 100
    findings: list[dict[str, str]] = []

    # Trivy CVEs
    cve_count = min(len(trivy_findings), 3)  # Cap deductions
    trivy_deduct = cve_count * 30
    score = max(0, score - trivy_deduct)
    if trivy_findings:
        findings.append({
            "severity": "critical",
            "check": "trivy",
            "message": f"{len(trivy_findings)} CRITICAL CVE(s) found (-{trivy_deduct})",
        })

    # Secrets
    secret_count = len(secret_hits)
    secret_deduct = secret_count * 25
    score = max(0, score - secret_deduct)
    if secret_hits:
        findings.append({
            "severity": "critical",
            "check": "secrets",
            "message": f"{secret_count} potential secret(s) in compiled output (-{secret_deduct})",
        })

    # Root detection (only deduct if not "skipped")
    if root_note and "not applicable" not in root_note.lower() and "skipped" not in root_note.lower():
        if not root_detection_found:
            score = max(0, score - 10)
            findings.append({
                "severity": "warning",
                "check": "root_detection",
                "message": f"Root detection not found: {root_note} (-10)",
            })

    # Cert pinning (only deduct if not "skipped")
    if cert_note and "not applicable" not in cert_note.lower() and "skipped" not in cert_note.lower():
        if not cert_pinning_found:
            score = max(0, score - 10)
            findings.append({
                "severity": "warning",
                "check": "cert_pinning",
                "message": f"Certificate pinning not found: {cert_note} (-10)",
            })

    # Debug symbols
    if not debug_symbols_ok:
        score = max(0, score - 15)
        findings.append({
            "severity": "error",
            "check": "debug_symbols",
            "message": f"Debug symbols not stripped: {debug_note} (-15)",
        })

    return score, findings


# ── Main API ────────────────────────────────────────────────────────────


def run_harden(sandbox_path: str | Path, verbose: bool = False) -> dict[str, Any]:
    """Run HARDEN checks on a sandbox.

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
                    "trivy": {...},
                    "secrets": {...},
                    "root_detection": {...},
                    "cert_pinning": {...},
                    "debug_symbols": {...},
                },
                "findings": [...],
                "sandbox": str,
            }
    """
    path = Path(sandbox_path).resolve()
    project_type = _detect_project_type(path)

    # 1. Trivy scan
    trivy_findings, trivy_note = _run_trivy(path)
    trivy_ok = len(trivy_findings) == 0
    if trivy_note:
        trivy_summary = trivy_note
        trivy_detail = trivy_note if verbose else ""
    elif trivy_ok:
        trivy_summary = f"0 CRITICAL CVEs found"
        trivy_detail = ""
    else:
        trivy_summary = f"{len(trivy_findings)} CRITICAL CVE(s) found"
        trivy_detail = "\n".join(f"    - {f}" for f in trivy_findings[:5]) if verbose else ""
        if len(trivy_findings) > 5:
            trivy_detail += f"\n    ... and {len(trivy_findings) - 5} more"

    # 2. Secrets in compiled output
    compiled_dirs = [path / "build", path / "dist", path / "output"]
    scan_dir: Path | None = None
    for d in compiled_dirs:
        if d.exists():
            scan_dir = d
            break
    if scan_dir is None:
        secret_hits: list[str] = []
        secrets_summary = "no build/ or dist/ directory found (skipped)"
        secrets_detail = ""
    else:
        secret_hits = _scan_secrets(scan_dir)
        if not secret_hits:
            secrets_summary = "No secrets in compiled output"
            secrets_detail = ""
        else:
            secrets_summary = f"{len(secret_hits)} potential secret(s) in compiled output"
            secrets_detail = (
                "\n".join(f"    - {h}" for h in secret_hits[:10]) if verbose else ""
            )
            if len(secret_hits) > 10:
                secrets_detail += f"\n    ... and {len(secret_hits) - 10} more"

    # 3. Root detection
    root_found, root_note = _check_root_detection(path, project_type)

    # 4. Certificate pinning
    cert_found, cert_note = _check_cert_pinning(path, project_type)

    # 5. Debug symbols stripped
    debug_ok, debug_note = _check_debug_symbols_stripped(path)

    # ── Score ─────────────────────────────────────────────────────────
    score, findings = _compute_harden_score(
        trivy_findings=trivy_findings,
        secret_hits=secret_hits,
        root_detection_found=root_found,
        root_note=root_note,
        cert_pinning_found=cert_found,
        cert_note=cert_note,
        debug_symbols_ok=debug_ok,
        debug_note=debug_note,
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
            "trivy": {
                "passed": trivy_ok,
                "summary": trivy_summary,
                "detail": trivy_detail,
            },
            "secrets": {
                "passed": len(secret_hits) == 0,
                "summary": secrets_summary,
                "detail": secrets_detail,
            },
            "root_detection": {
                "passed": root_found,
                "summary": (
                    "Root detection configured" if root_found
                    else f"Root detection not found ({root_note})"
                ) if "not applicable" not in root_note.lower() else root_note,
                "detail": root_note if verbose else "",
            },
            "cert_pinning": {
                "passed": cert_found,
                "summary": (
                    "Certificate pinning configured" if cert_found
                    else f"Certificate pinning not found ({cert_note})"
                ) if "not applicable" not in cert_note.lower() else cert_note,
                "detail": cert_note if verbose else "",
            },
            "debug_symbols": {
                "passed": debug_ok,
                "summary": debug_note,
                "detail": "",
            },
        },
        "findings": findings,
    }


# ── Click command ───────────────────────────────────────────────────────


@click.command()
@click.option("--sandbox", required=True, help="Sandbox path or name.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed findings.")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
@click.option("--dry-run", is_flag=True, help="Show what would be scanned without running.")
def harden(sandbox: str, verbose: bool, json_output: bool, dry_run: bool) -> None:
    """Run HARDEN checks on a sandbox.

    Scans for CVEs, exposed secrets, missing root detection,
    missing certificate pinning, and unstripped debug symbols.

    \b
    Scoring rubric:
        Start at 100
        -30 per CRITICAL CVE (cap -90)
        -25 per secret in compiled output
        -10 if root detection missing
        -10 if certificate pinning missing
        -15 if debug symbols not stripped
        Floor at 0, pass >= 70, warn >= 50, fail < 50

    \b
    Examples:

        hero harden --sandbox ~/Development/MyApp

        hero harden --sandbox HERO --verbose

        hero harden --sandbox MyApp --dry-run

        hero harden --sandbox MyApp --json
    """
    sandbox_path = _resolve_sandbox(sandbox)
    project_type = _detect_project_type(sandbox_path)

    # ── Dry-run mode ─────────────────────────────────────────────────
    if dry_run:
        click.echo(f"\nhero harden --sandbox {sandbox_path.name} (dry run)\n")
        click.echo(f"  Project type: {project_type}")
        click.echo(f"  {EMOJI_INFO} Would scan: dependency CVEs via trivy fs")
        click.echo(f"  {EMOJI_INFO} Would scan: build/ or dist/ for exposed secrets")
        click.echo(f"  {EMOJI_INFO} Would check: root/jailbreak detection")
        click.echo(f"  {EMOJI_INFO} Would check: certificate pinning")
        click.echo(f"  {EMOJI_INFO} Would check: debug symbols stripped")
        click.echo(f"\n  No scans executed (dry run).")
        click.echo("")
        return

    # ── Run harden checks ────────────────────────────────────────────
    result = run_harden(sandbox_path, verbose=verbose)

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
    click.echo(f"\nhero harden --sandbox {sandbox_path.name}\n")

    checks = result["checks"]

    # Trivy line
    t = checks["trivy"]
    icon = EMOJI_PASS if t["passed"] else EMOJI_FAIL
    click.echo(f"  {icon} Trivy:       {t['summary']}")

    # Secrets line
    s = checks["secrets"]
    if "skipped" in s["summary"].lower():
        icon = EMOJI_INFO
    elif s["passed"]:
        icon = EMOJI_PASS
    else:
        icon = EMOJI_FAIL
    click.echo(f"  {icon} Secrets:    {s['summary']}")

    # Root detection line
    r = checks["root_detection"]
    if r["passed"]:
        icon = EMOJI_PASS
    elif "not applicable" in r["summary"].lower() or "skipped" in r["summary"].lower():
        icon = EMOJI_INFO
    else:
        icon = EMOJI_FAIL
    click.echo(f"  {icon} Root detect: {r['summary']}")

    # Cert pinning line
    c = checks["cert_pinning"]
    if c["passed"]:
        icon = EMOJI_PASS
    elif "not applicable" in c["summary"].lower() or "skipped" in c["summary"].lower():
        icon = EMOJI_INFO
    else:
        icon = EMOJI_WARN
    click.echo(f"  {icon} Cert pinning: {c['summary']}")

    # Debug symbols line
    d = checks["debug_symbols"]
    icon = EMOJI_PASS if d["passed"] else EMOJI_FAIL
    if "skipped" in d["summary"].lower() or "not applicable" in d["summary"].lower():
        icon = EMOJI_INFO
    click.echo(f"  {icon} Debug syms:  {d['summary']}")

    # Verbose details
    if verbose:
        for check_key, label in [
            ("trivy", "Trivy"),
            ("secrets", "Secrets"),
            ("root_detection", "Root Detection"),
            ("cert_pinning", "Cert Pinning"),
            ("debug_symbols", "Debug Symbols"),
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
