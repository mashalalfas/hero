"""hero.viewport.states — Sandbox state machine.

States
------
SPAWNING  — sandbox just created, no data yet
BOOTING   — first dispatch file detected
WORKING   — active with tool calls flowing
BLOCKED   — active but no tool calls for >5 refresh cycles (~10s)
COMPLETING — task finished, verify/archive running
ARCHIVING — archive phase active
DEAD      — sandbox done, no activity
"""

from __future__ import annotations

import time
from enum import Enum


class SandboxState(str, Enum):
    SPAWNING = "spawning"
    BOOTING = "booting"
    WORKING = "working"
    BLOCKED = "blocked"
    COMPLETING = "completing"
    ARCHIVING = "archiving"
    DEAD = "dead"

    def __str__(self) -> str:
        return self.value


# Maps status strings from the cache/dispatch layer to initial states.
_STATUS_INITIAL: dict[str, str] = {
    "idle": SandboxState.DEAD.value,
    "active": SandboxState.WORKING.value,
    "running": SandboxState.WORKING.value,
    "dispatched": SandboxState.BOOTING.value,
    "pending": SandboxState.BOOTING.value,
    "error": SandboxState.DEAD.value,
    "failed": SandboxState.DEAD.value,
}

_STUCK_THRESHOLD = 5  # consecutive refresh cycles with zero tool calls → BLOCKED


def compute_sandbox_state(
    state_data: dict,
    prev_state: str | None,
    tool_call_count: int,
    no_progress_counter: int,
) -> str:
    """Compute the current state for a sandbox.

    Parameters
    ----------
    state_data:
        Raw cache state dict for this sandbox.
    prev_state:
        Previously computed state (may be a raw string, not necessarily an enum value).
    tool_call_count:
        Current total tool call count reported by the dispatch layer.
    no_progress_counter:
        Consecutive refresh cycles where tool_call_count has not increased.

    Returns
    -------
    str
        One of the ``SandboxState`` value strings.
    """
    # First, infer base state from the cache/dispatch status string.
    cache_status = state_data.get("status", "idle")
    base = _STATUS_INITIAL.get(cache_status, SandboxState.DEAD.value)

    # Boot detection: if we have a dispatch file with status=running but
    # the cache still says "dispatched", treat as BOOTING → WORKING.
    if base == SandboxState.BOOTING.value and tool_call_count > 0:
        base = SandboxState.WORKING.value

    # Stuck detection: WORKING + no progress for N cycles → BLOCKED.
    if base == SandboxState.WORKING.value and no_progress_counter >= _STUCK_THRESHOLD:
        return SandboxState.BLOCKED.value

    # De-escalate BLOCKED if activity resumed.
    if base == SandboxState.BLOCKED.value and tool_call_count > 0:
        # Only un-block if no_progress_counter was reset (caller responsibility).
        return SandboxState.WORKING.value

    return base
