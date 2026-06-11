"""Phase 5: TDD — Test coverage analysis and critical path identification.

Tuned: only counts real coverage data, skips test files from source count,
properly runs coverage tools.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from hero.eval.phases import BasePhase, PhaseResult, register_phase


@register_phase
class TddPhase(BasePhase):
    name = "tdd"
    number = 5
    description = "Test coverage analysis and critical path identification"

    def run(self, project_path: Path, eval_dir: Path, context: dict[str, Any]) -> PhaseResult:
        start = time.time()
        report_dir = eval_dir / "phases"
        report_dir.mkdir(parents=True, exist_ok=True)
        project_type = self._detect_project_type(project_path)

        coverage: dict[str, float] = {"lines": 0.0, "functions": 0.0, "branches": 0.0}
        uncovered_critical: list[str] = []
        test_files_count = 0
        source_files_count = 0

        # Count test files and source files
        test_dirs = {"test", "tests", "__tests__", "spec", "specs"}
        test_suffixes = {"_test.dart", "_test.py", ".test.js", ".test.ts", ".spec.js", ".spec.ts"}
        test_prefixes = ("test_",)

        skip = {"node_modules", ".git", "build", "dist", "target", ".venv", "__pycache__",
                ".dart_tool", "vendor", "ephemeral", ".plugin_symlinks"}

        for f in project_path.rglob("*"):
            if not f.is_file():
                continue
            if any(s in f.parts for s in skip):
                continue

            is_test = (
                any(d in f.parts for d in test_dirs)
                or any(f.name.endswith(s) for s in test_suffixes)
                or any(f.name.startswith(p) for p in test_prefixes)
                or f.name.endswith("_test.go")
            )

            if is_test:
                test_files_count += 1
            elif f.suffix in {".dart", ".go", ".js", ".ts", ".py", ".rs", ".java"}:
                source_files_count += 1

        # Run coverage tools
        if project_type == "flutter":
            coverage, uncovered_critical = self._flutter_coverage(project_path)
        elif project_type == "go":
            coverage, uncovered_critical = self._go_coverage(project_path)
        elif project_type == "node":
            coverage, uncovered_critical = self._node_coverage(project_path)
        elif project_type == "python":
            coverage, uncovered_critical = self._python_coverage(project_path)

        # Identify critical paths with no tests
        if test_files_count == 0 and source_files_count > 0:
            for f in project_path.rglob("*"):
                if not f.is_file():
                    continue
                if any(s in f.parts for s in skip):
                    continue
                if f.suffix in {".dart", ".go", ".js", ".ts", ".py"} and "test" not in f.parts:
                    uncovered_critical.append(str(f.relative_to(project_path)))
                    if len(uncovered_critical) >= 10:
                        break

        # Score — only penalize if we have evidence
        avg_coverage = (coverage["lines"] + coverage["functions"] + coverage["branches"]) / 3

        if avg_coverage > 0:
            # We have real coverage data
            score = int(avg_coverage)
        elif test_files_count > 0:
            # Tests exist but no coverage data — partial credit
            test_ratio = test_files_count / max(source_files_count, 1)
            score = min(70, int(test_ratio * 100))  # cap at 70 without coverage data
        else:
            # No tests at all
            score = 10

        findings: list[dict[str, Any]] = []

        if test_files_count == 0:
            findings.append({"severity": "major", "title": "No test files found",
                             "detail": f"Found {source_files_count} source files, 0 test files"})
        elif avg_coverage > 0 and avg_coverage < 50:
            findings.append({"severity": "major", "title": f"Low test coverage: {avg_coverage:.0f}%",
                             "detail": f"lines={coverage['lines']:.0f}%, functions={coverage['functions']:.0f}%, branches={coverage['branches']:.0f}%"})

        if uncovered_critical:
            findings.append({"severity": "minor", "title": f"{len(uncovered_critical)} uncovered critical paths",
                             "detail": ", ".join(uncovered_critical[:5])})

        report = {
            "projectType": project_type,
            "coverage": coverage,
            "testFiles": test_files_count,
            "sourceFiles": source_files_count,
            "uncoveredCriticalPaths": uncovered_critical[:20],
            "findings": findings,
        }
        (report_dir / "tdd.json").write_text(json.dumps(report, indent=2))

        return PhaseResult(
            phase_name=self.name, phase_number=self.number,
            status="completed", score=score, findings=findings,
            summary=f"Coverage: {avg_coverage:.0f}%, Tests: {test_files_count}, Sources: {source_files_count}",
            duration_seconds=time.time() - start,
            details=report,
        )

    def _flutter_coverage(self, path: Path) -> tuple[dict[str, float], list[str]]:
        cov: dict[str, float] = {"lines": 0.0, "functions": 0.0, "branches": 0.0}
        uncovered: list[str] = []
        try:
            result = subprocess.run(
                ["flutter", "test", "--coverage", "--no-pub"], cwd=str(path),
                capture_output=True, text=True, timeout=180,
            )
            lcov = path / "coverage" / "lcov.info"
            if lcov.exists():
                content = lcov.read_text()
                total = content.count("DA:")
                covered = len(re.findall(r"DA:\d+,[1-9]", content))
                val = (covered / total * 100) if total > 0 else 0.0
                cov["lines"] = val
                cov["functions"] = val
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return cov, uncovered

    def _go_coverage(self, path: Path) -> tuple[dict[str, float], list[str]]:
        cov: dict[str, float] = {"lines": 0.0, "functions": 0.0, "branches": 0.0}
        uncovered: list[str] = []
        try:
            result = subprocess.run(
                ["go", "test", "./...", "-coverprofile=/tmp/go-coverage.out"],
                cwd=str(path), capture_output=True, text=True, timeout=180,
            )
            match = re.search(r"total:\s+\(statements\)\s+(\d+\.\d+)%", result.stdout)
            if match:
                val = float(match.group(1))
                cov["lines"] = val
                cov["functions"] = val
            Path("/tmp/go-coverage.out").unlink(missing_ok=True)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return cov, uncovered

    def _node_coverage(self, path: Path) -> tuple[dict[str, float], list[str]]:
        cov: dict[str, float] = {"lines": 0.0, "functions": 0.0, "branches": 0.0}
        uncovered: list[str] = []
        try:
            subprocess.run(
                ["npx", "--yes", "jest", "--coverage", "--silent"],
                cwd=str(path), capture_output=True, text=True, timeout=180,
            )
            cov_file = path / "coverage" / "coverage-summary.json"
            if cov_file.exists():
                data = json.loads(cov_file.read_text())
                cov["lines"] = float(data.get("total", {}).get("lines", {}).get("pct", 0))
                cov["functions"] = float(data.get("total", {}).get("functions", {}).get("pct", 0))
                cov["branches"] = float(data.get("total", {}).get("branches", {}).get("pct", 0))
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            pass
        return cov, uncovered

    def _python_coverage(self, path: Path) -> tuple[dict[str, float], list[str]]:
        cov: dict[str, float] = {"lines": 0.0, "functions": 0.0, "branches": 0.0}
        uncovered: list[str] = []
        try:
            subprocess.run(
                ["python", "-m", "pytest", "--cov=.", "--cov-report=json", "-q"],
                cwd=str(path), capture_output=True, text=True, timeout=180,
            )
            cov_file = path / "coverage.json"
            if cov_file.exists():
                data = json.loads(cov_file.read_text())
                val = float(data.get("totals", {}).get("percent_covered", 0))
                cov["lines"] = val
                cov["functions"] = val
                cov["branches"] = val
                cov_file.unlink(missing_ok=True)
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            pass
        return cov, uncovered
