"""hero katana — View and manage Katana state for a sandbox."""

from __future__ import annotations

import click

from hero.state.index import IndexState
from hero.state.sandbox import SandboxState


@click.command()
@click.option(
    "--sandbox",
    type=str,
    required=True,
    help="Sandbox name (must be registered via hero scan).",
)
@click.option(
    "--spawn",
    type=str,
    default=None,
    help="Add a pending task (spawns soldier, decrements budget).",
)
@click.option(
    "--complete",
    type=str,
    default=None,
    help="Complete a pending task (increments budget).",
)
@click.option(
    "--compact",
    is_flag=True,
    default=False,
    help="Reset compactions_used counter (compact budget).",
)
@click.option(
    "--add-issue",
    type=str,
    default=None,
    help="Add a known issue to the katana list.",
)
def katana(sandbox: str, spawn: str | None, complete: str | None, compact: bool, add_issue: str | None) -> None:
    """View and manage Katana state for a sandbox.

    Shows:
    - pending tasks (katana.pending)
    - known issues (katana.known_issues)
    - budget state (tokens_remaining, compactions_used, bootstrap_max)

    Operations:
    --spawn TASK   Add a pending task (decrements budget tokens)
    --complete TASK   Complete a pending task (increments budget tokens)
    --compact     Reset compactions_used counter
    --add-issue ISSUE   Add a known issue

    Example:
        hero katana --sandbox sook-pro
        hero katana --sandbox sook-pro --spawn "fix memory leak"
        hero katana --sandbox sook-pro --complete "fix memory leak"
        hero katana --sandbox sook-pro --compact
    """
    index = IndexState()
    entry = index.get_sandbox(sandbox)

    if not entry:
        raise click.ClickException(
            f"Sandbox '{sandbox}' not found. Run 'hero scan' first."
        )

    sandbox_state = SandboxState(sandbox)

    # Handle operations
    if spawn:
        sandbox_state.add_pending_task(spawn)
        click.echo(f"Spawned task: {spawn}")
        # Show updated state
        _show_katana_status(sandbox_state, sandbox)
        return

    if complete:
        found = sandbox_state.complete_task(complete)
        if found:
            click.echo(f"Completed task: {complete}")
        else:
            click.echo(f"Task not found in pending list: {complete}")
        # Show updated state
        _show_katana_status(sandbox_state, sandbox)
        return

    if compact:
        sandbox_state.compact_budget()
        click.echo("Budget compactions reset.")
        # Show updated state
        _show_katana_status(sandbox_state, sandbox)
        return

    if add_issue:
        sandbox_state.add_known_issue(add_issue)
        click.echo(f"Added known issue: {add_issue}")
        # Show updated state
        _show_katana_status(sandbox_state, sandbox)
        return

    # Default: show status
    _show_katana_status(sandbox_state, sandbox)


def _show_katana_status(sandbox_state: SandboxState, sandbox_name: str) -> None:
    """Display Katana status for a sandbox."""
    status = sandbox_state.get_katana_status()

    pending = status["pending"]
    known_issues = status["known_issues"]
    budget = status["budget"]

    click.echo(f"\n=== Katana: {sandbox_name} ===")
    click.echo(f"pending[{len(pending)}]: {', '.join(pending) or 'none'}")
    click.echo(f"known_issues[{len(known_issues)}]: {', '.join(known_issues) or 'none'}")
    click.echo(f"budget:")
    click.echo(f"  tokens_remaining: {budget['tokens_remaining']}")
    click.echo(f"  compactions_used: {budget['compactions_used']}")
    click.echo(f"  bootstrap_max: {budget['bootstrap_max']}")


if __name__ == "__main__":
    katana()
