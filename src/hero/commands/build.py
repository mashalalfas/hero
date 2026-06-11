"""hero build — Run BUILD stage checks on a sandbox.

Checks:
1. Build — compile the project with hardening flags
2. Obfuscation — verify code obfuscation (Flutter)
3. ProGuard/R8 — Android minification config
4. Debug symbols — verify debug symbols are stripped (saved separately)

Part of the HERO pipeline: PRE-COMMIT → BUILD → HARDEN → LEGAL → CI/PR → VERIFY → ARCHIVE
"""

from __future__ import annotations

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

SANDBOX_DIR = Path.home() / ".hero" / "sandboxes"

# ── Helpers ──────────────────────────────────────────────────────────────


def _check_build(sandbox_path: Path, verbose: bool) -> dict[str, Any]:
    """Compile the project and return build result.

    Returns dict with: passed, summary, detail, returncode, command
    """
    project_type = _detect_project_type(sandbox_path)

    if project_type == "unknown":
        return {
            "passed": True,
            "summary": "no project type detected (skipped)",
            "detail": "",
            "returncode": 0,
            "command": "",
        }

    cmd: list[str] | None = None
    cmd_label = ""
    timeout = 300

    if project_type == "flutter":
        # Try Flutter APK build with obfuscation flags
        cmd = [
            "flutter", "build", "apk",
            "--obfuscate",
            "--split-debug-info=build/debug-info",
        ]
        cmd_label = "flutter build apk --obfuscate"
    elif project_type == "node":
        # Try npm build; fall back to yarn
        if (sandbox_path / "package.json").exists():
            pkg = (sandbox_path / "package.json").read_text(errors="ignore")
            if '"build"' in pkg or "'build'" in pkg:
                cmd = ["npm", "run", "build"]
                cmd_label = "npm run build"
            else:
                return {
                    "passed": True,
                    "summary": "no build script in package.json (skipped)",
                    "detail": "",
                    "returncode": 0,
                    "command": "",
                }
        else:
            return {
                "passed": True,
                "summary": "no package.json found (skipped)",
                "detail": "",
                "returncode": 0,
                "command": "",
            }
        timeout = 120
    elif project_type == "python":
        cmd = ["python", "-m", "build"]
        cmd_label = "python -m build"
        timeout = 120
    elif project_type == "rust":
        cmd = ["cargo", "build", "--release"]
        cmd_label = "cargo build --release"
        timeout = 300

    if not cmd:
        return {
            "passed": True,
            "summary": f"no build command for {project_type} (skipped)",
            "detail": "",
            "returncode": 0,
            "command": "",
        }

    result, err = _safe_run(cmd, cwd=sandbox_path, timeout=timeout)

    if result is None:
        # Tool not installed or timed out
        error_msg = err or f"{cmd[0]} not available"
        return {
            "passed": False,
            "summary": f"build failed: {error_msg}",
            "detail": error_msg if verbose else "",
            "returncode": -1,
            "command": " ".join(cmd),
        }

    output = (result.stdout or "") + (result.stderr or "")
    passed = result.returncode == 0

    if passed:
        summary = f"{cmd_label} succeeded"
        detail = ""
        if verbose and output.strip():
            # Show last few lines of build output
            lines = output.strip().split("\n")
            detail = "  Output:\n" + "\n".join(f"    {l}" for l in lines[-10:])
    else:
        # Try to extract a meaningful error summary
        error_lines: list[str] = []
        for line in output.split("\n"):
            line_s = line.strip()
            if not line_s:
                continue
            lower = line_s.lower()
            if any(kw in lower for kw in ["error", "failed", "exception", "cannot"]):
                error_lines.append(line_s[:200])
        summary = f"{cmd_label} failed"
        detail = ""
        if verbose:
            detail = "  Errors:\n" + "\n".join(f"    - {l}" for l in error_lines[:10])
            if not error_lines and output.strip():
                detail = "  Output:\n" + "\n".join(
                    f"    {l}" for l in output.strip().split("\n")[-10:]
                )

    return {
        "passed": passed,
        "summary": summary,
        "detail": detail,
        "returncode": result.returncode,
        "command": " ".join(cmd),
    }


