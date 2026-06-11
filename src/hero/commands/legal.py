"""hero legal — Run LEGAL stage checks and artifact generation.

Checks:
1. Config — legal-config.json presence / auto-generation
2. License scan — dependency allowlist/blocklist enforcement
3. SBOM — Software Bill of Materials generation
4. EULA — End User License Agreement generation
5. Privacy Policy — privacy policy generation (openterms or fallback)
6. Copyright — SPDX/Copyright header check (re-used from pre_commit)

Part of the HERO pipeline: PRE-COMMIT → BUILD → HARDEN → LEGAL → CI/PR → VERIFY → ARCHIVE
"""

from __future__ import annotations

import json
import subprocess
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any

import click

from hero.commands.check import EMOJI_PASS, EMOJI_WARN, EMOJI_FAIL, EMOJI_INFO
from hero.commands.pre_commit import (
    _check_copyright,
    _detect_project_type,
    _resolve_sandbox,
    _safe_run,
)

SANDBOX_DIR = Path.home() / ".hero" / "sandboxes"

DEFAULT_LEGAL_CONFIG: dict[str, Any] = {
    "project": "auto-detected",
    "type": "mobile_app",
    "jurisdiction": "UAE",
    "eulaSource": "commercial-standard-license",
    "dataCollection": "none",
    "hasAccounts": False,
    "hasBackend": False,
    "ossAllowlist": [
        "MIT",
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
    ],
    "ossBlocklist": [
        "GPL-2.0",
        "GPL-3.0",
        "AGPL-3.0",
        "SSPL",
    ],
    "stores": ["apple_app_store", "google_play"],
}

