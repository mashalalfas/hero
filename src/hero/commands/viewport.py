"""hero viewport — Live TUI dashboard with Rich.

Usage:
    hero viewport              # Full-screen live dashboard (auto-refresh 2s)
    hero viewport --once       # Single snapshot, then exit
    hero viewport --sandbox X  # Focus on one sandbox

Keyboard shortcuts (live mode):
    q        — quit
    r        — force refresh
    1-9      — focus sandbox by number
    ESC      — back to all sandboxes
"""

from __future__ import annotations

import click

from hero.viewport.renderer import run, run_tree
from hero.viewport.tree_renderer import build_tree_layout
from hero.viewport.metrics import collect


@click.command("viewport")
@click.option(
    "--once",
    is_flag=True,
    default=False,
    help="Print a single snapshot and exit (no live refresh).",
)
@click.option(
    "--sandbox",
    type=str,
    default=None,
    help="Focus the dashboard on a single sandbox by name.",
)
@click.option(
    "--mode",
    type=click.Choice(["dashboard", "tree", "web"], case_sensitive=False),
    default="tree",
    help="Viewport mode: tree (default, army hierarchy), dashboard (tabular metrics), or web (browser server).",
)
def viewport(once: bool, sandbox: str | None, mode: str) -> None:
    """HERO live viewport — pipeline tree, sandbox dashboard, or web UI.

    Shows pipeline state in a command-hierarchy tree (default), a tabular
    sandbox overview, or a browser-accessible dashboard.

    Modes:
      tree       — command-hierarchy tree showing pipeline flow (default)
      dashboard  — tabular sandbox overview with metrics
      web        — browser-based dashboard (FastAPI on :8765)

    Colour coding (dashboard):
      green  — usage < 50%
      yellow — usage 50–80%
      red    — usage > 80%
    """
    if mode == "web":
        import uvicorn
        from hero.web.server import app
        uvicorn.run(app, host="127.0.0.1", port=8765)
    elif mode == "tree":
        run_tree(once=once, sandbox=sandbox)
    else:
        run(once=once, sandbox=sandbox)


if __name__ == "__main__":
    viewport()
