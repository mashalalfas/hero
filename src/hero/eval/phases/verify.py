"""Phase 9: Verify — Re-run baseline to confirm fixes didn't break things."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from hero.eval.phases import BasePhase, PhaseResult, register_phase
from hero.eval.phases.baseline import BaselinePhase


@register_phase
class VerifyPhase(BasePhase):
    name = "verify"
    number = 9
    description = "Re-run baseline to confirm fixes didn't break anything"

    def run(self, project_path: Path, eval_dir: Path, context: dict[str, Any]) -> PhaseResult:
        start = time.time()
        report_dir = eval_dir / "phases"
        report_dir.mkdir(parents=True, exist_ok=True)

        # Get original baseline score
        baseline_file = report_dir / "baseline.json"
        original_score = 50
        if baseline_file.exists():
            try:
                orig = json.loads(baseline_file.read_text())
                original_score = orig.get("buildStatus", "unknown")
            except (json.JSONDecodeError, OSError):
                pass

        # Re-run baseline
        baseline = BaselinePhase()
        result = baseline.run(project_path, eval_dir / "re-verify", context)

        # Compare
        build_still_ok = result.details.get("buildStatus") in ("success", "unknown")
        tests_still_ok = result.details.get("testsPassed", True) or not result.details.get("testsFound", False)

        if build_still_ok and tests_still_ok:
            score = 90
            summary = "Build OK, tests OK — no regressions"
        elif build_still_ok:
            score = 70
            summary = "Build OK but tests failing"
        else:
            score = 40
            summary = "Build failing after fixes — regression detected"

        findings: list[dict[str, Any]] = []
        if not build_still_ok:
            findings.append({"severity": "critical", "title": "Build regression detected",
                             "detail": "Build was passing before fixes"})
        if not tests_still_ok:
            findings.append({"severity": "major", "title": "Test regression detected",
                             "detail": "Tests were passing before fixes"})

        report = {
            "buildStatus": result.details.get("buildStatus", "unknown"),
            "testsPassed": result.details.get("testsPassed", False),
            "regression": not (build_still_ok and tests_still_ok),
            "findings": findings,
        }
        (report_dir / "verify.json").write_text(json.dumps(report, indent=2))

        return PhaseResult(
            phase_name=self.name, phase_number=self.number,
            status="completed", score=score, findings=findings,
            summary=summary,
            duration_seconds=time.time() - start,
            details=report,
        )
