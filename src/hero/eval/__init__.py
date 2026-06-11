"""HERO Eval — Pre-launch quality evaluation pipeline.

Runs a project through 10 phases of analysis, generates a SCORECARD
with readiness score (0-100) and band (production-ready / ship-with-monitoring / needs-work / not-ready).

Usage:
    hero eval --sandbox <name>
    hero eval --sandbox <name> --phase security
    hero eval --sandbox <name> --fix
    hero eval --sandbox <name> --score
"""

from hero.eval.engine import EvalEngine
from hero.eval.scorer import Scorer, Scorecard
from hero.eval.report import ReportGenerator

__all__ = ["EvalEngine", "Scorer", "Scorecard", "ReportGenerator"]
