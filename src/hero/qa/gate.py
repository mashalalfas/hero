"""QA Gate — file-scope and diff-size checks on soldier output.

Two checks:

1. **File-scope** — every changed file must be in the allowed list.
2. **Diff-size** — no single file may exceed *max_diff_lines* of changes.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class QAResult:
    """Result of a QA gate check."""

    passed: bool
    violations: list[str] = field(default_factory=list)


class QAGate:
    """Quality gate that verifies soldier-generated diffs against policy."""

    def __init__(
        self,
        sandbox_path: Path,
        allowed_files: list[str],
        max_diff_lines: int = 200,
    ) -> None:
        self.sandbox_path = sandbox_path
        self.allowed_files = allowed_files
        self.max_diff_lines = max_diff_lines

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> QAResult:
        """Run all checks on the latest git diff inside *sandbox_path*.

        Returns
        -------
        QAResult
            With *passed* set to ``True`` iff every check succeeds.
        """
        violations: list[str] = []

        # Check 1 — file-scope
        changed_files = self._get_changed_files()
        for f in changed_files:
            if not self._is_allowed(f):
                violations.append(
                    f"Scope violation: {f} not in allowed files"
                )

        # Check 2 — diff-size
        diff_stats = self._get_diff_stats()
        for fname, lines_changed in diff_stats.items():
            if lines_changed > self.max_diff_lines:
                violations.append(
                    f"Oversized diff: {fname} changed {lines_changed} lines "
                    f"(max {self.max_diff_lines})"
                )

        return QAResult(passed=len(violations) == 0, violations=violations)

    def handle_failure(
        self, result: QAResult, task_id: str, task_data: dict
    ) -> None:
        """Handle a failed QA result: log violations and send task to DLQ.

        Parameters
        ----------
        result : QAResult
            The (failing) QA result.
        task_id : str
            Identifier of the soldier task.
        task_data : dict
            Full dispatch entry to persist in the dead-letter queue.
        """
        for v in result.violations:
            logger.error("QA violation [%s]: %s", task_id, v)
        if not result.passed:
            from hero.reliability.dlq import send_to_dlq  # noqa: PLC0415

            send_to_dlq(
                task_id,
                task_data,
                "; ".join(result.violations),
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    # Use ``git diff HEAD`` so that both staged and unstaged changes are
    # included in the QA gate check.

    def _get_changed_files(self) -> list[str]:
        """Return list of files changed in the working tree or index."""
        result = subprocess.run(
            ["git", "diff", "HEAD", "--name-only"],
            capture_output=True,
            text=True,
            cwd=str(self.sandbox_path),
        )
        return [f.strip() for f in result.stdout.splitlines() if f.strip()]

    def _get_diff_stats(self) -> dict[str, int]:
        """Return ``{filename: lines_changed}`` via ``git diff HEAD --stat``."""
        result = subprocess.run(
            ["git", "diff", "HEAD", "--stat"],
            capture_output=True,
            text=True,
            cwd=str(self.sandbox_path),
        )
        stats: dict[str, int] = {}
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if not stripped or "file changed" in stripped or "files changed" in stripped:
                continue
            parts = stripped.split("|")
            if len(parts) == 2:
                fname = parts[0].strip()
                count_str = parts[1].strip().split()[0]
                try:
                    stats[fname] = int(count_str)
                except ValueError:
                    pass
        return stats

    def _is_allowed(self, filepath: str) -> bool:
        """Check whether *filepath* is covered by the allowed list."""
        for allowed in self.allowed_files:
            if filepath == allowed or filepath.endswith("/" + allowed):
                return True
        return False
