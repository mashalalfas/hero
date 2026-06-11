"""Viewport Renderer — draws the Rich TUI dashboard."""

from __future__ import annotations

import os
import select
import sys
import time
from datetime import datetime
from typing import Any

import click
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from hero.viewport.delta import SessionDelta, capture_previous, compute_delta
from hero.viewport.metrics import ArmyMetrics, SandboxMetrics, MetricsCollector, collect
from hero.viewport.tree_renderer import SparklineTracker

REFRESH_INTERVAL = 2.0  # seconds


# ── helpers ─────────────────────────────────────────────────────────────────

def _usage_bar(ratio: float, width: int = 20) -> str:
    """Return a unicode progress bar string, e.g. '█████░░░░░ 50%'."""
    filled = max(0, min(width, round(ratio * width)))
    return "█" * filled + "░" * (width - filled)


def _bar_color(ratio: float) -> str:
    if ratio < 0.5:
        return "green"
    elif ratio < 0.8:
        return "yellow"
    return "red"


def _status_badge(status: str) -> Text:
    s = status.lower()
    palette = {
        "active": ("cyan", "●"),
        "running": ("cyan", "●"),
        "working": ("cyan", "●"),
        "idle": ("blue", "○"),
        "error": ("red", "✗"),
        "failed": ("red", "✗"),
        "dispatched": ("magenta", "◌"),
        "pending": ("magenta", "◌"),
        "spawning": ("yellow", "◌"),
        "booting": ("yellow", "◌"),
        "blocked": ("red", "⊘"),
        "completing": ("yellow", "◑"),
        "archiving": ("yellow", "◑"),
        "dead": ("grey50", "○"),
    }
    colour, icon = palette.get(s, ("white", "?"))
    return Text(f" {icon} {status[:8]} ", style=f"bold {colour}")


def _health_color(ratio: float) -> str:
    if ratio < 0.5:
        return "green"
    elif ratio < 0.8:
        return "yellow"
    return "red"


def _render_status_bar(
    army: ArmyMetrics,
    timestamp: str,
    error_count: int,
    frame: int,
) -> Panel:
    """Render a compact status bar with error count and frame counter."""
    parts: list[tuple[str, str]] = [
        (timestamp, "dim"),
    ]
    active = sum(1 for sb in army.sandboxes if sb.status in ("active", "running", "working"))
    total = len(army.sandboxes)
    parts.append(("  Active: ", "grey50"))
    parts.append((f"{active}/{total}", "bold cyan"))

    if error_count:
        parts.append(("  Errors: ", "grey50"))
        parts.append((str(error_count), "bold red"))

    parts.append(("  Frame: ", "grey50"))
    parts.append((str(frame), "dim"))

    text = Text()
    for content, style in parts:
        text.append(content, style=style)

    return Panel(
        text,
        border_style="grey30",
        padding=(0, 1),
    )


# ── panels ──────────────────────────────────────────────────────────────────

def _render_header(army: ArmyMetrics, sparkline: str = "", burn_rate: float = 0.0) -> Panel:
    bar = _usage_bar(army.usage_ratio)
    bar_color = _bar_color(army.usage_ratio)
    army_health = army.army_health

    header_text = Text()
    header_text.append("HERO⚡", style="bold white")
    header_text.append(f" T:{army.total_tokens_used:,}/{army.total_tokens_budget:,}", style=f"bold {bar_color}")
    header_text.append(f" {bar}", style=bar_color)
    header_text.append(f" {int(army.usage_ratio * 100)}%", style=bar_color)
    header_text.append(f" | Tools:{army.total_tool_calls}", style="bold")
    header_text.append(f" ●{army.active_subagents}", style="green")
    header_text.append(f" ○{army.idle_subagents}", style="blue")
    if sparkline:
        header_text.append(f"  {sparkline}", style="bold green")
    if burn_rate > 0:
        header_text.append(f"  {burn_rate:.0f}t/min", style="dim")
    header_text.append(f" | {datetime.utcnow().strftime('%H:%M:%S')}", style="dim")

    return Panel(
        header_text,
        title=None,
        border_style=army_health,
        padding=(0, 1),
    )


def _render_delta_banner(delta: SessionDelta) -> Panel | None:
    """Render the 'since last view' delta banner. Returns None if empty."""
    if delta.is_empty():
        return None

    from hero.viewport.delta import _render_delta_banner as _make_banner
    return _make_banner(delta)


