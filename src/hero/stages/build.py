"""BUILD pipeline stage.

Thin wrapper around :func:`hero.commands.build.run_build`.
Will be replaced with a native implementation in a future refactor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hero.commands.build import run_build as _run_build


def run_build(sandbox_path: Path, verbose: bool = False, **kwargs: Any) -> dict[str, Any]:
    """Run BUILD checks and return structured results.

    Parameters
    ----------
    sandbox_path : Path
        Path to the sandbox / project directory.
    verbose : bool, default=False
        Include detailed output in each check result.
    **kwargs
        Extra arguments forwarded to the underlying command function.

    Returns
    -------
    dict
        Standardised result dict with ``passed``, ``score``, ``status``,
        ``checks``, and ``findings``.
    """
    return _run_build(sandbox_path, verbose=verbose, **kwargs)