def _check_obfuscation(sandbox_path: Path, build_result: dict[str, Any], verbose: bool) -> dict[str, Any]:
    """Check if code obfuscation was applied during build.

    For Flutter: checks for --obfuscate flag in build output / debug-info dir.
    For Android: checks ProGuard/minification flags in build.gradle.
    For other types: not applicable.

    Returns dict with: passed, summary, detail
    """
    project_type = _detect_project_type(sandbox_path)

    if project_type == "flutter":
        # 1. Check build output for "obfuscate" keyword
        build_cmd_used = build_result.get("command", "")
        obfuscation_flag_used = "--obfuscate" in build_cmd_used

        # 2. Check if debug-info directory was created (indicates obfuscation ran)
        debug_info_dir = sandbox_path / "build" / "debug-info"
        debug_info_exists = debug_info_dir.exists() and any(debug_info_dir.iterdir())

        # 3. Also check build output text for obfuscation keyword
        obfuscation_in_output = False
        if build_result.get("detail"):
            obfuscation_in_output = "obfuscation" in build_result["detail"].lower()

        obfuscated = obfuscation_flag_used or debug_info_exists or obfuscation_in_output

        if obfuscated:
            parts = []
            if obfuscation_flag_used:
                parts.append("--obfuscate flag used")
            if debug_info_exists:
                parts.append("debug-info directory created")
            summary = f"obfuscation detected ({', '.join(parts)})"
            detail = ""
            if verbose:
                detail = f"  Command: {build_cmd_used}\n  debug-info dir: {debug_info_dir}"
        else:
            summary = "obfuscation NOT detected — --obfuscate flag not used"
            detail = ""
            if verbose:
                detail = "  Rebuild with: flutter build apk --obfuscate --split-debug-info=build/debug-info"

        return {
            "passed": obfuscated,
            "summary": summary,
            "detail": detail,
        }

    elif project_type == "android":
        # Android native: check build.gradle for minifyEnabled / proguard
        build_gradle = sandbox_path / "app" / "build.gradle"
        if not build_gradle.exists():
            # Also check nested android path
            build_gradle = sandbox_path / "android" / "app" / "build.gradle"

        minify_enabled = False
        if build_gradle.exists():
            try:
                content = build_gradle.read_text(errors="ignore")
                minify_enabled = "minifyEnabled true" in content or "minifyEnabled" in content
                proguard_mentioned = "proguard" in content.lower()
            except OSError:
                pass
        else:
            return {
                "passed": False,
                "summary": "build.gradle not found (cannot verify obfuscation)",
                "detail": str(build_gradle) if verbose else "",
            }

        if minify_enabled:
            summary = "minifyEnabled true (R8/ProGuard configured)"
            detail = ""
            if verbose:
                detail = f"  Config: {build_gradle}"
        else:
            summary = "minifyEnabled not set — code not obfuscated"
            detail = ""
            if verbose:
                detail = f"  Add to build.gradle: buildTypes.release.minifyEnabled true"

        return {
            "passed": minify_enabled,
            "summary": summary,
            "detail": detail,
        }

    # Other project types — obfuscation not applicable
    return {
        "passed": True,
        "summary": f"obfuscation check not applicable for {project_type} (skipped)",
        "detail": "",
    }


