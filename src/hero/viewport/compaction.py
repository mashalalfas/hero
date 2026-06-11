"""hero.viewport.compaction — Event compaction engine.

Compresses raw events (tool calls, status changes, errors) into a natural
language summary using a rolling 30-minute window.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


_MAX_RAW_EVENTS = 100
_WINDOW_MINUTES = 30


@dataclass
class Event:
    """A single raw viewport event."""

    timestamp: datetime
    event_type: str  # "tool_call", "status_change", "error", "stuck", "complete"
    sandbox: str | None = None
    details: str = ""


class CompactionEngine:
    """Rolling-window event compactor.

    Keeps up to ``MAX_RAW_EVENTS`` raw events in memory. Events older than
    ``WINDOW_MINUTES`` are compressed into a summary line and removed from
    the raw buffer.
    """

    def __init__(self, max_raw: int = _MAX_RAW_EVENTS, window_minutes: int = _WINDOW_MINUTES):
        self._events: deque[Event] = deque()
        self._max_raw = max_raw
        self._window = timedelta(minutes=window_minutes)
        self._compact_summaries: list[str] = []

    def add(self, event_type: str, sandbox: str | None = None, details: str = "") -> None:
        """Record a new raw event."""
        ev = Event(timestamp=datetime.utcnow(), event_type=event_type, sandbox=sandbox, details=details)
        self._events.append(ev)
        # Enforce max raw buffer size.
        while len(self._events) > self._max_raw:
            oldest = self._events.popleft()
            # Drop silently — if it was in the compaction window it's been summarised already.

    def compress(self, force: bool = False) -> list[str]:
        """Return accumulated compacted summary lines.

        Runs the compaction pass: any events older than the window are turned
        into a single summary sentence and the raw events are discarded.

        When *force* is True all remaining raw events are compacted regardless
        of age (useful for a final summary on shutdown).
        """
        now = datetime.utcnow()
        cutoff = now - self._window

        # Partition: keep recent, compact old.
        to_compact: list[Event] = []
        remaining: deque[Event] = deque()
        for ev in self._events:
            if force or ev.timestamp < cutoff:
                to_compact.append(ev)
            else:
                remaining.append(ev)
        self._events = remaining

        if not to_compact:
            return list(self._compact_summaries)

        summary = self._build_summary(to_compact)
        if summary:
            self._compact_summaries.append(summary)

        # Keep only the most recent summaries so they don't accumulate forever.
        # We keep the last 10 compacted summaries.
        self._compact_summaries = self._compact_summaries[-10:]
        return list(self._compact_summaries)

    def _build_summary(self, events: list[Event]) -> str:
        """Compress a batch of events into one natural-language sentence."""
        if not events:
            return ""

        # Bucket by event type.
        by_type: dict[str, list[Event]] = defaultdict(list)
        for ev in events:
            by_type[ev.event_type].append(ev)

        # Time range.
        earliest = min(ev.timestamp for ev in events)
        latest = max(ev.timestamp for ev in events)
        elapsed = latest - earliest
        if elapsed.total_seconds() < 60:
            time_str = "just now"
        elif elapsed.total_seconds() < 3600:
            time_str = f"last {int(elapsed.total_seconds() // 60)} min"
        else:
            time_str = f"last {int(elapsed.total_seconds() // 3600)}h"

        # Sandboxes involved.
        all_sandboxes: set[str] = set()
        for ev in events:
            if ev.sandbox:
                all_sandboxes.add(ev.sandbox)

        sb_list = sorted(all_sandboxes)
        if len(sb_list) > 3:
            sb_str = f"{len(sb_list)} sandboxes"
        else:
            sb_str = ", ".join(sb_list) if sb_list else "system"

        # Count by type.
        sandboxes_worked = set()
        sandboxes_completed = set()
        sandboxes_errored: list[tuple[str, str]] = []

        for ev in by_type.get("tool_call", []):
            if ev.sandbox:
                sandboxes_worked.add(ev.sandbox)
        for ev in by_type.get("status_change", []):
            if ev.sandbox and "complete" in ev.details.lower():
                sandboxes_completed.add(ev.sandbox)
        for ev in by_type.get("error", []):
            if ev.sandbox:
                sandboxes_errored.append((ev.sandbox, ev.details))

        parts: list[str] = [f"{time_str}: {len(sandboxes_worked)} sandboxes worked"]
        if sandboxes_completed:
            parts.append(f"{len(sandboxes_completed)} completed")
        if sandboxes_errored:
            err_sandboxes = {s for s, _ in sandboxes_errored}
            err_details = [d for _, d in sandboxes_errored]
            parts.append(f"{len(err_sandboxes)} errored ({', '.join(err_details[:2])})")

        # Budget info if we have any tool_call events with details containing budget data.
        budget_info = self._extract_budget_info(events)
        if budget_info:
            parts.append(f"budget {budget_info}")

        return " | ".join(parts)

    def _extract_budget_info(self, events: list[Event]) -> str:
        """Try to extract budget change information from events."""
        # Look for budget-related details in tool_call or status_change events.
        for ev in events:
            if "budget" in ev.details.lower():
                # Extract something like "44%" or "44→62%" from details.
                import re
                nums = re.findall(r"(\d+)%?", ev.details)
                if len(nums) >= 2:
                    return f"{nums[0]}→{nums[1]}%"
                elif len(nums) == 1:
                    return f"{nums[0]}%"
        return ""
