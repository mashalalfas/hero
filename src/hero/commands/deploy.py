"""hero deploy — Deploy soldiers to multiple sandboxes in parallel."""

from __future__ import annotations

import concurrent.futures
import threading
from pathlib import Path

import click

from hero.state.index import IndexState
from hero.soldier.spawner import SoldierSpawner
from hero.soldier.context import BudgetConfig, KatanaData


DEFAULT_BOOTSTRAP_MAX = 5000


def _spawn_in_sandbox(
    sandbox_name: str,
    sandbox_path: Path,
    task: str,
    budget: int,
) -> dict:
    """Spawn a soldier in a single sandbox. Thread-safe."""
    budget_config = BudgetConfig(
        bootstrap_max=budget,
        compactions_used=0,
        tokens_remaining=budget,
    )

    spawner = SoldierSpawner(sandbox_path)
    try:
        soldier_id = spawner.launch(task=task, budget=budget_config)
        return {
            "sandbox": sandbox_name,
            "status": "success",
            "soldier_id": soldier_id,
        }
    except Exception as e:
        return {
            "sandbox": sandbox_name,
            "status": "error",
            "error": str(e),
        }


@click.command()
@click.option(
    "--targets",
    required=True,
    type=str,
    help="Comma-separated list of sandbox names.",
)
@click.option(
    "--task",
    required=True,
    type=str,
    help="Task description for all target sandboxes.",
)
@click.option(
    "--budget",
    type=int,
    default=DEFAULT_BOOTSTRAP_MAX,
    help=f"Maximum budget per soldier (default: {DEFAULT_BOOTSTRAP_MAX}).",
)
@click.option(
    "--parallel",
    type=int,
    default=4,
    help="Max parallel spawns (default: 4).",
)
def deploy(targets: str, task: str, budget: int, parallel: int) -> None:
    """Deploy soldier agents to multiple sandboxes simultaneously.

    Parses --targets as comma-separated sandbox names, resolves each
    against INDEX.toon, and spawns soldiers in parallel.

    Example:
        hero deploy --targets sook-pro,freya,hoppy-backend --task "review logs"
    """
    index = IndexState()
    target_names = [t.strip() for t in targets.split(",") if t.strip()]

    if not target_names:
        raise click.ClickException("No targets specified.")

    # Resolve sandbox paths
    resolved: list[tuple[str, Path]] = []
    for name in target_names:
        entry = index.get_sandbox(name)
        if not entry:
            click.echo(f"Warning: Sandbox '{name}' not found in INDEX. Skipping.")
            continue
        path = Path(entry["path"])
        if not path.exists():
            click.echo(f"Warning: Sandbox path for '{name}' does not exist. Skipping.")
            continue
        resolved.append((name, path))

    if not resolved:
        raise click.ClickException("No valid targets found.")

    click.echo(f"Deploying to {len(resolved)} sandbox(es): {', '.join(t[0] for t in resolved)}")
    click.echo(f"  task: {task}")
    click.echo(f"  budget: {budget} per soldier")
    click.echo(f"  parallel workers: {parallel}")
    click.echo()

    results: list[dict] = []
    lock = threading.Lock()

    def worker(name: str, path: Path) -> None:
        result = _spawn_in_sandbox(name, path, task, budget)
        with lock:
            results.append(result)

    with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = [
            executor.submit(worker, name, path)
            for name, path in resolved
        ]
        concurrent.futures.wait(futures)

    # Report results
    click.echo("\n=== Deployment Results ===")
    successes = sum(1 for r in results if r["status"] == "success")
    failures = sum(1 for r in results if r["status"] == "error")

    for result in results:
        if result["status"] == "success":
            click.echo(f"  [OK] {result['sandbox']}: soldier {result['soldier_id']}")
        else:
            click.echo(f"  [FAIL] {result['sandbox']}: {result.get('error', 'unknown error')}")

    click.echo(f"\nSummary: {successes} succeeded, {failures} failed")

    if failures:
        raise click.ClickException(f"{failures} deployment(s) failed.")


if __name__ == "__main__":
    deploy()