EULA_TEMPLATE_PATH = (
    Path.home() / "Development" / "legal-templates" / "Commercial-Standard-License" / "License.md"
)
OPENTERMS_SRC = (
    Path.home() / "Development" / "legal-templates" / "openterms" / "src" / "app-privacy" / "index.ts"
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _read_text_safe(path: Path) -> str | None:
    try:
        return path.read_text(errors="ignore")
    except OSError:
        return None


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _normalise_license_id(raw: str) -> str:
    """Normalise a licence string to SPDX-ish id for comparison."""
    cleaned = raw.strip().lower()
    # Common normalisations
    mapping = {
        "mit license": "MIT",
        "apache 2.0": "Apache-2.0",
        "apache-2.0": "Apache-2.0",
        "bsd 2-clause": "BSD-2-Clause",
        "bsd-3-clause": "BSD-3-Clause",
        "isc": "ISC",
        "gpl-2.0": "GPL-2.0",
        "gpl v2.0": "GPL-2.0",
        "gpl-3.0": "GPL-3.0",
        "gpl v3.0": "GPL-3.0",
        "agpl-3.0": "AGPL-3.0",
        "sspl": "SSPL",
        "sspl v1": "SSPL",
    }
    return mapping.get(cleaned, raw.strip())


def _licence_in_list(licence_id: str, licence_list: list[str]) -> bool:
    """Check if a licence id matches any entry in a list (case-insensitive)."""
    lid = licence_id.lower()
    for entry in licence_list:
        if lid == entry.lower():
            return True
    return False


# ── Check 1: Config ─────────────────────────────────────────────────────


def _load_or_create_legal_config(sandbox_path: Path) -> tuple[dict[str, Any], bool]:
    """Load legal-config.json or create a default one.

    Returns (config_dict, was_auto_generated: bool).
    """
    config_path = sandbox_path / "legal-config.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text()), False
        except (json.JSONDecodeError, OSError):
            pass  # regenerate

    # Auto-generate defaults
    config = dict(DEFAULT_LEGAL_CONFIG)
    # Try to detect project name
    pubspec = sandbox_path / "pubspec.yaml"
    if pubspec.exists():
        try:
            for line in pubspec.read_text(errors="ignore").splitlines():
                if line.strip().startswith("name:"):
                    config["project"] = line.split(":", 1)[1].strip().strip('"').strip("'")
                    break
        except OSError:
            pass
    else:
        package_json = sandbox_path / "package.json"
        if package_json.exists():
            try:
                pj = json.loads(package_json.read_text())
                config["project"] = pj.get("name", "auto-detected")
            except (json.JSONDecodeError, OSError):
                pass

    _write_text(config_path, json.dumps(config, indent=2) + "\n")
    return config, True


# ── Check 2: License scan ───────────────────────────────────────────────


def _scan_licenses_node(sandbox_path: Path) -> tuple[list[dict[str, str]], str | None]:
    """Scan Node.js dependencies. Returns (entries, error_reason)."""
    entries: list[dict[str, str]] = []

    # Try license-checker first
    result, err = _safe_run(
        ["npx", "license-checker", "--production", "--json"],
        cwd=sandbox_path,
        timeout=120,
    )
    if result is not None and result.stdout.strip():
        try:
            data = json.loads(result.stdout)
            if data:
                # Read project name to detect root-package-only results
                pkg_json = sandbox_path / "package.json"
                project_name = None
                if pkg_json.exists():
                    try:
                        project_name = json.loads(pkg_json.read_text()).get("name")
                    except (json.JSONDecodeError, OSError):
                        pass

                # Check if license-checker only found the root package (no real deps)
                root_only = False
                if project_name and len(data) == 1:
                    only_key = next(iter(data))
                    only_name = only_key.split("@")[0] if "@" in only_key else only_key
                    if only_name == project_name:
                        root_only = True

                if not root_only:
                    for pkg_key, info in data.items():
                        # license-checker keys are "name@version"
                        name = pkg_key.split("@")[0] if "@" in pkg_key else pkg_key
                        lic = info.get("licenses", "UNKNOWN")
                        entries.append({"name": name, "license": lic})
                    return entries, None
        except (json.JSONDecodeError, ValueError):
            pass  # fall through to package-lock.json

    # Fallback: parse package-lock.json
    lock_file = sandbox_path / "package-lock.json"
    if not lock_file.exists():
        return entries, err or "no package-lock.json found"
    try:
        lock = json.loads(lock_file.read_text())
        packages = lock.get("packages", lock.get("dependencies", {}))
        for pkg_key, info in packages.items():
            if pkg_key == "":
                continue
            # Strip node_modules/ prefix and @version suffix
            name = pkg_key
            if name.startswith("node_modules/"):
                name = name[len("node_modules/"):]
            if "@" in name:
                name = name.rsplit("@", 1)[0]
            lic = info.get("license", "UNKNOWN")
            if isinstance(lic, dict):
                lic = lic.get("type", "UNKNOWN")
            entries.append({"name": name, "license": str(lic)})
        return entries, None
    except (json.JSONDecodeError, OSError) as exc:
        return entries, str(exc)


def _scan_licenses_flutter(sandbox_path: Path) -> tuple[list[dict[str, str]], str | None]:
    """Scan Flutter dependencies from pubspec.lock. Returns (entries, error_reason)."""
    entries: list[dict[str, str]] = []
    lock_file = sandbox_path / "pubspec.lock"
    if not lock_file.exists():
        return entries, "pubspec.lock not found"

    text = _read_text_safe(lock_file)
    if text is None:
        return entries, "cannot read pubspec.lock"

    # Parse YAML manually (avoid hard dependency on pyyaml if not installed)
    try:
        import yaml  # type: ignore[import-untyped]

        data = yaml.safe_load(text)
        packages = data.get("packages", {})
        for pkg_name, info in packages.items():
            lic = info.get("license", {})
            if isinstance(lic, dict):
                lic = lic.get("id") or lic.get("type") or "UNKNOWN"
            elif isinstance(lic, str):
                lic = lic
            else:
                lic = "UNKNOWN"
            version = info.get("version", "unknown")
            entries.append({"name": pkg_name, "license": str(lic), "version": str(version)})
        return entries, None
    except ImportError:
        # Manual YAML-ish parsing for pubspec.lock
        current_pkg: str | None = None
        current_lic: str | None = None
        current_ver: str | None = None
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and ":" in stripped:
                key, _, value = stripped.partition(":")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key == "package":
                    current_pkg = value
                    current_lic = None
                    current_ver = None
                elif key == "version" and current_pkg:
                    current_ver = value
                elif key == "license" and current_pkg:
                    current_lic = value
                elif key == "description" and current_pkg:
                    # End of current package block when we hit a new non-indented key
                    pass
            if current_pkg and current_lic and stripped == "":
                entries.append({
                    "name": current_pkg,
                    "license": current_lic,
                    "version": current_ver or "unknown",
                })
                current_pkg = None
                current_lic = None
                current_ver = None
        # Flush last package
        if current_pkg and current_lic:
            entries.append({
                "name": current_pkg,
                "license": current_lic,
                "version": current_ver or "unknown",
            })
        return entries, None


def _check_license_scan(
    sandbox_path: Path, config: dict[str, Any], verbose: bool
) -> dict[str, Any]:
    """Scan project dependencies and check against allowlist/blocklist."""
    project_type = _detect_project_type(sandbox_path)
    allowlist = [l.lower() for l in config.get("ossAllowlist", [])]
    blocklist = [l.lower() for l in config.get("ossBlocklist", [])]
    findings: list[str] = []
    blocked: list[dict[str, str]] = []

    if project_type == "node":
        entries, err = _scan_licenses_node(sandbox_path)
    elif project_type == "flutter":
        entries, err = _scan_licenses_flutter(sandbox_path)
    else:
        return {
            "passed": True,
            "summary": f"no dependency scan for project type '{project_type}' (skipped)",
            "detail": "",
            "blocked_count": 0,
            "blocked": [],
        }

    if err and not entries:
        return {
            "passed": True,
            "summary": f"license scan skipped: {err}",
            "detail": "",
            "blocked_count": 0,
            "blocked": [],
        }

    for entry in entries:
        raw_lic = entry.get("license", "UNKNOWN")
        norm_lic = _normalise_license_id(raw_lic).lower()

        if norm_lic in blocklist or _licence_in_list(raw_lic, config.get("ossBlocklist", [])):
            blocked.append(entry)
            findings.append(f"{entry['name']}: {raw_lic} (BLOCKED)")
        elif allowlist and not (
            norm_lic in allowlist or _licence_in_list(raw_lic, config.get("ossAllowlist", []))
        ):
            # Not explicitly allowlisted — warn but don't block
            findings.append(f"{entry['name']}: {raw_lic} (not in allowlist)")

    if blocked:
        passed = False
        summary = f"{len(blocked)} blocked license(s) found"
    elif findings:
        passed = True
        summary = f"{len(findings)} unallowlisted license(s) (not blocked)"
    else:
        passed = True
        summary = f"all {len(entries)} dependencies within allowlist (0 blocked)"

    detail = ""
    if verbose and findings:
        detail = "  Findings:\n" + "\n".join(f"    - {f}" for f in findings[:20])
        if len(findings) > 20:
            detail += f"\n    ... and {len(findings) - 20} more"

    return {
        "passed": passed,
        "summary": summary,
        "detail": detail,
        "blocked_count": len(blocked),
        "blocked": blocked,
    }


# ── Check 3: SBOM ───────────────────────────────────────────────────────


def _generate_sbom_flutter(sandbox_path: Path) -> dict[str, Any]:
    """Generate minimal SBOM from pubspec.lock."""
    lock_file = sandbox_path / "pubspec.lock"
    if not lock_file.exists():
        return {}

    text = _read_text_safe(lock_file)
    if text is None:
        return {}

    components: list[dict[str, Any]] = []
    try:
        import yaml  # type: ignore[import-untyped]

        data = yaml.safe_load(text)
        packages = data.get("packages", {})
        for pkg_name, info in packages.items():
            lic = info.get("license", {})
            if isinstance(lic, dict):
                lic_id = lic.get("id", "NOASSERTION")
            elif isinstance(lic, str):
                lic_id = lic
            else:
                lic_id = "NOASSERTION"
            components.append({
                "name": pkg_name,
                "version": str(info.get("version", "unknown")),
                "licenses": [{"license": {"id": str(lic_id)}}],
            })
    except ImportError:
        # Manual parse
        current_pkg: str | None = None
        current_lic: str | None = None
        current_ver: str | None = None
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and ":" in stripped:
                key, _, value = stripped.partition(":")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key == "package":
                    current_pkg = value
                    current_lic = None
                    current_ver = None
                elif key == "version" and current_pkg:
                    current_ver = value
                elif key == "license" and current_pkg:
                    current_lic = value
            if current_pkg and current_lic and stripped == "":
                components.append({
                    "name": current_pkg,
                    "version": current_ver or "unknown",
                    "licenses": [{"license": {"id": current_lic}}],
                })
                current_pkg = None
                current_lic = None
                current_ver = None
        if current_pkg and current_lic:
            components.append({
                "name": current_pkg,
                "version": current_ver or "unknown",
                "licenses": [{"license": {"id": current_lic}}],
            })

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "components": components,
    }


