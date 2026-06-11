"""hero archive — Run ARCHIVE stage on a sandbox.

ARCHIVE is the final pipeline stage. It collects build artifacts, SBOM,
legal documents, writes a structured journal entry, and consolidates
findings into the sandbox memory file.

Part of the HERO pipeline: PRE-COMMIT → BUILD → HARDEN → LEGAL → CI/PR → VERIFY → ARCHIVE
"""

from __future__ import annotations

import json as _json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import click

from hero.archivist.inline import _ensure_herolog, _append
from hero.commands.check import EMOJI_PASS, EMOJI_WARN, EMOJI_FAIL, EMOJI_INFO
from hero.commands.pre_commit import (
    _detect_project_type,
    _resolve_sandbox,
)

# ── Helpers ──────────────────────────────────────────────────────────────


def _ensure_archive_dir(sandbox_path: Path) -> Path:
    """Create sandbox_path/archive/ dir, return path."""
    archive_dir = sandbox_path / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    return archive_dir


def _collect_build_artifacts(sandbox_path: Path, project_type: str) -> dict[str, Any]:
    """Find build/ or dist/ output, copy files into archive/.

    Returns dict with: passed, summary, files, file_count, archive_size_bytes
    """
    archive_dir = _ensure_archive_dir(sandbox_path)
    build_archive_dir = archive_dir / "build"
    build_archive_dir.mkdir(parents=True, exist_ok=True)

    candidates: list[Path] = []
    if project_type == "flutter":
        candidates = [sandbox_path / "build"]
    elif project_type == "node":
        candidates = [sandbox_path / "dist", sandbox_path / "build"]
    elif project_type == "python":
        candidates = [sandbox_path / "dist", sandbox_path / "build"]
    elif project_type == "rust":
        candidates = [sandbox_path / "target" / "release", sandbox_path / "target" / "debug"]
    else:
        # General: try common output dirs
        candidates = [
            sandbox_path / "build",
            sandbox_path / "dist",
            sandbox_path / "target",
            sandbox_path / "output",
        ]

    collected_files: list[str] = []
    total_size = 0

    for src_dir in candidates:
        if src_dir.exists() and src_dir.is_dir():
            try:
                for f in src_dir.rglob("*"):
                    if f.is_file():
                        rel = f.relative_to(src_dir)
                        dest = build_archive_dir / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            shutil.copy2(f, dest)
                            collected_files.append(str(rel))
                            total_size += f.stat().st_size
                        except (OSError, shutil.Error):
                            pass
            except OSError:
                pass

    file_count = len(collected_files)
    if file_count > 0:
        return {
            "passed": True,
            "summary": f"{file_count} file(s) in archive/build/",
            "files": collected_files[:20],
            "file_count": file_count,
            "archive_size_bytes": total_size,
        }

    dir_names = ", ".join(d.name + "/" for d in candidates) if candidates else "build/ or dist/"
    return {
        "passed": False,
        "summary": f"{dir_names} not found (nothing to archive)",
        "files": [],
        "file_count": 0,
        "archive_size_bytes": 0,
    }


def _collect_sbom(sandbox_path: Path) -> dict[str, Any]:
    """Find SBOM files and copy to archive/.

    Returns dict with: passed, summary, files, sbom_path
    """
    archive_dir = _ensure_archive_dir(sandbox_path)
    sbom_archive_dir = archive_dir / "sbom"
    sbom_archive_dir.mkdir(parents=True, exist_ok=True)

    # Look for *.sbom*, SBOM*, cyclonedx*, spdx* patterns
    sbom_patterns = [
        "*.sbom*", "**/*.sbom*", "SBOM*", "**/SBOM*",
        "*cyclonedx*", "**/*cyclonedx*",
        "*spdx*", "**/*spdx*",
    ]

    sbom_files: list[Path] = []
    for pattern in sbom_patterns:
        sbom_files.extend(sandbox_path.glob(pattern))

    # Deduplicate
    seen = set()
    unique_sbom: list[Path] = []
    for f in sbom_files:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_sbom.append(f)

    copied: list[str] = []
    sbom_path: str | None = None

    for f in unique_sbom:
        try:
            dest = sbom_archive_dir / f.name
            shutil.copy2(f, dest)
            copied.append(f.name)
            if sbom_path is None:
                sbom_path = str(dest)
        except (OSError, shutil.Error):
            pass

    if copied:
        return {
            "passed": True,
            "summary": f"{len(copied)} SBOM file(s) archived",
            "files": copied[:10],
            "sbom_path": sbom_path,
        }

    return {
        "passed": False,
        "summary": "not found (skipped)",
        "files": [],
        "sbom_path": None,
    }


