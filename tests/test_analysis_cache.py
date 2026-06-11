"""Tests for hero.analysis_cache — memoized analyzer results."""

import json
import time
from pathlib import Path

import pytest

from hero.analysis_cache import (
    cached_analyze,
    get_cached,
    set_cached,
    invalidate,
    _cache_key,
    _hash_paths,
)


CACHE_DIR = Path.home() / ".hero" / "cache" / "analysis"


@pytest.fixture(autouse=True)
def clean_cache():
    """Clear analysis cache before and after each test."""
    invalidate()
    yield
    invalidate()


class TestHashPaths:
    def test_same_files_same_hash(self, tmp_path):
        f1 = tmp_path / "a.dart"
        f1.write_text("hello")
        time.sleep(0.01)  # ensure mtime differs if we touch it
        h1 = _hash_paths([f1])
        h2 = _hash_paths([f1])
        assert h1 == h2

    def test_different_mtime_different_hash(self, tmp_path):
        f1 = tmp_path / "a.dart"
        f1.write_text("hello")
        h1 = _hash_paths([f1])
        time.sleep(0.01)
        f1.write_text("world")  # changes mtime
        h2 = _hash_paths([f1])
        assert h1 != h2

    def test_missing_file_handled(self, tmp_path):
        # File doesn't exist yet — should not crash
        h = _hash_paths([tmp_path / "nonexistent.dart"])
        assert isinstance(h, str)
        assert len(h) == 16


class TestCacheKey:
    def test_same_params_same_key(self, tmp_path):
        k1 = _cache_key(tmp_path, ["flutter", "analyze"], ["lib/**/*.dart"])
        k2 = _cache_key(tmp_path, ["flutter", "analyze"], ["lib/**/*.dart"])
        assert k1 == k2

    def test_different_command_different_key(self, tmp_path):
        k1 = _cache_key(tmp_path, ["flutter", "analyze"])
        k2 = _cache_key(tmp_path, ["npm", "run", "lint"])
        assert k1 != k2

    def test_different_sandbox_different_key(self, tmp_path):
        k1 = _cache_key(tmp_path / "a", ["echo"])
        k2 = _cache_key(tmp_path / "b", ["echo"])
        assert k1 != k2


class TestSetGetCached:
    def test_set_and_get(self, tmp_path):
        result = {"success": True, "exit_code": 0, "output": "clean"}
        set_cached(tmp_path, ["echo", "test"], result)
        cached = get_cached(tmp_path, ["echo", "test"])
        assert cached is not None
        assert cached["result"]["success"] is True
        assert cached["result"]["output"] == "clean"

    def test_get_miss_returns_none(self, tmp_path):
        assert get_cached(tmp_path, ["nonexistent"]) is None

    def test_expired_entry_returns_none(self, tmp_path):
        set_cached(tmp_path, ["echo"], {"success": True})
        # get with ttl=0 should immediately expire
        assert get_cached(tmp_path, ["echo"], ttl=0) is None

    def test_cached_entry_survives_within_ttl(self, tmp_path):
        set_cached(tmp_path, ["echo"], {"success": True})
        # get with ttl=10 should succeed
        cached = get_cached(tmp_path, ["echo"], ttl=10)
        assert cached is not None
        assert cached["result"]["success"] is True


class TestCachedAnalyze:
    def test_first_call_runs_subprocess(self, tmp_path):
        result = cached_analyze(["echo", "hello"], tmp_path)
        assert result["cached"] is False
        assert result["success"] is True

    def test_second_call_returns_cached(self, tmp_path):
        cached_analyze(["echo", "first"], tmp_path)
        result = cached_analyze(["echo", "first"], tmp_path)
        assert result["cached"] is True
        assert result["success"] is True

    def test_cache_age_in_result(self, tmp_path):
        cached_analyze(["echo"], tmp_path)
        time.sleep(0.1)
        result = cached_analyze(["echo"], tmp_path)
        assert result["cached"] is True
        assert result["cached_at"] > 0

    def test_different_command_different_cache(self, tmp_path):
        cached_analyze(["echo", "a"], tmp_path)
        result = cached_analyze(["echo", "b"], tmp_path)
        assert result["cached"] is False  # different command = cache miss

    def test_with_source_globs(self, tmp_path):
        # Create a source file so the glob matches something
        (tmp_path / "main.dart").write_text("void main() {}")
        result = cached_analyze(
            ["echo", "flutter"],
            tmp_path,
            source_globs=["**/*.dart"],
        )
        assert result["cached"] is False
        # Second call with same globs should hit
        result2 = cached_analyze(
            ["echo", "flutter"],
            tmp_path,
            source_globs=["**/*.dart"],
        )
        assert result2["cached"] is True

    def test_source_file_change_invalidates(self, tmp_path):
        (tmp_path / "main.dart").write_text("v1")
        cached_analyze(["echo"], tmp_path, source_globs=["**/*.dart"])
        result1 = cached_analyze(["echo"], tmp_path, source_globs=["**/*.dart"])
        assert result1["cached"] is True

        # Modify source file — should get a cache miss
        time.sleep(0.01)
        (tmp_path / "main.dart").write_text("v2")
        result2 = cached_analyze(["echo"], tmp_path, source_globs=["**/*.dart"])
        assert result2["cached"] is False


class TestInvalidate:
    def test_invalidate_all(self, tmp_path):
        cached_analyze(["echo", "a"], tmp_path)
        cached_analyze(["echo", "b"], tmp_path)
        assert len(list(CACHE_DIR.glob("*.json"))) == 2
        removed = invalidate()
        assert removed == 2
        assert len(list(CACHE_DIR.glob("*.json"))) == 0

    def test_invalidate_sandbox(self, tmp_path):
        tmp2 = Path(tmp_path) / "other"
        tmp2.mkdir()
        cached_analyze(["echo"], tmp_path)
        cached_analyze(["echo"], tmp2)
        assert len(list(CACHE_DIR.glob("*.json"))) == 2
        removed = invalidate(tmp_path)
        assert removed == 1
        assert len(list(CACHE_DIR.glob("*.json"))) == 1