def _check_sbom(sandbox_path: Path, verbose: bool) -> dict[str, Any]:
    """Generate and validate SBOM."""
    legal_dir = sandbox_path / "legal"
    sbom_path = legal_dir / "sbom.json"
    project_type = _detect_project_type(sandbox_path)

    if project_type == "node":
        result, err = _safe_run(
            ["npx", "@cyclonedx/cyclonedx-npm", "--output-file", "legal/sbom.json"],
            cwd=sandbox_path,
            timeout=120,
        )
        if result is None or result.returncode != 0:
            # Try to generate a minimal one as fallback
            lock_file = sandbox_path / "package-lock.json"
            if lock_file.exists():
                try:
                    lock = json.loads(lock_file.read_text())
                    packages = lock.get("packages", lock.get("dependencies", {}))
                    components = []
                    for pkg_name, info in packages.items():
                        if pkg_name == "":
                            continue
                        lic = info.get("license", "NOASSERTION")
                        if isinstance(lic, dict):
                            lic = lic.get("type", "NOASSERTION")
                        components.append({
                            "name": pkg_name,
                            "version": str(info.get("version", "unknown")),
                            "licenses": [{"license": {"id": str(lic)}}],
                        })
                    sbom = {
                        "bomFormat": "CycloneDX",
                        "specVersion": "1.4",
                        "components": components,
                    }
                    _write_text(sbom_path, json.dumps(sbom, indent=2) + "\n")
                except (json.JSONDecodeError, OSError) as exc:
                    return {
                        "passed": False,
                        "summary": f"SBOM generation failed: {exc}",
                        "detail": err or str(exc) if verbose else "",
                    }
            else:
                return {
                    "passed": False,
                    "summary": f"SBOM generation failed: {err or 'no package-lock.json'}",
                    "detail": err or "" if verbose else "",
                }
    elif project_type == "flutter":
        sbom = _generate_sbom_flutter(sandbox_path)
        if sbom.get("components"):
            _write_text(sbom_path, json.dumps(sbom, indent=2) + "\n")
        else:
            return {
                "passed": False,
                "summary": "SBOM generation failed: no components found in pubspec.lock",
                "detail": "",
            }
    else:
        return {
            "passed": False,
            "summary": f"SBOM generation not supported for project type '{project_type}'",
            "detail": "",
        }

    # Validate output
    if not sbom_path.exists() or sbom_path.stat().st_size == 0:
        return {
            "passed": False,
            "summary": "SBOM file missing or empty after generation",
            "detail": str(sbom_path) if verbose else "",
        }

    try:
        sbom_data = json.loads(sbom_path.read_text())
        comp_count = len(sbom_data.get("components", []))
        passed = comp_count > 0
        summary = (
            f"SBOM generated at legal/sbom.json ({comp_count} components)"
            if passed
            else "SBOM generated but has 0 components"
        )
    except (json.JSONDecodeError, OSError) as exc:
        return {
            "passed": False,
            "summary": f"SBOM file invalid: {exc}",
            "detail": str(sbom_path) if verbose else "",
        }

    return {
        "passed": passed,
        "summary": summary,
        "detail": str(sbom_path) if verbose else "",
    }