def _collect_legal_docs(sandbox_path: Path) -> dict[str, Any]:
    """Find legal/ license documents and copy to archive/.

    Returns dict with: passed, summary, files
    """
    archive_dir = _ensure_archive_dir(sandbox_path)
    legal_archive_dir = archive_dir / "legal"
    legal_archive_dir.mkdir(parents=True, exist_ok=True)

    legal_patterns = [
        "EULA.md", "EULA.txt", "**/EULA.md", "**/EULA.txt",
        "PRIVACY.md", "PRIVACY.txt", "**/PRIVACY.md", "**/PRIVACY.txt",
        "legal-config.json", "**/legal-config.json",
        "LICENSE*", "**/LICENSE*",
        "NOTICE*", "**/NOTICE*",
        "THIRD_PARTY*", "**/THIRD_PARTY*",
        "legal/*", "**/legal/*",
    ]

    legal_files: list[Path] = []
    for pattern in legal_patterns:
        legal_files.extend(sandbox_path.glob(pattern))

    # Deduplicate and keep only actual files
    seen = set()
    unique_legal: list[Path] = []
    for f in legal_files:
        if not f.is_file():
            continue
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_legal.append(f)

    copied: list[str] = []
    for f in unique_legal:
        try:
            dest = legal_archive_dir / f.name
            shutil.copy2(f, dest)
            copied.append(f.name)
        except (OSError, shutil.Error):
            pass

    if copied:
        return {
            "passed": True,
            "summary": f"{len(copied)} file(s) in archive/legal/",
            "files": copied[:15],
        }

    return {
        "passed": False,
        "summary": "not found (skipped)",
        "files": [],
    }


def _write_journal(sandbox_path: Path, pipeline_id: str, task: str,
                   stage_scores: dict[str, Any]) -> dict[str, Any]:
    """Write or update journal.md in archive/ with structured entry.

    Reuses hero/archivist/inline._ensure_herolog() and _append().

    Returns dict with: passed, summary, journal_path
    """
    archive_dir = _ensure_archive_dir(sandbox_path)
    journal_path = archive_dir / "journal.md"

    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry_lines = [
            f"\n## ARCHIVE — {timestamp}\n",
            f"\n**Pipeline:** {pipeline_id or 'standalone'}",
            f"\n**Task:** {task}",
            f"\n**Timestamp:** {timestamp}\n",
            "\n### Stage Scores\n",
        ]

        if stage_scores:
            for stage_name, stage_data in stage_scores.items():
                score = stage_data.get("score", 0)
                status = stage_data.get("status", "unknown")
                details = stage_data.get("details", "")
                entry_lines.append(
                    f"- **{stage_name}**: {score}/100 ({status}) — {details}"
                )
        else:
            entry_lines.append("- (no stage scores provided)")

        entry_lines.append("\n")

        _ensure_herolog(journal_path)
        entry = "\n".join(entry_lines)
        _append(journal_path, entry)

        return {
            "passed": True,
            "summary": "journal.md written to archive/",
            "journal_path": str(journal_path),
        }
    except OSError as e:
        return {
            "passed": False,
            "summary": f"journal write failed: {e}",
            "journal_path": "",
        }


def _consolidate_memory(sandbox_path: Path, journal_path: str) -> dict[str, Any]:
    """Append journal content to sandbox memory file (memory/YYYY-MM-DD.md).

    Reuses the consolidation logic from go.py's _consolidate_journal().

    Returns dict with: passed, summary, memory_file
    """
    jp = Path(journal_path)
    if not jp.exists():
        return {
            "passed": False,
            "summary": "journal not found — nothing to consolidate",
            "memory_file": "",
        }

    journal_content = jp.read_text()
    if not journal_content.strip():
        return {
            "passed": False,
            "summary": "journal is empty — nothing to consolidate",
            "memory_file": "",
        }

    try:
        today = datetime.now().strftime("%Y-%m-%d")
        memory_dir = sandbox_path / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        memory_file = memory_dir / f"{today}.md"

        header = f"\n# ARCHIVE Consolidation — {today}\n\n"

        if memory_file.exists():
            existing = memory_file.read_text()
            if header not in existing:
                memory_file.write_text(existing + header + journal_content)
        else:
            memory_file.write_text(header + journal_content)

        return {
            "passed": True,
            "summary": f"consolidated to {memory_file.name}",
            "memory_file": str(memory_file),
        }
    except OSError as e:
        return {
            "passed": False,
            "summary": f"memory consolidation failed: {e}",
            "memory_file": "",
        }


