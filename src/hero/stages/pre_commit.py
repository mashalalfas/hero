"""PRE-COMMIT pipeline stage.

Thin wrapper around :func:`hero.commands.pre_commit.run_pre_commit`.
Will be replaced with a native implementation in a future refactor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hero.commands.pre_commit import run_pre_commit as _run_pre_commit


def run_pre_commit(
    sandbox_path: Path,
    verbose: bool = False,
    target: dict | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run PRE-COMMIT checks and return structured results.

    Parameters
    ----------
    sandbox_path : Path
        Path to the sandbox / project directory.
    verbose : bool, default=False
        Include detailed output in each check result.
    target : dict | None, default=None
        Target specification when building for a different platform.
        When provided and the platform differs from source, source-based
        linters (e.g. dart analyze) may be skipped.
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
        if platform in ("static_website", "web_app", "node_package"):
            print(f"  \u2139\ufe0f [pre_commit] Target platform '{platform}' differs from source. Skipping source-based linters.")
    return _run_pre_commit(sandbox_path, verbose=verbose)