def _check_proguard(sandbox_path: Path, verbose: bool) -> dict[str, Any]:
    """Check ProGuard/R8 configuration for Android projects.

    Checks:
    1. android/app/proguard-rules.pro exists
    2. minifyEnabled true in build.gradle

    Returns dict with: passed, summary, detail
    """
    project_type = _detect_project_type(sandbox_path)

    # Only relevant for Flutter Android or native Android
    if project_type not in ("flutter", "android", "unknown"):
        return {
            "passed": True,
            "summary": f"ProGuard check not applicable for {project_type} (skipped)",
            "detail": "",
        }

    # For Flutter, look in android/ subdirectory
    android_base = sandbox_path / "android" if project_type == "flutter" else sandbox_path

    proguard_file = android_base / "app" / "proguard-rules.pro"
    build_gradle = android_base / "app" / "build.gradle"

    # Check proguard-rules.pro
    proguard_exists = proguard_file.exists()
    proguard_content = ""
    if proguard_exists:
        try:
            proguard_content = proguard_file.read_text(errors="ignore")
        except OSError:
            pass

    # Check build.gradle for minifyEnabled
    minify_enabled = False
    gradle_content = ""
    if build_gradle.exists():
        try:
            gradle_content = build_gradle.read_text(errors="ignore")
            minify_enabled = "minifyEnabled true" in gradle_content
        except OSError:
            pass

    has_proguard = proguard_exists and bool(proguard_content.strip())
    has_minify = minify_enabled

    if project_type != "flutter" and project_type != "android":
        return {
            "passed": True,
            "summary": "ProGuard check not applicable (not an Android project)",
            "detail": "",
        }

    if has_proguard and has_minify:
        summary = "ProGuard/R8 fully configured (proguard-rules.pro + minifyEnabled)"
        detail = ""
        if verbose:
            detail = f"  Rules file: {proguard_file}\n  Build gradle: {build_gradle}"
        return {
            "passed": True,
            "summary": summary,
            "detail": detail,
        }

    missing: list[str] = []
    if not has_proguard:
        missing.append("proguard-rules.pro")
    if not has_minify:
        missing.append("minifyEnabled true")

    summary = f"Not configured (missing: {', '.join(missing)})"
    detail = ""
    if verbose:
        detail_parts = []
        if not has_proguard:
            detail_parts.append(f"  Create: {proguard_file}")
        if not has_minify:
            detail_parts.append(f"  Add to {build_gradle}: buildTypes.release.minifyEnabled true")
        detail = "\n".join(detail_parts)

    return {
        "passed": False,
        "summary": summary,
        "detail": detail,
    }


def _check_debug_symbols(sandbox_path: Path, build_result: dict[str, Any], verbose: bool) -> dict[str, Any]:
    """Verify that debug symbols were properly stripped during build.

    For Flutter: verify --split-debug-info flag was used and directory exists.
    For Android: check that release APK has debug symbols stripped.
    For other: not applicable.

    Returns dict with: passed, summary, detail
    """
    project_type = _detect_project_type(sandbox_path)

    if project_type == "flutter":
        build_cmd = build_result.get("command", "")
        split_debug_used = "--split-debug-info" in build_cmd
        debug_info_dir = sandbox_path / "build" / "debug-info"
        debug_info_ok = debug_info_dir.exists() and any(debug_info_dir.iterdir())

        if split_debug_used and debug_info_ok:
            file_count = len(list(debug_info_dir.iterdir()))
            summary = f"--split-debug-info used (debug-info/ has {file_count} file(s))"
            detail = ""
            if verbose:
                files = [str(f.relative_to(sandbox_path)) for f in debug_info_dir.iterdir()][:10]
                detail = f"  Files:\n" + "\n".join(f"    - {f}" for f in files)
                if len(list(debug_info_dir.iterdir())) > 10:
                    detail += "\n    ... and more"
            return {
                "passed": True,
                "summary": summary,
                "detail": detail,
            }

        if not split_debug_used and not debug_info_ok:
            summary = "--split-debug-info NOT used — debug symbols embedded in binary"
            detail = ""
            if verbose:
                detail = "  Rebuild with: flutter build apk --obfuscate --split-debug-info=build/debug-info"
            return {
                "passed": False,
                "summary": summary,
                "detail": detail,
            }

        # Partial: flag used but dir missing (or vice versa)
        parts = []
        if split_debug_used:
            parts.append("--split-debug-info flag used")
        else:
            parts.append("flag not used")
        if debug_info_ok:
            parts.append("debug-info directory exists")
        else:
            parts.append("debug-info directory missing/empty")

        summary = f"debug symbols partially stripped ({', '.join(parts)})"
        return {
            "passed": False,
            "summary": summary,
            "detail": "",
        }

    elif project_type == "android":
        # Android: check build/outputs/apk for debug symbols
        build_outputs = sandbox_path / "app" / "build" / "outputs"
        if not build_outputs.exists():
            return {
                "passed": False,
                "summary": "build/outputs not found — run build first",
                "detail": "",
            }

        # Look for .so files with debug info (simplified check)
        has_debug_syms = False
        for f in build_outputs.rglob("*"):
            if f.is_file() and f.suffix in (".so", ".symtab"):
                has_debug_syms = True
                break

        if has_debug_syms:
            return {
                "passed": False,
                "summary": "debug symbols detected in build output",
                "detail": "",
            }
        return {
            "passed": True,
            "summary": "debug symbols stripped (no .so/.symtab in outputs)",
            "detail": "",
        }

    return {
        "passed": True,
        "summary": f"debug symbols check not applicable for {project_type} (skipped)",
        "detail": "",
    }


