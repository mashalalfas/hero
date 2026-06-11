"""
Project detection and sandbox resolution utilities.

These are the single-copy-of-truth functions.  Every HERO command that
needs to figure out *what* a sandbox contains or *where* it lives should
route through this module.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# ── Constants ────────────────────────────────────────────────────────────

SANDBOX_DIR = Path.home() / ".hero" / "sandboxes"
INDEX_PATH = SANDBOX_DIR / "INDEX.toon"
DEVELOPMENT_DIR = Path.home() / "Development"

# Regex to extract a single sandbox entry block from INDEX.toon.
# The format is: {name: "...", path: "...", budget_max: N, skills_count: N, status: "...", last_seen: "..."}
_INDEX_ENTRY_RE = re.compile(
    r'\{\s*name:\s*"(?P<name>[^"]+)"\s*,\s*'
    r'path:\s*"(?P<path>[^"]+)"\s*,\s*'
    r'budget_max:\s*(?P<budget>\d+)\s*,\s*'
    r'skills_count:\s*(?P<skills>\d+)\s*,\s*'
    r'status:\s*"(?P<status>[^"]+)"\s*,\s*'
    r'last_seen:\s*"(?P<last_seen>[^"]+)"\s*\}'
)


# ── Sandbox resolution ───────────────────────────────────────────────────

def _parse_index_toon() -> dict[str, str]:
    """Parse INDEX.toon and return a ``{name: path}`` mapping.

    Returns an empty dict if the file doesn't exist or can't be parsed.
    """
    if not INDEX_PATH.exists():
        return {}
    text = INDEX_PATH.read_text()
    return {m.group("name"): m.group("path") for m in _INDEX_ENTRY_RE.finditer(text)}


def resolve_sandbox(sandbox_name_or_path: str) -> Path:
    """Resolve a sandbox identifier to an absolute filesystem path.

    Resolution order (first match wins):

    1. Look up ``sandbox_name_or_path`` as a *name* in ``INDEX.toon``.
       If found, return the path recorded there.
    2. Treat it as a literal filesystem path.
    3. Look in ``~/Development/<sandbox_name_or_path>``.

    Raises :class:`FileNotFoundError` if nothing matches.
    """
    # 1. INDEX.toon lookup
    index = _parse_index_toon()
    if sandbox_name_or_path in index:
        return Path(index[sandbox_name_or_path]).resolve()

    # 2. Literal path
    candidate = Path(sandbox_name_or_path)
    if candidate.exists():
        return candidate.resolve()

    # 3. ~/Development/<name>
    dev = DEVELOPMENT_DIR / sandbox_name_or_path
    if dev.exists():
        return dev.resolve()

    raise FileNotFoundError(
        f"Sandbox '{sandbox_name_or_path}' not found in "
        f"{INDEX_PATH}, as a literal path, or in "
        f"{DEVELOPMENT_DIR}/."
    )


# ── Project type detection ───────────────────────────────────────────────

def detect_project_type(path: Path) -> dict[str, Any]:
    """Detect the project type from marker files inside *path*.

    Returns a dictionary with the canonical shape:

    .. code-block:: python

        {
            "type": "flutter" | "node" | "electron" | "python" | "rust"
                    | "godot" | "unknown",
            "analyze_cmd": ["cmd", ...] | None,
            "build_cmd":   ["cmd", ...] | None,
            "analyzer":    "flutter" | "tsc" | "npm" | "ruff" | "cargo" | None,
            "source_globs": ["**/*.ext", ...] | None,
        }

    Detection logic (ordered by specificity):

    * **godot** — ``project.godot`` or ``engine.cfg``
    * **flutter** — ``pubspec.yaml``
    * **electron / node** — ``package.json``
      (electron when ``"electron"`` appears in ``dependencies`` or
      ``devDependencies``; otherwise plain node)
    * **python** — ``pyproject.toml``
    * **rust** — ``Cargo.toml``
    """
    result: dict[str, Any] = {
        "type": "unknown",
        "analyze_cmd": None,
        "build_cmd": None,
        "analyzer": None,
        "source_globs": None,
    }

    # ── Godot ──────────────────────────────────────────────────────────
    if (path / "project.godot").exists() or (path / "engine.cfg").exists():
        result.update(
            type="godot",
            source_globs=["**/*.gd", "**/*.tscn", "**/*.tres", "**/*.json"],
        )
        return result

    # ── Flutter ────────────────────────────────────────────────────────
    if (path / "pubspec.yaml").exists():
        result.update(
            type="flutter",
            analyze_cmd=["flutter", "analyze"],
            build_cmd=["flutter", "build", "apk", "--debug"],
            analyzer="flutter",
            source_globs=["lib/**/*.dart"],
        )
        return result

    # ── Node / Electron ────────────────────────────────────────────────
    if (path / "package.json").exists():
        pkg = path / "package.json"
        try:
            pkg_data = json.loads(pkg.read_text())
        except (json.JSONDecodeError, OSError):
            pkg_data = {}

        deps = {
            **(pkg_data.get("dependencies") or {}),
            **(pkg_data.get("devDependencies") or {}),
        }
        scripts = pkg_data.get("scripts") or {}

        if "electron" in deps:
            result.update(
                type="electron",
                analyze_cmd=["npx", "tsc", "--noEmit"],
                build_cmd=["npx", "vite", "build"],
                analyzer="tsc",
                source_globs=[
                    "src/**/*.ts", "src/**/*.tsx",
                    "**/*.ts", "**/*.tsx",
                ],
            )
        else:
            result.update(
                type="node",
                analyze_cmd=(
                    ["npm", "run", "lint"] if "lint" in scripts else None
                ),
                build_cmd=["npm", "run", "build"],
                analyzer="npm",
                source_globs=[
                    "src/**/*.js", "src/**/*.jsx",
                    "**/*.js", "**/*.jsx",
                    "**/*.ts", "**/*.tsx",
                ],
            )
        return result

    # ── Python ─────────────────────────────────────────────────────────
    if (path / "pyproject.toml").exists():
        result.update(
            type="python",
            analyze_cmd=["ruff", "check", "."],
            build_cmd=["python", "-m", "compileall", "."],
            source_globs=["src/**/*.py", "**/*.py"],
        )
        return result

    # ── Rust ───────────────────────────────────────────────────────────
    if (path / "Cargo.toml").exists():
        result.update(
            type="rust",
            analyze_cmd=["cargo", "check"],
            build_cmd=["cargo", "build", "--release"],
            analyzer="cargo",
            source_globs=["src/**/*.rs", "**/*.rs"],
        )
        return result

    return result
