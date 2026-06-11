"""Budget history tracking — append-only JSONL for budget trends.

Records every budget-affecting event (spawn, complete, compact) so we
can analyse token consumption patterns over time.

Usage:
    from hero.state.budget_history import record_event, get_history

    record_event("sook-pro", "spawn", before=50000, after=49800)
    events = get_history("sook-pro", limit=10)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HISTORY_FILE = Path.home() / ".hero" / "budget_history.jsonl"


def record_event(
    sandbox: str,
    event: str,
    before: int,
    after: int,
) -> None:
    """Append a budget event to the append-only history log.

    The log lives at ``~/.hero/budget_history.jsonl``.  Each line is a
    JSON object with ``ts``, ``sandbox``, ``event``, ``tokens_before``,
    and ``tokens_after``.

    Args:
        sandbox: Sandbox name (e.g. ``"sook-pro"``).
        event:   Event type — one of ``"spawn"``, ``"complete"``,
                 ``"compact"``, ``"compaction_record"``.
        before:  Token count *before* the event.
        after:   Token count *after* the event.
    """
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    entry: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "sandbox": sandbox,
        "event": event,
        "tokens_before": before,
        "tokens_after": after,
    }

    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def get_history(sandbox: str, limit: int = 20) -> list[dict[str, Any]]:
    """Read recent budget history for a sandbox.

    Returns entries newest-first, limited to ``limit`` rows.

    Args:
        sandbox: Sandbox name to filter by.
        limit:   Maximum number of entries to return (default 20).

    Returns:
        List of event dicts, most recent first.
    """
    if not HISTORY_FILE.exists():
        return []

    entries: list[dict[str, Any]] = []
    with open(HISTORY_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry: dict[str, Any] = json.loads(line)
                if entry.get("sandbox") == sandbox:
                    entries.append(entry)
            except json.JSONDecodeError:
                continue

    # Most recent first
    entries.sort(key=lambda e: e.get("ts", ""), reverse=True)
    return entries[:limit]


def get_all_history(limit: int = 50) -> list[dict[str, Any]]:
    """Read the most recent budget events across all sandboxes.

    Args:
        limit: Maximum number of entries to return (default 50).

    Returns:
        List of event dicts, most recent first.
    """
    if not HISTORY_FILE.exists():
        return []

    entries: list[dict[str, Any]] = []
    with open(HISTORY_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    entries.sort(key=lambda e: e.get("ts", ""), reverse=True)
    return entries[:limit]
