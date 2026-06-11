"""Tests for the Dead Letter Queue module."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from hero.reliability.dlq import (
    DLQ_DIR,
    send_to_dlq,
    list_dlq,
    retry_from_dlq,
    clear_dlq,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_dlq_dir():
    """Ensure a clean DLQ directory before and after each test."""
    DLQ_DIR.mkdir(parents=True, exist_ok=True)
    for f in DLQ_DIR.glob("*.json"):
        f.unlink()
    yield
    for f in DLQ_DIR.glob("*.json"):
        f.unlink()


@pytest.fixture
def sample_task_data() -> dict:
    """Standard dispatch entry to send to the DLQ."""
    return {
        "task_id": "abc123",
        "sandbox": "test-sandbox",
        "role": "soldier",
        "model": "openai/gpt-4",
        "task": "Run the analysis on the test project.",
        "workdir": "/home/max/Development/Taurus/test-sandbox",
        "timeout": 300,
        "budget": 5000,
        "status": "failed",
        "created_at": "2026-05-24T12:00:00",
        "dispatched_at": "2026-05-24T12:00:01",
        "completed_at": "2026-05-24T12:01:00",
        "result": "Timeout exceeded",
    }


# ---------------------------------------------------------------------------
# send_to_dlq
# ---------------------------------------------------------------------------

class TestSendToDlq:
    def test_writes_json_file(self, sample_task_data):
        """send_to_dlq creates a .json file in the DLQ directory."""
        path = send_to_dlq("abc123", sample_task_data, "Timeout exceeded")
        assert Path(path).exists()
        assert Path(path).parent == DLQ_DIR
        assert path.endswith("abc123.json")

    def test_entry_contains_expected_fields(self, sample_task_data):
        """The written JSON includes task_id, sandbox, original_task, error, timestamp."""
        path = send_to_dlq("abc123", sample_task_data, "Timeout exceeded")
        data = json.loads(Path(path).read_text())

        assert data["task_id"] == "abc123"
        assert data["sandbox"] == "test-sandbox"
        assert data["original_task"] == sample_task_data
        assert data["error"] == "Timeout exceeded"
        assert "dlq_timestamp" in data

        # Verify timestamp is ISO format
        datetime.fromisoformat(data["dlq_timestamp"])

    def test_returns_absolute_path(self, sample_task_data):
        """Returned path is an absolute string."""
        path = send_to_dlq("abc123", sample_task_data, "error")
        assert Path(path).is_absolute()

    def test_creates_dlq_dir_if_not_exists(self, sample_task_data):
        """DLQ directory is created automatically."""
        # Remove dir entirely
        import shutil
        shutil.rmtree(DLQ_DIR, ignore_errors=True)

        assert not DLQ_DIR.exists()
        path = send_to_dlq("abc123", sample_task_data, "error")
        assert DLQ_DIR.exists()
        assert Path(path).exists()

    def test_overwrites_existing_entry(self, sample_task_data):
        """Sending the same task_id overwrites the previous file."""
        path1 = send_to_dlq("abc123", sample_task_data, "First error")
        path2 = send_to_dlq("abc123", sample_task_data, "Second error")

        assert path1 == path2
        data = json.loads(Path(path2).read_text())
        assert data["error"] == "Second error"


# ---------------------------------------------------------------------------
# list_dlq
# ---------------------------------------------------------------------------

class TestListDlq:
    def test_empty_when_no_entries(self):
        """list_dlq returns empty list when DLQ is empty."""
        assert list_dlq() == []

    def test_lists_multiple_entries(self, sample_task_data):
        """Multiple DLQ entries are all returned."""
        send_to_dlq("task-a", sample_task_data, "Error A")
        send_to_dlq("task-b", sample_task_data, "Error B")

        entries = list_dlq()
        assert len(entries) == 2

        ids = {e["task_id"] for e in entries}
        assert ids == {"task-a", "task-b"}

    def test_entry_shape(self, sample_task_data):
        """Each entry has task_id, sandbox, error, timestamp."""
        send_to_dlq("abc123", sample_task_data, "my error")
        entries = list_dlq()

        assert len(entries) == 1
        e = entries[0]
        assert e["task_id"] == "abc123"
        assert e["sandbox"] == "test-sandbox"
        assert e["error"] == "my error"
        assert "timestamp" in e
        assert e["timestamp"] != ""

    def test_all_entries_returned(self, sample_task_data):
        """All DLQ entries are returned regardless of write order."""
        DLQ_DIR.mkdir(parents=True, exist_ok=True)

        for tid in ("task-c", "task-a", "task-b"):
            entry = {
                "task_id": tid,
                "sandbox": "s",
                "original_task": sample_task_data,
                "error": "err",
                "dlq_timestamp": "2026-05-24T12:00:00",
            }
            (DLQ_DIR / f"{tid}.json").write_text(json.dumps(entry))

        entries = list_dlq()
        assert len(entries) == 3
        returned_ids = {e["task_id"] for e in entries}
        assert returned_ids == {"task-a", "task-b", "task-c"}

    def test_skips_corrupt_files(self, sample_task_data):
        """Corrupt JSON files are skipped without raising."""
        DLQ_DIR.mkdir(parents=True, exist_ok=True)
        (DLQ_DIR / "good.json").write_text(json.dumps({
            "task_id": "good",
            "sandbox": "s",
            "error": "ok",
            "dlq_timestamp": "2026-05-24T12:00:00",
        }))
        (DLQ_DIR / "bad.json").write_text("not valid json")

        entries = list_dlq()
        assert len(entries) == 1
        assert entries[0]["task_id"] == "good"


# ---------------------------------------------------------------------------
# retry_from_dlq
# ---------------------------------------------------------------------------

class TestRetryFromDlq:
    def test_returns_none_if_not_found(self):
        """retry_from_dlq returns None for non-existent task."""
        assert retry_from_dlq("nonexistent") is None

    def test_returns_none_if_corrupt(self, sample_task_data):
        """retry_from_dlq returns None for corrupt entry."""
        DLQ_DIR.mkdir(parents=True, exist_ok=True)
        (DLQ_DIR / "corrupt.json").write_text("garbage")
        assert retry_from_dlq("corrupt") is None

    def test_returns_none_if_missing_task(self):
        """retry_from_dlq returns None if original_task is empty."""
        DLQ_DIR.mkdir(parents=True, exist_ok=True)
        (DLQ_DIR / "empty.json").write_text(json.dumps({
            "task_id": "empty",
            "sandbox": "s",
            "original_task": {},
            "error": "e",
            "dlq_timestamp": "2026-05-24T12:00:00",
        }))
        assert retry_from_dlq("empty") is None

    def test_returns_none_if_missing_task_field(self):
        """retry_from_dlq returns None if original_task is missing the 'task' key."""
        DLQ_DIR.mkdir(parents=True, exist_ok=True)
        (DLQ_DIR / "notask.json").write_text(json.dumps({
            "task_id": "notask",
            "sandbox": "s",
            "original_task": {"sandbox": "s", "role": "soldier"},
            "error": "e",
            "dlq_timestamp": "2026-05-24T12:00:00",
        }))
        assert retry_from_dlq("notask") is None

    @patch("hero.reliability.dlq.enqueue")
    def test_re_enqueues_task(self, mock_enqueue, sample_task_data):
        """retry_from_dlq calls enqueue with original task params."""
        mock_enqueue.return_value = "new-id-001"
        send_to_dlq("abc123", sample_task_data, "Timeout")

        result = retry_from_dlq("abc123")
        assert result == "new-id-001"

        mock_enqueue.assert_called_once_with(
            sandbox="test-sandbox",
            task="Run the analysis on the test project.",
            role="soldier",
            model="openai/gpt-4",
            model_short="",
            budget=5000,
            workdir="/home/max/Development/Taurus/test-sandbox",
            timeout=300,
            label="",
            max_tokens=8000,
            context_window=131072,
        )

    @patch("hero.reliability.dlq.enqueue")
    def test_removes_dlq_file_on_success(self, mock_enqueue, sample_task_data):
        """The DLQ file is deleted after a successful retry."""
        mock_enqueue.return_value = "new-id-001"
        send_to_dlq("abc123", sample_task_data, "Timeout")

        retry_from_dlq("abc123")
        assert not (DLQ_DIR / "abc123.json").exists()

    @patch("hero.reliability.dlq.enqueue")
    def test_leaves_dlq_file_on_enqueue_failure(self, mock_enqueue, sample_task_data):
        """The DLQ file is kept if enqueue raises."""
        mock_enqueue.side_effect = RuntimeError("enqueue failed")
        send_to_dlq("abc123", sample_task_data, "Timeout")

        result = retry_from_dlq("abc123")
        assert result is None
        assert (DLQ_DIR / "abc123.json").exists()


# ---------------------------------------------------------------------------
# clear_dlq
# ---------------------------------------------------------------------------

class TestClearDlq:
    def test_returns_zero_on_empty(self):
        """clear_dlq returns 0 when no entries match."""
        count = clear_dlq(older_than_days=1)
        assert count == 0

    def test_removes_old_entries(self, sample_task_data):
        """Entries older than the threshold are removed."""
        # Manually write an old entry
        DLQ_DIR.mkdir(parents=True, exist_ok=True)
        old_ts = (datetime.now() - timedelta(days=14)).isoformat()
        old_entry = {
            "task_id": "old-task",
            "sandbox": "s",
            "original_task": sample_task_data,
            "error": "old",
            "dlq_timestamp": old_ts,
        }
        (DLQ_DIR / "old-task.json").write_text(json.dumps(old_entry))

        # Write a recent entry
        fresh_ts = datetime.now().isoformat()
        fresh_entry = {
            "task_id": "fresh-task",
            "sandbox": "s",
            "original_task": sample_task_data,
            "error": "fresh",
            "dlq_timestamp": fresh_ts,
        }
        (DLQ_DIR / "fresh-task.json").write_text(json.dumps(fresh_entry))

        count = clear_dlq(older_than_days=7)
        assert count == 1
        assert not (DLQ_DIR / "old-task.json").exists()
        assert (DLQ_DIR / "fresh-task.json").exists()

    def test_keeps_recent_entries(self, sample_task_data):
        """Entries within the threshold are kept."""
        recent_ts = datetime.now().isoformat()
        DLQ_DIR.mkdir(parents=True, exist_ok=True)
        (DLQ_DIR / "recent.json").write_text(json.dumps({
            "task_id": "recent",
            "sandbox": "s",
            "original_task": sample_task_data,
            "error": "recent",
            "dlq_timestamp": recent_ts,
        }))

        count = clear_dlq(older_than_days=7)
        assert count == 0
        assert (DLQ_DIR / "recent.json").exists()

    def test_ignores_missing_timestamp(self, sample_task_data):
        """Entries without a dlq_timestamp are kept (not auto-cleared)."""
        DLQ_DIR.mkdir(parents=True, exist_ok=True)
        (DLQ_DIR / "no-ts.json").write_text(json.dumps({
            "task_id": "no-ts",
            "sandbox": "s",
            "original_task": sample_task_data,
            "error": "no timestamp",
        }))

        count = clear_dlq(older_than_days=7)
        assert count == 0
        assert (DLQ_DIR / "no-ts.json").exists()

    def test_clear_only_older_not_newer(self, sample_task_data):
        """Entries well before the threshold are removed; entries well after are kept."""
        DLQ_DIR.mkdir(parents=True, exist_ok=True)

        old_ts = (datetime.now() - timedelta(days=30)).isoformat()
        fresh_ts = (datetime.now() - timedelta(hours=1)).isoformat()

        (DLQ_DIR / "old.json").write_text(json.dumps({
            "task_id": "old",
            "sandbox": "s",
            "original_task": sample_task_data,
            "error": "old",
            "dlq_timestamp": old_ts,
        }))
        (DLQ_DIR / "fresh.json").write_text(json.dumps({
            "task_id": "fresh",
            "sandbox": "s",
            "original_task": sample_task_data,
            "error": "fresh",
            "dlq_timestamp": fresh_ts,
        }))

        count = clear_dlq(older_than_days=7)
        assert count == 1
        assert not (DLQ_DIR / "old.json").exists()
        assert (DLQ_DIR / "fresh.json").exists()