def _render_sandboxes(army: ArmyMetrics) -> Panel:
    table = Table(
        show_header=True,
        header_style="bold grey50",
        border_style="grey30",
        expand=True,
        padding=(0, 1),
        row_styles=["none", "dim"],
        min_width=60,
    )
    table.add_column("Sandbox", style="bold", min_width=10, max_width=12)
    table.add_column("Status", width=12)
    table.add_column("Model", min_width=14, max_width=22)
    table.add_column("Tokens", min_width=20, max_width=24)
    table.add_column("Tools", width=6, justify="right")

    # Filter out empty sandboxes and limit to 10
    active_sandboxes = [sb for sb in army.sandboxes if sb.name][:10]

    for sb in active_sandboxes:
        ratio = sb.usage_ratio
        bar = _usage_bar(ratio)
        bc = _bar_color(ratio)
        status_icon = _status_badge(sb.status)
        status_color = sb.status_color
        table.add_row(
            sb.name[:12],
            status_icon,
            Text(sb.model or "—", style="cyan" if sb.model else "dim"),
            Text.assemble((bar, bc), f" {int(ratio * 100)}%"),
            str(sb.tool_calls),
        )

    return Panel(
        table,
        title=Text("Sandboxes", style="bold"),
        border_style="grey35",
        padding=(0, 0),
    )


def _render_footer(show_delta_hint: bool = False) -> Panel:
    parts = [
        ("[q]", "grey30"), "quit ",
        ("[r]", "grey30"), "refresh ",
        ("[1-9]", "grey30"), "focus ",
        (f"refresh:{REFRESH_INTERVAL:.0f}s", "dim"),
    ]
    if show_delta_hint:
        parts.append((" ", "white"))
        parts.append(("[D]", "yellow"), "delta ")
    hint = Text.assemble(*parts)
    return Panel(hint, border_style="grey30", padding=(0, 0))


# ── layout ──────────────────────────────────────────────────────────────────

def build_layout(army: ArmyMetrics, delta: SessionDelta | None = None) -> Layout:
    """Build the full dashboard layout.

    If *delta* is non-empty a third panel is inserted between header and
    sandbox table.
    """
    layout = Layout()

    # Determine number of sections (header + optional delta + sandboxes + footer).
    num_sections = 4 if delta and not delta.is_empty() else 3

    # Estimate heights.
    delta_height = 3 if delta and not delta.is_empty() else 0
    num_sandboxes = min(len([sb for sb in army.sandboxes if sb.name]), 10)
    sandbox_height = num_sandboxes + 5  # table + borders

    if num_sections == 4:
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="delta", size=delta_height),
            Layout(name="sandboxes", size=sandbox_height),
            Layout(name="footer", size=3),
        )
    else:
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="sandboxes", size=sandbox_height),
            Layout(name="footer", size=3),
        )

    layout["header"].update(_render_header(army))
    if num_sections == 4:
        layout["delta"].update(_render_delta_banner(delta))
    layout["sandboxes"].update(_render_sandboxes(army))
    layout["footer"].update(_render_footer(show_delta_hint=(num_sections == 4)))
    return layout


# ── modes ───────────────────────────────────────────────────────────────────

def render_once(sandbox_filter: str | None = None) -> None:
    """Print one snapshot and exit."""
    console = Console()
    army = collect(sandbox_filter)
    delta = compute_delta(army)
    console.print(build_layout(army, delta))


def render_live(console: Console, sandbox_filter: str | None = None) -> None:
    """Live auto-refreshing dashboard using Rich Live display."""
    from hero.viewport.delta import capture_previous

    from rich.live import Live

    with Live(console=console, refresh_per_second=0.5, screen=True) as live:
        # Capture initial snapshot for delta computation on first render.
        army = collect(sandbox_filter)
        capture_previous(army)

        # Put terminal in raw mode for key-by-key input
        old_settings = None
        try:
            import termios
            old_settings = termios.tcgetattr(sys.stdin)
            new_settings = old_settings[:]
            new_settings[3] &= ~termios.ICANON
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, new_settings)
        except (ImportError, termios.error):
            pass

        try:
            while True:
                army = collect(sandbox_filter)
                delta = compute_delta(army)
                live.update(build_layout(army, delta))
                capture_previous(army)

                # Non-blocking input check (10ms poll)
                if select.select([sys.stdin], [], [], 0.01)[0]:
                    ch = sys.stdin.read(1)
                    if ch == "q":
                        break
                    elif ch == "r":
                        continue
                    elif ch == "d":
                        # Toggle delta on/off (in live mode, always show next render)
                        pass
                    elif ch == "\x1b":
                        import time as _time
                        _time.sleep(0.01)
                        rest = ""
                        while select.select([sys.stdin], [], [], 0.001)[0]:
                            rest += sys.stdin.read(1)
                        if not rest:
                            sandbox_filter = None
                    elif ch.isdigit():
                        idx = int(ch) - 1
                        if 0 <= idx < len(army.sandboxes):
                            sandbox_filter = army.sandboxes[idx].name
        finally:
            if old_settings is not None:
                try:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                except Exception:
                    pass