def _check_autoversion(sandbox_path: Path, verbose: bool, bump: bool = False) -> dict[str, Any]:
    """Detect version source, report current version, and optionally bump.

    Supports:
    - Flutter: pubspec.yaml (version: x.y.z+code)
    - Node.js: package.json ("version": "x.y.z")
    - Python: pyproject.toml (project.version) or __init__.py __version__
    - Rust: Cargo.toml ([package] version = "x.y.z")

    If bump=True and a version source is found, increments the build/metadata
    number (Flutter: build number +1, others: patch version +1) and writes
    the updated file.

    Returns dict with: passed, summary, detail, version
    """
    project_type = _detect_project_type(sandbox_path)
    version_source = None
    current_version = None
    new_version = None
    bumped = False
    detail_lines: list[str] = []

    # ── Flutter: pubspec.yaml ───────────────────────────────────────
    pubspec = sandbox_path / "pubspec.yaml"
    if pubspec.exists():
        try:
            content = pubspec.read_text(errors="ignore")
            # Match "version: x.y.z+code" or "version: x.y.z"
            m = re.search(r'^version:\s*([\d.]+(?:\+\d+)?)\s*$', content, re.MULTILINE)
            if m:
                version_source = "pubspec.yaml"
                current_version = m.group(1)
                if bump:
                    if "+" in current_version:
                        base, build_num = current_version.rsplit("+", 1)
                        try:
                            new_build = int(build_num) + 1
                            new_version = f"{base}+{new_build}"
                            new_content = content.replace(
                                f"version: {current_version}",
                                f"version: {new_version}",
                                1
                            )
                            pubspec.write_text(new_content)
                            bumped = True
                        except ValueError:
                            new_version = current_version
                    else:
                        # No build number — add +1
                        new_version = f"{current_version}+1"
                        new_content = content.replace(
                            f"version: {current_version}",
                            f"version: {new_version}",
                            1
                        )
                        pubspec.write_text(new_content)
                        bumped = True
                else:
                    new_version = current_version
        except OSError as e:
            detail_lines.append(f"  Error reading pubspec.yaml: {e}")

    # ── Node.js: package.json ───────────────────────────────────────
    pkg_json = sandbox_path / "package.json"
    if not version_source and pkg_json.exists():
        try:
            import json as _json
            data = _json.loads(pkg_json.read_text(errors="ignore"))
            if "version" in data:
                version_source = "package.json"
                current_version = data["version"]
                if bump:
                    parts = current_version.split(".")
                    try:
                        parts[-1] = str(int(parts[-1]) + 1)
                        new_version = ".".join(parts)
                        data["version"] = new_version
                        pkg_json.write_text(_json.dumps(data, indent=2) + "\n")
                        bumped = True
                    except (ValueError, IndexError):
                        new_version = current_version
                else:
                    new_version = current_version
        except (OSError, _json.JSONDecodeError) as e:
            detail_lines.append(f"  Error reading package.json: {e}")

    # ── Rust: Cargo.toml ────────────────────────────────────────────
    cargo = sandbox_path / "Cargo.toml"
    if not version_source and cargo.exists():
        try:
            import tomllib
            data = tomllib.loads(cargo.read_text(errors="ignore"))
            if "package" in data and "version" in data["package"]:
                version_source = "Cargo.toml"
                current_version = data["package"]["version"]
                if bump:
                    parts = current_version.split(".")
                    try:
                        parts[-1] = str(int(parts[-1]) + 1)
                        new_version = ".".join(parts)
                        new_content = cargo.read_text(errors="ignore")
                        new_content = new_content.replace(
                            f'version = "{current_version}"',
                            f'version = "{new_version}"',
                            1
                        )
                        cargo.write_text(new_content)
                        bumped = True
                    except (ValueError, IndexError):
                        new_version = current_version
                else:
                    new_version = current_version
        except (OSError, ImportError, ValueError) as e:
            detail_lines.append(f"  Error reading Cargo.toml: {e}")

    # ── Python: pyproject.toml or __init__.py ───────────────────────
    pyproject = sandbox_path / "pyproject.toml"
    init_py = sandbox_path / "src" / sandbox_path.name / "__init__.py"
    if not version_source and pyproject.exists():
        try:
            import tomllib
            data = tomllib.loads(pyproject.read_text(errors="ignore"))
            if "project" in data and "version" in data["project"]:
                version_source = "pyproject.toml"
                current_version = data["project"]["version"]
                if bump:
                    parts = current_version.split(".")
                    try:
                        parts[-1] = str(int(parts[-1]) + 1)
                        new_version = ".".join(parts)
                        new_content = pyproject.read_text(errors="ignore")
                        new_content = new_content.replace(
                            f'version = "{current_version}"',
                            f'version = "{new_version}"',
                            1
                        )
                        pyproject.write_text(new_content)
                        bumped = True
                    except (ValueError, IndexError):
                        new_version = current_version
                else:
                    new_version = current_version
        except (OSError, ImportError, ValueError) as e:
            detail_lines.append(f"  Error reading pyproject.toml: {e}")

    elif not version_source and init_py.exists():
        try:
            m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', init_py.read_text(errors="ignore"))
            if m:
                version_source = str(init_py.relative_to(sandbox_path))
                current_version = m.group(1)
                new_version = current_version
                # Python __init__.py auto-bump not supported — too fragile
                if bump:
                    detail_lines.append(f"  Auto-bump not supported for __init__.py (edit manually)")
        except (OSError, ValueError):
            pass

    # ── Compose result ──────────────────────────────────────────────
    if version_source:
        version_str = current_version or "?"
        if bump and bumped and new_version:
            summary = f"{version_source} v{current_version} → v{new_version} (bumped)"
            if verbose:
                detail_lines.append(f"  Source: {version_source}")
                detail_lines.append(f"  Previous: v{current_version}")
                detail_lines.append(f"  New:      v{new_version}")
        elif bump and not bumped:
            summary = f"{version_source} v{current_version} (bump skipped — see details)"
            if verbose:
                detail_lines.append(f"  Source: {version_source}")
                detail_lines.append(f"  Version: v{current_version}")
                detail_lines.append(f"  Auto-bump not possible for this version format")
        else:
            summary = f"{version_source} v{current_version}"
            if verbose:
                detail_lines.append(f"  Source: {version_source}")
                detail_lines.append(f"  Version: v{current_version}")
                detail_lines.append(f"  Pass --bump to auto-increment")

        return {
            "passed": True,
            "summary": summary,
            "detail": "\n".join(detail_lines) if detail_lines else "",
            "version": current_version,
            "new_version": new_version,
            "source": version_source,
            "bumped": bumped,
        }

    # No version source found
    summary = "no version source detected"
    if verbose:
        detail_lines.append("  Checked: pubspec.yaml, package.json, Cargo.toml, pyproject.toml, __init__.py")
        detail_lines.append("  Add a version field to enable auto-versioning")

    return {
        "passed": False,
        "summary": summary,
        "detail": "\n".join(detail_lines) if detail_lines else "",
        "version": None,
        "new_version": None,
        "source": None,
        "bumped": False,
    }


