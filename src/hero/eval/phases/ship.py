"""Phase 10: Ship — Package launch bundle and final readiness check."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from hero.eval.phases import BasePhase, PhaseResult, register_phase


@register_phase
class ShipPhase(BasePhase):
    name = "ship"
    number = 10
    description = "Package launch bundle and final readiness assessment"

    def run(self, project_path: Path, eval_dir: Path, context: dict[str, Any]) -> PhaseResult:
        start = time.time()
        report_dir = eval_dir / "phases"
        report_dir.mkdir(parents=True, exist_ok=True)

        findings: list[dict[str, Any]] = []

        # Check for readiness indicators
        checks = {
            "has_readme": (project_path / "README.md").exists() or (project_path / "readme.md").exists(),
            "has_license": any((project_path / lic).exists() for lic in ["LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE"]),
            "has_changelog": any((project_path / cl).exists() for cl in ["CHANGELOG.md", "CHANGELOG", "CHANGES.md", "HISTORY.md"]),
            "has_gitignore": (project_path / ".gitignore").exists(),
            "git_clean": self._check_git_clean(project_path),
            "no_secrets_in_git": self._check_git_secrets(project_path),
        }

        failed_checks = [k for k, v in checks.items() if not v]

        if not checks["has_readme"]:
            findings.append({"severity": "major", "title": "No README.md found"})
        if not checks["has_license"]:
            findings.append({"severity": "minor", "title": "No LICENSE file found"})
        if not checks["has_changelog"]:
            findings.append({"severity": "nit", "title": "No CHANGELOG found"})
        if not checks["git_clean"]:
            findings.append({"severity": "minor", "title": "Uncommitted changes in git"})
        if not checks["no_secrets_in_git"]:
            findings.append({"severity": "critical", "title": "Potential secrets in git history"})

        # Score
        score = 100
        score -= len([f for f in findings if f["severity"] == "critical"]) * 25
        score -= len([f for f in findings if f["severity"] == "major"]) * 10
        score -= len([f for f in findings if f["severity"] == "minor"]) * 5
        score -= len([f for f in findings if f["severity"] == "nit"]) * 2
        score = max(0, min(100, score))

        report = {
            "checks": checks,
            "failedChecks": failed_checks,
            "findings": findings,
        }
        (report_dir / "ship.json").write_text(json.dumps(report, indent=2))

        return PhaseResult(
            phase_name=self.name, phase_number=self.number,
            status="completed", score=score, findings=findings,
            summary=f"Checks passed: {len(checks) - len(failed_checks)}/{len(checks)}",
            duration_seconds=time.time() - start,
            details=report,
        )

    def _check_git_clean(self, path: Path) -> bool:
        """Check if git working directory is clean."""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"], cwd=str(path),
                capture_output=True, text=True, timeout=10,
            )
            return result.stdout.strip() == ""
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return True  # not a git repo or git not available

    def _check_git_secrets(self, path: Path) -> bool:
        """Check for potential secrets in git diff (staged changes)."""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "diff", "--cached"], cwd=str(path),
                capture_output=True, text=True, timeout=10,
            )
            import re
            secret_pattern = r'(?:password|secret|api_key|token|credential)\s*[=:]\s*["\'][^"\']{8,}'
            return not re.search(secret_pattern, result.stdout, re.IGNORECASE)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return True