# ── entry point ──────────────────────────────────────────────────────────────

def run(once: bool = False, sandbox: str | None = None) -> None:
    """Main entry point for the viewport dashboard (dashboard mode).

    Args:
        once:     If True, print one snapshot and exit.
        sandbox:  Optional sandbox name to focus the dashboard on.
    """
    if once:
        render_once(sandbox_filter=sandbox)
    else:
        render_live(Console(), sandbox_filter=sandbox)


def run_tree(once: bool = False, sandbox: str | None = None) -> None:
    """Main entry point for the viewport dashboard (tree/army mode).

    Args:
        once:     If True, print one snapshot and exit.
        sandbox:  Optional sandbox name to focus the dashboard on.
    """
    from hero.viewport.tree_renderer import build_tree_layout, _build_dispatch_map
    from hero.viewport.intel import detect_bottlenecks, compute_budget_projections, generate_actions

    console = Console()
    army = collect(sandbox)

    # Collect dispatch data once, share with tree layout
    sandbox_names = {sb.name for sb in army.sandboxes}
    dispatch_map = _build_dispatch_map(sandbox_names)

    bottlenecks = detect_bottlenecks(army, dispatch_map)
    projections = compute_budget_projections(army)
    actions = generate_actions(bottlenecks, projections)

    # Add header at top
    header = _render_header(army)

    if once:
        # Print each panel sequentially. Console.print(Layout) is
        # clipped at terminal height (typically 25 lines), so we
        # print children directly instead of nesting.
        console.print(header)
        body_layout = build_tree_layout(
            army, bottlenecks, projections, actions,
            dispatch_map=dispatch_map,
        )
        for child in body_layout._children:
            if child._renderable:
                console.print(child._renderable)
    else:
        from rich.live import Live
        with Live(console=console, refresh_per_second=0.5, screen=True) as live:
            old_settings = None
            try:
                import termios
                old_settings = termios.tcgetattr(sys.stdin)
                new_settings = old_settings[:]
                new_settings[3] &= ~termios.ICANON
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, new_settings)
            except (ImportError, termios.error):
                pass

            # ── Navigation & UI state ────────────────────────────────────
            detail_mode: bool = False
            selected_sandbox: str | None = None
            selected_idx: int = 0
            search_mode: bool = False
            search_query: str = ""
            frame_counter: int = 0

            sparkline_tracker = SparklineTracker()
            capture_previous(army)

            import time as _time

            try:
                while True:
                    army = collect(sandbox)
                    frame_counter = (frame_counter + 1) % 60

                    sparkline_tracker.record(army)
                    sparkline = sparkline_tracker.sparkline()
                    burn_rate = sparkline_tracker.burn_rate()

                    # ── Delta ──────────────────────────────────────────────
                    delta = compute_delta(army)
                    capture_previous(army)
                    delta_banner = _render_delta_banner(delta)

                    # ── Search / sandbox list ──────────────────────────────
                    all_sandbox_names = sorted(
                        [sb.name for sb in army.sandboxes if sb.name],
                        key=lambda n: n.lower(),
                    )

                    if search_mode and search_query:
                        matched = [s for s in all_sandbox_names if search_query.lower() in s.lower()]
                        sandbox_list = matched
                    else:
                        sandbox_list = sorted(
                            all_sandbox_names,
                            key=lambda n: (
                                0 if any(s.name == n and s.status in ("active", "running", "working")
                                         for s in army.sandboxes) else 1,
                                n.lower(),
                            )
                        )

                    # Clamp selection index to valid range
                    if not sandbox_list:
                        selected_idx = 0
                    elif selected_idx >= len(sandbox_list):
                        selected_idx = len(sandbox_list) - 1

                    # If detail mode and sandbox disappeared, reset
                    if detail_mode and selected_sandbox not in sandbox_list:
                        detail_mode = False
                        selected_sandbox = None

                    # Rebuild dispatch map each cycle (data changes each cycle)
                    sb_names = {sb.name for sb in army.sandboxes}
                    dispatch_map = _build_dispatch_map(sb_names)
                    bottlenecks = detect_bottlenecks(army, dispatch_map)
                    projections = compute_budget_projections(army)
                    actions = generate_actions(bottlenecks, projections)

                    # ── Header with sparkline ─────────────────────────────
                    header = _render_header(army, sparkline=sparkline, burn_rate=burn_rate)

                    # ── Build layout with optional delta banner & status bar ──
                    layout = Layout()
                    if delta_banner:
                        layout.split_column(
                            Layout(name="header", size=3),
                            Layout(name="delta", size=3),
                            Layout(name="body"),
                            Layout(name="status_bar", size=3),
                        )
                        layout["header"].update(header)
                        layout["delta"].update(delta_banner)
                    else:
                        layout.split_column(
                            Layout(name="header", size=3),
                            Layout(name="body"),
                            Layout(name="status_bar", size=3),
                        )
                        layout["header"].update(header)

                    # Pass dispatch map to avoid re-detection inside build_tree_layout
                    body = build_tree_layout(
                        army,
                        bottlenecks=bottlenecks,
                        projections=projections,
                        actions=actions,
                        selected_sandbox=selected_sandbox if detail_mode else None,
                        highlight_sandbox=sandbox_list[selected_idx] if sandbox_list and not detail_mode else None,
                        dispatch_map=dispatch_map,
                        frame=frame_counter,
                        delta=delta,
                    )
                    layout["body"].update(body)

                    # ── Status bar ────────────────────────────────────────────
                    error_count = sum(1 for sb in army.sandboxes if sb.status in ("error", "failed"))
                    status_bar = _render_status_bar(
                        army,
                        datetime.now().strftime("%H:%M:%S"),
                        error_count,
                        frame_counter,
                    )
                    layout["status_bar"].update(status_bar)

                    live.update(layout)

                    # ── Keyboard input ────────────────────────────────────
                    if select.select([sys.stdin], [], [], 0.01)[0]:
                        ch = sys.stdin.read(1)

                        if search_mode:
                            # ── Search mode: capture characters ───────────
                            if ch == "\r" or ch == "\n":  # Enter → apply filter
                                search_mode = False
                                if sandbox_list:
                                    selected_idx = 0
                            elif ch == "\x1b":  # Esc → cancel search
                                search_mode = False
                                search_query = ""
                            elif ch == "\x7f" or ch == "\b":  # Backspace
                                search_query = search_query[:-1]
                            else:
                                search_query += ch
                        else:
                            # ── Normal navigation mode ──────────────────────
                            if ch == "q":
                                if detail_mode:
                                    detail_mode = False
                                    selected_sandbox = None
                                else:
                                    break
                            elif ch == "r":
                                continue
                            elif ch == "j":
                                # Move selection DOWN (same as ↓ arrow)
                                if not detail_mode and sandbox_list:
                                    selected_idx = (selected_idx + 1) % len(sandbox_list)
                            elif ch == "k":
                                # Move selection UP (same as ↑ arrow)
                                if not detail_mode and sandbox_list:
                                    selected_idx = (selected_idx - 1) % len(sandbox_list)
                            elif ch == "/":
                                # Enter search mode
                                search_mode = True
                                search_query = ""
                            elif ch == "d":
                                # Toggle detail mode (alias for Enter/Esc)
                                if not detail_mode and sandbox_list:
                                    selected_sandbox = sandbox_list[selected_idx]
                                    detail_mode = True
                                elif detail_mode:
                                    detail_mode = False
                                    selected_sandbox = None
                            elif ch == "\r" or ch == "\n":
                                # Enter — drill into selected sandbox
                                if not detail_mode and sandbox_list:
                                    selected_sandbox = sandbox_list[selected_idx]
                                    detail_mode = True
                            elif ch == "\x1b":
                                _time.sleep(0.01)
                                rest = ""
                                while select.select([sys.stdin], [], [], 0.001)[0]:
                                    rest += sys.stdin.read(1)
                                if rest == "[A":
                                    # ↑ arrow
                                    if not detail_mode and sandbox_list:
                                        selected_idx = (selected_idx - 1) % len(sandbox_list)
                                elif rest == "[B":
                                    # ↓ arrow
                                    if not detail_mode and sandbox_list:
                                        selected_idx = (selected_idx + 1) % len(sandbox_list)
                                elif not rest:
                                    # Bare ESC — exit drill-down
                                    if detail_mode:
                                        detail_mode = False
                                        selected_sandbox = None
                            elif ch.isdigit():
                                idx = int(ch) - 1
                                if 0 <= idx < len(sandbox_list):
                                    selected_idx = idx
            finally:
                if old_settings is not None:
                    try:
                        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                    except Exception:
                        pass
