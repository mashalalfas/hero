"""Phase 1: Baseline — Run tests, lint, build to establish metrics."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from hero.eval.phases import BasePhase, PhaseResult, register_phase


@register_phase
class BaselinePhase(BasePhase):
    name = "baseline"
    number = 1
    description = "Run tests, lint, build to establish baseline metrics"

    def run(self, project_path: Path, eval_dir: Path, context: dict[str, Any]) -> PhaseResult:
        start = time.time()
        project_type = self._detect_project_type(project_path)
        report_dir = eval_dir / "phases"
        report_dir.mkdir(parents=True, exist_ok=True)

        results: dict[str, Any] = {
            "projectType": project_type,
            "buildStatus": "unknown",
            "testsFound": False,
            "testsPassed": False,
            "lintIssues": 0,
            "errors": 0,
            "warnings": 0,
        }

        if project_type == "unknown":
            results["buildStatus"] = "skipped"
            return PhaseResult(
                phase_name=self.name, phase_number=self.number,
                status="skipped", score=50,
                summary="Unknown project type — baseline skipped",
                duration_seconds=time.time() - start,
                details=results,
            )

        # Run project-type-specific commands
        if project_type == "flutter":
            results.update(self._run_flutter(project_path))
        elif project_type == "go":
            results.update(self._run_go(project_path))
        elif project_type == "node":
            results.update(self._run_node(project_path))
        elif project_type == "python":
            results.update(self._run_python(project_path))
        elif project_type == "rust":
            results.update(self._run_rust(project_path))

        # Calculate score
        score = 100
        findings: list[dict[str, Any]] = []

        if results["buildStatus"] == "failed":
            score -= 30
            findings.append({"severity": "major", "title": "Build failed", "detail": results.get("buildError", "")})
        elif results["buildStatus"] == "success":
            pass  # no deduction

        if results["testsFound"] and not results["testsPassed"]:
            score -= 25
            findings.append({"severity": "major", "title": "Tests failing", "detail": results.get("testError", "")})
        elif not results["testsFound"]:
            score -= 15
            findings.append({"severity": "minor", "title": "No tests found"})

        score -= min(results["errors"] * 3, 20)
        score -= min(results["warnings"], 10)
        score = max(0, min(100, score))

        # Save report
        report_path = report_dir / "baseline.json"
        report_path.write_text(json.dumps(results, indent=2))

        return PhaseResult(
            phase_name=self.name, phase_number=self.number,
            status="completed", score=score, findings=findings,
            summary=f"Build: {results['buildStatus']}, Tests: {'pass' if results['testsPassed'] else 'fail' if results['testsFound'] else 'none'}",
            duration_seconds=time.time() - start,
            details=results,
        )

    def _run_cmd(self, cmd: list[str], cwd: Path, timeout: int = 120) -> tuple[int, str, str]:
        """Run a command, return (exit_code, stdout, stderr)."""
        try:
            result = subprocess.run(
                cmd, cwd=str(cwd), capture_output=True, text=True,
                timeout=timeout, env={**dict(__import__("os").environ), "CI": "true"},
            )
            return result.returncode, result.stdout, result.stderr
        except FileNotFoundError:
            return -1, "", f"Command not found: {cmd[0]}"
        except subprocess.TimeoutExpired:
            return -2, "", f"Timed out after {timeout}s"

    def _run_flutter(self, path: Path) -> dict[str, Any]:
        r: dict[str, Any] = {"buildStatus": "unknown", "testsFound": False, "testsPassed": False, "lintIssues": 0, "errors": 0, "warnings": 0}

        # pub get
        code, _, _ = self._run_cmd(["flutter", "pub", "get"], path, 60)
        if code != 0:
            r["buildStatus"] = "failed"
            r["buildError"] = "flutter pub get failed"
            return r

        # analyze
        code, stdout, _ = self._run_cmd(["flutter", "analyze", "--no-pub"], path, 120)
        r["errors"] = stdout.lower().count(" error")
        r["warnings"] = stdout.lower().count(" warning")
        r["lintIssues"] = r["errors"] + r["warnings"]

        # test
        code, stdout, stderr = self._run_cmd(["flutter", "test", "--no-pub"], path, 120)
        r["testsFound"] = "0 tests" not in (stdout + stderr) and code != -1
        r["testsPassed"] = code == 0 and r["testsFound"]
        r["testError"] = stderr[:500] if code != 0 else ""
        if r["testsPassed"]:
            r["testOutput"] = stdout[:1000]

        r["buildStatus"] = "success" if r["errors"] == 0 else "failed"
        return r

    def _run_go(self, path: Path) -> dict[str, Any]:
        r: dict[str, Any] = {"buildStatus": "unknown", "testsFound": False, "testsPassed": False, "lintIssues": 0, "errors": 0, "warnings": 0}

        code, stdout, stderr = self._run_cmd(["go", "vet", "./..."], path, 120)
        r["errors"] = (stdout + stderr).lower().count("error")
        r["warnings"] = (stdout + stderr).lower().count("warning")

        code, stdout, stderr = self._run_cmd(["go", "test", "./...", "-count=1"], path, 120)
        r["testsFound"] = "no test files" not in (stdout + stderr)
        r["testsPassed"] = code == 0 and r["testsFound"]
        r["testError"] = stderr[:500] if code != 0 else ""

        r["buildStatus"] = "success" if r["errors"] == 0 else "failed"
        return r

    def _run_node(self, path: Path) -> dict[str, Any]:
        r: dict[str, Any] = {"buildStatus": "unknown", "testsFound": False, "testsPassed": False, "lintIssues": 0, "errors": 0, "warnings": 0}

        # Check for lock file
        has_lock = (path / "package-lock.json").exists() or (path / "yarn.lock").exists() or (path / "pnpm-lock.yaml").exists()
        if has_lock:
            self._run_cmd(["npm", "ci", "--ignore-scripts"], path, 120)

        # lint
        code, stdout, _ = self._run_cmd(["npx", "--yes", "eslint", ".", "--max-warnings=100"], path, 120)
        if code == -1:  # eslint not found
            code, stdout, _ = self._run_cmd(["npm", "run", "lint", "--if-present"], path, 120)
        r["errors"] = stdout.lower().count("error")
        r["warnings"] = stdout.lower().count("warning")
        r["lintIssues"] = r["errors"] + r["warnings"]

        # test
        code, stdout, stderr = self._run_cmd(["npm", "test", "--if-present"], path, 120)
        r["testsFound"] = code != -1 and "no test" not in (stdout + stderr).lower()
        r["testsPassed"] = code == 0 and r["testsFound"]
        r["testError"] = stderr[:500] if code != 0 else ""

        r["buildStatus"] = "success" if r["errors"] == 0 else "failed"
        return r

    def _run_python(self, path: Path) -> dict[str, Any]:
        r: dict[str, Any] = {"buildStatus": "unknown", "testsFound": False, "testsPassed": False, "lintIssues": 0, "errors": 0, "warnings": 0}

        # ruff check
        code, stdout, _ = self._run_cmd(["python", "-m", "ruff", "check", "."], path, 60)
        if code == -1:
            code, stdout, _ = self._run_cmd(["python", "-m", "flake8", "."], path, 60)
        r["errors"] = (stdout or "").count(": E")
        r["warnings"] = (stdout or "").count(": W")
        r["lintIssues"] = r["errors"] + r["warnings"]

        # pytest
        code, stdout, stderr = self._run_cmd(["python", "-m", "pytest", "--tb=short", "-q"], path, 120)
        r["testsFound"] = "no tests ran" not in (stdout + stderr).lower() and code != -1
        r["testsPassed"] = code == 0 and r["testsFound"]
        r["testError"] = stderr[:500] if code != 0 else ""

        r["buildStatus"] = "success" if r["errors"] == 0 else "failed"
        return r

    def _run_rust(self, path: Path) -> dict[str, Any]:
        r: dict[str, Any] = {"buildStatus": "unknown", "testsFound": False, "testsPassed": False, "lintIssues": 0, "errors": 0, "warnings": 0}

        code, stdout, stderr = self._run_cmd(["cargo", "check"], path, 180)
        output = stdout + stderr
        r["errors"] = output.count("error[")
        r["warnings"] = output.count("warning[")

        code, stdout, stderr = self._run_cmd(["cargo", "test"], path, 180)
        r["testsFound"] = "0 passed" not in (stdout + stderr) and code != -1
        r["testsPassed"] = code == 0 and r["testsFound"]
        r["testError"] = stderr[:500] if code != 0 else ""

        r["buildStatus"] = "success" if r["errors"] == 0 else "failed"
        return r
