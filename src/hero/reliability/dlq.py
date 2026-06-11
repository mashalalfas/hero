"""Dead Letter Queue — persist, inspect, and retry failed dispatch tasks.

Failed tasks are written to ~/.hero/dead_letter/ as JSON files so they
can be audited and retried later without losing the original context.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from hero.logging import get_logger
from hero.soldier.dispatch import enqueue

_logger = get_logger("dlq")

DLQ_DIR = Path.home() / ".hero" / "dead_letter"


def _ensure_dlq_dir() -> None:
    """Create the dead letter directory if it doesn't exist."""
    DLQ_DIR.mkdir(parents=True, exist_ok=True)


def _dlq_path(task_id: str) -> Path:
    """Return the expected DLQ file path for a given task ID."""
    return DLQ_DIR / f"{task_id}.json"


def send_to_dlq(task_id: str, task_data: dict, error: str) -> str:
    """Persist a failed dispatch task to the dead letter queue.

    Writes the full dispatch entry alongside the error message and a
    timestamp so operators can inspect, replay, or debug the failure.

    Args:
        task_id: The original dispatch task ID.
        task_data: The full dispatch entry dict (as returned by get_task).
        error: Human-readable error description.

    Returns:
        The absolute path to the written DLQ file.
    """
    _ensure_dlq_dir()

    entry = {
        "task_id": task_id,
        "sandbox": task_data.get("sandbox", ""),
        "original_task": task_data,
        "error": error,
        "dlq_timestamp": datetime.now().isoformat(),
    }

    path = _dlq_path(task_id)
    path.write_text(json.dumps(entry, indent=2))

    _logger.info(
        "Sent to DLQ",
        task_id=task_id,
        sandbox=entry["sandbox"],
        dlq_path=str(path),
        error=error,
    )

    return str(path)


def list_dlq() -> list[dict]:
    """List every task currently in the dead letter queue.

    Each entry contains the task_id, sandbox, error message, and the
    timestamp of when it was moved to the DLQ.

    Returns:
        A list of dicts, sorted by dlq_timestamp ascending.
    """
    _ensure_dlq_dir()

    entries: list[dict] = []
    for path in sorted(DLQ_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text())
            entries.append({
                "task_id": data.get("task_id", path.stem),
                "sandbox": data.get("sandbox", ""),
                "error": data.get("error", ""),
                "timestamp": data.get("dlq_timestamp", ""),
            })
        except (json.JSONDecodeError, OSError) as exc:
            _logger.warning("Corrupt DLQ entry", path=str(path), error=str(exc))
            continue

    return entries


def retry_from_dlq(task_id: str) -> str | None:
    """Re-enqueue a failed task from the dead letter queue.

    Reads the original dispatch entry, calls :func:`enqueue` with the
    same parameters, and — on success — removes the DLQ file.

    Args:
        task_id: The task ID of the dead-lettered entry.

    Returns:
        The new task_id assigned by enqueue, or None if the DLQ entry
        could not be found or re-enqueued.
    """
    path = _dlq_path(task_id)
    if not path.exists():
        _logger.warning("DLQ entry not found", task_id=task_id)
        return None

    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        _logger.error("Failed to read DLQ entry", task_id=task_id, error=str(exc))
        return None

    original = data.get("original_task", {})
    if not original:
        _logger.error("DLQ entry has no original_task", task_id=task_id)
        return None

    sandbox = original.get("sandbox", data.get("sandbox", ""))
    task = original.get("task", "")
    if not task:
        _logger.error("DLQ entry has no task to retry", task_id=task_id)
        return None

    try:
        new_task_id = enqueue(
            sandbox=sandbox,
            task=task,
            role=original.get("role", "soldier"),
            model=original.get("model", ""),
            model_short=original.get("model_short", ""),
            budget=original.get("budget", 5000),
            workdir=original.get("workdir", ""),
            timeout=original.get("timeout", 600),
            label=original.get("label", ""),
            max_tokens=original.get("max_tokens", 8000),
            context_window=original.get("context_window", 131072),
        )
    except Exception as exc:
        _logger.error("Failed to re-enqueue DLQ task", task_id=task_id, error=str(exc))
        return None

    # Success — remove the DLQ file
    try:
        path.unlink()
    except OSError:
        _logger.warning("Could not remove DLQ file after retry", path=str(path))

    _logger.info(
        "Retried from DLQ",
        original_task_id=task_id,
        new_task_id=new_task_id,
        sandbox=sandbox,
    )

    return new_task_id


def clear_dlq(older_than_days: int = 7) -> int:
    """Remove dead letter entries older than a given number of days.

    Useful for periodic cleanup so the DLQ doesn't grow unbounded.

    Args:
        older_than_days: Remove entries whose dlq_timestamp is at least
                         this many days in the past (default 7).

    Returns:
        The number of entries removed.
    """
    _ensure_dlq_dir()

    cutoff = datetime.now() - timedelta(days=older_than_days)
    removed = 0

    for path in DLQ_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text())
            ts_str = data.get("dlq_timestamp", "")
            if ts_str:
                ts = datetime.fromisoformat(ts_str)
                if ts < cutoff:
                    path.unlink()
                    removed += 1
                    _logger.debug(
                        "Cleared old DLQ entry",
                        task_id=data.get("task_id", path.stem),
                        timestamp=ts_str,
                    )
        except (json.JSONDecodeError, OSError, ValueError):
            # If we can't parse the timestamp, keep the entry for manual review
            continue

    _logger.info("Cleared DLQ entries", count=removed, older_than_days=older_than_days)
    return removed