# ── Check 4: EULA ───────────────────────────────────────────────────────


def _check_eula(sandbox_path: Path, config: dict[str, Any], verbose: bool) -> dict[str, Any]:
    """Generate EULA from Commercial-Standard-License template."""
    legal_dir = sandbox_path / "legal"
    eula_path = legal_dir / "EULA.md"

    template_text = _read_text_safe(EULA_TEMPLATE_PATH)
    if template_text is None:
        return {
            "passed": False,
            "summary": f"EULA template not found at {EULA_TEMPLATE_PATH}",
            "detail": str(EULA_TEMPLATE_PATH) if verbose else "",
        }

    project_name = config.get("project", "the Software")
    jurisdiction = config.get("jurisdiction", "UAE")
    year = datetime.now().year

    eula_content = template_text
    eula_content = eula_content.replace("[NAME HERE]", project_name)
    eula_content = eula_content.replace("[NUM]", "1")
    # Also substitute year placeholder if present
    eula_content = eula_content.replace("[YEAR]", str(year))
    # Substitute jurisdiction if template uses it
    eula_content = eula_content.replace("[JURISDICTION]", jurisdiction)

    try:
        _write_text(eula_path, eula_content)
    except OSError as exc:
        return {
            "passed": False,
            "summary": f"EULA write failed: {exc}",
            "detail": str(eula_path) if verbose else "",
        }

    source_label = "Commercial-Standard-License"
    return {
        "passed": True,
        "summary": f"legal/EULA.md generated ({source_label})",
        "detail": str(eula_path) if verbose else "",
    }


