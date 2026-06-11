"""HERO pipeline stage modules.

CLI-agnostic pipeline stage functions. Each stage accepts a sandbox Path
and returns a consistent dict result. They can be invoked from Click
commands or from ``hero go`` pipeline execution.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

STAGES: list[str] = [
    "navigate",
    "pre_commit",
    "build",
    "harden",
    "legal",
    "cipr",
    "verify",
    "archive",
]

# Lazy imports to avoid heavy startup
_STAGE_MODULES: dict[str, Any] = {}


def _load_stage(name: str) -> Any:
    """Lazy-load a stage module by name."""
    if name in _STAGE_MODULES:
        return _STAGE_MODULES[name]

    if name == "navigate":
        from hero.stages import navigate as mod
    elif name == "pre_commit":
        from hero.stages import pre_commit as mod
    elif name == "build":
        from hero.stages import build as mod
    elif name == "harden":
        from hero.stages import harden as mod
    elif name == "legal":
        from hero.stages import legal as mod
    elif name == "cipr":
        from hero.stages import cipr as mod
    elif name == "verify":
        from hero.stages import verify as mod
    elif name == "archive":
        from hero.stages import archive as mod
    else:
        raise ValueError(f"Unknown stage: {name}")

    _STAGE_MODULES[name] = mod
    return mod


def run_stage(name: str, sandbox_path: Path, verbose: bool = False, **kwargs: Any) -> dict[str, Any]:
    """Dispatch a pipeline stage by name.

    Parameters
    ----------
    name : str
        Stage name — must be one of :data:`STAGES`.
    sandbox_path : Path
        Path to the sandbox / project directory.
    verbose : bool, default=False
        Include detailed output in each check result.
    **kwargs
        Extra arguments forwarded to the stage function.

    Returns
    -------
    dict
        Standardised result dict with ``passed``, ``score``, ``status``,
        ``checks``, and ``findings``.
    """
    mod = _load_stage(name)
    runner = getattr(mod, f"run_{name}")
    return runner(sandbox_path, verbose=verbose, **kwargs)


def resolve_mode(mode: str) -> list[str]:
    """Return the ordered stage list for a given pipeline mode.

    Parameters
    ----------
    mode : str
        One of ``quick``, ``full``, ``smart``, ``ci``, ``audit``.

    Returns
    -------
    list[str]
        Ordered list of stage names to execute.
    """
    mode = mode.lower().strip()

    if mode == "quick":
        return ["navigate", "pre_commit", "build", "verify"]

    if mode == "full":
        return list(STAGES)

    if mode == "ci":
        return ["pre_commit", "build", "cipr", "verify"]

    if mode == "audit":
        return ["harden", "legal"]

    if mode == "smart":
        return _resolve_smart_mode()

    raise ValueError(f"Unknown mode: {mode!r}. Choose from: quick, full, smart, ci, audit")


def _resolve_smart_mode() -> list[str]:
    """Auto-detect which stages to run based on git changes.

    Looks at files changed since the last commit (or since HEAD~1 if
    nothing is staged) and maps them to relevant stages.
    """
    try:
        changed = _get_changed_files()
    except Exception:
        # If git fails, fall back to full pipeline
        return list(STAGES)

    if not changed:
        # Nothing changed — minimal run
        return ["navigate", "verify"]

    # Pattern → stage mapping
    patterns = {
        "navigate": ["*.md", "*.rst", "*.txt", "docs/**"],
        "pre_commit": ["*.py", "*.js", "*.ts", "*.java", "*.go", "*.rs", "*.c", "*.cpp", "*.h"],
        "build": ["Dockerfile", "Makefile", "*.gradle", "pom.xml", "package.json", "Cargo.toml", "pyproject.toml", "setup.py"],
        "harden": ["*.tf", "*.yaml", "*.yml", "*.json"],
        "legal": ["LICENSE*", "LEGAL*", "NOTICE*", "COPYING*", "legal-config.json"],
        "cipr": [".github/**", ".gitlab-ci.yml", "Jenkinsfile", "*.test.*", "tests/**"],
        "verify": [],  # always included
        "archive": [],  # always included if we got this far
    }

    selected: set[str] = {"navigate", "verify"}

    for stage, globs in patterns.items():
        for f in changed:
            fpath = Path(f)
            for g in globs:
                if _match_glob(fpath, g):
                    selected.add(stage)
                    break

    # Archive is always last if anything meaningful ran
    if len(selected) > 2:
        selected.add("archive")

    return [s for s in STAGES if s in selected]


def _get_changed_files() -> list[str]:
    """Return list of files changed since last commit or in working tree."""
    # Try staged + unstaged changes first
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    files = [f.strip() for f in result.stdout.splitlines() if f.strip()]

    if not files:
        # Fall back to changes in the last commit
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        files = [f.strip() for f in result.stdout.splitlines() if f.strip()]

    return files


def _match_glob(path: Path, pattern: str) -> bool:
    """Simple glob matching supporting ``*`` and ``**``."""
    import fnmatch

    parts = path.parts
    pat_parts = pattern.replace("**", "\0").split("/")

    # Direct name match
    if len(pat_parts) == 1 and pat_parts[0].replace("\0", "**") == pattern:
        return fnmatch.fnmatch(path.name, pattern)

    # Full path match
    str_path = str(path).replace("\\", "/")
    return fnmatch.fnmatch(str_path, pattern) or fnmatch.fnmatch(path.name, pattern)
