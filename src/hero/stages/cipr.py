"""CI/PR pipeline stage.

Thin wrapper around :func:`hero.commands.cipr.run_cipr`.
Will be replaced with a native implementation in a future refactor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hero.commands.cipr import run_cipr as _run_cipr


def run_cipr(sandbox_path: Path, verbose: bool = False, **kwargs: Any) -> dict[str, Any]:
    """Run CI/PR checks and return structured results.

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
    return _run_cipr(sandbox_path, verbose=verbose, **kwargs)