# ── Check 5: Privacy Policy ─────────────────────────────────────────────


def _generate_privacy_via_openterms(config: dict[str, Any]) -> str | None:
    """Try to generate privacy policy via openterms. Returns content or None."""
    # Try npx first
    result, err = _safe_run(
        ["npx", "@entva/openterms"],
        cwd=Path.home(),
        timeout=60,
    )
    if result is not None and result.stdout.strip():
        return result.stdout.strip()

    # Try local source via tsx or ts-node
    tsx_candidates = [
        ["npx", "tsx", str(OPENTERMS_SRC)],
        ["npx", "ts-node", str(OPENTERMS_SRC)],
    ]
    for cmd in tsx_candidates:
        result, err = _safe_run(cmd, cwd=Path.home(), timeout=60)
        if result is not None and result.stdout.strip():
            return result.stdout.strip()

    return None


def _generate_privacy_fallback(config: dict[str, Any]) -> str:
    """Generate minimal privacy policy fallback."""
    project_name = config.get("project", "this app")
    date = _now()
    return textwrap.dedent(f"""\
        # Privacy Policy

        **Last updated:** {date}

        **{project_name}** does not collect, store, or transmit any personal data.
        All data is processed locally on your device.

        ## Data Collection
        This app does not collect personal information, usage analytics, or device identifiers.

        ## Third-Party Services
        This app does not integrate with third-party analytics or advertising SDKs.

        ## Contact
        For questions about this privacy policy, contact the developer.
    """)


