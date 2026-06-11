"""Git branch management for HERO pipelines.

Provides functions to create feature branches, commit changes,
and rollback to the original branch after pipeline execution.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def create_pipeline_branch(sandbox_path: Path, pipeline_id: str) -> str:
    """Create a feature branch ``hero/<pipeline_id>`` from current HEAD.

    Args:
        sandbox_path: Path to the git repository (sandbox).
        pipeline_id: Unique pipeline identifier.

    Returns:
        The name of the created branch.

    Raises:
        RuntimeError: If the working tree is not clean.
        subprocess.CalledProcessError: If a git command fails.
    """
    # Check git status first — must be clean
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=str(sandbox_path),
    )
    if status.stdout.strip():
        raise RuntimeError(
            f"Working tree not clean at {sandbox_path}. "
            "Commit or stash changes first."
        )

    branch = f"hero/{pipeline_id}"
    subprocess.run(
        ["git", "checkout", "-b", branch],
        cwd=str(sandbox_path),
        check=True,
    )
    return branch


def commit_pipeline_changes(sandbox_path: Path, message: str) -> None:
    """Auto-commit all changes with a ``[hero]``-prefixed message.

    Args:
        sandbox_path: Path to the git repository (sandbox).
        message: Commit message body (prefixed with ``[hero]`` automatically).

    Raises:
        subprocess.CalledProcessError: If a git command fails.
    """
    subprocess.run(
        ["git", "add", "-A"],
        cwd=str(sandbox_path),
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", f"[hero] {message}"],
        cwd=str(sandbox_path),
        check=True,
    )


def rollback_pipeline(
    sandbox_path: Path,
    original_branch: str,
    pipeline_branch: str,
) -> None:
    """Rollback: switch back to the original branch and delete the pipeline branch.

    Args:
        sandbox_path: Path to the git repository (sandbox).
        original_branch: Name of the branch to return to.
        pipeline_branch: Name of the pipeline branch to delete.

    Raises:
        subprocess.CalledProcessError: If a git command fails.
    """
    subprocess.run(
        ["git", "checkout", original_branch],
        cwd=str(sandbox_path),
        check=True,
    )
    subprocess.run(
        ["git", "branch", "-D", pipeline_branch],
        cwd=str(sandbox_path),
        check=True,
    )


def get_current_branch(sandbox_path: Path) -> str:
    """Get the current git branch name.

    Args:
        sandbox_path: Path to the git repository (sandbox).

    Returns:
        The current branch name.

    Raises:
        subprocess.CalledProcessError: If a git command fails.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        cwd=str(sandbox_path),
        check=True,
    )
    return result.stdout.strip()
