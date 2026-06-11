"""Tests for PipelineExecutor — circuit breaker gate + QA gate integration.

These tests build on the existing ``test_pipeline_executor.py`` suite
and add coverage for the new quality-gate features.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from hero.pipeline.executor import PipelineExecutor
from hero.reliability.circuit_breaker import is_quarantined, record_failure, unquarantine


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def sandbox_repo(tmp_path: Path) -> Path:
    """Create a temp git repo with an initial commit."""
    repo = tmp_path / "sandbox"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(repo), capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(repo), capture_output=True,
    )
    initial = repo / "README.md"
    initial.write_text("# Sandbox\n")
    subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=str(repo), capture_output=True,
    )
    return repo


@pytest.fixture
def manifest_with_sandbox(sandbox_repo: Path) -> dict:
    """Pipeline manifest pointing to the git sandbox repo."""
    return {
        "pipeline_id": "qa-test-pipeline",
        "sandbox": str(sandbox_repo),
        "task": "test-qa-gate",
        "steps": {
            "dispatch": {"task_ids": ["soldier01"]},
            "spawn": {
                "commands": [
                    {
                        "task_id": "soldier01",
                        "sandbox": str(sandbox_repo),
                        "role": "soldier",
                        "label": "qa-soldier-1",
                    },
                ],
            },
            "verify": {"enabled": False},
            "archive": {"enabled": False},
        },
    }


@pytest.fixture
def manifest_file(tmp_path: Path, manifest_with_sandbox: dict) -> Path:
    """Write a manifest file and return its path."""
    pipeline_dir = tmp_path / ".hero" / "pipeline"
    pipeline_dir.mkdir(parents=True, exist_ok=True)
    path = pipeline_dir / "qa-test-pipeline.json"
    path.write_text(json.dumps(manifest_with_sandbox, indent=2))
    return path


# ── Circuit breaker gate ────────────────────────────────────────────────


class TestCircuitBreakerGate:
    """PipelineExecutor.run() must reject quarantined sandboxes."""

    def test_raises_on_quarantined_sandbox(self, manifest_file: Path) -> None:
        sandbox_name = "__test_cb_" + manifest_file.stem
        try:
            # Record 3 failures to trigger quarantine
            for _ in range(3):
                record_failure(sandbox_name)

            assert is_quarantined(sandbox_name), "sanity: sandbox should be quarantined"

            manifest_data = json.loads(manifest_file.read_text())
            manifest_data["sandbox"] = sandbox_name
            manifest_file.write_text(json.dumps(manifest_data, indent=2))

            executor = PipelineExecutor(manifest_file)
            with pytest.raises(RuntimeError, match="quarantined"):
                executor.run()
        finally:
            unquarantine(sandbox_name)

    def test_ok_on_unquarantined_sandbox(self, manifest_file: Path) -> None:
        executor = PipelineExecutor(manifest_file)
        # We don't have dispatch files so polling will timeout — instead
        # patch the poll to skip and confirm the circuit breaker doesn't fire.
        with patch.object(executor, "_poll_tasks"):
            result = executor.run(poll_interval=1, max_wait=1)
        assert result.status in ("completed", "running")

    def test_unrelated_sandboxes_not_affected(self, manifest_file: Path) -> None:
        other = "some-other-sandbox"
        for _ in range(3):
            record_failure(other)
        try:
            executor = PipelineExecutor(manifest_file)
            with patch.object(executor, "_poll_tasks"):
                result = executor.run(poll_interval=1, max_wait=1)
            assert result.status in ("completed", "running")
        finally:
            unquarantine(other)


# ── QA gate integration ─────────────────────────────────────────────────


class TestQAGateIntegration:
    """PipelineExecutor.run() must run the QA gate before polling soldiers."""

    def test_qa_gate_passes_with_allowed_changes(
        self, manifest_file: Path, sandbox_repo: Path
    ) -> None:
        """A diff touching only allowed files should pass the QA gate."""
        safe_file = sandbox_repo / "README.md"
        safe_file.write_text("# Updated readme\n")
        subprocess.run(
            ["git", "add", "README.md"],
            cwd=str(sandbox_repo), capture_output=True,
        )

        executor = PipelineExecutor(
            manifest_file,
            allowed_files=["README.md"],
        )
        with patch.object(executor, "_poll_tasks"):
            result = executor.run(poll_interval=1, max_wait=1)
        assert result.status in ("completed", "running")

    def test_qa_gate_rejects_unallowed_changes(
        self, manifest_file: Path, sandbox_repo: Path
    ) -> None:
        """A diff with unallowed files should cause a RuntimeError."""
        bad_file = sandbox_repo / "secret.py"
        bad_file.write_text("x = 1\n")
        subprocess.run(
            ["git", "add", "secret.py"],
            cwd=str(sandbox_repo), capture_output=True,
        )

        executor = PipelineExecutor(
            manifest_file,
            allowed_files=["README.md"],
        )
        with pytest.raises(RuntimeError, match="QA gate rejected"):
            executor.run()

    def test_qa_gate_skipped_when_no_allowed_files(
        self, manifest_file: Path, sandbox_repo: Path
    ) -> None:
        """If no allowed_files are specified, the QA gate is skipped."""
        bad_file = sandbox_repo / "secret.py"
        bad_file.write_text("x = 1\n")
        subprocess.run(
            ["git", "add", "secret.py"],
            cwd=str(sandbox_repo), capture_output=True,
        )

        executor = PipelineExecutor(manifest_file)  # no allowed_files
        with patch.object(executor, "_poll_tasks"):
            result = executor.run(poll_interval=1, max_wait=1)
        assert result.status in ("completed", "running")