def _check_privacy_policy(
    sandbox_path: Path, config: dict[str, Any], verbose: bool
) -> dict[str, Any]:
    """Generate Privacy Policy. Returns check result dict."""
    legal_dir = sandbox_path / "legal"
    privacy_path = legal_dir / "PRIVACY.md"
    used_fallback = False

    # Try openterms
    openterms_content = _generate_privacy_via_openterms(config)
    if openterms_content is None:
        content = _generate_privacy_fallback(config)
        used_fallback = True
    else:
        content = openterms_content

    try:
        _write_text(privacy_path, content)
    except OSError as exc:
        return {
            "passed": False,
            "summary": f"Privacy Policy write failed: {exc}",
            "detail": str(privacy_path) if verbose else "",
        }

    if used_fallback:
        summary = "legal/PRIVACY.md generated (fallback template — openterms unavailable)"
    else:
        summary = "legal/PRIVACY.md generated (openterms)"

    return {
        "passed": True,
        "summary": summary,
        "detail": str(privacy_path) if verbose else "",
        "used_fallback": used_fallback,
    }


# ── Scoring ─────────────────────────────────────────────────────────────


def _compute_legal_score(
    config_result: dict[str, Any],
    license_result: dict[str, Any],
    sbom_result: dict[str, Any],
    eula_result: dict[str, Any],
    privacy_result: dict[str, Any],
    copyright_result: dict[str, Any],
) -> tuple[int, list[dict[str, str]]]:
    """Compute final LEGAL score (0-100) and findings list.

    Scoring rubric:

        Start at 100
        -15 if legal-config.json was auto-generated
        -15 per blocked license found
        -20 if SBOM missing or invalid
        -20 if EULA not generated
        -15 if Privacy Policy not generated
        -5 if using fallback Privacy Policy template
        -2 per missing copyright header
        Floor at 0
    """
    score = 100
    findings: list[dict[str, str]] = []

    # Config deduction
    if config_result.get("auto_generated"):
        score = max(0, score - 15)
        findings.append({
            "severity": "warning",
            "check": "config",
            "message": "legal-config.json auto-generated from defaults (-15)",
        })

    # License scan
    blocked_count = license_result.get("blocked_count", 0)
    if blocked_count > 0:
        deduction = blocked_count * 15
        score = max(0, score - deduction)
        for entry in license_result.get("blocked", [])[:10]:
            findings.append({
                "severity": "error",
                "check": "license_scan",
                "message": f"Blocked license: {entry['name']} ({entry.get('license', 'UNKNOWN')}) (-15)",
            })
        if blocked_count > 10:
            findings.append({
                "severity": "error",
                "check": "license_scan",
                "message": f"... and {blocked_count - 10} more blocked licenses",
            })

    # SBOM
    if not sbom_result.get("passed"):
        score = max(0, score - 20)
        findings.append({
            "severity": "error",
            "check": "sbom",
            "message": f"SBOM missing or invalid: {sbom_result.get('summary', '')} (-20)",
        })

    # EULA
    if not eula_result.get("passed"):
        score = max(0, score - 20)
        findings.append({
            "severity": "error",
            "check": "eula",
            "message": f"EULA not generated: {eula_result.get('summary', '')} (-20)",
        })

    # Privacy Policy
    if not privacy_result.get("passed"):
        score = max(0, score - 15)
        findings.append({
            "severity": "error",
            "check": "privacy_policy",
            "message": f"Privacy Policy not generated (-15)",
        })
    elif privacy_result.get("used_fallback"):
        score = max(0, score - 5)
        findings.append({
            "severity": "warning",
            "check": "privacy_policy",
            "message": "Privacy Policy using fallback template (-5)",
        })

    # Copyright headers
    missing_headers = copyright_result.get("missing", 0)
    if missing_headers > 0:
        deduction = missing_headers * 2
        score = max(0, score - deduction)
        for _ in range(min(missing_headers, 5)):
            findings.append({
                "severity": "warning",
                "check": "copyright",
                "message": f"Missing copyright/SPDX header (deduction -2)",
            })

    return score, findings


