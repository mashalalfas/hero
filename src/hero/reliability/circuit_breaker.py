"""Circuit breaker — tracks consecutive failures per sandbox and quarantines bad ones.

When a sandbox accumulates >= 3 consecutive failures, it's quarantined.
Quarantine auto-resets after 10 minutes (stale cooldown) or via explicit unquarantine.

Storage: ~/.hero/circuit_breaker.json
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hero.logging import get_logger

FAILURE_FILE = Path.home() / ".hero" / "circuit_breaker.json"

_write_lock = threading.Lock()
logger = get_logger("circuit_breaker")

STALE_COOLDOWN_SECONDS = 600  # 10 minutes


def _load() -> dict[str, Any]:
    """Load circuit breaker state from disk. Returns empty dict on failure."""
    try:
        if FAILURE_FILE.exists():
            raw = FAILURE_FILE.read_text()
            if not raw.strip():
                return {"sandboxes": {}}
            data = json.loads(raw)
            if isinstance(data, dict) and "sandboxes" in data:
                return data
            return {"sandboxes": {}}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read circuit breaker file", error=str(exc))
        return {"sandboxes": {}}
    return {"sandboxes": {}}


def _save(state: dict[str, Any]) -> None:
    """Atomically save circuit breaker state to disk."""
    try:
        FAILURE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = FAILURE_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
        tmp.replace(FAILURE_FILE)
    except OSError as exc:
        logger.error("Failed to write circuit breaker file", error=str(exc))


def _ensure_sandbox(state: dict[str, Any], sandbox: str) -> dict[str, Any]:
    """Return the sandbox entry, creating a default if missing."""
    sandboxes = state.setdefault("sandboxes", {})
    if sandbox not in sandboxes:
        now = datetime.now(timezone.utc).isoformat()
        sandboxes[sandbox] = {
            "consecutive_failures": 0,
            "last_failure": now,
            "status": "active",
        }
    return sandboxes[sandbox]


def record_failure(sandbox: str) -> bool:
    """Increment consecutive_failures for a sandbox.

    If failures >= 3, sets status to "quarantined".
    Returns True if the sandbox is now quarantined, False otherwise.
    """
    with _write_lock:
        state = _load()
        entry = _ensure_sandbox(state, sandbox)
        entry["consecutive_failures"] = entry.get("consecutive_failures", 0) + 1
        entry["last_failure"] = datetime.now(timezone.utc).isoformat()

        if entry["consecutive_failures"] >= 3:
            entry["status"] = "quarantined"
            logger.warning(
                "Sandbox quarantined",
                sandbox=sandbox,
                failures=entry["consecutive_failures"],
            )
            _save(state)
            return True

        _save(state)
        return False


def record_success(sandbox: str) -> None:
    """Reset consecutive_failures to 0 and set status to 'active'."""
    with _write_lock:
        state = _load()
        entry = _ensure_sandbox(state, sandbox)
        was_quarantined = entry.get("status") == "quarantined"
        entry["consecutive_failures"] = 0
        entry["status"] = "active"

        _save(state)

        if was_quarantined:
            logger.info(
                "Sandbox unquarantined via successful operation",
                sandbox=sandbox,
            )


def is_quarantined(sandbox: str) -> bool:
    """Check if a sandbox is quarantined.

    If the sandbox is quarantined but the last failure was more than
    STALE_COOLDOWN_SECONDS (600s / 10 min) ago, auto-resets it to active.

    Returns True if the sandbox is currently quarantined (and not stale).
    """
    with _write_lock:
        state = _load()
        sandboxes = state.get("sandboxes", {})
        entry = sandboxes.get(sandbox)
        if entry is None:
            return False

        if entry.get("status") != "quarantined":
            return False

        # Check stale cooldown
        last_failure_str = entry.get("last_failure", "")
        if last_failure_str:
            try:
                last_failure = datetime.fromisoformat(last_failure_str)
                now = datetime.now(timezone.utc)
                # Normalize naive datetime to UTC for comparison
                if last_failure.tzinfo is None:
                    last_failure = last_failure.replace(tzinfo=timezone.utc)
                elapsed = (now - last_failure).total_seconds()
                if elapsed >= STALE_COOLDOWN_SECONDS:
                    entry["consecutive_failures"] = 0
                    entry["status"] = "active"
                    _save(state)
                    logger.info(
                        "Sandbox auto-unquarantined (stale cooldown expired)",
                        sandbox=sandbox,
                        elapsed_seconds=int(elapsed),
                    )
                    return False
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Failed to parse last_failure timestamp",
                    sandbox=sandbox,
                    error=str(exc),
                )
                # Can't validate — assume still quarantined
                return True

        return True


def unquarantine(sandbox: str) -> None:
    """Force reset a sandbox to active, clearing failure count."""
    with _write_lock:
        state = _load()
        sandboxes = state.get("sandboxes", {})
        if sandbox in sandboxes:
            sandboxes[sandbox]["consecutive_failures"] = 0
            sandboxes[sandbox]["status"] = "active"
            _save(state)
            logger.info("Sandbox force-unquarantined", sandbox=sandbox)
        else:
            logger.warning(
                "Attempted to unquarantine unknown sandbox",
                sandbox=sandbox,
            )


def get_status(sandbox: str) -> dict[str, Any] | None:
    """Get the current status dict for a sandbox, or None if unknown."""
    state = _load()
    return state.get("sandboxes", {}).get(sandbox)


def get_all_status() -> dict[str, Any]:
    """Get the full circuit breaker state."""
    return _load()


__all__ = [
    "record_failure",
    "record_success",
    "is_quarantined",
    "unquarantine",
    "get_status",
    "get_all_status",
    "FAILURE_FILE",
    "STALE_COOLDOWN_SECONDS",
]
