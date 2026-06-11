"""Dependency graph — parse package files across sandboxes to show cross-project dependencies."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

import yaml


SANDBOXES_DIR = Path.home() / ".hero" / "sandboxes"
DEV_DIR = Path.home() / "Development"
TAURUS_DIR = DEV_DIR / "Taurus"


@dataclass
class Dependency:
    source: str    # sandbox name
    target: str    # package name
    type: str      # "flutter" | "node" | "python" | "rust"
    version: str   # version constraint from package file


@dataclass
class ScanResult:
    sandbox: str
    path: str
    deps: list[Dependency] = field(default_factory=list)


def scan_all_sandboxes() -> list[dict[str, Any]]:
    """Scan all registered sandboxes and extract their dependencies.

    Walks the sandboxes directory to find registered sandboxes, resolves
    their project paths, and extracts dependencies from pubspec.yaml,
    package.json, pyproject.toml, and Cargo.toml files.

    Returns:
        List of dependency dicts with source, target, type, version keys.
    """
    deps: list[dict[str, Any]] = []
    if not SANDBOXES_DIR.exists():
        return deps

    # Load the index file for real sandbox-to-path mapping
    from hero.state.index import IndexState
    index = IndexState()
    sandboxes = index.list_sandboxes()

    for entry in sandboxes:
        sandbox_name = entry.get("name", "")
        sandbox_path_str = entry.get("path", "")
        if not sandbox_name or not sandbox_path_str:
            continue
        sandbox_path = Path(sandbox_path_str)
        if sandbox_path.exists():
            deps.extend(_extract_deps(sandbox_name, sandbox_path))

    # Also check any sandbox dirs that aren't in the index yet
    for item in sorted(SANDBOXES_DIR.iterdir()):
        if not item.is_dir() or item.name.endswith(".toon"):
            continue
        sandbox_name = item.name
        # Skip if already handled via index
        if any(d.get("source") == sandbox_name for d in deps):
            continue
        sandbox_path = _resolve_sandbox_path(sandbox_name)
        if sandbox_path:
            deps.extend(_extract_deps(sandbox_name, sandbox_path))

    return deps


def scan_sandbox(sandbox_name: str) -> list[dict[str, Any]]:
    """Scan a single sandbox by name.

    Args:
        sandbox_name: Name of the sandbox to scan.

    Returns:
        List of dependency dicts for that sandbox.
    """
    sandbox_path = _resolve_sandbox_path(sandbox_name)
    if not sandbox_path:
        return []
    return _extract_deps(sandbox_name, sandbox_path)


def _resolve_sandbox_path(name: str) -> Optional[Path]:
    """Find the project directory for a sandbox name.

    Checks the Taurus directory first, then Development, then the index.

    Args:
        name: Sandbox/project name.

    Returns:
        Path to the project directory, or None if not found.
    """
    # Check index first
    from hero.state.index import IndexState
    index = IndexState()
    entry = index.get_sandbox(name)
    if entry and entry.get("path"):
        candidate = Path(entry["path"])
        if candidate.exists():
            return candidate

    # Fall back to directory-based lookup
    for base in [TAURUS_DIR, DEV_DIR]:
        candidate = base / name
        if candidate.exists():
            return candidate
    return None


def _extract_deps(name: str, path: Path) -> list[dict[str, Any]]:
    """Extract dependencies from a project directory.

    Supports Flutter (pubspec.yaml), Node (package.json),
    Python (pyproject.toml), and Rust (Cargo.toml).

    Args:
        name: The sandbox/project name.
        path: Path to the project directory.

    Returns:
        List of dependency dicts with source, target, type, version keys.
    """
    deps: list[dict[str, Any]] = []

    # Flutter
    pubspec = path / "pubspec.yaml"
    if pubspec.exists():
        try:
            data = yaml.safe_load(pubspec.read_text())
            if data:
                for section in ["dependencies", "dev_dependencies"]:
                    section_data = data.get(section) or {}
                    for dep, ver in section_data.items():
                        if dep == name:
                            continue
                        if isinstance(ver, str):
                            deps.append({
                                "source": name,
                                "target": dep,
                                "type": "flutter",
                                "version": ver,
                            })
                        elif isinstance(ver, dict):
                            # Handle sdk-constrained deps like flutter: {sdk: flutter}
                            if "sdk" not in ver:
                                deps.append({
                                    "source": name,
                                    "target": dep,
                                    "type": "flutter",
                                    "version": str(ver),
                                })
        except Exception:
            pass

    # Node
    package_json = path / "package.json"
    if package_json.exists():
        try:
            with open(package_json) as f:
                data = json.load(f)
            for section in ["dependencies", "devDependencies"]:
                for dep, ver in (data.get(section) or {}).items():
                    deps.append({
                        "source": name,
                        "target": dep,
                        "type": "node",
                        "version": str(ver),
                    })
        except Exception:
            pass

    # Python
    pyproject = path / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text()
            in_project_deps = False
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("["):
                    in_project_deps = "project.dependencies" in stripped or stripped == "[project]"
                    continue
                if in_project_deps and "=" in stripped and not stripped.startswith("#"):
                    parts = stripped.split("=", 1)
                    dep_name = parts[0].strip().strip('"').strip("'")
                    dep_version = parts[1].strip().strip('"').strip("'").strip(",")
                    if dep_name and dep_version:
                        deps.append({
                            "source": name,
                            "target": dep_name,
                            "type": "python",
                            "version": dep_version,
                        })
        except Exception:
            pass

    # Rust
    cargo = path / "Cargo.toml"
    if cargo.exists():
        try:
            data = yaml.safe_load(cargo.read_text())
            if data:
                for section in ["dependencies", "dev-dependencies"]:
                    section_data = data.get(section) or {}
                    for dep, ver in section_data.items():
                        if isinstance(ver, str):
                            deps.append({
                                "source": name,
                                "target": dep,
                                "type": "rust",
                                "version": ver,
                            })
                        elif isinstance(ver, dict):
                            dep_version = ver.get("version", "")
                            deps.append({
                                "source": name,
                                "target": dep,
                                "type": "rust",
                                "version": dep_version,
                            })
        except Exception:
            pass

    return deps
