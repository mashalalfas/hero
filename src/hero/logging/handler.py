"""Structured JSONL logger with rotation and level filtering."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

_LOG_DIR = Path.home() / ".hero" / "logs"
_CONFIG_PATH = Path.home() / ".hero" / "config.yaml"
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
_MAX_ROTATED = 3

_LEVELS: dict[str, int] = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
}

_write_lock = threading.Lock()

# Lazy-loaded level cache: None means "not yet loaded"
_level_cache: int | None = None
_level_lock = threading.Lock()


def _load_level() -> int:
    """Load the configured logging level from config.yaml (default INFO).

    Supports both WARNING and WARN as level names.
    """
    try:
        if _CONFIG_PATH.exists():
            raw = _CONFIG_PATH.read_text()
            cfg = yaml.safe_load(raw) or {}
            level_str = cfg.get("logging", {}).get("level", "INFO").upper()
            # Normalize WARN to WARNING
            if level_str == "WARN":
                level_str = "WARNING"
            return _LEVELS.get(level_str, 20)
    except Exception:
        pass
    return 20  # INFO


def _get_level() -> int:
    """Thread-safe lazy access to configured level."""
    global _level_cache
    if _level_cache is None:
        with _level_lock:
            if _level_cache is None:
                _level_cache = _load_level()
    return _level_cache


def _ensure_log_dir() -> None:
    """Create log directory if it doesn't exist."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)


def _log_file() -> Path:
    """Return the current log file path, derived from _LOG_DIR.

    Using a function instead of a module-level constant allows
    tests to patch _LOG_DIR without stale _LOG_FILE references.
    """
    return _LOG_DIR / "hero.jsonl"


def _rotate_logs() -> None:
    """Rotate hero.jsonl when it exceeds max size.

    Renames current file to hero.jsonl.1, shifts existing .N files up,
    keeps at most _MAX_ROTATED old files.
    """
    log_path = _log_file()
    if not log_path.exists():
        return
    if log_path.stat().st_size < _MAX_BYTES:
        return

    # Shift existing rotated files upward
    for i in range(_MAX_ROTATED - 1, 0, -1):
        src = log_path.with_name(f"hero.jsonl.{i}")
        dst = log_path.with_name(f"hero.jsonl.{i + 1}")
        if src.exists():
            dst.unlink(missing_ok=True)
            src.rename(dst)

    # Rename current log to .1
    dst = log_path.with_name("hero.jsonl.1")
    dst.unlink(missing_ok=True)
    log_path.rename(dst)


class Logger:
    """Structured JSONL logger.

    Writes one JSON object per line to ~/.hero/logs/hero.jsonl.
    Thread-safe, auto-rotating at 10 MB, configurable level filtering.
    """

    def __init__(self, ns: str) -> None:
        self._ns = ns

    def _log(self, level: str, detail: str, **extra: Any) -> None:
        configured = _get_level()
        level_num = _LEVELS.get(level, 20)
        if level_num < configured:
            return

        now = datetime.now(timezone.utc)
        ts = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"

        record: dict[str, Any] = {
            "ts": ts,
            "level": level,
            "ns": self._ns,
            "detail": detail,
        }
        record.update(extra)

        line = json.dumps(record, sort_keys=False, ensure_ascii=False) + "\n"

        with _write_lock:
            _ensure_log_dir()
            _rotate_logs()
            with _log_file().open("a", encoding="utf-8") as fh:
                fh.write(line)

    def debug(self, detail: str, **extra: Any) -> None:
        """Log at DEBUG level."""
        self._log("DEBUG", detail, **extra)

    def info(self, detail: str, **extra: Any) -> None:
        """Log at INFO level."""
        self._log("INFO", detail, **extra)

    def warning(self, detail: str, **extra: Any) -> None:
        """Log at WARNING level."""
        self._log("WARNING", detail, **extra)

    def error(self, detail: str, **extra: Any) -> None:
        """Log at ERROR level."""
        self._log("ERROR", detail, **extra)