# ── Main API ────────────────────────────────────────────────────────────


def run_legal(sandbox_path: str | Path, verbose: bool = False) -> dict[str, Any]:
    """Run all LEGAL checks and artifact generation.

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
                "score": int,
                "status": str,   # "pass" | "warn" | "fail"
                "checks": {
                    "config": {"passed": bool, "summary": str, "auto_generated": bool},
                    "license_scan": {"passed": bool, "summary": str, "blocked_count": int},
                    "sbom": {"passed": bool, "summary": str},
                    "eula": {"passed": bool, "summary": str},
                    "privacy_policy": {"passed": bool, "summary": str, "used_fallback": bool},
                    "copyright": {"passed": bool, "summary": str, "missing": int, "total": int},
                },
                "findings": [...],
                "sandbox": str,
            }
    """
    path = Path(sandbox_path).resolve()

    # 1. Config
    config, auto_generated = _load_or_create_legal_config(path)
    config_result = {
        "passed": True,
        "summary": (
            "legal-config.json auto-generated (defaults applied)"
            if auto_generated
            else "legal-config.json present"
        ),
        "detail": str(path / "legal-config.json"),
        "auto_generated": auto_generated,
    }

    # 2. License scan
    license_result = _check_license_scan(path, config, verbose)

    # 3. SBOM
    sbom_result = _check_sbom(path, verbose)

    # 4. EULA
    eula_result = _check_eula(path, config, verbose)

    # 5. Privacy Policy
    privacy_result = _check_privacy_policy(path, config, verbose)

    # 6. Copyright (re-used from pre_commit)
    copyright_result = _check_copyright(path, verbose)

    # Score
    score, findings = _compute_legal_score(
        config_result,
        license_result,
        sbom_result,
        eula_result,
        privacy_result,
        copyright_result,
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
        "passed": passed,
        "score": score,
        "status": status,
        "checks": {
            "config": config_result,
            "license_scan": {
                "passed": license_result["passed"],
                "summary": license_result["summary"],
                "detail": license_result.get("detail", ""),
                "blocked_count": license_result.get("blocked_count", 0),
            },
            "sbom": {
                "passed": sbom_result["passed"],
                "summary": sbom_result["summary"],
                "detail": sbom_result.get("detail", ""),
            },
            "eula": {
                "passed": eula_result["passed"],
                "summary": eula_result["summary"],
                "detail": eula_result.get("detail", ""),
            },
            "privacy_policy": {
                "passed": privacy_result["passed"],
                "summary": privacy_result["summary"],
                "detail": privacy_result.get("detail", ""),
                "used_fallback": privacy_result.get("used_fallback", False),
            },
            "copyright": {
                "passed": copyright_result["passed"],
                "summary": copyright_result["summary"],
                "detail": copyright_result.get("detail", ""),
                "missing": copyright_result.get("missing", 0),
                "total": copyright_result.get("total", 0),
            },
        },
        "findings": findings,
    }


# ── Click command ───────────────────────────────────────────────────────


