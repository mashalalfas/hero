"""
Subprocess helpers for HERO CLI commands.

Every command that shells out to an external tool (linter, compiler,
analyser, test runner) should use :func:`safe_run` — the single
implementation that consistently handles timeouts, missing binaries, and
unexpected errors.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def safe_run(
    cmd: list[str],
    cwd: Path,
    timeout: int = 60,
) -> tuple[subprocess.CompletedProcess[str] | None, str | None]:
    """Run an external command safely.

    Parameters
    ----------
    cmd:
        Command and arguments as a list of strings (e.g.
        ``["flutter", "analyze"]``).
    cwd:
        Working directory for the subprocess.
    timeout:
        Maximum wall-clock time in seconds before the process is killed.

    Returns
    -------
    (result, error_reason)
        *result* is the completed process on success, ``None`` on failure.
        *error_reason* is ``None`` on success, or a human-readable string
        describing what went wrong.
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result, None
    except FileNotFoundError:
        return None, f"{cmd[0]} not found"
    except subprocess.TimeoutExpired:
        return None, f"{cmd[0]} timed out after {timeout}s"
    except Exception as exc:
        return None, str(exc)
