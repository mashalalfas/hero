"""Tests for structured JSONL logging system."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from hero.logging import get_logger


@pytest.fixture(autouse=True)
def _reset_logger_cache() -> None:
    """Reset the in-module logger cache between tests."""
    import hero.logging

    hero.logging._loggers.clear()


@pytest.fixture
def tmp_log_dir() -> Path:
    """Provide a temporary log directory, isolated from real ~/.hero."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def tmp_config(tmp_log_dir: Path) -> Path:
    """Create a temporary config.yaml with DEBUG level."""
    cfg = tmp_log_dir / "config.yaml"
    cfg.write_text("logging:\n  level: DEBUG\n")
    return cfg


def _patch_env(log_dir: Path, config_path: Path) -> None:
    """Point the handler module at a temporary log dir and config.

    Directly sets module globals so they're effective immediately.
    Also resets the level cache so the next log call reads from the
    patched config path.
    """
    import hero.logging.handler as hnd

    hnd._LOG_DIR = log_dir
    hnd._CONFIG_PATH = config_path
    hnd._level_cache = None


class TestJsonlFormat:
    """Verify JSONL output format matches specification."""

    def test_basic_log_line(self, tmp_log_dir: Path, tmp_config: Path) -> None:
        """A single info call produces one valid JSON line."""
        _patch_env(tmp_log_dir, tmp_config)

        logger = get_logger("test_ns")
        logger.info("hello world", custom_key=42)

        log_file = tmp_log_dir / "hero.jsonl"
        assert log_file.exists()

        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 1

        record = json.loads(lines[0])
        assert record["level"] == "INFO"
        assert record["ns"] == "test_ns"
        assert record["detail"] == "hello world"
        assert record["custom_key"] == 42
        assert "ts" in record
        assert record["ts"].endswith("Z")

    def test_error_log(self, tmp_log_dir: Path, tmp_config: Path) -> None:
        """Error log includes level and extra fields."""
        _patch_env(tmp_log_dir, tmp_config)

        logger = get_logger("test_error")
        logger.error("spawn failed", sandbox="sook-pro", error="timeout")

        log_file = tmp_log_dir / "hero.jsonl"
        assert log_file.exists()

        record = json.loads(log_file.read_text().strip())
        assert record["level"] == "ERROR"
        assert record["ns"] == "test_error"
        assert record["detail"] == "spawn failed"
        assert record["sandbox"] == "sook-pro"
        assert record["error"] == "timeout"

    def test_warning_log(self, tmp_log_dir: Path, tmp_config: Path) -> None:
        """Warning log includes extra structured fields."""
        _patch_env(tmp_log_dir, tmp_config)

        logger = get_logger("budget")
        logger.warning("Budget low", sandbox="freya", tokens_remaining=200)

        log_file = tmp_log_dir / "hero.jsonl"
        record = json.loads(log_file.read_text().strip())
        assert record["level"] == "WARNING"
        assert record["ns"] == "budget"
        assert record["tokens_remaining"] == 200

    def test_multiple_lines(self, tmp_log_dir: Path, tmp_config: Path) -> None:
        """Multiple log calls produce separate JSON lines."""
        _patch_env(tmp_log_dir, tmp_config)

        logger = get_logger("multi")
        logger.info("first")
        logger.info("second")
        logger.info("third")

        log_file = tmp_log_dir / "hero.jsonl"
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 3
        for i, line in enumerate(lines):
            record = json.loads(line)
            assert record["detail"] in ("first", "second", "third")


