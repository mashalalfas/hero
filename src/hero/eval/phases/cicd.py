"""Phase 4: CI/CD — Generate CI/CD pipeline configuration."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from hero.eval.phases import BasePhase, PhaseResult, register_phase


@register_phase
class CicdPhase(BasePhase):
    name = "cicd"
    number = 4
    description = "CI/CD pipeline generation and analysis"

    def run(self, project_path: Path, eval_dir: Path, context: dict[str, Any]) -> PhaseResult:
        start = time.time()
        report_dir = eval_dir / "phases"
        report_dir.mkdir(parents=True, exist_ok=True)
        project_type = self._detect_project_type(project_path)

        findings: list[dict[str, Any]] = []
        has_ci = False
        ci_provider = "none"

        # Check for existing CI configs
        ci_paths = [
            (".github/workflows", "GitHub Actions"),
            (".gitlab-ci.yml", "GitLab CI"),
            ("Jenkinsfile", "Jenkins"),
            (".circleci/config.yml", "CircleCI"),
            (".travis.yml", "Travis CI"),
            ("bitbucket-pipelines.yml", "Bitbucket Pipelines"),
        ]

        for ci_path, provider in ci_paths:
            full = project_path / ci_path
            if full.exists():
                has_ci = True
                ci_provider = provider
                break

        if not has_ci:
            findings.append({"severity": "major", "title": "No CI/CD pipeline found",
                             "detail": f"Consider adding {self._suggest_ci(project_type)}"})

        # Check for test automation
        has_test_config = False
        test_markers = ["jest.config", "pytest.ini", "setup.cfg", ".mocharc", "phpunit.xml"]
        for marker in test_markers:
            if list(project_path.glob(f"*{marker}*")):
                has_test_config = True
                break

        if not has_test_config and project_type != "unknown":
            findings.append({"severity": "minor", "title": "No test runner config found"})

        # Score
        score = 100
        if not has_ci:
            score -= 30
        if not has_test_config:
            score -= 15
        score = max(0, min(100, score))

        report = {
            "hasCI": has_ci,
            "ciProvider": ci_provider,
            "hasTestConfig": has_test_config,
            "projectType": project_type,
            "findings": findings,
        }
        (report_dir / "cicd.json").write_text(json.dumps(report, indent=2))

        return PhaseResult(
            phase_name=self.name, phase_number=self.number,
            status="completed", score=score, findings=findings,
            summary=f"CI: {'yes' if has_ci else 'no'} ({ci_provider}), Tests: {'configured' if has_test_config else 'not configured'}",
            duration_seconds=time.time() - start,
            details=report,
        )

    def _suggest_ci(self, project_type: str) -> str:
        suggestions = {
            "flutter": "GitHub Actions workflow with flutter test + flutter build",
            "go": "GitHub Actions with go test + go build",
            "node": "GitHub Actions with npm test + npm build",
            "python": "GitHub Actions with pytest + ruff check",
            "rust": "GitHub Actions with cargo test + cargo build",
        }
        return suggestions.get(project_type, "GitHub Actions workflow")
