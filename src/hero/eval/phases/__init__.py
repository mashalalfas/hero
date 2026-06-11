"""Phase base class and registry for the eval pipeline."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PhaseResult:
    """Result from a single evaluation phase."""
    phase_name: str
    phase_number: int
    status: str  # "completed", "failed", "skipped"
    score: int  # 0-100
    findings: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    duration_seconds: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def critical(self) -> int:
        return sum(1 for f in self.findings if f.get("severity") == "critical")

    @property
    def major(self) -> int:
        return sum(1 for f in self.findings if f.get("severity") == "major")

    @property
    def minor(self) -> int:
        return sum(1 for f in self.findings if f.get("severity") == "minor")

    @property
    def nit(self) -> int:
        return sum(1 for f in self.findings if f.get("severity") == "nit")


class BasePhase(ABC):
    """Base class for all evaluation phases."""

    name: str = "base"
    number: int = 0
    description: str = ""

    @abstractmethod
    def run(self, project_path: Path, eval_dir: Path, context: dict[str, Any]) -> PhaseResult:
        """Run this phase against the project.

        Args:
            project_path: Path to the project source code.
            eval_dir: Path to store eval artifacts for this phase.
            context: Results from previous phases (for dependent checks).

        Returns:
            PhaseResult with score, findings, and summary.
        """
        ...

    def _detect_project_type(self, project_path: Path) -> str:
        """Detect project type from marker files."""
        markers = {
            "flutter": "pubspec.yaml",
            "go": "go.mod",
            "node": "package.json",
            "python": "pyproject.toml",
            "rust": "Cargo.toml",
            "java": "pom.xml",
            "java-gradle": "build.gradle",
            "c": "CMakeLists.txt",
        }
        # Check root
        for ptype, marker in markers.items():
            if (project_path / marker).exists():
                return ptype
        # Check one level deeper
        for entry in project_path.iterdir():
            if entry.is_dir() and not entry.name.startswith("."):
                for ptype, marker in markers.items():
                    if (entry / marker).exists():
                        return ptype
        return "unknown"


# Phase registry — populated by imports
PHASES: dict[int, type[BasePhase]] = {}


def register_phase(phase_cls: type[BasePhase]) -> type[BasePhase]:
    """Register a phase class in the global registry."""
    PHASES[phase_cls.number] = phase_cls
    return phase_cls