# ── Scoring ─────────────────────────────────────────────────────────────


def _compute_archive_score(
    build_artifacts_check: dict[str, Any],
    sbom_check: dict[str, Any],
    legal_check: dict[str, Any],
    journal_check: dict[str, Any],
    memory_check: dict[str, Any],
) -> tuple[int, list[dict[str, str]]]:
    """Compute final ARCHIVE score (0-100) and list of findings.

    Scoring rubric:
        Start at 100
        -20 if no build artifacts found to archive
        -20 if no SBOM found
        -15 if no legal docs found
        -15 if journal write failed
        -10 if memory consolidation failed
        Floor at 0
    """
    score = 100
    findings: list[dict[str, str]] = []

    # Build artifacts
    if not build_artifacts_check["passed"]:
        score = max(0, score - 20)
        findings.append({
            "severity": "warning",
            "check": "build_artifacts",
            "message": f"No build artifacts to archive: {build_artifacts_check['summary']} (-20)",
        })

    # SBOM
    if not sbom_check["passed"]:
        score = max(0, score - 20)
        findings.append({
            "severity": "warning",
            "check": "sbom",
            "message": f"SBOM not found: {sbom_check['summary']} (-20)",
        })

    # Legal docs
    if not legal_check["passed"]:
        score = max(0, score - 15)
        findings.append({
            "severity": "warning",
            "check": "legal_docs",
            "message": f"Legal docs not found: {legal_check['summary']} (-15)",
        })

    # Journal write
    if not journal_check["passed"]:
        score = max(0, score - 15)
        findings.append({
            "severity": "error",
            "check": "journal",
            "message": f"Journal write failed: {journal_check['summary']} (-15)",
        })

    # Memory consolidation
    if not memory_check["passed"]:
        score = max(0, score - 10)
        findings.append({
            "severity": "error",
            "check": "memory_consolidation",
            "message": f"Memory consolidation failed: {memory_check['summary']} (-10)",
        })

    return score, findings


# ── Main API ────────────────────────────────────────────────────────────


