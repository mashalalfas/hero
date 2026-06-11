"""Tests for hero.core.locks (FileLock) and hero.core.exchange."""

from __future__ import annotations

import json
import multiprocessing
import os
import tempfile
import time
from pathlib import Path

import pytest

from hero.core.locks import FileLock


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _isolate_lock_dir(monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect LOCK_DIR to a temp directory so tests are isolated."""
    tmp = tempfile.mkdtemp(prefix="hero_test_locks_")
    monkeypatch.setattr("hero.core.locks.LOCK_DIR", Path(tmp))
    return Path(tmp)


# ── FileLock tests ──────────────────────────────────────────────────────

class TestFileLock:
    """Tests for hero.core.locks.FileLock."""

    def test_acquire_and_release(self) -> None:
        """FileLock is acquired and released correctly."""
        lock = FileLock("test_resource")
        assert lock.fd is None

        with lock:
            assert lock.fd is not None
            lock_path = lock.lock_path
            assert lock_path.exists()
            # Lock file should exist while held
            assert os.path.exists(str(lock_path))

        # After the context exits, fd should be None (released + closed)
        assert lock.fd is None

    def test_lock_path_created(self) -> None:
        """Lock file is created in the correct directory."""
        lock = FileLock("my_lock")
        with lock:
            assert lock.lock_path.exists()
            assert lock.lock_path.suffix == ".lock"
            assert str(lock.lock_path).endswith("my_lock.lock")

    def test_different_resources_dont_block(self) -> None:
        """Two locks on different resource names can be held simultaneously."""
        lock_a = FileLock("resource_a")
        lock_b = FileLock("resource_b")

        with lock_a:
            # Acquiring lock_b should succeed immediately — different resource
            with lock_b:
                assert lock_a.fd is not None
                assert lock_b.fd is not None

    def test_timeout_when_contended(self) -> None:
        """FileLock raises TimeoutError when another process holds the lock.

        Uses a short timeout to keep the test fast.
        """
        # Use a subprocess that holds the lock briefly
        def _holder_worker(lock_dir: str, event: multiprocessing.synchronize.Event) -> None:
            import hero.core.locks as locks_module

            locks_module.LOCK_DIR = Path(lock_dir)
            lock = locks_module.FileLock("timeout_test", timeout=5.0, poll=0.01)
            with lock:
                event.set()  # tell main process "I have the lock"
                time.sleep(1.0)  # hold it for 1 second

        tmpdir = tempfile.mkdtemp(prefix="hero_timeout_test_")
        ready = multiprocessing.Event()
        p = multiprocessing.Process(target=_holder_worker, args=(tmpdir, ready))
        p.start()
        ready.wait(timeout=3)  # wait for subprocess to acquire

        # Now try to acquire with a very short timeout
        import hero.core.locks as locks_module

        locks_module.LOCK_DIR = Path(tmpdir)
        contended = FileLock("timeout_test", timeout=0.3, poll=0.05)
        with pytest.raises(TimeoutError, match="Could not acquire lock"):
            with contended:
                pass  # should not reach here

        p.join(timeout=3)

    def test_reentrant_same_process(self) -> None:
        """Within the same process, FileLock can be acquired again after release."""
        lock = FileLock("reentrant_test")
        with lock:
            pass  # release

        # Should be able to re-acquire
        with lock:
            assert lock.fd is not None

    def test_lock_exclusive_across_threads(self) -> None:
        """Two threads in the same process both wait but only one holds at a time."""
        import threading

        held = threading.Event()
        released = threading.Event()
        errors: list[str] = []

        def worker1() -> None:
            lock = FileLock("thread_test", timeout=5.0, poll=0.01)
            with lock:
                held.set()  # I have it
                time.sleep(0.2)
            released.set()  # I released

        def worker2() -> None:
            lock = FileLock("thread_test", timeout=5.0, poll=0.01)
            try:
                with lock:
                    # If we get here while worker1 still holds, that's a bug
                    if not released.is_set():
                        errors.append("worker2 acquired while worker1 still held")
            except TimeoutError:
                errors.append("worker2 timed out unexpectedly")

        t1 = threading.Thread(target=worker1)
        t2 = threading.Thread(target=worker2)
        t1.start()
        held.wait(timeout=1)
        t2.start()
        t1.join(timeout=3)
        t2.join(timeout=3)

        assert not errors, f"Lock exclusivity violations: {errors}"

    def test_cleanup_on_file_not_exists(self) -> None:
        """Even if the lock file is removed while held, __exit__ is safe."""
        lock = FileLock("ephemeral")
        fd_before = None
        with lock:
            fd_before = lock.fd
            # Simulate external cleanup — delete the lock file
            try:
                os.unlink(str(lock.lock_path))
            except OSError:
                pass

        # Should not raise; fd was closed
        assert lock.fd is None
        assert fd_before is not None

    def test_default_timeout(self) -> None:
        """Default timeout is 30.0 seconds."""
        lock = FileLock("defaults")
        assert lock.timeout == 30.0
        assert lock.poll == 0.1

    def test_custom_timeout_and_poll(self) -> None:
        """Custom timeout and poll values are stored."""
        lock = FileLock("custom", timeout=5.0, poll=0.5)
        assert lock.timeout == 5.0
        assert lock.poll == 0.5


# ── Exchange tests ──────────────────────────────────────────────────────

class TestExchange:
    """Tests for hero.core.exchange."""

    @pytest.fixture(autouse=True)
    def _isolate_exchange_dir(self, monkeypatch: pytest.MonkeyPatch) -> Path:
        """Redirect EXCHANGE_DIR to a temp directory."""
        import hero.core.exchange as exc_mod

        tmp = tempfile.mkdtemp(prefix="hero_test_exchange_")
        monkeypatch.setattr(exc_mod, "EXCHANGE_DIR", Path(tmp))
        monkeypatch.setattr(exc_mod, "CHANNEL_DIR", Path(tmp) / "channels")
        return Path(tmp)

    def test_post_and_read_messages(self) -> None:
        """Messages posted can be read back in order."""
        from hero.core.exchange import post_message, read_messages

        post_message("test_chan", "soldier_a", {"greeting": "hello", "seq": 1})
        post_message("test_chan", "soldier_b", {"greeting": "hi", "seq": 1})
        post_message("test_chan", "soldier_a", {"greeting": "hello again", "seq": 2})

        msgs = read_messages("test_chan")
        assert len(msgs) == 3
        # Messages are sorted by filename: "soldier_a-0001", "soldier_a-0002", "soldier_b-0001"
        assert msgs[0]["greeting"] == "hello"
        assert msgs[1]["greeting"] == "hello again"
        assert msgs[2]["greeting"] == "hi"

    def test_post_message_returns_path(self) -> None:
        """post_message returns the file path it wrote to."""
        from hero.core.exchange import post_message

        path = post_message("chan", "sol_x", {"key": "value"})
        assert path.exists()
        assert path.suffix == ".json"
        assert "sol_x" in str(path)
        assert "-0001" in str(path)

        data = json.loads(path.read_text())
        assert data["key"] == "value"

    def test_read_empty_channel(self) -> None:
        """read_messages returns empty list for non-existent channel."""
        from hero.core.exchange import read_messages

        msgs = read_messages("nonexistent")
        assert msgs == []

    def test_read_empty_messages_dir(self) -> None:
        """read_messages returns empty list when channel dir exists but is empty."""
        from hero.core.exchange import ensure_channel, read_messages

        ensure_channel("empty_chan")
        msgs = read_messages("empty_chan")
        assert msgs == []

    def test_read_state(self) -> None:
        """read_state returns state dict or None."""
        from hero.core.exchange import read_state, write_state

        # No state yet
        assert read_state("state_chan") is None

        write_state("state_chan", {"mode": "smart", "iterations": 3})
        state = read_state("state_chan")
        assert state is not None
        assert state["mode"] == "smart"
        assert state["iterations"] == 3

    def test_write_state_overwrites(self) -> None:
        """write_state overwrites the previous state."""
        from hero.core.exchange import read_state, write_state

        write_state("overwrite_chan", {"version": 1})
        write_state("overwrite_chan", {"version": 2, "extra": True})

        state = read_state("overwrite_chan")
        assert state is not None
        assert state["version"] == 2
        assert state["extra"] is True

    def test_ensure_channel(self) -> None:
        """ensure_channel creates the messages directory."""
        from hero.core.exchange import ensure_channel

        path = ensure_channel("bootstrap")
        assert path.exists()
        assert path.is_dir()
        assert path.name == "messages"

    def test_post_message_sequence_ordering(self) -> None:
        """Sequence numbers increment correctly per soldier."""
        from hero.core.exchange import post_message, read_messages

        post_message("seq_chan", "a", {"n": 1})
        post_message("seq_chan", "a", {"n": 2})
        post_message("seq_chan", "b", {"n": 1})
        post_message("seq_chan", "a", {"n": 3})

        msgs = read_messages("seq_chan")

        nums = [m["n"] for m in msgs]
        assert nums == [1, 2, 3, 1]

    def test_message_round_trip(self) -> None:
        """Full round-trip: post complex message → read it back intact."""
        from hero.core.exchange import post_message, read_messages

        complex_msg = {
            "soldier": "architect-7",
            "phase": "design",
            "data": {"layers": ["domain", "application", "infrastructure"]},
            "timestamp": "2026-06-09T13:57:00",
            "nested": {"deep": {"value": 42}},
        }
        post_message("roundtrip", "architect-7", complex_msg)
        msgs = read_messages("roundtrip")
        assert len(msgs) == 1
        assert msgs[0] == complex_msg


# ── Integration: lock + exchange together ───────────────────────────────

class TestLockAndExchange:
    """Verify that locks and exchange work together in realistic scenarios."""

    @pytest.fixture(autouse=True)
    def _isolate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Isolate both lock and exchange directories."""
        import hero.core.exchange as exc_mod
        import hero.core.locks as lock_mod

        lock_dir = tempfile.mkdtemp(prefix="hero_int_lock_")
        exc_dir = tempfile.mkdtemp(prefix="hero_int_exc_")
        monkeypatch.setattr(lock_mod, "LOCK_DIR", Path(lock_dir))
        monkeypatch.setattr(exc_mod, "EXCHANGE_DIR", Path(exc_dir))
        monkeypatch.setattr(exc_mod, "CHANNEL_DIR", Path(exc_dir) / "channels")

    def test_write_state_under_lock(self) -> None:
        """write_state uses FileLock to serialise concurrent writes."""
        from hero.core.exchange import read_state, write_state
        from hero.core.locks import FileLock

        # write_state internally acquires FileLock("exchange_state_test_lock")
        write_state("test_lock", {"count": 1})
        state = read_state("test_lock")
        assert state == {"count": 1}

        # Simulate concurrent state write from another "process" in same thread
        # This works because the first write releases the lock after writing
        write_state("test_lock", {"count": 2})
        state = read_state("test_lock")
        assert state == {"count": 2}

    def test_same_channel_multiple_soldiers(self) -> None:
        """Multiple soldiers can post to the same channel without contention."""
        from hero.core.exchange import post_message, read_messages

        CHANNEL = "multi_soldier"
        soldier_ids = [f"soldier_{i}" for i in range(5)]
        for sid in soldier_ids:
            for seq in range(3):
                post_message(CHANNEL, sid, {"soldier": sid, "seq": seq})

        msgs = read_messages(CHANNEL)
        assert len(msgs) == 15  # 5 soldiers × 3 messages

        # Each soldier's messages are sequential
        for sid in soldier_ids:
            soldier_msgs = [m for m in msgs if m["soldier"] == sid]
            assert [m["seq"] for m in soldier_msgs] == [0, 1, 2]
