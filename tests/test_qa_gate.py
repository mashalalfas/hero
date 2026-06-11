"""Tests for QAGate and QAResult."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from hero.qa.gate import QAGate, QAResult


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def sandbox_with_git(tmp_path: Path) -> Path:
    """Create a temporary git repo for testing diff-based checks."""
    repo = tmp_path / "sandbox"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(repo),
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(repo),
        capture_output=True,
    )
    # Initial commit so we can diff against something
    initial = repo / "README.md"
    initial.write_text("# Sandbox\n")
    subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=str(repo),
        capture_output=True,
    )
    return repo


def _add_and_stage(repo: Path, rel_path: str, content: str) -> None:
    """Write *content* to *rel_path* inside *repo* and git-add it."""
    target = repo / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    subprocess.run(["git", "add", rel_path], cwd=str(repo), capture_output=True)


# ── QAResult tests ──────────────────────────────────────────────────────


class TestQAResult:
    def test_passed_no_violations(self) -> None:
        result = QAResult(passed=True)
        assert result.passed is True
        assert result.violations == []

    def test_failed_with_violations(self) -> None:
        result = QAResult(passed=False, violations=["err1", "err2"])
        assert result.passed is False
        assert result.violations == ["err1", "err2"]

    def test_default_violations_is_empty(self) -> None:
        result = QAResult(passed=True)
        assert result.violations == []


# ── File-scope check ────────────────────────────────────────────────────


class TestFileScopeCheck:
    def test_allows_whitelisted_file(self, sandbox_with_git: Path) -> None:
        allowed = ["src/main.py", "README.md"]
        gate = QAGate(sandbox_with_git, allowed_files=allowed)

        (sandbox_with_git / "README.md").write_text("# Updated\n")

        result = gate.run()
        assert result.passed is True
        assert result.violations == []

    def test_rejects_unlisted_file(self, sandbox_with_git: Path) -> None:
        allowed = ["src/main.py"]
        gate = QAGate(sandbox_with_git, allowed_files=allowed)

        _add_and_stage(sandbox_with_git, "secret.cfg", "key=value\n")

        result = gate.run()
        assert result.passed is False
        assert any("secret.cfg" in v for v in result.violations)

    def test_accepts_nested_allowed_file(self, sandbox_with_git: Path) -> None:
        allowed = ["src/main.py", "docs/guide.md"]
        gate = QAGate(sandbox_with_git, allowed_files=allowed)

        _add_and_stage(sandbox_with_git, "docs/guide.md", "# Guide\n")

        result = gate.run()
        assert result.passed is True

    def test_scope_violation_has_terse_message(self, sandbox_with_git: Path) -> None:
        """Violation messages should be concise and actionable."""
        gate = QAGate(sandbox_with_git, allowed_files=["safe.py"])
        _add_and_stage(sandbox_with_git, "rogue.py", "x = 1\n")

        result = gate.run()
        assert len(result.violations) >= 1
        msg = result.violations[0]
        assert "Scope violation" in msg
        assert "rogue.py" in msg


# ── Diff-size check ─────────────────────────────────────────────────────


class TestDiffSizeCheck:
    def test_small_diff_passes(self, sandbox_with_git: Path) -> None:
        gate = QAGate(
            sandbox_with_git,
            allowed_files=["small.py"],
            max_diff_lines=100,
        )
        _add_and_stage(sandbox_with_git, "small.py", "x = 1\n")
        result = gate.run()
        assert result.passed is True

    def test_large_diff_fails(self, sandbox_with_git: Path) -> None:
        gate = QAGate(
            sandbox_with_git,
            allowed_files=["big.py"],
            max_diff_lines=5,
        )
        big = "\n".join(f"line_{i}" for i in range(50)) + "\n"
        _add_and_stage(sandbox_with_git, "big.py", big)

        result = gate.run()
        assert result.passed is False
        assert any("big.py" in v for v in result.violations)
        assert any("50" in v for v in result.violations)

    def test_max_diff_lines_zero_rejects_any_change(self, sandbox_with_git: Path) -> None:
        gate = QAGate(
            sandbox_with_git,
            allowed_files=["tiny.py"],
            max_diff_lines=0,
        )
        _add_and_stage(sandbox_with_git, "tiny.py", "x = 1\n")

        result = gate.run()
        assert result.passed is False

    def test_multiple_files_exceed_limit(self, sandbox_with_git: Path) -> None:
        gate = QAGate(
            sandbox_with_git,
            allowed_files=["a.py", "b.py"],
            max_diff_lines=2,
        )
        _add_and_stage(
            sandbox_with_git, "a.py", "line1\nline2\nline3\nline4\nline5\n"
        )
        _add_and_stage(
            sandbox_with_git, "b.py", "line1\nline2\nline3\nline4\nline5\n"
        )

        result = gate.run()
        assert result.passed is False
        # Should flag both files
        violations = [v for v in result.violations if "Oversized diff" in v]
        assert len(violations) >= 2


# ── handle_failure ──────────────────────────────────────────────────────


class TestHandleFailure:
    def test_logs_and_sends_to_dlq(self, sandbox_with_git: Path) -> None:
        gate = QAGate(sandbox_with_git, allowed_files=["safe.py"], max_diff_lines=10)
        _add_and_stage(sandbox_with_git, "bad.py", "x = 1\n")

        result = gate.run()
        assert result.passed is False

        # Should not raise
        gate.handle_failure(result, "task-001", {"path": "bad.py"})

    def test_handle_failure_creates_dlq_entry(self, sandbox_with_git: Path) -> None:
        gate = QAGate(sandbox_with_git, allowed_files=["safe.py"], max_diff_lines=10)
        _add_and_stage(sandbox_with_git, "rogue.py", "leak = True\n")

        result = gate.run()
        assert result.passed is False

        # Clear any pre-existing DLQ entries for this task
        dlq_dir = Path.home() / ".hero" / "dead_letter"
        dlq_file = dlq_dir / "task-002.json"
        if dlq_file.exists():
            dlq_file.unlink()

        gate.handle_failure(result, "task-002", {"cmd": "test"})

        assert dlq_file.exists()
        record = json.loads(dlq_file.read_text())
        assert record["task_id"] == "task-002"
        assert "Scope violation" in record.get("error", "")
        assert "rogue.py" in record.get("error", "")

        # Cleanup
        dlq_file.unlink()

    def test_handle_failure_silent_on_pass(self, sandbox_with_git: Path) -> None:
        gate = QAGate(
            sandbox_with_git,
            allowed_files=["safe.py"],
            max_diff_lines=10,
        )
        _add_and_stage(sandbox_with_git, "safe.py", "x = 1\n")

        result = gate.run()
        assert result.passed is True

        # Should not raise or modify state
        gate.handle_failure(result, "task-003", {"path": "safe.py"})
