"""Tests for hero.state.cache — StateCache LRU cache with TTL."""

import time
import threading
from pathlib import Path

import pytest

from hero.state.cache import StateCache, CacheEntry, default_cache
from hero.state.sandbox import SandboxState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_sandbox(tmp_path):
    """Create a sandbox directory with minimal TOON files."""
    sandbox_dir = tmp_path / "test-sandbox"
    sandbox_dir.mkdir(parents=True)

    (sandbox_dir / "BUDGET.toon").write_text(
        "bootstrap_max:5000\ncompactions_used:0\ntokens_remaining:5000\n"
    )
    (sandbox_dir / "SKILLS.toon").write_text("skills:[python,rust]\n")
    (sandbox_dir / "MEMORY.toon").write_text("pending:[]\nknown_issues:[]\n")
    (sandbox_dir / "HEARTBEAT.toon").write_text(
        'name:"test-sandbox"\npath:"/tmp/test-sandbox"\nstatus:"idle"\n'
    )
    return tmp_path


# ---------------------------------------------------------------------------
# CacheEntry
# ---------------------------------------------------------------------------

class TestCacheEntry:
    def test_is_valid_before_expiry(self):
        entry = CacheEntry(data={"foo": 1}, ttl=10.0)
        assert entry.is_valid is True

    def test_is_invalid_after_expiry(self):
        entry = CacheEntry(data={"foo": 1}, ttl=0.001)
        time.sleep(0.05)
        assert entry.is_valid is False

    def test_refresh_resets_clock(self):
        entry = CacheEntry(data={"foo": 1}, ttl=0.001)
        time.sleep(0.02)
        entry.refresh()
        assert entry.is_valid is True


# ---------------------------------------------------------------------------
# StateCache — basic lifecycle
# ---------------------------------------------------------------------------

class TestStateCacheBasic:
    def test_initial_state(self):
        cache = StateCache()
        assert len(cache) == 0
        assert "anything" not in cache

    def test_set_and_get_hit(self):
        cache = StateCache()
        state = {"name": "s1", "budget": {"tokens_remaining": 100}}
        cache.set("s1", state)
        result = cache.get("s1")
        assert result == state
        assert result is state  # no copy

    def test_get_miss_returns_none(self):
        cache = StateCache()
        assert cache.get("nonexistent") is None

    def test_get_miss_increments_miss_counter(self):
        cache = StateCache()
        cache.get("missing")
        assert cache.misses == 1
        assert cache.hits == 0

    def test_get_hit_increments_hit_counter(self):
        cache = StateCache()
        cache.set("s1", {})
        cache.get("s1")
        assert cache.hits == 1
        assert cache.misses == 0

    def test_get_expired_entry_returns_none(self):
        cache = StateCache(default_ttl=0)
        cache.set("s1", {"v": 1}, ttl_seconds=0)
        time.sleep(0.05)
        assert cache.get("s1") is None

    def test_set_overwrites_existing(self):
        cache = StateCache()
        cache.set("s1", {"v": 1})
        cache.set("s1", {"v": 2})
        assert cache.get("s1") == {"v": 2}

    def test_invalidate_single(self):
        cache = StateCache()
        cache.set("s1", {})
        cache.set("s2", {})
        cache.invalidate("s1")
        assert cache.get("s1") is None
        assert cache.get("s2") is not None

    def test_invalidate_all(self):
        cache = StateCache()
        cache.set("s1", {})
        cache.set("s2", {})
        cache.invalidate()
        assert cache.get("s1") is None
        assert cache.get("s2") is None

    def test_contains_valid(self):
        cache = StateCache()
        cache.set("s1", {})
        assert "s1" in cache

    def test_contains_expired(self):
        cache = StateCache(default_ttl=0)
        cache.set("s1", {})
        time.sleep(0.05)
        assert "s1" not in cache

    def test_stats(self):
        cache = StateCache()
        cache.set("s1", {})
        cache.set("s2", {})
        cache.get("s1")     # hit
        cache.get("s1")     # hit
        cache.get("ghost")  # miss
        s = cache.stats()
        assert s["hits"] == 2
        assert s["misses"] == 1
        assert s["entries"] == 2
        assert s["valid"] == 2
        assert s["hit_rate"] == pytest.approx(2 / 3, rel=1e-3)

    def test_clear_stats(self):
        cache = StateCache()
        cache.set("s1", {})
        cache.get("s1")
        cache.get("ghost")
        cache.clear_stats()
        assert cache.hits == 0
        assert cache.misses == 0

    def test_invalidate_stale(self):
        cache = StateCache(default_ttl=0)
        cache.set("fresh", {}, ttl_seconds=9999)
        cache.set("stale", {}, ttl_seconds=0)
        time.sleep(0.05)
        removed = cache.invalidate_stale()
        assert removed == 1
        assert cache.get("fresh") is not None
        assert cache.get("stale") is None