# ── Scoring ─────────────────────────────────────────────────────────────


def _compute_build_score(
    build_check: dict[str, Any],
    obfuscation_check: dict[str, Any],
    proguard_check: dict[str, Any],
    debug_symbols_check: dict[str, Any],
    autoversion_check: dict[str, Any],
    project_type: str,
) -> tuple[int, list[dict[str, str]]]:
    """Compute final BUILD score (0-100) and list of findings.

    Scoring rubric:

        Start at 100
        -20 if build fails entirely
        -15 if obfuscation not detected (Flutter)
        -15 if ProGuard/R8 not configured (Android)
        -15 if debug symbols not stripped
        -5  if no version source detected (warn only)
        Floor at 0
    """
    score = 100
    findings: list[dict[str, str]] = []

    # Build failure
    if not build_check["passed"]:
        score = max(0, score - 20)
        findings.append({
            "severity": "error",
            "check": "build",
            "message": f"Build failed: {build_check['summary']} (-20)",
        })

    # Obfuscation (Flutter only)
    if project_type == "flutter" and not obfuscation_check["passed"]:
        score = max(0, score - 15)
        findings.append({
            "severity": "error",
            "check": "obfuscation",
            "message": f"Obfuscation not detected: {obfuscation_check['summary']} (-15)",
        })

    # ProGuard/R8 (Android only)
    if project_type in ("flutter", "android"):
        if not proguard_check["passed"]:
            score = max(0, score - 15)
            findings.append({
                "severity": "error",
                "check": "proguard",
                "message": f"ProGuard/R8 not configured: {proguard_check['summary']} (-15)",
                })

    # Debug symbols
    if not debug_symbols_check["passed"]:
        score = max(0, score - 15)
        findings.append({
            "severity": "error",
            "check": "debug_symbols",
            "message": f"Debug symbols not stripped: {debug_symbols_check['summary']} (-15)",
        })

    # Auto-version (warn only — info finding, not blocking)
    if not autoversion_check["passed"]:
        score = max(0, score - 5)
        findings.append({
            "severity": "warning",
            "check": "autoversion",
            "message": f"No version source detected: {autoversion_check['summary']} (-5)",
        })
    elif autoversion_check.get("bumped"):
        findings.append({
            "severity": "info",
            "check": "autoversion",
            "message": f"Version auto-bumped: {autoversion_check.get('version')} → {autoversion_check.get('new_version')}",
        })

    return score, findings


