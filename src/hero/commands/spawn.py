"""hero spawn — Launch a soldier agent in a sandbox."""

from __future__ import annotations

from pathlib import Path

import click

from hero.state.index import IndexState
from hero.state.sandbox import SandboxState, invalidate_cache
from hero.soldier.spawner import SoldierSpawner
from hero.soldier.context import BudgetConfig, KatanaData, SandboxData, build_context


DEFAULT_BOOTSTRAP_MAX = 5000


@click.command()
@click.option(
    "--sandbox",
    required=True,
    type=str,
    help="Sandbox name (must be registered via hero scan).",
)
@click.option(
    "--task",
    required=True,
    type=str,
    help="Task description for the soldier.",
)
@click.option(
    "--budget",
    type=int,
    default=DEFAULT_BOOTSTRAP_MAX,
    help=f"Maximum budget for this soldier (default: {DEFAULT_BOOTSTRAP_MAX}).",
)
@click.option(
    "--role",
    type=click.Choice(["lead", "architect", "soldier", "researcher", "archivist", "utility"]),
    default="soldier",
    help="Army role for model selection (default: soldier).",
)
def spawn(sandbox: str, task: str, budget: int, role: str) -> None:
    """Launch a soldier agent in a sandbox with TOON context injection.

    The soldier receives:
    - Sandbox name and path
    - Budget state (bootstrap_max, compactions_used, tokens_remaining)
    - Katana state (pending tasks, known issues)
    - Task description
    - Model assignment based on role

    Example:
        hero spawn --sandbox sook-pro --task "fix theme switcher lag"
        hero spawn --sandbox sook-pro --task "design new architecture" --role architect
    """
    index = IndexState()
    entry = index.get_sandbox(sandbox)

    if not entry:
        raise click.ClickException(
            f"Sandbox '{sandbox}' not found. Run 'hero scan' first."
        )

    sandbox_path = Path(entry["path"])
    if not sandbox_path.exists():
        raise click.ClickException(f"Sandbox path does not exist: {sandbox_path}")

    # Load real sandbox state from TOON files
    sandbox_state = SandboxState(sandbox)
    state_data = sandbox_state.load()

    # Build BudgetConfig from real state
    budget_config = BudgetConfig(
        bootstrap_max=state_data["budget"]["bootstrap_max"],
        compactions_used=state_data["budget"]["compactions_used"],
        tokens_remaining=state_data["budget"]["tokens_remaining"],
    )

    # Build KatanaData from real state
    katana_data = KatanaData(
        pending=state_data["katana"]["pending"],
        known_issues=state_data["katana"]["known_issues"],
    )

    # Build full SandboxData for context injection
    sandbox_data = SandboxData(
        name=sandbox,
        budget=budget_config,
        katana=katana_data,
    )

    # Build and display the TOON context being injected
    toon_context = build_context(sandbox_data, task)

    # Get model info for display
    from hero.soldier.spawner import get_model_for_role
    model, provider = get_model_for_role(role)

    click.echo(f"Spawning soldier in sandbox '{sandbox}'...")
    click.echo(f"  role: {role}")
    click.echo(f"  model: {model} ({provider})")
    click.echo(f"  task: {task}")
    click.echo(f"  budget: bootstrap_max={budget_config.bootstrap_max}, "
               f"compactions_used={budget_config.compactions_used}, "
               f"tokens_remaining={budget_config.tokens_remaining}")
    click.echo(f"\nTOON context being injected:")
    click.echo("-" * 40)
    click.echo(toon_context)
    click.echo("-" * 40)

    spawner = SoldierSpawner(sandbox_path)

    try:
        soldier_id = spawner.launch(task=task, budget=budget_config, role=role, model_override=(model, provider))
        # Update sandbox status so dashboard shows the tree hierarchy
        sandbox_state.update_status("running")
        sandbox_state.add_pending_task(f"[{role}] {task}")
        invalidate_cache(sandbox)
        click.echo(f"\nSoldier spawned successfully!")
        click.echo(f"  soldier_id: {soldier_id}")
        click.echo(f"  sandbox: {sandbox}")
        click.echo(f"  role: {role}")
        click.echo(f"  model: {model}")
        click.echo(f"  task: {task}")
        click.echo(f"\n  ➜ Check dashboard at http://192.168.8.149:8765")
    except RuntimeError as e:
        raise click.ClickException(f"Failed to spawn soldier: {e}")


if __name__ == "__main__":
    spawn()