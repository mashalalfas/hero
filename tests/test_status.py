"""Tests for hero.state.status — per-sub-agent status files."""

from __future__ import annotations

import json
import time

import pytest

from hero.state.status import (
    STATUS_DIR,
    clean_status,
    list_status,
    read_status,
    write_status,
)


@pytest.fixture(autouse=True)
def _isolate_status_dir(tmp_path, monkeypatch):
    """Redirect STATUS_DIR to a temp dir for every test."""
    test_dir = tmp_path / "status"
    test_dir.mkdir()
    monkeypatch.setattr("hero.state.status.STATUS_DIR", test_dir)
    yield
    # tmp_path auto-cleanup


def _write(task_id: str, **kwargs) -> None:
    write_status(task_id, {"task_id": task_id, **kwargs})


def test_write_and_read_roundtrip():
    _write("t1", sandbox="proj", status="completed", score=90)
    data = read_status("t1")
    assert data is not None
    assert data["task_id"] == "t1"
    assert data["sandbox"] == "proj"
    assert data["status"] == "completed"
    assert data["score"] == 90
    assert "_updated_at" in data


def test_read_missing_returns_none():
    assert read_status("does-not-exist") is None


def test_overwrite_is_atomic():
    _write("t1", status="pending")
    time.sleep(0.01)
    _write("t1", status="completed")
    data = read_status("t1")
    assert data["status"] == "completed"
    # tmp artifact should not survive
    assert not list(STATUS_DIR.glob("*.tmp"))


def test_list_status_empty_when_no_files():
    assert list_status() == []


def test_list_status_sorted_newest_first():
    _write("old", status="completed")
    time.sleep(0.02)
    _write("new", status="completed")
    results = list_status()
    assert [r["task_id"] for r in results] == ["new", "old"]


def test_list_status_filter_by_sandbox():
    _write("a", sandbox="alpha", status="completed")
    _write("b", sandbox="beta", status="completed")
    results = list_status(sandbox="alpha")
    assert [r["task_id"] for r in results] == ["a"]


def test_clean_status_removes_old():
    _write("old", status="completed")
    # Back-date the file so it looks >24h old
    import hero.state.status as _status_mod
    old_file = _status_mod.STATUS_DIR / "old.json"
    assert old_file.exists(), f"expected old.json at {old_file}"
    old_time = time.time() - (25 * 3600)
    import os
    os.utime(old_file, (old_time, old_time))

    _write("fresh", status="completed")
    removed = clean_status(age_hours=24)
    assert removed == 1
    assert read_status("old") is None
    assert read_status("fresh") is not None


def test_clean_status_noop_on_empty_dir(tmp_path, monkeypatch):
    """clean_status should not raise when directory is empty."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.setattr("hero.state.status.STATUS_DIR", empty_dir)
    assert clean_status(age_hours=1) == 0


def test_write_adds_timestamp():
    before = time.time()
    _write("t1", status="completed")
    after = time.time()
    data = read_status("t1")
    assert before <= data["_updated_at"] <= after
