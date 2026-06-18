"""BUILD pipeline stage.

Thin wrapper around :func:`hero.commands.build.run_build`.
Will be replaced with a native implementation in a future refactor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hero.commands.build import run_build as _run_build


def run_build(
    sandbox_path: Path,
    verbose: bool = False,
    target: dict | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run BUILD checks and return structured results.

    Parameters
    ----------
    sandbox_path : Path
        Path to the sandbox / project directory.
    verbose : bool, default=False
        Include detailed output in each check result.
    target : dict | None, default=None
        Target specification dict with at least ``platform`` and
        ``build_tool`` keys. When provided, the build context is
        logged for visibility.
    **kwargs
        Extra arguments forwarded to the underlying command function.

    Returns
    -------
    dict
        Standardised result dict with ``passed``, ``score``, ``status``,
        ``checks``, and ``findings``.
    """
    if target and target.get("platform", "") not in ("", None):
        platform = target["platform"]
        build_tool = target.get("build_tool", "unknown")
        print(f"  \u2139\ufe0f [build] Building for target '{platform}' with tool '{build_tool}'")
    return _run_build(sandbox_path, verbose=verbose, **kwargs)
