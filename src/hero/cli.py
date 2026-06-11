"""HERO CLI — Click-based command-line interface."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from hero import __version__
from hero.logging import get_logger


HERO_HOME = Path.home() / ".hero"
SANDBOX_DIR = HERO_HOME / "sandboxes"


def ensure_hero_home() -> None:
    """Ensure ~/.hero/ and ~/.hero/sandboxes/ exist."""
    HERO_HOME.mkdir(exist_ok=True)
    SANDBOX_DIR.mkdir(exist_ok=True)


# Initialize logging at module level for the CLI namespace
_cli_logger = get_logger("cli")


# Import commands at module level so they're registered before Click parses --help
from hero.commands.scan import scan  # noqa: E402
from hero.commands.spawn import spawn  # noqa: E402
from hero.commands.status import status  # noqa: E402
from hero.commands.deploy import deploy  # noqa: E402
from hero.commands.graph import graph  # noqa: E402
from hero.commands.katana import katana  # noqa: E402
from hero.commands.heartbeat import heartbeat  # noqa: E402
from hero.commands.budget import budget
from hero.commands.tell import tell
from hero.commands.eval import eval as eval_cmd
from hero.commands.dispatch import dispatch
from hero.commands.orchestrate import orchestrate
from hero.commands.assemble import assemble
from hero.commands.go import go
from hero.commands.pipeline import pipeline
from hero.commands.viewport import viewport
from hero.commands.dlq import dlq
from hero.commands.check import check
from hero.commands.kill import kill
from hero.commands.watch import watch
from hero.commands.clean import clean
from hero.commands.prune import prune
from hero.commands.score import score
from hero.commands.pre_commit import pre_commit
from hero.commands.legal import legal
from hero.commands.build import build
from hero.commands.harden import harden  # noqa: E402
from hero.commands.cipr import cipr  # noqa: E402
from hero.commands.verify import verify  # noqa: E402
from hero.commands.archive import archive  # noqa: E402
from hero.commands.ready import ready  # noqa: E402
from hero.commands.sweep import sweep  # noqa: E402
from hero.commands.map import map as map_cmd  # noqa: E402
from hero.commands.exchange import exchange  # noqa: E402


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """HERO — CLI multi-agent orchestration system.

    Manage AI soldier agents across project sandboxes using token-efficient
    TOON state format and Graphify code navigation.
    """
    ensure_hero_home()
    _cli_logger.info("hero start", version=__version__)


# Register commands at module load
main.add_command(scan)
main.add_command(spawn)
main.add_command(status)
main.add_command(deploy)
main.add_command(graph)
main.add_command(katana)
main.add_command(heartbeat)
main.add_command(budget)
main.add_command(tell)
main.add_command(eval_cmd)
main.add_command(dispatch)
main.add_command(orchestrate)
main.add_command(assemble)
main.add_command(go)
main.add_command(pipeline)
main.add_command(viewport)
main.add_command(dlq)
main.add_command(check)
main.add_command(kill)
main.add_command(watch)
main.add_command(clean)
main.add_command(prune)
main.add_command(score)
main.add_command(pre_commit)
main.add_command(legal)
main.add_command(build)
main.add_command(harden)
main.add_command(cipr)
main.add_command(verify)
main.add_command(archive)
main.add_command(ready)
main.add_command(sweep)
main.add_command(map_cmd)
main.add_command(exchange)


if __name__ == "__main__":
    main()
