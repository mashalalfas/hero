"""EvalEngine — Pipeline orchestrator for the HERO evaluation system."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from hero.eval.phases import PHASES, BasePhase, PhaseResult
from hero.eval.scorer import Scorer, Scorecard
from hero.eval.report import ReportGenerator

# Import all phases to trigger registration
from hero.eval.phases import baseline, security, code_review, cicd  # noqa: F401
from hero.eval.phases import tdd, performance, accessibility, fix  # noqa: F401
from hero.eval.phases import verify, ship  # noqa: F401

EVAL_HOME = Path.home() / ".hero" / "evals"


class EvalEngine:
    """Orchestrates the full evaluation pipeline.

    Usage:
        engine = EvalEngine("sook-pro", Path("/path/to/project"))
        card = engine.run()                    # all phases
        card = engine.run(phases=[2, 3])       # security + code-review only
        card = engine.run(fix=True)            # run fix phase after eval
    """

    def __init__(self, sandbox_name: str, project_path: Path):
        self.sandbox_name = sandbox_name
        self.project_path = project_path
        self.eval_dir = EVAL_HOME / sandbox_name
        self.scorer = Scorer(sandbox_name)
        self.context: dict[str, Any] = {}

    def run(
        self,
        phases: list[int] | None = None,
        fix_after: bool = False,
        score_only: bool = False,
    ) -> Scorecard:
        """Run the evaluation pipeline.

        Args:
            phases: Specific phase numbers to run (None = all).
            fix_after: Run the fix phase after all other phases.
            score_only: Skip execution, just compute score from existing reports.

        Returns:
            Scorecard with overall score and band.
        """
        start = time.time()

        # Ensure eval directory exists
        self.eval_dir.mkdir(parents=True, exist_ok=True)
        phases_dir = self.eval_dir / "phases"
        phases_dir.mkdir(parents=True, exist_ok=True)

        # Determine which phases to run
        if phases:
            phase_nums = phases
        else:
            phase_nums = sorted(PHASES.keys())

        # Remove fix (8) from auto-run — it's opt-in
        if 8 in phase_nums and not fix_after:
            phase_nums.remove(8)

        # Run phases
        for phase_num in phase_nums:
            phase_cls = PHASES.get(phase_num)
            if not phase_cls:
                continue

            phase: BasePhase = phase_cls()
            result = phase.run(self.project_path, self.eval_dir, self.context)
            self.scorer.add_result(result)

            # Store result in context for dependent phases
            self.context[phase.name] = result.details

        # Run fix phase if requested
        if fix_after and 8 in PHASES:
            fix_phase = PHASES[8]()
            fix_result = fix_phase.run(self.project_path, self.eval_dir, self.context)
            self.scorer.add_result(fix_result)

        # Compute scorecard
        card = self.scorer.compute()
        card.duration_seconds = time.time() - start

        # Generate reports
        reporter = ReportGenerator(self.eval_dir)
        reporter.generate(card)

        return card

    def get_existing_scorecard(self) -> Scorecard | None:
        """Load an existing scorecard from disk."""
        scorecard_file = self.eval_dir / "SCORECARD.json"
        if not scorecard_file.exists():
            return None

        import json
        try:
            data = json.loads(scorecard_file.read_text())
            card = Scorecard(
                sandbox_name=data.get("sandbox", self.sandbox_name),
                overall=data.get("overall", 0),
                band=data.get("band", "not-ready"),
                total_critical=data.get("summary", {}).get("critical", 0),
                total_major=data.get("summary", {}).get("major", 0),
                total_minor=data.get("summary", {}).get("minor", 0),
                total_nit=data.get("summary", {}).get("nit", 0),
                total_findings=data.get("summary", {}).get("totalFindings", 0),
                duration_seconds=data.get("durationSeconds", 0),
            )
            # Reconstruct band emoji
            for (low, high), (band, emoji) in [
                ((80, 101), ("production-ready", "🟢")),
                ((60, 80), ("ship-with-monitoring", "🟡")),
                ((40, 60), ("needs-work", "🟠")),
                ((0, 40), ("not-ready", "🔴")),
            ]:
                if low <= card.overall < high:
                    card.band_emoji = emoji
                    break

            card.phase_scores = data.get("phases", {})
            return card
        except (json.JSONDecodeError, KeyError):
            return None

    @staticmethod
    def list_evals() -> list[dict[str, Any]]:
        """List all past evaluations."""
        if not EVAL_HOME.exists():
            return []

        evals = []
        for entry in sorted(EVAL_HOME.iterdir()):
            if not entry.is_dir():
                continue
            scorecard_file = entry / "SCORECARD.json"
            if scorecard_file.exists():
                import json
                try:
                    data = json.loads(scorecard_file.read_text())
                    evals.append({
                        "sandbox": data.get("sandbox", entry.name),
                        "overall": data.get("overall", 0),
                        "band": data.get("band", "unknown"),
                        "generatedAt": data.get("generatedAt", "unknown"),
                    })
                except (json.JSONDecodeError, OSError):
                    pass
        return evals
