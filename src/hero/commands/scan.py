"""hero scan — Discover projects and create INDEX.toon."""

from __future__ import annotations

from pathlib import Path

import click

from hero.state.index import IndexState


# Project markers — any one means it's a project root
PROJECT_MARKERS = [
    "SPEC.md",
    "pyproject.toml",
    "package.json",
    "go.mod",
    "Cargo.toml",
    "pubspec.yaml",
    "build.gradle",
    "build.gradle.kts",
    "CMakeLists.txt",
    "CLAUDE.md",
]

# Skip these directory names entirely (never descend into them)
SKIP_DIRS = {
    "__pycache__", "node_modules", ".venv", "venv", ".git",
    "android", "ios", "linux", "macos", "windows", "build",
    "test", "assets", "lib", "NB", "Logos",
    ".opencode", ".next", ".nuxt", "dist", "target",
    "ephemeral", ".plugin_symlinks",
}

# Skip these top-level ~/Development entries entirely
SKIP_TOP_LEVEL = {
    "AGENTS.md", "ASSETS", "BOOTSTRAP.md", "HEARTBEAT.md", "IDENTITY.md",
    "SOUL.md", "TOOLS.md", "USER.md",
    "Images", "memory", "sandboxes", "state",
    "Anti-Ai-Design", "Tencent",
    # Flutter/cross-platform subdirs — never top-level projects
    "android", "ios", "linux", "macos", "windows",
}

# Skip these project dirs even if they have marker files (meta-dirs, not real projects)
SKIP_PROJECTS = {
    "Taurus",       # Meta/monorepo root — scan subdirs instead
    "Toffee",      # Parent of mobile/ — mobile/ is the real project
}


def _is_project_root(path: Path) -> bool:
    """Return True if path has any project marker file."""
    return any((path / marker).exists() for marker in PROJECT_MARKERS)


def discover_projects(base_dir: Path) -> list[dict[str, str]]:
    """Discover project directories.

    Strategy: Scan top-level and Taurus/ specially to avoid node_modules noise.
    Projects must be real application roots, not library subdirs.

    Rules:
    - Top-level ~/Development/ entries: scan each for markers
    - Taurus/: scan subdirs for markers (don't descend into node_modules/build)
    - Skip anything in SKIP_TOP_LEVEL / SKIP_DIRS
    """
    projects = []
    seen: dict[str, bool] = {}

    def add_project(path: Path) -> None:
        """Add project if not already seen (by resolved path)."""
        resolved = str(path.resolve())
        if resolved in seen:
            return
        seen[resolved] = True
        projects.append({
            "name": path.name,
            "path": str(path),
        })

    if not base_dir.exists():
        return projects

    # ----------------------------------------------------------------
    # 1. Top-level ~/Development/ scan
    # ----------------------------------------------------------------
    for entry in sorted(base_dir.iterdir()):
        if not entry.is_dir():
            continue
        name = entry.name
        if name in SKIP_TOP_LEVEL or name.startswith("."):
            continue

        if _is_project_root(entry):
            if name in SKIP_PROJECTS:
                # Skip the meta-dir itself but scan its direct subdirs
                for sub in sorted(entry.iterdir()):
                    if not sub.is_dir():
                        continue
                    sub_name = sub.name
                    if sub_name.startswith(".") or sub_name in SKIP_DIRS:
                        continue
                    if _is_project_root(sub):
                        add_project(sub)
            else:
                add_project(entry)



    return sorted(projects, key=lambda p: p["name"])


@click.command()
@click.option(
    "--path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=str(Path.home() / "Development"),
    help="Base directory to scan for projects.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be indexed without writing INDEX.toon.",
)
def scan(path: Path, dry_run: bool) -> None:
    """Scan ~/Development/ for project directories and create INDEX.toon.

    Discovers projects by looking for SPEC.md, pyproject.toml, package.json,
    go.mod, pubspec.yaml, build.gradle, or CLAUDE.md marker files.
    Creates ~/.hero/sandboxes/INDEX.toon with the discovered sandboxes.
    """
    click.echo(f"Scanning {path} for projects...")

    discovered = discover_projects(path)

    if not discovered:
        click.echo("No projects found.")
        return

    click.echo(f"Found {len(discovered)} project(s):")
    for proj in discovered:
        click.echo(f"  - {proj['name']} ({proj['path']})")

    if dry_run:
        click.echo("\n(Dry run — not writing INDEX.toon)")
        return

    index = IndexState()
    for proj in discovered:
        index.add_sandbox(
            name=proj["name"],
            path=proj["path"],
            budget_max=5000,
        )

    click.echo(f"\nINDEX.toon updated at {index.index_file}")


if __name__ == "__main__":
    scan()