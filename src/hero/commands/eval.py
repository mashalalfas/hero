"""hero eval — Run the pre-launch evaluation pipeline."""

from __future__ import annotations

from pathlib import Path

import click

from hero.state.index import IndexState


@click.group(invoke_without_command=True)
@click.option("--sandbox", type=str, default=None, help="Sandbox to evaluate.")
@click.option("--phase", type=int, default=None, help="Run a single phase (by number).")
@click.option("--phases", type=str, default=None, help="Comma-separated phase numbers (e.g. '1,2,3').")
@click.option("--fix", "fix_after", is_flag=True, default=False, help="Run fix phase after evaluation.")
@click.option("--score", "score_only", is_flag=True, default=False, help="Show existing scorecard without re-running.")
@click.option("--list-evals", "list_evals", is_flag=True, default=False, help="List all past evaluations.")
@click.pass_context
def eval(ctx: click.Context, sandbox: str | None, phase: int | None, phases: str | None,
         fix_after: bool, score_only: bool, list_evals: bool) -> None:
    """Run the pre-launch evaluation pipeline.

    Evaluates a project sandbox through 10 phases: baseline, security,
    code-review, CI/CD, TDD, performance, accessibility, fix, verify, ship.

    Generates a SCORECARD.json with overall readiness score (0-100) and band.

    \b
    Examples:
        hero eval --sandbox sook-pro
        hero eval --sandbox sook-pro --phase 2
        hero eval --sandbox sook-pro --phases 1,2,3
        hero eval --sandbox sook-pro --fix
        hero eval --sandbox sook-pro --score
        hero eval --list-evals
    """
    if ctx.invoked_subcommand is not None:
        return

    # List evaluations
    if list_evals:
        _list_evaluations()
        return

    # Require sandbox name
    if not sandbox:
        raise click.ClickException("Error: --sandbox is required. Use 'hero eval --list-evals' to see past evaluations.")

    # Resolve project path
    index = IndexState()
    entry = index.get_sandbox(sandbox)
    if not entry:
        raise click.ClickException(f"Sandbox '{sandbox}' not found in INDEX. Run 'hero scan' first.")

    project_path = Path(entry["path"])
    if not project_path.exists():
        raise click.ClickException(f"Project path does not exist: {project_path}")

    # Score only mode
    if score_only:
        _show_scorecard(sandbox)
        return

    # Parse phases
    phase_list = None
    if phase:
        phase_list = [phase]
    elif phases:
        phase_list = [int(p.strip()) for p in phases.split(",") if p.strip()]

    # Run evaluation
    click.echo(f"🔍 Evaluating: {sandbox}")
    click.echo(f"   Project: {project_path}")
    if phase_list:
        click.echo(f"   Phases: {phase_list}")
    click.echo()

    from hero.eval.engine import EvalEngine
    engine = EvalEngine(sandbox, project_path)
    card = engine.run(phases=phase_list, fix_after=fix_after)

    # Display results
    _display_scorecard(card)


def _display_scorecard(card) -> None:
    """Display the scorecard in the terminal."""
    click.echo()
    click.echo("═" * 60)
    click.echo(f"  📊 SCORECARD: {card.sandbox_name}")
    click.echo("═" * 60)
    click.echo()

    # Overall
    click.echo(f"  OVERALL: {card.overall}/100  {card.band_emoji} {card.band}")
    click.echo()

    # Phase breakdown
    click.echo("  Phase Scores:")
    click.echo("  " + "─" * 50)

    for phase_num in sorted(card.phase_scores.keys()):
        phase = card.phase_scores[phase_num]
        bar_len = phase["score"] // 5
        bar = "█" * bar_len + "░" * (20 - bar_len)
        status_icon = "✅" if phase["status"] == "completed" else "⏭️" if phase["status"] == "skipped" else "❌"
        click.echo(f"  {status_icon} {phase['name']:15s} {bar} {phase['score']:3d}/100")

    click.echo("  " + "─" * 50)
    click.echo()

    # Findings
    click.echo("  Findings:")
    if card.total_critical:
        click.echo(f"    🔴 Critical: {card.total_critical}")
    if card.total_major:
        click.echo(f"    🟠 Major:    {card.total_major}")
    if card.total_minor:
        click.echo(f"    🟡 Minor:    {card.total_minor}")
    if card.total_nit:
        click.echo(f"    ⚪ Nit:      {card.total_nit}")
    click.echo(f"    Total:      {card.total_findings}")
    click.echo()

    # Duration
    click.echo(f"  ⏱  Duration: {card.duration_seconds:.1f}s")
    click.echo()

    # Report location
    from hero.eval.engine import EVAL_HOME
    eval_dir = EVAL_HOME / card.sandbox_name
    click.echo(f"  📄 Reports: {eval_dir}/")
    click.echo(f"     SCORECARD.json, SCORECARD.toon, READY-REPORT.md")
    click.echo()

    click.echo("═" * 60)


def _show_scorecard(sandbox: str) -> None:
    """Show existing scorecard for a sandbox."""
    from hero.eval.engine import EvalEngine
    engine = EvalEngine(sandbox, Path("."))  # path doesn't matter for loading
    card = engine.get_existing_scorecard()
    if not card:
        raise click.ClickException(f"No scorecard found for '{sandbox}'. Run 'hero eval --sandbox {sandbox}' first.")
    _display_scorecard(card)


def _list_evaluations() -> None:
    """List all past evaluations."""
    from hero.eval.engine import EvalEngine
    evals = EvalEngine.list_evals()

    if not evals:
        click.echo("No evaluations found. Run 'hero eval --sandbox <name>' to start one.")
        return

    click.echo(f"Past Evaluations: {len(evals)}")
    click.echo()
    click.echo(f"  {'Sandbox':20s} {'Score':6s} {'Band':25s} {'Date'}")
    click.echo("  " + "─" * 75)

    for e in evals:
        band_emoji = {"production-ready": "🟢", "ship-with-monitoring": "🟡",
                      "needs-work": "🟠", "not-ready": "🔴"}.get(e["band"], "⚪")
        click.echo(f"  {e['sandbox']:20s} {e['overall']:3d}/100 {band_emoji} {e['band']:22s} {e['generatedAt']}")


if __name__ == "__main__":
    eval()
