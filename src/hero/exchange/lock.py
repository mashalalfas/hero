"""Atomic file-based lock using O_CREAT | O_EXCL."""

from __future__ import annotations

import os
import time
from pathlib import Path

from hero.logging import get_logger

logger = get_logger("exchange.lock")

LOCK_DIR = Path.home() / ".hero" / "exchange" / "lock"
DEFAULT_TTL = 300  # 5 minutes


def acquire_lock(name: str, ttl: int = DEFAULT_TTL) -> bool:
    """Try to acquire a named lock. Returns True if acquired."""
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = LOCK_DIR / name
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        logger.debug("Lock acquired", name=name)
        return True
    except FileExistsError:
        # Check if lock is stale
        try:
            age = time.time() - lock_path.stat().st_mtime
            if age > ttl:
                logger.warning("Lock expired, reclaiming", name=name, age_seconds=age)
                lock_path.unlink(missing_ok=True)
                # Retry once
                try:
                    fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.close(fd)
                    return True
                except FileExistsError:
                    return False
        except OSError:
            pass
        return False


def release_lock(name: str) -> None:
    """Release a named lock."""
    lock_path = LOCK_DIR / name
    try:
        lock_path.unlink(missing_ok=True)
        logger.debug("Lock released", name=name)
    except OSError as exc:
        logger.warning("Failed to release lock", name=name, error=str(exc))


def is_locked(name: str) -> bool:
    """Check if a lock exists and is not stale."""
    lock_path = LOCK_DIR / name
    if not lock_path.exists():
        return False
    try:
        age = time.time() - lock_path.stat().st_mtime
        if age > DEFAULT_TTL:
            lock_path.unlink(missing_ok=True)
            return False
        return True
    except OSError:
        return False