@click.command()
@click.option("--sandbox", required=True, help="Sandbox path or name.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed findings.")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
@click.option("--dry-run", is_flag=True, help="Show what would be generated without writing files.")
def legal(sandbox: str, verbose: bool, json_output: bool, dry_run: bool) -> None:
    """Run LEGAL checks and generate legal artifacts on a sandbox.

    Checks for license compliance, generates SBOM, EULA, and Privacy Policy,
    and verifies copyright headers.

    \b
    Scoring rubric:
        - Start at 100
        -15 if legal-config.json auto-generated
        -15 per blocked license found
        -20 if SBOM missing or invalid
        -20 if EULA not generated
        -15 if Privacy Policy not generated
        -5 if using fallback Privacy Policy template
        -2 per missing copyright header
        Floor at 0, pass >= 70, warn >= 50, fail < 50

    \b
    Generated artifacts (written to <sandbox>/legal/):
        EULA.md, PRIVACY.md, sbom.json

    Examples:

        hero legal --sandbox ~/Development/MyApp

        hero legal --sandbox MyApp --verbose

        hero legal --sandbox MyApp --dry-run

        hero legal --sandbox MyApp --json
    """
    sandbox_path = _resolve_sandbox(sandbox)

    if dry_run:
        click.echo(f"\nhero legal --sandbox {sandbox_path.name} (dry run)\n")
        project_type = _detect_project_type(sandbox_path)
        click.echo(f"  Project type: {project_type}")

        config_path = sandbox_path / "legal-config.json"
        if config_path.exists():
            click.echo(f"  {EMOJI_PASS} legal-config.json: exists")
        else:
            click.echo(f"  {EMOJI_WARN} legal-config.json: would be auto-generated with defaults")

        eula_template = _read_text_safe(EULA_TEMPLATE_PATH)
        if eula_template:
            click.echo(f"  {EMOJI_PASS} EULA template: found at {EULA_TEMPLATE_PATH}")
            click.echo(f"  {EMOJI_INFO} Would write: legal/EULA.md")
        else:
            click.echo(f"  {EMOJI_FAIL} EULA template: NOT found at {EULA_TEMPLATE_PATH}")

        click.echo(f"  {EMOJI_INFO} Would write: legal/PRIVACY.md")
        click.echo(f"  {EMOJI_INFO} Would write: legal/sbom.json")
        click.echo(f"  {EMOJI_INFO} Would check: copyright headers in lib/, src/, test/")
        click.echo("")
        click.echo("  No files written (dry run).")
        click.echo("")
        return

    result = run_legal(sandbox_path, verbose=verbose)

    # ── JSON output ──────────────────────────────────────────────────
    if json_output:
        import json as _json

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
    click.echo(f"\nhero legal --sandbox {sandbox_path.name}\n")

    checks = result["checks"]

    # Config line
    c = checks["config"]
    icon = EMOJI_WARN if c.get("auto_generated") else EMOJI_PASS
    click.echo(f"  {icon} Config:    {c['summary']}")

    # License scan line
    l = checks["license_scan"]
    if l["passed"]:
        icon = EMOJI_PASS
    elif l.get("blocked_count", 0) > 0:
        icon = EMOJI_FAIL
    else:
        icon = EMOJI_WARN
    click.echo(f"  {icon} Licenses:  {l['summary']}")

    # SBOM line
    s = checks["sbom"]
    icon = EMOJI_PASS if s["passed"] else EMOJI_FAIL
    click.echo(f"  {icon} SBOM:      {s['summary']}")

    # EULA line
    e = checks["eula"]
    icon = EMOJI_PASS if e["passed"] else EMOJI_FAIL
    click.echo(f"  {icon} EULA:      {e['summary']}")

    # Privacy Policy line
    p = checks["privacy_policy"]
    if p["passed"]:
        if p.get("used_fallback"):
            icon = EMOJI_WARN
        else:
            icon = EMOJI_PASS
    else:
        icon = EMOJI_FAIL
    click.echo(f"  {icon} Privacy:   {p['summary']}")

    # Copyright line
    cr = checks["copyright"]
    if cr["passed"]:
        icon = EMOJI_PASS
    elif cr.get("missing", 0) > 0:
        icon = EMOJI_WARN
    else:
        icon = EMOJI_FAIL
    click.echo(f"  {icon} Copyright: {cr['summary']}")

    # Verbose details
    if verbose:
        for check_key, label in [
            ("config", "Config"),
            ("license_scan", "License Scan"),
            ("sbom", "SBOM"),
            ("eula", "EULA"),
            ("privacy_policy", "Privacy Policy"),
            ("copyright", "Copyright"),
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
        click.echo(f"  {EMOJI_FAIL} {errors_count} error(s), {EMOJI_WARN} {warnings_count} warning(s)")

    click.echo("")
