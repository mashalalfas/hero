"""Tests for PipelineExecutor and PipelineResult."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from hero.pipeline.executor import PIPELINE_DIR, PipelineExecutor, PipelineResult


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def manifest_data() -> dict:
    """Typical pipeline manifest as produced by ``hero go``."""
    return {
        "pipeline_id": "test1234",
        "sandbox": "sook-pro",
        "task": "fix theme switcher",
        "project_type": "flutter",
        "created_at": "2026-05-24T12:00:00",
        "dry_run": False,
        "steps": {
            "analysis": {"status": "done", "result": {"success": True}},
            "dispatch": {
                "status": "done",
                "task_ids": ["soldier01", "soldier02"],
            },
            "spawn": {
                "status": "ready",
                "commands": [
                    {
                        "task_id": "soldier01",
                        "sandbox": "sook-pro",
                        "role": "soldier",
                        "model": "opencode-go/deepseek-v4-flash",
                        "label": "sook-pro-soldier-1",
                        "sessions_spawn": {
                            "label": "sook-pro-soldier-1",
                            "model": "opencode-go/deepseek-v4-flash",
                        },
                    },
                    {
                        "task_id": "soldier02",
                        "sandbox": "sook-pro",
                        "role": "soldier",
                        "model": "opencode-go/deepseek-v4-flash",
                        "label": "sook-pro-soldier-2",
                        "sessions_spawn": {
                            "label": "sook-pro-soldier-2",
                            "model": "opencode-go/deepseek-v4-flash",
                        },
                    },
                ],
            },
            "verify": {"enabled": True, "task_id": "verify01"},
            "self_review": {"enabled": True, "task_id": "selfreview01"},
            "archive": {"enabled": True, "task_id": "archive01"},
        },
    }


@pytest.fixture
def manifest_file(tmp_path: Path, manifest_data: dict) -> Path:
    """Write a manifest and return its path."""
    pipeline_dir = tmp_path / ".hero" / "pipeline"
    pipeline_dir.mkdir(parents=True, exist_ok=True)
    path = pipeline_dir / "test1234.json"
    path.write_text(json.dumps(manifest_data, indent=2))
    return path


@pytest.fixture
def dispatch_dir(tmp_path: Path) -> Path:
    """Create a dispatch directory and return path."""
    d = tmp_path / ".hero" / "dispatch"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _make_dispatch_toon(dispatch_dir: Path, task_id: str, status: str, result: str = "") -> Path:
    """Write a .toon dispatch file and return path."""
    path = dispatch_dir / f"{task_id}.toon"
    lines = [
        f'task_id: "{task_id}"',
        f'sandbox: "sook-pro"',
        f'status: "{status}"',
    ]
    if result:
        lines.append(f'result: "{result}"')
    lines.append(f'created_at: "{datetime.now().isoformat()}"')
    path.write_text("\n".join(lines) + "\n")
    return path


# ── PipelineResult tests ────────────────────────────────────────────────


class TestPipelineResult:
    """Tests for PipelineResult data class."""

    def test_summary_completed(self) -> None:
        soldiers = [
            {"task_id": "a", "status": "completed", "result": "ok"},
            {"task_id": "b", "status": "completed", "result": "ok"},
        ]
        result = PipelineResult(
            pipeline_id="abc123def",
            sandbox="sook-pro",
            task="fix theme",
            status="completed",
            soldiers=soldiers,
            verify_status="passed",
            archive_status="completed",
            started_at="2026-05-24T12:00:00",
            completed_at="2026-05-24T12:05:00",
        )
        summary = result.summary()
        assert "abc123" in summary
        assert "completed" in summary
        assert "2/2" in summary

    def test_summary_with_failures(self) -> None:
        soldiers = [
            {"task_id": "a", "status": "completed", "result": "ok"},
            {"task_id": "b", "status": "failed", "result": "error"},
        ]
        result = PipelineResult(
            pipeline_id="abc123def",
            sandbox="sook-pro",
            task="fix theme",
            status="failed",
            soldiers=soldiers,
            started_at="2026-05-24T12:00:00",
            completed_at="2026-05-24T12:05:00",
        )
        summary = result.summary()
        assert "1 failed" in summary

    def test_summary_empty_soldiers(self) -> None:
        result = PipelineResult(
            pipeline_id="abc123",
            sandbox="sook-pro",
            task="fix theme",
            status="completed",
            started_at="2026-05-24T12:00:00",
        )
        summary = result.summary()
        assert "completed" in summary


# ── PipelineExecutor tests ──────────────────────────────────────────────


class TestPipelineExecutorInit:
    """Tests for PipelineExecutor construction."""

    def test_loads_manifest(self, manifest_file: Path) -> None:
        executor = PipelineExecutor(manifest_file)
        assert executor.pipeline_id == "test1234"
        assert executor.sandbox == "sook-pro"
        assert executor.task == "fix theme switcher"

    def test_raises_on_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            PipelineExecutor(Path("/nonexistent/manifest.json"))

    def test_builds_soldiers_from_task_ids(self, manifest_file: Path) -> None:
        executor = PipelineExecutor(manifest_file)
        assert len(executor.soldiers) == 2
        assert executor.soldiers[0]["task_id"] == "soldier01"
        assert executor.soldiers[1]["task_id"] == "soldier02"

    def test_soldiers_have_labels_from_commands(self, manifest_file: Path) -> None:
        executor = PipelineExecutor(manifest_file)
        assert executor.soldiers[0]["label"] == "sook-pro-soldier-1"
        assert executor.soldiers[1]["label"] == "sook-pro-soldier-2"


class TestPipelineExecutorFindExtraTasks:
    """Tests for _find_extra_tasks."""

    def test_detects_verify_task(self, manifest_file: Path) -> None:
        executor = PipelineExecutor(manifest_file)
        executor._find_extra_tasks()
        assert len(executor.verify_tasks) == 1
        assert executor.verify_tasks[0]["task_id"] == "verify01"

    def test_detects_archive_task(self, manifest_file: Path) -> None:
        executor = PipelineExecutor(manifest_file)
        executor._find_extra_tasks()
        assert len(executor.archive_tasks) == 1
        assert executor.archive_tasks[0]["task_id"] == "archive01"

    def test_detects_self_review_task(self, manifest_file: Path) -> None:
        executor = PipelineExecutor(manifest_file)
        executor._find_extra_tasks()
        assert len(executor.self_review_tasks) == 1
        assert executor.self_review_tasks[0]["task_id"] == "selfreview01"
        assert executor.self_review_tasks[0]["label"] == "Self-Review (self_review)"


class TestPipelineExecutorPollTasks:
    """Tests for _poll_tasks with mocked dispatch."""

    def test_all_completed(self, manifest_file: Path, dispatch_dir: Path, tmp_path: Path) -> None:
        """Polling returns when all tasks are completed."""
        PIPELINE_DIR.mkdir(parents=True, exist_ok=True)

        # Write completed dispatch files for both soldiers
        _make_dispatch_toon(dispatch_dir, "soldier01", "completed", "all good")
        _make_dispatch_toon(dispatch_dir, "soldier02", "completed", "done")

        executor = PipelineExecutor(manifest_file)
        tasks = [
            {"task_id": "soldier01", "status": "pending", "result": None},
            {"task_id": "soldier02", "status": "pending", "result": None},
        ]

        with patch(
            "hero.pipeline.executor.get_task",
            side_effect=_mock_get_task(dispatch_dir),
        ):
            executor._poll_tasks(tasks, poll_interval=0.1, max_wait=30)

        assert tasks[0]["status"] == "completed"
        assert tasks[1]["status"] == "completed"

    def test_one_failed(self, manifest_file: Path, dispatch_dir: Path) -> None:
        """Polling detects a failed task."""
        _make_dispatch_toon(dispatch_dir, "soldier01", "completed", "ok")
        _make_dispatch_toon(dispatch_dir, "soldier02", "failed", "build error")

        executor = PipelineExecutor(manifest_file)
        tasks = [
            {"task_id": "soldier01", "status": "pending", "result": None},
            {"task_id": "soldier02", "status": "pending", "result": None},
        ]

        with patch(
            "hero.pipeline.executor.get_task",
            side_effect=_mock_get_task(dispatch_dir),
        ):
            executor._poll_tasks(tasks, poll_interval=0.1, max_wait=30)

        assert tasks[0]["status"] == "completed"
        assert tasks[1]["status"] == "failed"

    def test_polls_until_terminal(self, manifest_file: Path, dispatch_dir: Path) -> None:
        """Polling waits for pending→completed transition."""
        # Start with pending for soldier02
        _make_dispatch_toon(dispatch_dir, "soldier01", "completed")
        _make_dispatch_toon(dispatch_dir, "soldier02", "pending")

        executor = PipelineExecutor(manifest_file)
        tasks = [
            {"task_id": "soldier01", "status": "pending", "result": None},
            {"task_id": "soldier02", "status": "pending", "result": None},
        ]

        call_count = [0]

        def _delayed_get_task(task_id: str) -> dict | None:
            call_count[0] += 1
            # On third call, mark soldier02 as completed
            if call_count[0] >= 3 and task_id == "soldier02":
                _make_dispatch_toon(dispatch_dir, "soldier02", "completed", "finally done")
            return _do_get_task(dispatch_dir, task_id)

        with patch(
            "hero.pipeline.executor.get_task",
            side_effect=_delayed_get_task,
        ):
            executor._poll_tasks(tasks, poll_interval=0.05, max_wait=30)

        assert tasks[0]["status"] == "completed"
        assert tasks[1]["status"] == "completed"
        assert tasks[1]["result"] == "finally done"
        assert call_count[0] >= 3

    def test_timeout_raises(self, manifest_file: Path, dispatch_dir: Path) -> None:
        """Polling raises TimeoutError after max_wait."""
        _make_dispatch_toon(dispatch_dir, "soldier01", "completed")
        _make_dispatch_toon(dispatch_dir, "soldier02", "pending")  # stays pending

        executor = PipelineExecutor(manifest_file)
        tasks = [
            {"task_id": "soldier01", "status": "pending", "result": None},
            {"task_id": "soldier02", "status": "pending", "result": None},
        ]

        with patch(
            "hero.pipeline.executor.get_task",
            side_effect=_mock_get_task(dispatch_dir),
        ):
            with pytest.raises(TimeoutError, match="timed out"):
                executor._poll_tasks(tasks, poll_interval=0.05, max_wait=1)


class TestPipelineExecutorRun:
    """Tests for PipelineExecutor.run() -- end-to-end."""

    def test_all_soldiers_succeed(self, manifest_file: Path, dispatch_dir: Path, tmp_path: Path) -> None:
        """Run returns completed when all soldiers succeed."""
        _make_dispatch_toon(dispatch_dir, "soldier01", "completed", "ok")
        _make_dispatch_toon(dispatch_dir, "soldier02", "completed", "ok")
        _make_dispatch_toon(dispatch_dir, "selfreview01", "completed", "ready")
        _make_dispatch_toon(dispatch_dir, "verify01", "completed", "passed")
        _make_dispatch_toon(dispatch_dir, "archive01", "completed", "done")

        executor = PipelineExecutor(manifest_file)

        with patch(
            "hero.pipeline.executor.get_task",
            side_effect=_mock_get_task(dispatch_dir),
        ):
            result = executor.run(poll_interval=0.1, max_wait=30)

        assert result.status == "completed"
        assert result.self_review_status == "passed"
        assert result.verify_status == "passed"
        assert result.archive_status == "completed"
        assert result.completed_at is not None

    def test_soldier_failure(self, manifest_file: Path, dispatch_dir: Path) -> None:
        """Run returns failed when a soldier fails."""
        _make_dispatch_toon(dispatch_dir, "soldier01", "completed", "ok")
        _make_dispatch_toon(dispatch_dir, "soldier02", "failed", "compile error")

        executor = PipelineExecutor(manifest_file)

        with patch(
            "hero.pipeline.executor.get_task",
            side_effect=_mock_get_task(dispatch_dir),
        ):
            result = executor.run(poll_interval=0.1, max_wait=30)

        assert result.status == "failed"
        assert result.verify_status is None

    def test_verify_failure(self, manifest_file: Path, dispatch_dir: Path) -> None:
        """Run returns verify_failed when verify task fails."""
        _make_dispatch_toon(dispatch_dir, "soldier01", "completed", "ok")
        _make_dispatch_toon(dispatch_dir, "soldier02", "completed", "ok")
        _make_dispatch_toon(dispatch_dir, "selfreview01", "completed", "ready")
        _make_dispatch_toon(dispatch_dir, "verify01", "failed", "build broke")
        _make_dispatch_toon(dispatch_dir, "archive01", "pending", "")

        executor = PipelineExecutor(manifest_file)

        with patch(
            "hero.pipeline.executor.get_task",
            side_effect=_mock_get_task(dispatch_dir),
        ):
            result = executor.run(poll_interval=0.1, max_wait=30)

        assert result.status == "verify_failed"
        assert result.verify_status == "failed"
        assert result.archive_status == "skipped"


    def test_no_verify_no_archive(self, manifest_file: Path, tmp_path: Path) -> None:
        """Run with no verify/archive task IDs passes through."""
        simple_manifest = {
            "pipeline_id": "simple01",
            "sandbox": "sandbox-a",
            "task": "simple task",
            "steps": {
                "dispatch": {"task_ids": ["task_a"]},
                "spawn": {"commands": []},
                "verify": {"enabled": False},
                "archive": {"enabled": False},
            },
        }
        pipeline_dir = tmp_path / ".hero" / "pipeline"
        pipeline_dir.mkdir(parents=True, exist_ok=True)
        path = pipeline_dir / "simple01.json"
        path.write_text(json.dumps(simple_manifest, indent=2))

        dispatch_dir = tmp_path / ".hero" / "dispatch"
        dispatch_dir.mkdir(parents=True, exist_ok=True)
        _make_dispatch_toon(dispatch_dir, "task_a", "completed", "done")

        executor = PipelineExecutor(path)

        with patch(
            "hero.pipeline.executor.get_task",
            side_effect=_mock_get_task(dispatch_dir),
        ):
            result = executor.run(poll_interval=0.1, max_wait=30)

        assert result.status == "completed"
        assert result.verify_status == "passed"
        assert result.archive_status == "skipped"

    def test_updates_manifest_on_disk(self, manifest_file: Path, dispatch_dir: Path) -> None:
        """Run writes status changes back to the manifest file."""
        _make_dispatch_toon(dispatch_dir, "soldier01", "completed", "ok")
        _make_dispatch_toon(dispatch_dir, "soldier02", "completed", "ok")
        _make_dispatch_toon(dispatch_dir, "selfreview01", "completed", "ready")
        _make_dispatch_toon(dispatch_dir, "verify01", "completed", "passed")
        _make_dispatch_toon(dispatch_dir, "archive01", "completed", "done")

        executor = PipelineExecutor(manifest_file)

        with patch(
            "hero.pipeline.executor.get_task",
            side_effect=_mock_get_task(dispatch_dir),
        ):
            executor.run(poll_interval=0.1, max_wait=30)

        # Verify manifest was updated on disk
        updated = json.loads(manifest_file.read_text())
        assert updated.get("status") == "completed"
        assert len(updated.get("soldiers", [])) == 2
        assert updated.get("verify_status") == "passed"
        assert updated.get("self_review_status") == "passed"
        assert updated.get("archive_status") == "completed"
        assert updated.get("started_at") is not None
        assert updated.get("completed_at") is not None

    def test_no_soldiers(self, tmp_path: Path) -> None:
        """Run gracefully handles pipelines with no soldier tasks."""
        empty_manifest = {
            "pipeline_id": "empty01",
            "sandbox": "sandbox-a",
            "task": "empty task",
            "steps": {
                "dispatch": {"task_ids": []},
                "spawn": {"commands": []},
                "verify": {"enabled": False},
                "archive": {"enabled": False},
            },
        }
        pipeline_dir = tmp_path / ".hero" / "pipeline"
        pipeline_dir.mkdir(parents=True, exist_ok=True)
        path = pipeline_dir / "empty01.json"
        path.write_text(json.dumps(empty_manifest, indent=2))

        executor = PipelineExecutor(path)
        result = executor.run(poll_interval=0.1, max_wait=30)

        assert result.status == "completed"
        assert len(result.soldiers) == 0


# ── Helpers ─────────────────────────────────────────────────────────────


def _mock_get_task(dispatch_dir: Path):
    """Return a side_effect function that reads dispatch files from a dir."""
    return lambda task_id: _do_get_task(dispatch_dir, task_id)


def _do_get_task(dispatch_dir: Path, task_id: str) -> dict | None:
    """Read a dispatch file by task_id from the given directory."""
    toon_file = dispatch_dir / f"{task_id}.toon"
    json_file = dispatch_dir / f"{task_id}.json"

    if toon_file.exists():
        return _parse_simple_toon(toon_file.read_text(), task_id)
    if json_file.exists():
        return json.loads(json_file.read_text())
    return None


def _parse_simple_toon(content: str, task_id: str) -> dict:
    """Parse a minimal TOON file for test dispatch entries."""
    result: dict = {"task_id": task_id}
    for line in content.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if ": " in line:
            key, _, value = line.partition(": ")
            value = value.strip().strip('"')
            result[key] = value
    return result
