"""Per-sub-agent status files — avoids session file contention when
multiple sub-agents complete concurrently.

Each task gets its own status file under ~/.hero/status/<task_id>.json.
The parent reads status files instead of waiting for session announcements,
so no two agents ever write to the same file.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

STATUS_DIR = Path.home() / ".hero" / "status"


def _ensure_dir() -> None:
    STATUS_DIR.mkdir(parents=True, exist_ok=True)


def write_status(task_id: str, data: dict) -> None:
    """Write a status file for a sub-agent.

    The file is written atomically (write-then-rename) so a reader never
    sees a partially-written JSON document.
    """
    _ensure_dir()
    status_file = STATUS_DIR / f"{task_id}.json"
    payload = dict(data)
    payload["_updated_at"] = time.time()
    tmp = status_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(status_file)


def read_status(task_id: str) -> dict | None:
    """Read a status file for a sub-agent. Returns None if missing or corrupt."""
    status_file = STATUS_DIR / f"{task_id}.json"
    if not status_file.exists():
        return None
    try:
        return json.loads(status_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def list_status(sandbox: str | None = None) -> list[dict]:
    """List all status files, optionally filtered by sandbox, newest first."""
    if not STATUS_DIR.exists():
        return []
    results: list[dict] = []
    for f in sorted(
        STATUS_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if sandbox and data.get("sandbox") != sandbox:
            continue
        results.append(data)
    return results


def clean_status(age_hours: int = 24) -> int:
    """Remove status files whose mtime is older than *age_hours*.

    Returns the number of files removed.
    """
    if not STATUS_DIR.exists():
        return 0
    now = time.time()
    cutoff = now - (age_hours * 3600)
    cleaned = 0
    for f in STATUS_DIR.glob("*.json"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)
                cleaned += 1
        except OSError:
            pass
    return cleaned