# ── Main API ────────────────────────────────────────────────────────────


def run_build(sandbox_path: str | Path, verbose: bool = False, bump: bool = False) -> dict[str, Any]:
    """Run all BUILD checks and return structured results.

    Parameters
    ----------
    sandbox_path : str or Path
        Path to the sandbox/project directory.
    verbose : bool, default=False
        Include detailed output in each check result.
    bump : bool, default=False
        Auto-increment version before building.

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
                    "build": {...},
                    "obfuscation": {...},
                    "proguard": {...},
                    "debug_symbols": {...},
                    "autoversion": {...},
                },
                "findings": [...],
                "sandbox": str,
                "version": {...},
            }
    """
    path = Path(sandbox_path).resolve()
    project_type = _detect_project_type(path)

    # Run build first (other checks depend on its result)
    build_check = _check_build(path, verbose)

    # Obfuscation check (uses build result for command/output info)
    obfuscation_check = _check_obfuscation(path, build_check, verbose)

    # ProGuard/R8 check (Android only)
    proguard_check = _check_proguard(path, verbose)

    # Debug symbols check (uses build result)
    debug_symbols_check = _check_debug_symbols(path, build_check, verbose)

    # Auto-version check (new — detects + optionally bumps)
    autoversion_check = _check_autoversion(path, verbose, bump=bump)

    score, findings = _compute_build_score(
        build_check, obfuscation_check, proguard_check, debug_symbols_check, autoversion_check, project_type
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
            "build": {
                "passed": build_check["passed"],
                "summary": build_check["summary"],
                "detail": build_check.get("detail", ""),
            },
            "obfuscation": {
                "passed": obfuscation_check["passed"],
                "summary": obfuscation_check["summary"],
                "detail": obfuscation_check.get("detail", ""),
            },
            "proguard": {
                "passed": proguard_check["passed"],
                "summary": proguard_check["summary"],
                "detail": proguard_check.get("detail", ""),
            },
            "debug_symbols": {
                "passed": debug_symbols_check["passed"],
                "summary": debug_symbols_check["summary"],
                "detail": debug_symbols_check.get("detail", ""),
            },
            "autoversion": {
                "passed": autoversion_check["passed"],
                "summary": autoversion_check["summary"],
                "detail": autoversion_check.get("detail", ""),
                "version": autoversion_check.get("version"),
                "new_version": autoversion_check.get("new_version"),
                "bumped": autoversion_check.get("bumped", False),
            },
        },
        "findings": findings,
        "version": {
            "current": autoversion_check.get("version"),
            "new": autoversion_check.get("new_version"),
            "source": autoversion_check.get("source"),
            "bumped": autoversion_check.get("bumped", False),
        } if autoversion_check.get("version") else None,
    }


