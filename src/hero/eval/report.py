"""Scorecard report generation — TOON + Markdown output."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from hero.eval.scorer import Scorecard


class ReportGenerator:
    """Generates human-readable and machine-readable scorecard reports."""

    def __init__(self, eval_dir: Path):
        self.eval_dir = eval_dir

    def generate(self, card: Scorecard) -> None:
        """Generate both TOON and Markdown reports."""
        self._write_scorecard_json(card)
        self._write_markdown(card)
        self._write_toon(card)

    def _write_scorecard_json(self, card: Scorecard) -> None:
        """Write SCORECARD.json — machine-readable."""
        data = {
            "sandbox": card.sandbox_name,
            "overall": card.overall,
            "band": card.band,
            "phases": card.phase_scores,
            "summary": {
                "critical": card.total_critical,
                "major": card.total_major,
                "minor": card.total_minor,
                "nit": card.total_nit,
                "totalFindings": card.total_findings,
            },
            "durationSeconds": round(card.duration_seconds, 1),
            "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        path = self.eval_dir / "SCORECARD.json"
        path.write_text(json.dumps(data, indent=2))

    def _write_markdown(self, card: Scorecard) -> None:
        """Write READY-REPORT.md — human-readable."""
        lines = [
            f"# QB Readiness Report: {card.sandbox_name}",
            "",
            f"**Score:** {card.overall}/100 {card.band_emoji} {card.band}",
            f"**Generated:** {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}",
            f"**Duration:** {card.duration_seconds:.1f}s",
            "",
            "## Phase Scores",
            "",
            "| Phase | Score | Status | Summary |",
            "|-------|-------|--------|---------|",
        ]

        for phase_num in sorted(card.phase_scores.keys()):
            phase = card.phase_scores[phase_num]
            emoji = "✅" if phase["status"] == "completed" else "⏭️" if phase["status"] == "skipped" else "❌"
            lines.append(f"| {phase['name']} | {phase['score']}/100 | {emoji} {phase['status']} | {phase['summary']} |")

        lines.extend([
            "",
            "## Findings Summary",
            "",
            f"- **Critical:** {card.total_critical}",
            f"- **Major:** {card.total_major}",
            f"- **Minor:** {card.total_minor}",
            f"- **Nit:** {card.total_nit}",
            f"- **Total:** {card.total_findings}",
            "",
        ])

        if card.total_critical > 0:
            lines.extend([
                "## ⚠️ Critical Issues",
                "",
            ])
            for phase_num in sorted(card.phase_scores.keys()):
                phase = card.phase_scores[phase_num]
                if phase["critical"] > 0:
                    lines.append(f"- **{phase['name']}**: {phase['critical']} critical issue(s)")
            lines.append("")

        # Band meaning
        lines.extend([
            "## Readiness Bands",
            "",
            "| Band | Score | Meaning |",
            "|------|-------|---------|",
            "| 🟢 production-ready | 80-100 | Ship it |",
            "| 🟡 ship-with-monitoring | 60-79 | Ship with caution |",
            "| 🟠 needs-work | 40-59 | Fix before shipping |",
            "| 🔴 not-ready | 0-39 | Do not ship |",
            "",
        ])

        (self.eval_dir / "READY-REPORT.md").write_text("\n".join(lines))

    def _write_toon(self, card: Scorecard) -> None:
        """Write SCORECARD.toon — token-efficient format."""
        lines = [
            f"scorecard{{sandbox,overall,band}}: {card.sandbox_name},{card.overall},{card.band}",
            f"findings{{critical,major,minor,nit}}: {card.total_critical},{card.total_major},{card.total_minor},{card.total_nit}",
            f"phases[{len(card.phase_scores)}]{{name,score,status}}:",
        ]
        for phase_num in sorted(card.phase_scores.keys()):
            phase = card.phase_scores[phase_num]
            lines.append(f"  {phase['name']},{phase['score']},{phase['status']}")

        (self.eval_dir / "SCORECARD.toon").write_text("\n".join(lines))