# ---------------------------------------------------------------------------
# LRU eviction
# ---------------------------------------------------------------------------

class TestLRUEviction:
    def test_evicts_oldest_when_full(self):
        cache = StateCache(maxsize=3)
        cache.set("a", {})
        cache.set("b", {})
        cache.set("c", {})
        cache.set("d", {})           # should evict "a"
        assert cache.get("a") is None
        assert cache.get("b") is not None
        assert cache.get("c") is not None
        assert cache.get("d") is not None
        assert cache.evictions >= 1

    def test_evictions_counter(self):
        cache = StateCache(maxsize=2)
        cache.set("a", {})
        cache.set("b", {})
        cache.set("c", {})           # evicts "a"
        assert cache.evictions == 1

    def test_access_moves_to_end(self):
        """Accessing an item should mark it most-recently-used."""
        cache = StateCache(maxsize=3)
        cache.set("a", {})
        cache.set("b", {})
        cache.set("c", {})
        cache.get("a")               # moves "a" to end
        cache.set("d", {})           # evicts "b" (now oldest)
        assert cache.get("a") is not None
        assert cache.get("b") is None


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_reads_and_writes(self):
        cache = StateCache()
        errors: list[Exception] = []

        def writer(idx):
            try:
                for i in range(200):
                    cache.set(f"key-{idx}", {"idx": idx, "i": i})
            except Exception as e:
                errors.append(e)

        def reader(idx):
            try:
                for _ in range(200):
                    cache.get(f"key-{idx}")
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(4):
            threads.append(threading.Thread(target=writer, args=(i,)))
            threads.append(threading.Thread(target=reader, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"


# ---------------------------------------------------------------------------
# batch_load — integration with SandboxState
# ---------------------------------------------------------------------------

class TestBatchLoad:
    def test_batch_load_fills_cache(self, tmp_sandbox):
        cache = StateCache()
        base_paths = {"sandbox-a": tmp_sandbox}
        results = cache.batch_load(["sandbox-a"], base_paths=base_paths)
        assert "sandbox-a" in results
        assert results["sandbox-a"]["name"] == "sandbox-a"
        assert len(cache) == 1

    def test_batch_load_cache_hit(self, tmp_sandbox):
        cache = StateCache()
        base_paths = {"sandbox-a": tmp_sandbox}
        cache.batch_load(["sandbox-a"], base_paths=base_paths)
        assert cache.misses == 1

        cache.batch_load(["sandbox-a"], base_paths=base_paths)
        assert cache.hits == 1            # hit counter incremented
        assert cache.misses == 1          # unchanged → no extra disk read

    def test_batch_load_multiple(self, tmp_sandbox):
        cache = StateCache()
        base_paths = {"sandbox-a": tmp_sandbox, "sandbox-b": tmp_sandbox}
        results = cache.batch_load(["sandbox-a", "sandbox-b"], base_paths=base_paths)
        assert set(results.keys()) == {"sandbox-a", "sandbox-b"}
        assert cache.misses == 2

    def test_batch_load_mixed_hit_miss(self, tmp_sandbox):
        cache = StateCache()
        base_paths = {"sandbox-a": tmp_sandbox}
        cache.batch_load(["sandbox-a"], base_paths=base_paths)
        cache.clear_stats()
        base_paths["sandbox-b"] = tmp_sandbox
        results = cache.batch_load(["sandbox-a", "sandbox-b"], base_paths=base_paths)
        assert cache.hits == 1
        assert cache.misses == 1
        assert "sandbox-a" in results
        assert "sandbox-b" in results

    def test_batch_load_empty_list(self):
        cache = StateCache()
        results = cache.batch_load([])
        assert results == {}

    def test_batch_load_expired_entry_refreshes(self, tmp_sandbox):
        cache = StateCache(default_ttl=0)
        base_paths = {"sandbox-a": tmp_sandbox}
        cache.batch_load(["sandbox-a"], base_paths=base_paths)
        assert cache.misses == 1
        time.sleep(0.05)
        cache.batch_load(["sandbox-a"], base_paths=base_paths)
        assert cache.misses == 2   # expired → re-read from disk

    def test_batch_load_respects_maxsize(self, tmp_sandbox):
        cache = StateCache(maxsize=2)
        base_paths = {f"s{i}": tmp_sandbox for i in range(5)}
        cache.batch_load(list(base_paths.keys()), base_paths=base_paths)
        assert len(cache) <= 2

    def test_batch_load_returns_expected_state_shape(self, tmp_sandbox):
        cache = StateCache()
        base_paths = {"sandbox-a": tmp_sandbox}
        result = cache.batch_load(["sandbox-a"], base_paths=base_paths)["sandbox-a"]
        assert "name" in result
        assert "budget" in result
        assert "skills" in result
        assert "katana" in result
        assert "status" in result


# ---------------------------------------------------------------------------
# batch_load with loader kwarg
# ---------------------------------------------------------------------------

class TestBatchLoadWithLoader:
    def _make_shared_sandbox(self, tmp_path):
        """Create a sandbox dir with files that look like 'shared' sandbox."""
        d = tmp_path / "shared"
        d.mkdir(parents=True)
        (d / "BUDGET.toon").write_text(
            "bootstrap_max:5000\ncompactions_used:0\ntokens_remaining:5000\n"
        )
        (d / "SKILLS.toon").write_text("skills:[]\n")
        (d / "MEMORY.toon").write_text("pending:[]\nknown_issues:[]\n")
        (d / "HEARTBEAT.toon").write_text(
            'name:"shared"\npath:"/tmp/shared"\nstatus:"idle"\n'
        )
        return tmp_path

    def test_loader_reused(self, tmp_path):
        """Pass a pre-built SandboxState as loader."""
        self._make_shared_sandbox(tmp_path)
        cache = StateCache()
        loader = SandboxState("shared", base_path=tmp_path)
        results = cache.batch_load(["shared"], loader=loader)
        assert results["shared"]["name"] == "shared"

    def test_cache_hit_skips_disk(self, tmp_path):
        """A second batch_load for the same sandbox must not increment misses."""
        cache = StateCache()
        base_paths = {"s1": tmp_path}
        cache.batch_load(["s1"], base_paths=base_paths)
        assert cache.misses == 1
        cache.batch_load(["s1"], base_paths=base_paths)
        assert cache.misses == 1      # unchanged — disk was not touched
        assert cache.hits == 1


# ---------------------------------------------------------------------------
# Integration: invalidate after mutation
# ---------------------------------------------------------------------------

class TestInvalidateAfterMutation:
    def test_spawn_invalidates_target(self, tmp_sandbox):
        cache = StateCache()
        base_paths = {"s1": tmp_sandbox}
        cache.batch_load(["s1"], base_paths=base_paths)
        assert cache.get("s1") is not None
        cache.invalidate("s1")
        assert cache.get("s1") is None

    def test_batch_invalidate_all_on_scan(self, tmp_sandbox):
        cache = StateCache()
        base_paths = {f"s{i}": tmp_sandbox for i in range(5)}
        cache.batch_load(list(base_paths.keys()), base_paths=base_paths)
        assert len(cache) == 5
        cache.invalidate()
        assert len(cache) == 0
