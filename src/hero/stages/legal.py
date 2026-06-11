"""LEGAL pipeline stage.

Thin wrapper around :func:`hero.commands.legal.run_legal`.
Will be replaced with a native implementation in a future refactor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hero.commands.legal import run_legal as _run_legal


def run_legal(sandbox_path: Path, verbose: bool = False, **kwargs: Any) -> dict[str, Any]:
    """Run LEGAL checks and return structured results.

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
    return _run_legal(sandbox_path, verbose=verbose, **kwargs)
