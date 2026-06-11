"""hero.viewport.delta — Session delta tracking.

Tracks what changed since the operator last opened the viewport, rendered
as a compact banner below the header.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from rich.panel import Panel
from rich.text import Text

from hero.viewport.metrics import ArmyMetrics, SandboxMetrics


@dataclass
class SessionDelta:
    """What changed since the previous viewport snapshot."""

    new_sandboxes: list[str] = field(default_factory=list)
    finished_sandboxes: list[str] = field(default_factory=list)
    errored_count: int = 0
    budget_delta: int = 0  # percentage points change in usage ratio
    time_elapsed: str = ""

    def is_empty(self) -> bool:
        return (
            not self.new_sandboxes
            and not self.finished_sandboxes
            and self.errored_count == 0
            and self.budget_delta == 0
        )


# Module-level cache of previous snapshot for delta computation.
_previous_snapshot: ArmyMetrics | None = None
_first_render: bool = True


def capture_previous(army: ArmyMetrics) -> None:
    """Store *army* as the previous snapshot for the next render cycle."""
    global _previous_snapshot
    _previous_snapshot = ArmyMetrics(
        total_tokens_used=army.total_tokens_used,
        total_tokens_budget=army.total_tokens_budget,
        total_tool_calls=army.total_tool_calls,
        active_subagents=army.active_subagents,
        idle_subagents=army.idle_subagents,
        sandboxes=[_copy_sandbox(sb) for sb in army.sandboxes],
    )


def compute_delta(
    current: ArmyMetrics, previous: ArmyMetrics | None = None
) -> SessionDelta:
    """Compute the delta between *current* and *previous* snapshots.

    If *previous* is None the function uses the internally-cached snapshot
    from the last call to ``capture_previous``.  On the very first call
    (no cached snapshot) an empty delta is returned.
    """
    if previous is None:
        previous = _previous_snapshot

    if previous is None:
        return SessionDelta()

    delta = SessionDelta()

    # Track per-sandbox: new or finished.
    prev_names = {sb.name for sb in previous.sandboxes}
    curr_names = {sb.name for sb in current.sandboxes}

    delta.new_sandboxes = sorted(curr_names - prev_names)
    delta.finished_sandboxes = sorted(prev_names - curr_names)

    # Errored count — only count sandboxes that newly errored.
    prev_status: dict[str, str] = {sb.name: sb.status for sb in previous.sandboxes}
    curr_status: dict[str, str] = {sb.name: sb.status for sb in current.sandboxes}
    delta.errored_count = sum(
        1
        for sb in current.sandboxes
        if curr_status.get(sb.name, "") in ("error", "failed")
        and prev_status.get(sb.name, "") not in ("error", "failed")
    )

    # Budget delta (percentage points).
    prev_ratio = previous.usage_ratio
    curr_ratio = current.usage_ratio
    delta.budget_delta = int(round((curr_ratio - prev_ratio) * 100))

    # Time elapsed since previous snapshot (approximate, using UTC now).
    # This is a display value; the real clock is handled by the renderer.
    now = datetime.utcnow()
    # We cannot know the exact previous timestamp without storing it, so
    # the renderer fills in a human-readable "since last view" text.
    delta.time_elapsed = ""  # filled by renderer

    return delta


def _copy_sandbox(sb: SandboxMetrics) -> SandboxMetrics:
    """Return a shallow copy of a SandboxMetrics for snapshot storage."""
    return SandboxMetrics(
        name=sb.name,
        tokens_used=sb.tokens_used,
        tokens_remaining=sb.tokens_remaining,
        tokens_budget=sb.tokens_budget,
        tool_calls=sb.tool_calls,
        subagent_count=sb.subagent_count,
        status=sb.status,
        progress=sb.progress,
        current_task=sb.current_task,
        model=sb.model,
        last_updated=sb.last_updated,
    )


# ── banner rendering ─────────────────────────────────────────────────────────


def _render_delta_banner(delta: SessionDelta) -> Panel:
    """Build a Rich Panel summarising what changed since the last view.

    Returns ``None`` if the delta is empty (nothing new to report).
    """
    from rich.panel import Panel
    from rich.text import Text

    if delta.is_empty():
        return None

    parts: list[tuple[str, str]] = []

    if delta.new_sandboxes:
        names = ", ".join(delta.new_sandboxes[:3])
        if len(delta.new_sandboxes) > 3:
            names += f" +{len(delta.new_sandboxes) - 3} more"
        parts.append(("NEW", "bold green"))
        parts.append((" ", "white"))
        parts.append((names, "green"))

    if delta.finished_sandboxes:
        names = ", ".join(delta.finished_sandboxes[:3])
        if len(delta.finished_sandboxes) > 3:
            names += f" +{len(delta.finished_sandboxes) - 3} more"
        parts.append(("DONE", "bold blue"))
        parts.append((" ", "white"))
        parts.append((names, "blue"))

    if delta.errored_count:
        parts.append(("⚠ ERRORS", "bold red"))
        parts.append((" ", "white"))
        parts.append((str(delta.errored_count), "red"))

    if delta.budget_delta != 0:
        sign = "+" if delta.budget_delta > 0 else ""
        parts.append(("BUDGET", "bold yellow"))
        parts.append((" ", "white"))
        color = "red" if delta.budget_delta > 0 else "green"
        parts.append((f"{sign}{delta.budget_delta}%", color))

    text = Text()
    for i, (content, style) in enumerate(parts):
        if i > 0 and content != " ":
            text.append(" │ ")
        text.append(content, style=style)

    border_color = "green" if delta.budget_delta <= 0 else "yellow" if delta.errored_count == 0 else "red"

    return Panel(
        text,
        border_style=border_color,
        padding=(0, 1),
    )