def run_archive(sandbox_path: str | Path, verbose: bool = False,
                pipeline_id: str | None = None,
                task: str = "",
                stage_scores: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run all ARCHIVE checks and return structured results.

    Parameters
    ----------
    sandbox_path : str or Path
        Path to the sandbox/project directory.
    verbose : bool, default=False
        Include detailed output in each check result.
    pipeline_id : str or None, default=None
        Pipeline identifier for journal entry.
    task : str, default=""
        Task description for journal entry.
    stage_scores : dict or None, default=None
        Scores from earlier pipeline stages to include in journal.

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
                "checks": {
                    "build_artifacts": {...},
                    "sbom": {...},
                    "legal_docs": {...},
                    "journal": {...},
                    "memory_consolidation": {...},
                },
                "findings": [...],
            }
    """
    path = Path(sandbox_path).resolve()
    project_type = _detect_project_type(path)

    # 1. Collect build artifacts
    build_artifacts_check = _collect_build_artifacts(path, project_type)

    # 2. Collect SBOM
    sbom_check = _collect_sbom(path)

    # 3. Collect legal docs
    legal_check = _collect_legal_docs(path)

    # 4. Write journal
    journal_check = _write_journal(path, pipeline_id or "", task, stage_scores or {})

    # 5. Consolidate memory
    journal_path = journal_check.get("journal_path", "")
    memory_check = _consolidate_memory(path, journal_path)

    score, findings = _compute_archive_score(
        build_artifacts_check,
        sbom_check,
        legal_check,
        journal_check,
        memory_check,
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
            "build_artifacts": {
                "passed": build_artifacts_check["passed"],
                "summary": build_artifacts_check["summary"],
                "detail": "",
                "file_count": build_artifacts_check.get("file_count", 0),
                "archive_size_bytes": build_artifacts_check.get("archive_size_bytes", 0),
            },
            "sbom": {
                "passed": sbom_check["passed"],
                "summary": sbom_check["summary"],
                "detail": "",
            },
            "legal_docs": {
                "passed": legal_check["passed"],
                "summary": legal_check["summary"],
                "detail": "",
            },
            "journal": {
                "passed": journal_check["passed"],
                "summary": journal_check["summary"],
                "detail": "",
            },
            "memory_consolidation": {
                "passed": memory_check["passed"],
                "summary": memory_check["summary"],
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
@click.option("--dry-run", is_flag=True, help="Show what would be archived without collecting.")
@click.option("--pipeline-id", type=str, default=None,
              help="Pipeline identifier (auto-generated if not set).")
def archive(sandbox: str, verbose: bool, json_output: bool, dry_run: bool,
            pipeline_id: str | None) -> None:
    """Run ARCHIVE stage on a sandbox.

    Collects build artifacts, SBOM, legal documents, writes a structured
    journal entry, and consolidates findings into the sandbox memory file.

    \b
    Scoring rubric:
        Start at 100
        -20 if no build artifacts found to archive
        -20 if no SBOM found
        -15 if no legal docs found
        -15 if journal write failed
        -10 if memory consolidation failed
        Floor at 0, pass >= 70, warn >= 50, fail < 50

    \b
    Examples:

        hero archive --sandbox ~/Development/MyApp

        hero archive --sandbox HERO --verbose

        hero archive --sandbox MyApp --dry-run

        hero archive --sandbox MyApp --json

        hero archive --sandbox HERO --pipeline-id my-pipeline-001
    """
    sandbox_path = _resolve_sandbox(sandbox)
    project_type = _detect_project_type(sandbox_path)

    # Auto-generate pipeline ID if not set
    if pipeline_id is None:
        pipeline_id = f"{sandbox_path.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # ── Dry-run mode ─────────────────────────────────────────────────
    if dry_run:
        click.echo(f"\nhero archive --sandbox {sandbox_path.name} (dry run)\n")
        click.echo(f"  Project type: {project_type}")
        click.echo(f"  Pipeline ID:  {pipeline_id}")
        click.echo("")
        click.echo(f"  {EMOJI_INFO} Would collect: build artifacts from build/ or dist/")
        click.echo(f"  {EMOJI_INFO} Would collect: SBOM files (*.sbom*, SBOM*, cyclonedx*, spdx*)")
        click.echo(f"  {EMOJI_INFO} Would collect: legal docs (EULA, PRIVACY, LICENSE, legal-config)")
        click.echo(f"  {EMOJI_INFO} Would write:   journal.md in archive/")
        click.echo(f"  {EMOJI_INFO} Would consolidate: journal → memory/YYYY-MM-DD.md")
        click.echo(f"\n  No archive operations executed (dry run).")
        click.echo("")
        return

    # ── Run archive checks ───────────────────────────────────────────
    result = run_archive(sandbox_path, verbose=verbose,
                         pipeline_id=pipeline_id, task="")

    # ── JSON output ──────────────────────────────────────────────────
    if json_output:
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
    click.echo(f"\nhero archive --sandbox {sandbox_path.name}\n")

    checks = result["checks"]

    # Build artifacts line
    ba = checks["build_artifacts"]
    icon = EMOJI_PASS if ba["passed"] else EMOJI_INFO
    click.echo(f"  {icon} Build artifacts    {ba['summary']}")

    # SBOM line
    sb = checks["sbom"]
    if sb["passed"]:
        icon = EMOJI_PASS
    elif "skipped" in sb["summary"].lower() or "not found" in sb["summary"].lower():
        icon = EMOJI_INFO
    else:
        icon = EMOJI_WARN
    click.echo(f"  {icon} SBOM               {sb['summary']}")

    # Legal docs line
    ld = checks["legal_docs"]
    if ld["passed"]:
        icon = EMOJI_PASS
    elif "skipped" in ld["summary"].lower() or "not found" in ld["summary"].lower():
        icon = EMOJI_INFO
    else:
        icon = EMOJI_WARN
    click.echo(f"  {icon} Legal docs         {ld['summary']}")

    # Journal line
    j = checks["journal"]
    icon = EMOJI_PASS if j["passed"] else EMOJI_FAIL
    click.echo(f"  {icon} Journal            {j['summary']}")

    # Memory consolidation line
    mc = checks["memory_consolidation"]
    icon = EMOJI_PASS if mc["passed"] else EMOJI_FAIL
    click.echo(f"  {icon} Memory consolidated {mc['summary']}")

    # Verbose details
    if verbose:
        for check_key, label in [
            ("build_artifacts", "Build artifacts"),
            ("sbom", "SBOM"),
            ("legal_docs", "Legal docs"),
            ("journal", "Journal"),
            ("memory_consolidation", "Memory consolidation"),
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
        error_count = sum(1 for f in result["findings"] if f["severity"] == "error")
        warning_count = sum(1 for f in result["findings"] if f["severity"] == "warning")
        parts = []
        if error_count:
            parts.append(f"{EMOJI_FAIL} {error_count} error(s)")
        if warning_count:
            parts.append(f"{EMOJI_WARN} {warning_count} warning(s)")
        click.echo(f"  {' '.join(parts)}")

    click.echo("")