# ── Click command ───────────────────────────────────────────────────────


@click.command()
@click.option("--sandbox", required=True, help="Sandbox path or name.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed findings.")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
@click.option("--dry-run", is_flag=True, help="Show what would be built without running the build.")
@click.option("--bump", is_flag=True, help="Auto-increment version before building.")
def build(sandbox: str, verbose: bool, json_output: bool, dry_run: bool, bump: bool) -> None:
    """Run BUILD checks on a sandbox.

    Compiles the project with hardening flags and verifies obfuscation,
    ProGuard/R8, debug symbol stripping, and versioning.

    \b
    Scoring rubric:
        - Start at 100
        -20 if build fails
        -15 if obfuscation not detected (Flutter)
        -15 if ProGuard/R8 not configured (Android)
        -15 if debug symbols not stripped
        -5  if no version source detected (warn)
        Floor at 0, pass >= 70, warn >= 50, fail < 50

    \b
    Supported project types:
        Flutter, Node.js, Python, Rust

    \b
    Version sources (auto-detected):
        Flutter: pubspec.yaml (version: x.y.z+code)
        Node.js: package.json ("version": "x.y.z")
        Rust:    Cargo.toml ([package] version = "x.y.z")
        Python:  pyproject.toml (project.version) or __init__.py __version__

    \b
    Use --bump to auto-increment the version before building:
        Flutter: build number +1 (x.y.z+N → x.y.z+N+1)
        Others:  patch +1 (x.y.z → x.y.(z+1))

    Examples:

        hero build --sandbox ~/Development/MyApp

        hero build --sandbox ~/Development/MyApp --verbose

        hero build --sandbox ~/Development/MyApp --bump

        hero build --sandbox MyApp --dry-run

        hero build --sandbox MyApp --json
    """
    sandbox_path = _resolve_sandbox(sandbox)
    project_type = _detect_project_type(sandbox_path)

    # ── Dry-run mode ─────────────────────────────────────────────────
    if dry_run:
        click.echo(f"\nhero build --sandbox {sandbox_path.name} (dry run)\n")
        click.echo(f"  Project type: {project_type}")

        if project_type == "flutter":
            click.echo(f"  {EMOJI_INFO} Would run: flutter build apk --obfuscate --split-debug-info=build/debug-info")
            click.echo(f"  {EMOJI_INFO} Would check: obfuscation in build output")
            click.echo(f"  {EMOJI_INFO} Would check: build/debug-info/ directory")
            android_bg = sandbox_path / "android" / "app" / "build.gradle"
            if android_bg.exists():
                click.echo(f"  {EMOJI_INFO} Would check: ProGuard/R8 in android/app/build.gradle")
                click.echo(f"  {EMOJI_INFO} Would check: android/app/proguard-rules.pro")
        elif project_type == "node":
            click.echo(f"  {EMOJI_INFO} Would run: npm run build")
        elif project_type == "python":
            click.echo(f"  {EMOJI_INFO} Would run: python -m build")
        elif project_type == "rust":
            click.echo(f"  {EMOJI_INFO} Would run: cargo build --release")
        else:
            click.echo(f"  {EMOJI_WARN} No recognised project type — checks will be skipped")

        # Version info
        click.echo(f"")
        av = _check_autoversion(sandbox_path, verbose=False, bump=False)
        if av["passed"] and av.get("version"):
            click.echo(f"  {EMOJI_INFO} Version source: {av['source']} → {av['version']}")
            if bump:
                click.echo(f"  {EMOJI_INFO} --bump flag: would auto-increment version")
            else:
                click.echo(f"  {EMOJI_INFO} Add --bump to auto-increment version before build")
        else:
            click.echo(f"  {EMOJI_INFO} Version: no source detected (pubspec.yaml, package.json, Cargo.toml, pyproject.toml)")

        click.echo(f"\n  No build executed (dry run).")
        click.echo("")
        return

    # ── Run build checks ─────────────────────────────────────────────
    result = run_build(sandbox_path, verbose=verbose, bump=bump)

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
                    "version": v.get("version"),
                    "new_version": v.get("new_version"),
                    "bumped": v.get("bumped", False),
                }
                for k, v in result["checks"].items()
            },
            "findings": result["findings"],
            "version": result.get("version"),
        }
        click.echo(_json.dumps(json_result, indent=2))
        return

    # ── Pretty output ────────────────────────────────────────────────
    click.echo(f"\nhero build --sandbox {sandbox_path.name}\n")

    checks = result["checks"]

    # Build line
    b = checks["build"]
    icon = EMOJI_PASS if b["passed"] else EMOJI_FAIL
    click.echo(f"  {icon} Build:       {b['summary']}")

    # Obfuscation line
    o = checks["obfuscation"]
    icon = EMOJI_PASS if o["passed"] else EMOJI_FAIL
    click.echo(f"  {icon} Obfuscation: {o['summary']}")

    # ProGuard line
    p = checks["proguard"]
    if p["passed"]:
        icon = EMOJI_PASS
    elif "skipped" in p["summary"].lower() or "not applicable" in p["summary"].lower():
        icon = EMOJI_INFO
    else:
        icon = EMOJI_WARN
    click.echo(f"  {icon} ProGuard:    {p['summary']}")

    # Debug symbols line
    d = checks["debug_symbols"]
    icon = EMOJI_PASS if d["passed"] else EMOJI_FAIL
    if "skipped" in d["summary"].lower() or "not applicable" in d["summary"].lower():
        icon = EMOJI_INFO
    click.echo(f"  {icon} Debug syms:  {d['summary']}")

    # Auto-version line
    v = checks["autoversion"]
    if v["passed"]:
        if v.get("bumped"):
            icon = EMOJI_PASS
            click.echo(f"  {icon} Version:     {v['summary']}")
        else:
            click.echo(f"  {EMOJI_INFO} Version:     {v['summary']}")
    else:
        click.echo(f"  {EMOJI_WARN} Version:     {v['summary']}")

    # Verbose details
    if verbose:
        for check_key, label in [
            ("build", "Build"),
            ("obfuscation", "Obfuscation"),
            ("proguard", "ProGuard"),
            ("debug_symbols", "Debug Symbols"),
            ("autoversion", "Version"),
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
        errors_count = sum(1 for f in result["findings"] if f["severity"] == "error")
        warnings_count = sum(1 for f in result["findings"] if f["severity"] == "warning")
        info_count = sum(1 for f in result["findings"] if f["severity"] == "info")
        parts = []
        if errors_count:
            parts.append(f"{EMOJI_FAIL} {errors_count} error(s)")
        if warnings_count:
            parts.append(f"{EMOJI_WARN} {warnings_count} warning(s)")
        if info_count and not errors_count and not warnings_count:
            parts.append(f"{EMOJI_INFO} {info_count} note(s)")
        if parts:
            click.echo(f"  {' '.join(parts)}")

    click.echo("")
