"""hero status — Show all sandbox states in compact TOON.

Uses StateCache.batch_load() for multi-sandbox reads to avoid redundant
disk I/O.  Katana data (pending tasks, known issues) is only read when
``--verbose`` is set, saving one file read per sandbox in normal mode.
"""

from __future__ import annotations

from pathlib import Path

import click

from hero.state.index import IndexState
from hero.state.sandbox import SandboxState, get_cache


@click.command()
@click.option(
    "--sandbox",
    type=str,
    default=None,
    help="Show only this sandbox (by name).",
)
@click.option(
    "--format",
    type=click.Choice(["toon", "json", "plain"]),
    default="toon",
    help="Output format.",
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Include katana data (pending tasks, known issues).",
)
def status(sandbox: str | None, format: str, verbose: bool) -> None:
    """Show all sandbox states in compact TOON format.

    Displays sandbox name, path, budget, status, and katana data
    for all registered sandboxes, or a single sandbox if --sandbox is given.

    Uses StateCache to minimise disk reads.  Add --verbose to include
    katana (MEMORY.toon) data.
    """
    index = IndexState()

    if sandbox:
        # Show single sandbox
        entry = index.get_sandbox(sandbox)
        if not entry:
            raise click.ClickException(f"Sandbox '{sandbox}' not found in INDEX.")
        _show_sandbox_status(entry, format, verbose=verbose)
    else:
        # Show all sandboxes — use batch_load via StateCache
        entries = index.list_sandboxes()
        if not entries:
            click.echo("No sandboxes registered. Run 'hero scan' first.")
            return

        names = [e.get("name", "unknown") for e in entries]
        cache = get_cache()

        # Batch-load all sandbox states (one round of disk I/O, cache for repeats)
        states = cache.batch_load(names)

        click.echo(f"Registered sandboxes: {len(entries)}\n")
        for i, entry in enumerate(entries):
            name = entry.get("name", "unknown")
            # Merge index entry metadata with cached sandbox state
            merged = dict(states.get(name, {}))
            merged.setdefault("path", entry.get("path", ""))
            # Only overwrite with index status if sandbox state didn't load
            if not merged:
                merged = {
                    "name": name,
                    "path": entry.get("path", ""),
                    "budget": {"bootstrap_max": entry.get("budget_max", 5000),
                               "compactions_used": 0,
                               "tokens_remaining": 5000},
                    "skills": [],
                    "katana": {"pending": [], "known_issues": []},
                    "status": entry.get("status", "idle"),
                }
            _show_sandbox_status_merged(merged, format, verbose=verbose)
            if i < len(entries) - 1:
                click.echo()


def _show_sandbox_status(entry: dict, fmt: str, verbose: bool = False) -> None:
    """Display a single sandbox's status (backwards-compat entry path)."""
    name = entry.get("name", "unknown")
    sandbox_state = SandboxState(name)
    state_data = sandbox_state.load(include_katana=verbose)
    _render_status(name, entry, state_data, fmt, verbose=verbose)


def _show_sandbox_status_merged(merged: dict, fmt: str, verbose: bool = False) -> None:
    """Display a sandbox using pre-merged data from batch_load."""
    name = merged.get("name", "unknown")
    # Reconstruct a minimal entry-like object from the merged dict
    entry = {
        "name": name,
        "path": merged.get("path", ""),
        "status": merged.get("status", "idle"),
        "budget_max": merged.get("budget", {}).get("bootstrap_max", 5000),
        "last_seen": "cached",
    }
    _render_status(name, entry, merged, fmt, verbose=verbose)


def _render_status(name: str, entry: dict, state_data: dict, fmt: str,
                   verbose: bool = False) -> None:
    """Common rendering logic for all status display paths."""
    path = entry.get("path", "")
    status_val = entry.get("status", "idle")
    budget_max = entry.get("budget_max", 5000)
    last_seen = entry.get("last_seen", "never")

    if fmt == "plain":
        click.echo(f"=== {name} ===")
        click.echo(f"  path: {path}")
        click.echo(f"  status: {status_val}")
        click.echo(f"  budget_max: {budget_max}")
        click.echo(f"  last_seen: {last_seen}")
        return

    # TOON or JSON format
    if fmt == "json":
        import json
        click.echo(json.dumps(state_data, indent=2))
        return

    # TOON format
    katana_pending = state_data.get("katana", {}).get("pending", [])
    katana_issues = state_data.get("katana", {}).get("known_issues", [])
    budget = state_data.get("budget", {})

    lines = [
        f"sandbox: {name}",
        f"path: \"{path}\"",
        f"status: {status_val}",
        f"last_seen: {last_seen}",
        f"budget{{bootstrap_max,compactions_used,tokens_remaining}}: "
        f"{budget.get('bootstrap_max', 5000)},"
        f"{budget.get('compactions_used', 0)},"
        f"{budget.get('tokens_remaining', 5000)}",
    ]

    if verbose:
        lines.append(f"katana:")
        lines.append(
            f"  pending[{len(katana_pending)}]: {', '.join(katana_pending) or 'none'}"
        )
        lines.append(
            f"  known_issues[{len(katana_issues)}]: {', '.join(katana_issues) or 'none'}"
        )
    else:
        lines.append("katana: (use --verbose to show pending/known_issues)")

    click.echo("\n".join(lines))


if __name__ == "__main__":
    status()