class TestRotation:
    """Verify log rotation at 10MB boundary."""

    def test_rotation_shifts_files(self, tmp_log_dir: Path, tmp_config: Path) -> None:
        """When log exceeds max bytes, current file moves to .1 and .N files shift."""
        import hero.logging.handler as hnd

        _patch_env(tmp_log_dir, tmp_config)

        orig_max = hnd._MAX_BYTES
        hnd._MAX_BYTES = 300

        try:
            logger = get_logger("rotate_test")

            # Write enough to trigger multiple rotations
            for _ in range(100):
                logger.info("padding " + "x" * 80)

            log_file = tmp_log_dir / "hero.jsonl"
            rotated_1 = tmp_log_dir / "hero.jsonl.1"
            rotated_2 = tmp_log_dir / "hero.jsonl.2"
            rotated_3 = tmp_log_dir / "hero.jsonl.3"

            assert log_file.exists()

            # At least one rotated file should exist
            any_rotated = rotated_1.exists() or rotated_2.exists() or rotated_3.exists()
            assert any_rotated, "No rotated files created"

            # All existing rotated files should contain valid JSONL
            for f in (rotated_1, rotated_2, rotated_3):
                if f.exists():
                    assert f.stat().st_size > 0, f"{f.name} is empty"
                    for line in f.read_text().strip().splitlines():
                        if line.strip():
                            json.loads(line)  # raises on corrupt

            # Current file should also contain valid JSONL
            for line in log_file.read_text().strip().splitlines():
                if line.strip():
                    json.loads(line)

        finally:
            hnd._MAX_BYTES = orig_max

    def test_concurrent_writes_no_corruption(self, tmp_log_dir: Path, tmp_config: Path) -> None:
        """Concurrent writes never produce corrupt JSON, even during rotation."""
        import concurrent.futures
        import threading

        import hero.logging.handler as hnd

        _patch_env(tmp_log_dir, tmp_config)

        orig_max = hnd._MAX_BYTES
        hnd._MAX_BYTES = 1000

        try:
            logger = get_logger("concurrent")
            barrier = threading.Barrier(8)

            def _write(idx: int) -> None:
                barrier.wait()
                for _ in range(25):
                    logger.info(f"t-{idx}", seq=idx)

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                futures = [pool.submit(_write, i) for i in range(8)]
                concurrent.futures.wait(futures)

            log_file = tmp_log_dir / "hero.jsonl"
            rotated_files = list(tmp_log_dir.glob("hero.jsonl.*"))
            all_files = [log_file] + rotated_files

            total_lines = 0
            bad_lines = []

            for f in all_files:
                if f.exists():
                    for lineno, line in enumerate(f.read_text().strip().splitlines(), 1):
                        if line.strip():
                            try:
                                json.loads(line)
                            except json.JSONDecodeError as exc:
                                bad_lines.append((f.name, lineno, str(exc)))
                            total_lines += 1

            assert not bad_lines, f"Corrupt JSON lines: {bad_lines[:5]}"

            # Rotation may discard old lines, but at least some should remain
            # (with MAX_BYTES=1000, each file holds ~10 lines, and we keep
            # current + 3 rotated = ~40 lines minimum)
            assert total_lines > 10, f"Too few valid log lines after rotation: {total_lines}"

        finally:
            hnd._MAX_BYTES = orig_max


class TestLevelFiltering:
    """Verify level filtering from config.yaml."""

    def test_info_passes_with_info_level(self, tmp_log_dir: Path) -> None:
        """With level=INFO, info calls pass, debug calls are filtered."""
        cfg_path = tmp_log_dir / "config.yaml"
        cfg_path.write_text("logging:\n  level: INFO\n")
        _patch_env(tmp_log_dir, cfg_path)

        logger = get_logger("filter")
        logger.debug("should not appear")
        logger.info("should appear")

        log_file = tmp_log_dir / "hero.jsonl"
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["detail"] == "should appear"

    def test_debug_passes_with_debug_level(self, tmp_log_dir: Path) -> None:
        """With level=DEBUG, both debug and info calls pass."""
        cfg_path = tmp_log_dir / "config.yaml"
        cfg_path.write_text("logging:\n  level: DEBUG\n")
        _patch_env(tmp_log_dir, cfg_path)

        logger = get_logger("filter")
        logger.debug("debug msg")
        logger.info("info msg")

        log_file = tmp_log_dir / "hero.jsonl"
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 2

    def test_default_level_is_info(self, tmp_log_dir: Path) -> None:
        """Without config, default level is INFO so debug is filtered."""
        cfg_path = tmp_log_dir / "config.yaml"
        # Write config with no logging section
        cfg_path.write_text("version: '1.0'\n")
        _patch_env(tmp_log_dir, cfg_path)

        logger = get_logger("default")
        logger.debug("should not appear")
        logger.warning("warning appears")

        log_file = tmp_log_dir / "hero.jsonl"
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["detail"] == "warning appears"

    def test_error_always_passes(self, tmp_log_dir: Path) -> None:
        """Even with level=ERROR, error calls produce output."""
        cfg_path = tmp_log_dir / "config.yaml"
        cfg_path.write_text("logging:\n  level: ERROR\n")
        _patch_env(tmp_log_dir, cfg_path)

        logger = get_logger("always")
        logger.info("should not appear")
        logger.error("should appear")

        log_file = tmp_log_dir / "hero.jsonl"
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["detail"] == "should appear"


class TestGetLogger:
    """Verify get_logger caching and API."""

    def test_same_name_returns_same_instance(self) -> None:
        """get_logger with same name returns cached instance."""
        a = get_logger("mymodule")
        b = get_logger("mymodule")
        assert a is b

    def test_different_names_different_instances(self) -> None:
        """get_logger with different names returns different instances."""
        a = get_logger("module_a")
        b = get_logger("module_b")
        assert a is not b

    def test_get_logger_importable(self) -> None:
        """get_logger is importable from hero.logging."""
        from hero.logging import get_logger as gl

        assert callable(gl)
