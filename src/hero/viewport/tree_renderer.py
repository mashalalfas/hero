"""hero.viewport.tree_renderer — Rich tree layout builder for Army Tree viewport.

Renders pipelines as indented tree hierarchies with box-drawing connectors,
coloured by status. Used via ``hero viewport --mode tree``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree as RichTree

from hero.viewport.metrics import ArmyMetrics
from hero.viewport.tree import (
    TreeNode,
    build_pipeline_state,
    _load_dispatch_files,
    _status_icon as _status_icon_original,
)
from hero.viewport.intel import detect_bottlenecks, BudgetProjection, Action, Bottleneck, SandboxDetail, collect_sandbox_detail
from hero.viewport.delta import SessionDelta, _render_delta_banner


# ── Pulse animation frames ─────────────────────────────────────────────────

_PULSE_FRAMES: dict[str, list[str]] = {
    "active":   ["●", "◉", "◎", "◉"],
    "working":  ["◌", "◔", "◐", "◒", "◓", "◑"],
    "running":  ["●", "◉", "◎", "◉"],
    "blocked":  ["⊘", "⊖", "⊘"],
    "queued":   ["◌", "○", "◌"],
    "pending":  ["◌", "○", "◌"],
    "booting":  ["◌", "◔", "◐", "◔"],
    "spawning": ["◌", "◔", "◐", "◔"],
}


def _status_icon(status: str, frame: int = 0) -> tuple[str, str]:
    """Return (icon, colour) for a given status string, with pulse animation.

    When *frame* > 0 and *status* has animation frames defined in
    ``_PULSE_FRAMES``, the icon cycles through the frame sequence.
    """
    icon, color = _status_icon_original(status)
    if frame > 0:
        status_lower = (status or "idle").lower()
        frames = _PULSE_FRAMES.get(status_lower)
        if frames:
            icon = frames[frame % len(frames)]
    return icon, color



# ── Tree → text lines ────────────────────────────────────────────────────────

def _render_simple_tree(
    node: TreeNode,
    indent: str = "",
    branch: str = "",
    is_root: bool = True,
) -> list[str]:
    """Render tree as indented lines with branch connectors.

    Uses Rich markup::

        ● COMM running — Fix theme switcher
        ├── ✓ LEAD done
        │   └── ◌ ARCH queued — Verify → Fix → Archive
        │       ├── ◌ SOLDIER queued — model: step-3.5
        │       └── ◌ VERIFY queued
    """
    lines: list[str] = []
    icon_s, color = _status_icon(node.status)

    content = (
        f"[bold {color}]{icon_s} {node.role}[/bold {color}]"
        f" [{color}]{node.status}[/{color}]"
    )

    if node.model:
        content += f" [dim]{node.model}[/dim]"
    if node.task:
        content += f" [dim]— {node.task[:55]}[/dim]"
    if node.is_error and node.error_detail:
        content += f" [red]✗ {node.error_detail[:40]}[/red]"

    if is_root:
        lines.append(content)
    else:
        # Trim long lines to avoid wrapping past terminal
        max_len = 120
        display_line = indent + branch + content
        if len(display_line) > max_len:
            # Try to find a good break point
            display_line = display_line[:max_len - 3] + "..."
        lines.append(display_line)

    child_count = len(node.children)
    for idx, child in enumerate(node.children):
        is_last = (idx == child_count - 1)

        if is_root:
            child_br = "└── " if is_last else "├── "
            child_indent = ""
        else:
            child_br = "└── " if is_last else "├── "
            child_indent = indent + ("    " if branch == "└── " else "│   ")

        child_lines = _render_simple_tree(child, child_indent, child_br, is_root=False)
        lines.extend(child_lines)

    return lines


def build_tree_text(root: TreeNode) -> Text:
    """Convert a TreeNode tree into a Rich Text block."""
    raw_lines = _render_simple_tree(root)
    padded = [""] + raw_lines + [""]
    return Text.from_markup("\n".join(padded), overflow="fold")


def _build_rich_tree(
    node: TreeNode,
    parent_tree: RichTree | None = None,
    frame: int = 0,
) -> RichTree:
    """Recursively build a Rich Tree from TreeNode hierarchy.

    - Each TreeNode becomes parent_tree.add(label)
    - Label uses Rich markup from ``_status_icon``:
      ``\"[bold color]icon role[/bold color] [color]status[/color]\"``
    - If node.model: append ``\"[dim]model[/dim]\"``
    - If node.task: append ``\" [dim]— task[:55][/dim]\"``
    - If is_error: append ``\" [red]✗ error_detail[:40][/red]\"``
    """
    icon_s, color = _status_icon(node.status, frame=frame)

    label = (
        f"[bold {color}]{icon_s} {node.role}[/bold {color}]"
        f" [{color}]{node.status}[/{color}]"
    )
    if node.model:
        label += f" [dim]{node.model}[/dim]"
    if node.task:
        label += f" [dim]— {node.task[:55]}[/dim]"
    if node.is_error and node.error_detail:
        label += f" [red]✗ {node.error_detail[:40]}[/red]"

    if parent_tree is None:
        tree = RichTree(label)
    else:
        tree = parent_tree.add(label)

    for child in node.children:
        _build_rich_tree(child, parent_tree=tree, frame=frame)

    return tree


# ── Panels ───────────────────────────────────────────────────────────────────

def _render_tree_panel(tree_node: TreeNode, title: str) -> Panel:
    content = build_tree_text(tree_node)
    return Panel(content, title=title, border_style="cyan", padding=(0, 1))


def _render_collapsed_sandbox(
    sandbox_name: str,
    status: str,
    current_task: str | None = None,
    selected: bool = False,
) -> Panel:
    icon, color = _status_icon(status)
    task_str = f" — {current_task[:40]}" if current_task else ""
    line = Text()
    if selected:
        line.append("► ", style="bold yellow")
    else:
        line.append("  ")
    line.append(f"{icon} ", style=color)
    line.append(sandbox_name, style="bold white")
    line.append(f"  {status}{task_str}", style="dim")
    return Panel(line, border_style="grey30", padding=(0, 0))


def _render_intel_panel(bottlenecks: list) -> Panel:
    """Render detected bottlenecks as a Rich Panel.

    Each line:
        ⚠ [severity] [sandbox]: [detail] — [suggestion]

    Color by severity: critical=red, warning=yellow, info=blue.
    """
    if not bottlenecks:
        return Panel(
            Text("Intelligence Zone — all clear", style="dim green"),
            title="Intelligence Zone",
            border_style="green",
            padding=(0, 1),
        )

    lines: list[Text] = []
    for b in bottlenecks:
        color = {
            "critical": "red",
            "warning": "yellow",
            "info": "blue",
        }.get(b.severity, "white")

        line = Text()
        line.append("⚠ ", style=color)
        line.append(f"[{b.severity}] ", style=color)
        line.append(f"{b.sandbox_name}: ", style="bold" + color)
        line.append(b.detail, style="dim")
        line.append(" — ", style="dim")
        line.append(b.suggestion, style="italic dim")
        lines.append(line)
        lines.append(Text(""))  # blank separator

    content = Text.assemble(*lines)
    return Panel(
        content,
        title="Intelligence Zone",
        border_style="magenta",
        padding=(0, 1),
    )


def _render_budget_panel(projections: list[BudgetProjection]) -> Panel:
    """Render budget projections as a Rich Panel table.

    Columns: Sandbox | Used/Budget | % | Burn/min | ETA | Status
    Row colours: green / yellow / red based on status.
    """
    if not projections:
        return Panel(
            Text("Budget Projections — no data", style="dim"),
            title="Budget",
            border_style="grey30",
            padding=(0, 1),
        )

    from rich.table import Table
    table = Table(
        show_header=True,
        header_style="bold grey50",
        border_style="grey30",
        expand=True,
        padding=(0, 1),
        row_styles=["none", "dim"],
    )
    table.add_column("Sandbox", style="bold", min_width=10, max_width=14)
    table.add_column("Used/Budget", min_width=14, max_width=18)
    table.add_column("%", width=6, justify="right")
    table.add_column("Burn/min", width=10, justify="right")
    table.add_column("ETA", width=8, justify="right")
    table.add_column("Status", width=10)

    status_color_map = {
        "healthy": "green",
        "warning": "yellow",
        "critical": "red",
    }

    for p in projections:
        color = status_color_map.get(p.status, "white")
        eta_str = str(p.eta_minutes) + "m" if p.eta_minutes is not None else "—"
        burn_str = f"{p.burn_rate:.0f}" if p.burn_rate > 0 else "—"
        pct_str = f"{p.usage_pct * 100:.0f}%"
        used_budget = f"{p.tokens_used:,}/{p.tokens_budget:,}"

        table.add_row(
            Text(p.sandbox_name, style=color),
            Text(used_budget, style="dim"),
            Text(pct_str, style=color),
            Text(burn_str, style=color),
            Text(eta_str, style=color),
            Text(f"[{p.status}]", style=color),
        )

    return Panel(
        table,
        title="Budget Projections",
        border_style="cyan",
        padding=(0, 0),
    )


def _render_action_panel(actions: list[Action]) -> Panel:
    """Render suggested actions as a Rich Panel.

    Priority icons: high=🔴, medium=🟡, low=🔵.
    """
    if not actions:
        return Panel(
            Text("Action Queue — all clear", style="dim green"),
            title="Action Queue",
            border_style="green",
            padding=(0, 1),
        )

    priority_icon = {
        "high": "🔴",
        "medium": "🟡",
        "low": "🔵",
    }
    priority_color = {
        "high": "red",
        "medium": "yellow",
        "low": "blue",
    }

    lines: list[Text] = []
    for a in actions:
        icon = priority_icon.get(a.priority, "⚪")
        color = priority_color.get(a.priority, "white")
        line = Text()
        line.append(f"{icon} ", style=color)
        line.append(a.description, style="bold" + color)
        line.append("\n    ", style="dim")
        line.append(a.suggestion, style="italic dim")
        lines.append(line)
        lines.append(Text(""))  # blank separator

    content = Text.assemble(*lines)
    return Panel(
        content,
        title="Action Queue",
        border_style="magenta",
        padding=(0, 1),
    )


# ── Dispatch map helper ───────────────────────────────────────────────────────

def _collect_pipeline_sandboxes() -> list[str]:
    """Find all sandbox names that have active (non-completed) pipeline manifests."""
    pipeline_dir = Path.home() / ".hero" / "pipeline"
    if not pipeline_dir.exists():
        return []
    seen: set[str] = set()
    result: list[str] = []
    for f in sorted(pipeline_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            sb = data.get("sandbox")
            status = data.get("status", "")
            # Skip completed/failed pipelines — they're historical
            if status in ("completed", "failed"):
                continue
            if sb and sb not in seen:
                seen.add(sb)
                result.append(sb)
        except (json.JSONDecodeError, OSError):
            pass
    return result


def _build_dispatch_map(sandbox_names: set[str]) -> dict[str, dict]:
    """Load latest dispatch file for every sandbox name."""
    dispatch_map: dict[str, dict] = {}
    pipeline_sandboxes = _collect_pipeline_sandboxes()
    for sb_name in pipeline_sandboxes:
        dispatch_files = _load_dispatch_files(sb_name)
        if dispatch_files:
            latest = max(dispatch_files.values(), key=lambda d: float(d.get("last_updated", 0)))
            dispatch_map[sb_name] = latest
    for sb_name in sandbox_names - set(dispatch_map):
        dispatch_files = _load_dispatch_files(sb_name)
        if dispatch_files:
            latest = max(dispatch_files.values(), key=lambda d: float(d.get("last_updated", 0)))
            dispatch_map[sb_name] = latest
    return dispatch_map


# ── Footer ────────────────────────────────────────────────────────────────────

def _render_footer() -> Panel:
    """Keyboard shortcut footer, matching dashboard mode."""
    parts = [
        ("[q]", "grey30"), "quit ",
        ("[r]", "grey30"), "refresh ",
        ("[↑↓]", "grey30"), "nav ",
        ("[Enter]", "grey30"), "detail ",
        ("[Esc]", "grey30"), "back ",
        ("refresh:2s", "dim"),
    ]
    hint = Text.assemble(*parts)
    return Panel(hint, border_style="grey30", padding=(0, 0))


def _render_status_bar(
    army: ArmyMetrics,
    last_refresh: str = "",
    error_count: int = 0,
    frame: int = 0,
) -> Panel:
    """Bottom status bar with live metrics and keyboard shortcuts.

    Layout::

        🔄 HH:MM:SS  │  📦 N sandboxes  │  ▶ N active  │  ⚠ N errors  │
        [q]quit [r]refresh [/]search [j↓] [k↑] [d]detail
    """
    from datetime import datetime

    time_str = datetime.now().strftime("%H:%M:%S")
    active = sum(
        1 for sb in army.sandboxes
        if sb.status in ("active", "running", "working")
    )
    total = len([sb for sb in army.sandboxes if sb.name])

    text = Text()
    text.append("🔄 ", style="dim")
    text.append(time_str, style="bold")
    text.append(f"  │  📦 {total} sandboxes", style="dim")
    text.append(f"  │  ▶ {active} active", style="green" if active > 0 else "dim")
    text.append(f"  │  ⚠ {error_count} errors", style="red" if error_count > 0 else "dim")
    text.append(f"  │  ", style="dim")
    text.append("[q]quit ", style="grey30")
    text.append("[r]refresh ", style="grey30")
    text.append("[/]search ", style="grey30")
    text.append("[j↓] ", style="grey30")
    text.append("[k↑] ", style="grey30")
    text.append("[d]detail", style="grey30")

    return Panel(text, border_style="grey30", padding=(0, 0))


# ── Single-node COMM tree for non-pipeline sandboxes ────────────────────────

def _render_single_node_tree(
    sandbox_name: str,
    status: str,
    task: str | None = None,
    model: str | None = None,
    selected: bool = False,
) -> Panel:
    """Render a simplified single-node COMM tree for a non-pipeline sandbox.

    Format::

        ● COMM idle — sandbox-name
            └── [dim]sandbox-name [model][/dim]
    """
    icon, color = _status_icon(status)
    task_str = f" — {task[:45]}" if task else ""
    model_str = f"  [{model}]" if model else ""

    prefix = "► " if selected else "  "
    lines: list[str] = []
    lines.append(
        f"{prefix}[bold {color}]{icon} COMM[/bold {color}]"
        f" [{color}]{status}[/{color}]"
        f" — {sandbox_name}{task_str}"
    )
    lines.append(f"    └── [dim]{sandbox_name}{model_str}[/dim]")

    content = Text.from_markup("\n".join(lines), overflow="fold")
    return Panel(content, title=f"[bold]{sandbox_name}[/bold]", border_style="cyan", padding=(0, 1))


# ── Detail panel ───────────────────────────────────────────────────────────

# Shared status colour map for detail rendering
_DETAIL_STEP_COLORS: dict[str, str] = {
    "done": "green",
    "completed": "green",
    "success": "green",
    "active": "cyan",
    "running": "cyan",
    "working": "cyan",
    "queued": "yellow",
    "pending": "yellow",
    "dispatched": "yellow",
    "failed": "red",
    "error": "red",
    "timeout": "red",
}

_DETAIL_STEP_ICONS: dict[str, str] = {
    "done": "✓", "completed": "✓", "success": "✓",
    "active": "●", "running": "●", "working": "●",
    "queued": "◌", "pending": "◌", "dispatched": "◌",
    "failed": "✗", "error": "✗", "timeout": "✗",
}


def _render_sandbox_detail_panel(detail: SandboxDetail) -> Panel:
    """Render full drill-down detail for one sandbox.

    Sections:
      - Header: name, status, model, current task
      - Budget: full breakdown with bar
      - Pipeline: task, steps status
      - Dispatch tasks: table of all task entries
      - Errors: any error/failed results
      - Git: branch status
      - Katana: pending tasks, known issues
    """
    from rich.table import Table
    from rich.text import Text

    lines: list[Text | str] = []

    # ── Header section ──────────────────────────────────────────────────
    icon_s, color = _status_icon(detail.status)
    header = Text()
    header.append(f"{icon_s} ", style=color)
    header.append(detail.name, style="bold white")
    header.append(f"  [{detail.status}]", style=color)
    if detail.model:
        header.append(f"  model: {detail.model}", style="cyan")
    if detail.current_task:
        header.append(f"\n   task: {detail.current_task[:100]}", style="dim")
    header.append("")
    lines.append(header)
    lines.append("")

    # ── Budget section ──────────────────────────────────────────────────
    bar_width = 24
    filled = max(0, min(bar_width, round(detail.usage_pct * bar_width)))
    bar = "█" * filled + "░" * (bar_width - filled)
    bar_color = "red" if detail.usage_pct >= 0.8 else ("yellow" if detail.usage_pct >= 0.5 else "green")

    budget_lines = [
        ("Budget", f"{detail.tokens_used:,}/{detail.tokens_budget:,}  {bar}  {detail.usage_pct * 100:.0f}%"),
        ("Compactions", str(detail.compactions_used)),
        ("Tool calls", str(detail.tool_calls)),
        ("Subagents", str(detail.subagent_count)),
        ("State cycles", str(detail.no_progress_counter)),
    ]
    budget_header = Text(f"Budget", style=f"bold underline {bar_color}")
    lines.append(budget_header)
    for label, val in budget_lines:
        t = Text()
        t.append(f"  {label}: ", style="bold grey50")
        if label == "Budget":
            t.append(val, style=bar_color)
        else:
            t.append(val, style="white")
        lines.append(t)
    lines.append("")

    # ── Workdir / Git ───────────────────────────────────────────────────
    if detail.workdir:
        lines.append(Text.from_markup("[bold underline]Location[/bold underline]"))
        lines.append(Text(f"  Workdir: {detail.workdir}", style="dim"))
        if detail.last_compacted:
            lines.append(Text(f"  Git: {detail.last_compacted}", style="green"))
        lines.append("")

    # ── Pipeline section ────────────────────────────────────────────────
    if detail.pipeline_task:
        lines.append(Text.from_markup("[bold underline]Pipeline[/bold underline]"))
        lines.append(Text(f"  Task: {detail.pipeline_task[:120]}", style="dim"))
        if detail.pipeline_created:
            lines.append(Text(f"  Created: {detail.pipeline_created[:19]}", style="dim"))
        if detail.pipeline_steps:
            for step_name, step_data in detail.pipeline_steps.items():
                if isinstance(step_data, dict):
                    st = step_data.get("status", "unknown")
                    sc = _DETAIL_STEP_COLORS.get(st, "white")
                    pfx = _DETAIL_STEP_ICONS.get(st, "?")
                    t = Text()
                    t.append(f"    {pfx} {step_name} [{st}]", style=sc)
                    if step_name == "fix" and step_data.get("model"):
                        t.append(f" model:{step_data['model']}", style="dim")
                    lines.append(t)
        lines.append("")

    # ── Dispatch tasks table ────────────────────────────────────────────
    if detail.dispatch_tasks:
        lines.append(Text.from_markup("[bold underline]Dispatch Tasks[/bold underline]"))

        dt_table = Table(
            show_header=True,
            header_style="bold grey50",
            border_style="grey30",
            padding=(0, 1),
            box=None,
            expand=True,
        )
        dt_table.add_column("ID", style="dim", width=10, no_wrap=True)
        dt_table.add_column("Role", width=10, no_wrap=True)
        dt_table.add_column("Status", width=10)
        dt_table.add_column("Model", width=18, overflow="fold")
        dt_table.add_column("Label", min_width=12, max_width=30, overflow="fold")

        for t in detail.dispatch_tasks:
            st = t.get("status", "?")
            st_color = _DETAIL_STEP_COLORS.get(st, "white")
            st_icon = _DETAIL_STEP_ICONS.get(st, "○")
            dt_table.add_row(
                Text(t.get("task_id", "")[:8], style="dim"),
                Text(t.get("role", ""), style="bold"),
                Text(f"{st_icon} {st[:8]}", style=st_color),
                Text(t.get("model", "")[:18], style="cyan" if t.get("model") else "dim"),
                Text(t.get("label", "")[:28], style="dim"),
            )

        lines.append(dt_table)
        lines.append("")

    # ── Errors section ──────────────────────────────────────────────────
    if detail.errors:
        lines.append(Text.from_markup(f"[bold underline red]Errors ({len(detail.errors)})[/bold underline red]"))
        for err in detail.errors[:5]:
            e = Text()
            e.append(f"  ✗ [{err.get('role', '?')}]", style="red")
            e.append(f" {err.get('task_id', '')[:8]}", style="dim")
            e.append(f"  {err.get('detail', '')[:150]}", style="red dim")
            lines.append(e)
        if len(detail.errors) > 5:
            lines.append(Text(f"  ... and {len(detail.errors) - 5} more", style="dim red"))
        lines.append("")

    # ── Katana section ──────────────────────────────────────────────────
    if detail.pending_tasks:
        lines.append(Text.from_markup(f"[bold underline yellow]Pending Tasks ({len(detail.pending_tasks)})[/bold underline yellow]"))
        for pt in detail.pending_tasks[:5]:
            lines.append(Text(f"  ◌ {pt[:100]}", style="yellow dim"))
        if len(detail.pending_tasks) > 5:
            lines.append(Text(f"  ... and {len(detail.pending_tasks) - 5} more", style="dim yellow"))
        lines.append("")

    if detail.known_issues:
        lines.append(Text.from_markup(f"[bold underline red]Known Issues ({len(detail.known_issues)})[/bold underline red]"))
        for ki in detail.known_issues[:5]:
            lines.append(Text(f"  ⚠ {ki[:100]}", style="red dim"))
        if len(detail.known_issues) > 5:
            lines.append(Text(f"  ... and {len(detail.known_issues) - 5} more", style="dim red"))
        lines.append("")

    # ── Hint ────────────────────────────────────────────────────────────
    lines.append(Text.from_markup("[dim]Press [bold]ESC[/bold] or [bold]q[/bold] to go back[/dim]"))

    from rich.console import Group as RichGroup
    # Filter None items; flatten any Table objects so they join cleanly
    cleaned = [l for l in lines if l is not None]
    content = RichGroup(*cleaned)
    return Panel(
        content,
        title=f"[bold]📋 {detail.name} — Drill-Down[/bold]",
        border_style="cyan",
        padding=(0, 1),
    )


def _estimate_height(panel: Panel) -> int:
    """Rough line-count estimate for layout sizing.

    Tables render to multiple lines. If the renderable is a Table,
    estimate N rows + header + borders.
    """
    from rich.table import Table
    renderable = panel.renderable

    if isinstance(renderable, Table):
        # Table: header (2) + borders (2) + N data rows + 1 spare
        approx_rows = renderable.row_count if hasattr(renderable, "row_count") else 5
        return max(approx_rows + 5, 6)

    if hasattr(renderable, "plain"):
        text = renderable.plain
    elif hasattr(renderable, "__str__"):
        text = str(renderable)
    else:
        text = ""
    line_count = text.count("\n") + 3  # borders + minimal
    return max(line_count, 3)


# ── Sparkline tracker ─────────────────────────────────────────────────────────

class SparklineTracker:
    """Records token usage history across refresh cycles for sparkline rendering.

    Tracks per-sandbox and aggregate token usage over a rolling window.
    Uses real wall-clock timestamps for burn-rate calculation when available,
    falling back to a 2s-per-sample estimate when timestamps are not recorded
    (backward compat path).
    """

    def __init__(self, window: int = 30):
        self.history: dict[str, list[int]] = {}
        self._times: dict[str, list[float]] = {}
        self._window = window

    def record(self, army: ArmyMetrics) -> None:
        """Record the current token usage snapshot with a wall-clock timestamp."""
        import time
        now = time.time()

        total = army.total_tokens_used
        if "__total__" not in self.history:
            self.history["__total__"] = []
            self._times["__total__"] = []
        self.history["__total__"].append(total)
        self._times["__total__"].append(now)
        if len(self.history["__total__"]) > self._window:
            self.history["__total__"] = self.history["__total__"][-self._window:]
            self._times["__total__"] = self._times["__total__"][-self._window:]

        for sb in army.sandboxes:
            name = sb.name
            if name not in self.history:
                self.history[name] = []
                self._times[name] = []
            self.history[name].append(sb.tokens_used)
            self._times[name].append(now)
            if len(self.history[name]) > self._window:
                self.history[name] = self.history[name][-self._window:]
                self._times[name] = self._times[name][-self._window:]

    def sparkline(self, sandbox: str = "__total__") -> str:
        """Render a unicode sparkline: ▁▂▃▄▅▆▇█"""
        vals = self.history.get(sandbox, [])
        if len(vals) < 2:
            return ""
        mn, mx = min(vals), max(vals)
        span = max(mx - mn, 1)
        bars = "▁▂▃▄▅▆▇█"
        return "".join(bars[min(int((v - mn) / span * 7), 7)] for v in vals)

    def burn_rate(self, sandbox: str = "__total__") -> float:
        """Return tokens/minute burn rate based on history delta.

        Uses wall-clock timestamps when available; falls back to a 2s-per-sample
        estimate for backward compatibility.
        """
        vals = self.history.get(sandbox, [])
        times = self._times.get(sandbox, [])
        if len(vals) < 2:
            return 0.0
        delta_tokens = vals[-1] - vals[0]
        if delta_tokens <= 0:
            return 0.0
        if len(times) >= 2:
            elapsed = times[-1] - times[0]
            if elapsed > 0:
                return delta_tokens / (elapsed / 60.0)
        # Fallback: assume 2s per sample
        delta_time_min = (len(vals) - 1) * 2.0 / 60.0
        if delta_time_min <= 0:
            return 0.0
        return delta_tokens / delta_time_min


# ── Main layout builder ───────────────────────────────────────────────────────

def build_tree_layout(
    army: ArmyMetrics,
    bottlenecks: list[Bottleneck] | None = None,
    projections: list[BudgetProjection] | None = None,
    actions: list[Action] | None = None,
    selected_sandbox: str | None = None,
    highlight_sandbox: str | None = None,
    dispatch_map: dict[str, dict] | None = None,
    frame: int = 0,
    delta: SessionDelta | None = None,
) -> Layout:
    """Build a vertical Layout of tree panels, one per sandbox.

    Parameters
    ----------
    army:
        Current army-level metrics snapshot.
    bottlenecks:
        Pre-computed list of Bottleneck objects (or None to skip intel panel).
    projections:
        Pre-computed list of BudgetProjection objects (or None to skip budget panel).
    actions:
        Pre-computed list of Action objects (or None to skip action panel).
    selected_sandbox:
        If set, show the drill-down detail panel for this sandbox instead of trees.
    highlight_sandbox:
        Sandbox name to visually highlight with ► prefix.
    dispatch_map:
        Pre-built dispatch map — avoids redundant re-detection inside this function.
    frame:
        Animation frame counter for pulsing status icons.
    delta:
        SessionDelta snapshot for the delta-change banner.

    Returns
    -------
    Layout
        A Rich Layout with panels stacked vertically, including a keyboard footer.
    """
    sandbox_names = {sb.name for sb in army.sandboxes}

    # ── Drill-down mode: show detail panel for selected sandbox ─────────
    if selected_sandbox:
        dm = dispatch_map or _build_dispatch_map(sandbox_names)
        detail = collect_sandbox_detail(selected_sandbox, army, dm)
        detail_panel = _render_sandbox_detail_panel(detail)
        error_count = sum(1 for sb in army.sandboxes if sb.status in ("error", "failed"))
        footer_panel = _render_status_bar(army, error_count=error_count, frame=frame)
        layout = Layout()
        layout.split_column(
            Layout(name="detail", size=_estimate_height(detail_panel)),
            Layout(name="footer", size=3),
        )
        layout["detail"].update(detail_panel)
        layout["footer"].update(footer_panel)
        return layout

    # Use the passed-in dispatch map for pipeline lookups
    if dispatch_map is None:
        dispatch_map = _build_dispatch_map(sandbox_names)

    # Collect pipeline sandboxes from manifests
    pipeline_sandboxes = _collect_pipeline_sandboxes()

    tree_panels: list[Panel] = []

    # ── Intel panel at top ───────────────────────────────────────────────
    if bottlenecks is not None:
        intel_panel = _render_intel_panel(bottlenecks)
        tree_panels.append(intel_panel)

    # ── Budget projection panel ────────────────────────────────────────────
    if projections:
        budget_panel = _render_budget_panel(projections)
        tree_panels.append(budget_panel)

    # ── Action queue panel ─────────────────────────────────────────────────
    if actions:
        action_panel = _render_action_panel(actions)
        tree_panels.append(action_panel)

    # ── Delta banner (between header panels and tree body) ────────────────
    if delta is not None and not delta.is_empty():
        banner = _render_delta_banner(delta)
        if banner is not None:
            tree_panels.append(banner)

    # Pipeline sandboxes — auto-expand active, collapse idle
    for sb_name in pipeline_sandboxes:
        sb_metrics = next((s for s in army.sandboxes if s.name == sb_name), None)
        status = sb_metrics.status if sb_metrics else "idle"
        task_label = sb_metrics.current_task if sb_metrics and sb_metrics.current_task else None
        selected = (sb_name == highlight_sandbox)

        active_statuses = {"active", "running", "working", "booting"}
        if status in active_statuses:
            # Full Rich Tree rendering
            dispatch_data = _load_dispatch_files(sb_name)
            pipeline = build_pipeline_state(sb_name, {}, dispatch_data)
            if task_label is None:
                task_label = pipeline.task
            prefix = "► " if selected else "  "
            title = (
                f"{prefix}[bold]{sb_name}[/bold]  {task_label[:50]}"
                if task_label else f"{prefix}{sb_name}"
            )
            rich_tree = _build_rich_tree(pipeline.root_node, frame=frame)
            tree_panels.append(Panel(
                rich_tree,
                title=title,
                border_style="cyan",
                padding=(0, 1),
            ))
        else:
            # Collapsed view for idle/dead/completed
            tree_panels.append(_render_collapsed_sandbox(
                sb_name, status, current_task=task_label, selected=selected,
            ))

    # Non-pipeline sandboxes — expand active, collapse idle
    idle_names = sandbox_names - set(pipeline_sandboxes)
    for sb_name in sorted(idle_names):
        sb_metrics = next((s for s in army.sandboxes if s.name == sb_name), None)
        status = sb_metrics.status if sb_metrics else "idle"
        task = sb_metrics.current_task if sb_metrics else None
        model = sb_metrics.model if sb_metrics else None
        selected = (sb_name == highlight_sandbox)

        active_statuses = {"active", "running", "working", "booting"}
        if status in active_statuses:
            # Show full single-node tree for active sandboxes
            tree_panels.append(_render_single_node_tree(
                sb_name, status, task=task, model=model, selected=selected,
            ))
        else:
            # Collapsed view for idle/dead/completed
            tree_panels.append(_render_collapsed_sandbox(
                sb_name, status, current_task=task, selected=selected,
            ))

    has_any_sandbox = bool(pipeline_sandboxes or idle_names)

    if not has_any_sandbox:
        error_count = sum(1 for sb in army.sandboxes if sb.status in ("error", "failed"))
        footer_panel = _render_status_bar(army, error_count=error_count, frame=frame)
        layout = Layout()
        layout.split_column(
            Layout(name="panel", size=_estimate_height(_render_intel_panel([]))),
            Layout(name="footer", size=3),
        )
        layout["panel"].update(_render_intel_panel([]))
        layout["footer"].update(footer_panel)
        return layout

    heights = [_estimate_height(p) for p in tree_panels]
    named_layouts = [Layout(name=f"p{i}", size=h) for i, h in enumerate(heights)]
    error_count = sum(1 for sb in army.sandboxes if sb.status in ("error", "failed"))
    footer_panel = _render_status_bar(army, error_count=error_count, frame=frame)
    layout = Layout()
    layout.split_column(*named_layouts, Layout(name="footer", size=3))

    for i, panel in enumerate(tree_panels):
        layout[f"p{i}"].update(panel)
    layout["footer"].update(footer_panel)
    return layout
