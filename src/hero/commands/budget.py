"""hero budget — Multi-sandbox budget query command.

Subcommands:
    hero budget [--query ..] [--sandbox ..] [--format ..]
        Default (invoke-without-command): query/filter budgets.
    hero budget summary
        Table of all sandboxes with usage / remaining / utilisation.
    hero budget top --limit 10
        Top N consumers by tokens used.
    hero budget alert --threshold 2000
        List sandboxes with remaining tokens below threshold.

Supports filtering by budget values and status using query expressions.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

import click
from rich.console import Console
from rich.table import Table
from rich.text import Text

from hero.state.budget_history import get_all_history, get_history
from hero.state.toon import toon_read


SANDBOX_DIR = Path.home() / ".hero" / "sandboxes"

# ═══════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════

_console = Console()


def _load_all_budgets(sandbox_dir: Path | None = None) -> list[dict[str, Any]]:
    """Load budget data from all sandbox BUDGET.toon files."""
    dir_path = sandbox_dir or SANDBOX_DIR
    budgets: list[dict[str, Any]] = []

    if not dir_path.exists():
        return budgets

    for entry in sorted(dir_path.iterdir()):
        if not entry.is_dir():
            continue

        budget_file = entry / "BUDGET.toon"
        heartbeat_file = entry / "HEARTBEAT.toon"

        budget_data = toon_read(budget_file) if budget_file.exists() else {}
        heartbeat_data = toon_read(heartbeat_file) if heartbeat_file.exists() else {}

        bootstrap_max = budget_data.get("bootstrap_max", 5000)
        tokens_remaining = budget_data.get("tokens_remaining", 5000)
        compactions_used = budget_data.get("compactions_used", 0)
        tokens_used = bootstrap_max - tokens_remaining

        sandbox_data = {
            "name": entry.name,
            "path": str(entry),
            "bootstrap_max": bootstrap_max,
            "compactions_used": compactions_used,
            "tokens_remaining": tokens_remaining,
            "tokens_used": max(0, tokens_used),
            "utilization": (tokens_used / bootstrap_max * 100) if bootstrap_max > 0 else 0.0,
            "status": heartbeat_data.get("status", "idle"),
        }
        budgets.append(sandbox_data)

    return budgets


def _format_budget_toon(budgets: list[dict[str, Any]]) -> str:
    """Format budget results as TOON output."""
    if not budgets:
        return "# No budgets found"

    lines: list[str] = []
    for b in budgets:
        lines.append(f"sandbox: {b['name']}")
        lines.append(f'  path: "{b["path"]}"')
        lines.append(f"  status: {b['status']}")
        lines.append("  budget:")
        lines.append(f"    bootstrap_max: {b['bootstrap_max']}")
        lines.append(f"    compactions_used: {b['compactions_used']}")
        lines.append(f"    tokens_remaining: {b['tokens_remaining']}")
        lines.append(f"    tokens_used: {b['tokens_used']}")
        lines.append(f"    utilization: {b['utilization']:.1f}")
        lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# Query expression parser (unchanged from original)
# ═══════════════════════════════════════════════════════════════════


def _parse_query_expression(query: str) -> Callable:
    """Parse a budget query expression into a callable filter.

    Supports:
        - budget < 2000
        - budget > 5000
        - budget == 3000
        - budget <= 1000
        - budget >= 4000
        - status == "active"
        - status == 'active'
        - AND / OR operators
        - Parentheses for grouping

    Args:
        query: Query expression string

    Returns:
        Callable that takes a sandbox data dict and returns bool

    Raises:
        ValueError: If the expression is invalid
    """
    normalized = query.strip()

    def _make_evaluator(expr: str):
        """Create a safe evaluator for budget expressions."""
        allowed_names: dict[str, Any] = {
            "and": True,
            "or": True,
            "True": True,
            "False": False,
            "None": None,
            "active": "active",
            "idle": "idle",
            "frozen": "frozen",
        }

        # Check for dangerous patterns BEFORE the safe-character check so
        # the "Disallowed keyword" error takes priority over "Invalid chars"
        dangerous = [
            "import",
            "exec",
            "eval",
            "open",
            "file",
            "read",
            "write",
            "__",
            "lambda",
            "class",
            "def",
            "return",
            "yield",
            "global",
            "nonlocal",
            "assert",
            "break",
            "continue",
            "pass",
            "raise",
        ]
        lower_expr = expr.lower()
        for d in dangerous:
            if d in lower_expr:
                raise ValueError(f"Disallowed keyword in query expression: {d}")

        # Validate the expression contains only safe characters and words
        safe_pattern = re.compile(r"^[\s\w<>=!.\+\-'\(\),\[\]]+$")
        if not safe_pattern.match(expr):
            raise ValueError(f"Invalid characters in query expression: {expr}")

        # Convert AND/OR to Python keywords
        py_expr = expr
        py_expr = re.sub(r"\bAND\b", "and", py_expr, flags=re.IGNORECASE)
        py_expr = re.sub(r"\bOR\b", "or", py_expr, flags=re.IGNORECASE)

        def evaluator(sandbox_data: dict) -> bool:
            """Evaluate the expression against sandbox data."""
            namespace: dict[str, Any] = {
                "budget": sandbox_data.get("tokens_remaining", 0),
                "budget_max": sandbox_data.get("bootstrap_max", 0),
                "tokens_used": sandbox_data.get("tokens_used", 0),
                "utilization": sandbox_data.get("utilization", 0.0),
                "compactions": sandbox_data.get("compactions_used", 0),
                "status": sandbox_data.get("status", "idle"),
                "name": sandbox_data.get("name", ""),
            }
            namespace.update(allowed_names)

            try:
                result = eval(py_expr, {"__builtins__": {}}, namespace)  # noqa: S307
                return bool(result)
            except Exception as e:
                raise ValueError(f"Failed to evaluate expression '{expr}': {e}") from e

        return evaluator

    return _make_evaluator(normalized)


# ═══════════════════════════════════════════════════════════════════
# The budget command group
# ═══════════════════════════════════════════════════════════════════


@click.group(invoke_without_command=True)
@click.pass_context
@click.option(
    "--query",
    type=str,
    default=None,
    help=(
        "Budget query expression. "
        "Examples: 'budget < 2000', 'budget > 5000 AND status == active', "
        "'compactions >= 3 OR budget < 1000'"
    ),
)
@click.option(
    "--sandbox",
    type=str,
    default=None,
    help="Filter to a specific sandbox by name.",
)
@click.option(
    "--fmt",
    "--format",
    "format_",
    type=click.Choice(["toon", "json", "plain"]),
    default="toon",
    help="Output format.",
)
def budget(
    ctx: click.Context,
    query: str | None,
    sandbox: str | None,
    format_: str,
) -> None:
    """Query and display budget state across all sandboxes.

    Without a subcommand, runs the budget query using --query, --sandbox,
    and --format options.

    Subcommands:
        summary   Table view of all sandbox budget usage.
        top       Top N consumers by tokens used.
        alert     Sandboxes with remaining tokens below threshold.
        history   Show recent budget events for a sandbox.

    Query Operators:
        Comparisons: <, >, <=, >=, ==, !=
        Logical: AND, OR
        Grouping: ( )

    Query Fields:
        budget         tokens_remaining
        budget_max     bootstrap_max
        tokens_used    tokens consumed
        utilization    usage percentage (0-100)
        compactions    compactions_used
        status         sandbox status (idle, active, etc.)
        name           sandbox name
    """
    if ctx.invoked_subcommand is None:
        _run_query(query, sandbox, format_)


# ═══════════════════════════════════════════════════════════════════
# Default: original query behaviour
# ═══════════════════════════════════════════════════════════════════


def _run_query(
    query: str | None,
    sandbox: str | None,
    format_: str,
) -> None:
    """Execute the original budget query logic."""
    all_budgets = _load_all_budgets()

    if not all_budgets:
        click.echo("No sandboxes found. Run 'hero scan' first.")
        return

    # Filter by specific sandbox if requested
    if sandbox:
        all_budgets = [b for b in all_budgets if b["name"] == sandbox]
        if not all_budgets:
            raise click.ClickException(f"Sandbox '{sandbox}' not found.")

    # Apply query filter if provided
    if query:
        try:
            filter_func = _parse_query_expression(query)
            filtered = [b for b in all_budgets if filter_func(b)]
        except ValueError as e:
            raise click.ClickException(f"Invalid query expression: {e}") from e

        all_budgets = filtered

    # Output results
    if not all_budgets:
        click.echo("No sandboxes match the query.")
        return

    if format_ == "plain":
        for b in all_budgets:
            click.echo(
                f"{b['name']}: budget={b['tokens_remaining']}, "
                f"compactions={b['compactions_used']}, "
                f"status={b['status']}"
            )
    elif format_ == "json":
        import json

        click.echo(json.dumps(all_budgets, indent=2))
    else:
        click.echo(_format_budget_toon(all_budgets))


# ═══════════════════════════════════════════════════════════════════
# Subcommand: summary
# ═══════════════════════════════════════════════════════════════════


@budget.command(name="summary")
def budget_summary() -> None:
    """Show all sandboxes with budget usage in a colour-coded table."""
    all_budgets = _load_all_budgets()

    if not all_budgets:
        click.echo("No sandboxes found. Run 'hero scan' first.")
        return

    table = Table(
        title="Sandbox Budget Summary",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Sandbox", style="cyan")
    table.add_column("Used", justify="right")
    table.add_column("Remaining", justify="right")
    table.add_column("Util", justify="right")

    total_used = 0
    total_max = 0

    for b in all_budgets:
        used = b["tokens_used"]
        remaining = b["tokens_remaining"]
        util = b["utilization"]
        total_used += used
        total_max += b["bootstrap_max"]

        # Color-code utilisation
        if util >= 80:
            style = "bold red"
            indicator = " ⚠"
        elif util >= 60:
            style = "bold yellow"
            indicator = " ▲"
        else:
            style = "bold green"
            indicator = ""

        used_fmt = f"{used:,}"
        remaining_fmt = f"{remaining:,}"
        util_fmt = f"{util:.1f}%{indicator}"

        table.add_row(
            b["name"],
            Text(used_fmt, style=style),
            Text(remaining_fmt),
            Text(util_fmt, style=style),
        )

    # Totals row
    overall_util = (total_used / total_max * 100) if total_max > 0 else 0.0

    total_style = "bold red" if overall_util >= 80 else "bold yellow" if overall_util >= 60 else "bold green"
    table.add_row(
        Text("Total", style="bold"),
        Text(f"{total_used:,}", style=total_style),
        Text(f"{total_max - total_used:,}"),
        Text(f"{overall_util:.1f}%", style=total_style),
    )

    _console.print(table)


# ═══════════════════════════════════════════════════════════════════
# Subcommand: top
# ═══════════════════════════════════════════════════════════════════


@budget.command(name="top")
@click.option(
    "--limit",
    type=int,
    default=10,
    show_default=True,
    help="Number of top consumers to show.",
)
def budget_top(limit: int) -> None:
    """Show top N sandbox consumers by tokens used."""
    all_budgets = _load_all_budgets()

    if not all_budgets:
        click.echo("No sandboxes found. Run 'hero scan' first.")
        return

    # Sort by tokens_used descending
    sorted_budgets = sorted(all_budgets, key=lambda b: b["tokens_used"], reverse=True)
    top_budgets = sorted_budgets[:limit]

    table = Table(
        title=f"Top {limit} Token Consumers",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("#", justify="right", style="dim")
    table.add_column("Sandbox", style="cyan")
    table.add_column("Tokens Used", justify="right")
    table.add_column("Remaining", justify="right")
    table.add_column("Util", justify="right")
    table.add_column("Compactions", justify="right")

    for i, b in enumerate(top_budgets, start=1):
        util = b["utilization"]
        util_style = "bold red" if util >= 80 else "bold yellow" if util >= 60 else "bold green"

        table.add_row(
            str(i),
            b["name"],
            f"{b['tokens_used']:,}",
            f"{b['tokens_remaining']:,}",
            Text(f"{util:.1f}%", style=util_style),
            str(b["compactions_used"]),
        )

    _console.print(table)


# ═══════════════════════════════════════════════════════════════════
# Subcommand: alert
# ═══════════════════════════════════════════════════════════════════


@budget.command(name="alert")
@click.option(
    "--threshold",
    type=int,
    default=2000,
    show_default=True,
    help="Alert when remaining tokens drop below this value.",
)
def budget_alert(threshold: int) -> None:
    """List sandboxes with remaining tokens below the threshold."""
    all_budgets = _load_all_budgets()

    if not all_budgets:
        click.echo("No sandboxes found. Run 'hero scan' first.")
        return

    low_budgets = [b for b in all_budgets if b["tokens_remaining"] < threshold]

    if not low_budgets:
        click.echo(
            f"All sandboxes have at least {threshold:,} remaining tokens. ✓"
        )
        return

    table = Table(
        title=f"Budget Alert — Remaining < {threshold:,}",
        show_header=True,
        header_style="bold red",
    )
    table.add_column("Sandbox", style="cyan")
    table.add_column("Remaining", justify="right")
    table.add_column("Used", justify="right")
    table.add_column("Util", justify="right")
    table.add_column("Status")

    for b in low_budgets:
        remaining = b["tokens_remaining"]
        util = b["utilization"]

        if remaining <= 0:
            remaining_style = "bold red"
            status_icon = "⛔ EXHAUSTED"
        elif remaining < threshold // 2:
            remaining_style = "bold red"
            status_icon = "⚠ CRITICAL"
        else:
            remaining_style = "bold yellow"
            status_icon = "⚠ LOW"

        table.add_row(
            b["name"],
            Text(f"{remaining:,}", style=remaining_style),
            f"{b['tokens_used']:,}",
            f"{util:.1f}%",
            status_icon,
        )

    _console.print(table)


# ═══════════════════════════════════════════════════════════════════
# Subcommand: history
# ═══════════════════════════════════════════════════════════════════


@budget.command(name="history")
@click.option(
    "--sandbox",
    type=str,
    default=None,
    help="Filter to a specific sandbox (omit for all).",
)
@click.option(
    "--limit",
    type=int,
    default=20,
    show_default=True,
    help="Number of recent events to show.",
)
@click.option(
    "--fmt",
    "--format",
    "format_",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format.",
)
def budget_history(
    sandbox: str | None,
    limit: int,
    format_: str,
) -> None:
    """Show recent budget history events."""
    if sandbox:
        entries = get_history(sandbox, limit=limit)
    else:
        entries = get_all_history(limit=limit)

    if not entries:
        click.echo("No budget history available.")
        return

    if format_ == "json":
        import json

        click.echo(json.dumps(entries, indent=2))
        return

    table = Table(
        title=f"Budget History{' for ' + sandbox if sandbox else ''}",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Timestamp")
    table.add_column("Sandbox", style="cyan")
    table.add_column("Event")
    table.add_column("Before", justify="right")
    table.add_column("After", justify="right")
    table.add_column("Delta", justify="right")

    for entry in entries:
        ts = entry.get("ts", "")
        # Trim timestamp for readability
        if len(ts) > 19:
            ts = ts[:19] + "Z"
        event = entry.get("event", "")
        before = entry.get("tokens_before", 0)
        after = entry.get("tokens_after", 0)
        delta = after - before

        # Colour delta
        if delta < 0:
            delta_text = Text(f"{delta:,}", style="bold red")
        elif delta > 0:
            delta_text = Text(f"+{delta:,}", style="bold green")
        else:
            delta_text = Text("0", style="dim")

        # Colour event type
        event_style = {
            "spawn": "bold yellow",
            "complete": "bold green",
            "compact": "bold blue",
            "compaction_record": "dim",
        }.get(event, "white")
        event_text = Text(event, style=event_style)

        table.add_row(
            ts,
            entry.get("sandbox", ""),
            event_text,
            f"{before:,}",
            f"{after:,}",
            delta_text,
        )

    _console.print(table)


if __name__ == "__main__":
    budget()
