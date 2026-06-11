"""Score aggregation and band assignment for the eval pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hero.eval.phases import PhaseResult


# Score bands
BANDS = {
    (80, 101): ("production-ready", "🟢"),
    (60, 80):  ("ship-with-monitoring", "🟡"),
    (40, 60):  ("needs-work", "🟠"),
    (0, 40):   ("not-ready", "🔴"),
}

# Phase weights for overall score
PHASE_WEIGHTS: dict[int, float] = {
    1: 15,   # baseline
    2: 20,   # security
    3: 15,   # code-review
    4: 5,    # cicd
    5: 15,   # tdd
    6: 10,   # performance
    7: 5,    # accessibility
    8: 0,    # fix (doesn't contribute to score)
    9: 10,   # verify
    10: 5,   # ship
}


@dataclass
class Scorecard:
    """Final scorecard from the eval pipeline."""
    sandbox_name: str
    overall: int = 0
    band: str = "not-ready"
    band_emoji: str = "🔴"
    phase_scores: dict[int, dict[str, Any]] = field(default_factory=dict)
    total_critical: int = 0
    total_major: int = 0
    total_minor: int = 0
    total_nit: int = 0
    total_findings: int = 0
    duration_seconds: float = 0.0


class Scorer:
    """Aggregates phase results into a final scorecard."""

    def __init__(self, sandbox_name: str):
        self.sandbox_name = sandbox_name
        self.results: list[PhaseResult] = []

    def add_result(self, result: PhaseResult) -> None:
        """Add a phase result."""
        self.results.append(result)

    def compute(self) -> Scorecard:
        """Compute the final scorecard."""
        card = Scorecard(sandbox_name=self.sandbox_name)

        weighted_sum = 0.0
        total_weight = 0.0

        for result in self.results:
            weight = PHASE_WEIGHTS.get(result.phase_number, 5)
            weighted_sum += result.score * weight
            total_weight += weight

            card.phase_scores[result.phase_number] = {
                "name": result.phase_name,
                "score": result.score,
                "status": result.status,
                "summary": result.summary,
                "critical": result.critical,
                "major": result.major,
                "minor": result.minor,
                "nit": result.nit,
                "duration": result.duration_seconds,
            }

            card.total_critical += result.critical
            card.total_major += result.major
            card.total_minor += result.minor
            card.total_nit += result.nit
            card.total_findings += len(result.findings)
            card.duration_seconds += result.duration_seconds

        # Calculate weighted overall
        if total_weight > 0:
            card.overall = int(weighted_sum / total_weight)
        else:
            card.overall = 50

        # Apply penalties for critical issues
        card.overall -= card.total_critical * 5
        card.overall = max(0, min(100, card.overall))

        # Assign band
        for (low, high), (band, emoji) in BANDS.items():
            if low <= card.overall < high:
                card.band = band
                card.band_emoji = emoji
                break

        return card
