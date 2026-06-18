"""TOON context builder for soldier agent injection.

Provides ContextCache for deduplicated project context loading
across multiple soldiers in the same pipeline.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class BudgetConfig:
    """Budget configuration for a soldier spawn."""
    bootstrap_max: int
    compactions_used: int = 0
    tokens_remaining: Optional[int] = None


@dataclass
class TargetProfile:
    """What the soldier should build, independent of what exists on disk.

    Separates the *target* (what to produce) from the *source* (what exists
    on disk). This prevents soldiers from conflating project files with
    build intent.

    Attributes:
        platform: Target platform name (e.g. "website", "flutter_app", "docs", "api").
        build_tool: Build tool to use (e.g. "npm", "flutter", "cargo", "mkdocs").
        output_dir: Directory where build artifacts land (e.g. "dist/", "build/web/").
        output_files: List of expected output files or glob patterns.
        validation: Validation strategy name (e.g. "html-validate", "dart analyze").
    """
    platform: str
    build_tool: str
    output_dir: str
    output_files: list[str]
    validation: str


@dataclass
class KatanaData:
    """Katana state (pending tasks and known issues)."""
    pending: list[str]
    known_issues: list[str]


@dataclass
class SandboxData:
    """Sandbox data for context building."""
    name: str
    budget: BudgetConfig
    katana: KatanaData


class ContextCache:
    """Caches repeated project context so soldiers in the same pipeline
    don't each re-read the same README, PLAN.md, or config files.

    Usage::

        cache = ContextCache()
        readme = cache.get_or_load("README", sandbox_path / "README.md")
        plan = cache.get_or_load("PLAN", sandbox_path / "PLAN.md")
    """

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}

    def get_or_load(self, key: str, path: Path, max_chars: int = 2000) -> str:
        """Return cached content for *key*, or load from *path* and cache it.

        Args:
            key: Cache key (e.g. "README", "PLAN", "package.json").
            path: Filesystem path to load if not cached.
            max_chars: Maximum characters to read (default 2000).

        Returns:
            Cached or freshly-loaded content. Empty string if path doesn't exist.
        """
        if key not in self._cache and path.exists():
            content = path.read_text()[:max_chars]
            self._cache[key] = content
        return self._cache.get(key, "")

    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()

    def load_skill_kit(self, role_name: str, kit_dir: Path) -> dict[str, str]:
        """Load skill cards for a given role from a skill kit directory.

        Looks for ``{kit_dir}/{role_name}/SKILL_CARDS.md`` and caches the
        content internally so that multiple soldiers in the same pipeline
        don't re-read the same file.  Returns an empty dict if the file
        doesn't exist — never raises ``FileNotFoundError``.

        The returned dict is suitable for passing as ``cached_context`` to
        :func:`build_context`, which renders each entry under a
        ``## Shared context: {key}`` heading.

        Args:
            role_name: Role name (e.g. ``"web-designer"``). This is used
                       as the subdirectory name under *kit_dir*.
            kit_dir: Path to the skill kit root directory containing
                     role-named subdirectories (e.g.
                     ``Path("/home/max/Development/HERO/skills")``).

        Returns:
            A dict ``{"skill_cards": content}`` if the file was found and
            loaded, or an empty dict ``{}`` if the file does not exist.
        """
        cache_key = f"skill_kit::{role_name}"
        if cache_key in self._cache:
            content = self._cache[cache_key]
            return {"skill_cards": content} if content else {}

        skill_cards_path = kit_dir / role_name / "SKILL_CARDS.md"
        if not skill_cards_path.exists():
            return {}

        content = skill_cards_path.read_text()
        self._cache[cache_key] = content
        return {"skill_cards": content}


def build_context(
    sandbox: SandboxData,
    task: str,
    target: TargetProfile | None = None,
    cached_context: dict[str, str] | None = None,
) -> str:
    """Build TOON context block for agent injection.

    Args:
        sandbox: Sandbox data with name, budget, and katana state.
        task: Task description for the soldier.
        target: Optional target profile describing WHAT to build
                (independent of what exists on disk). When provided,
                injects platform hints so soldiers don't conflate
                source project type with build target.
        cached_context: Optional shared context dict (keyed by label)
                        to append as ## Shared context blocks.

    Returns:
        TOON formatted context block for soldier agent.
    """
    tokens_str = (
        str(sandbox.budget.tokens_remaining)
        if sandbox.budget.tokens_remaining is not None
        else "unlimited"
    )

    pending_items = ", ".join(sandbox.katana.pending) if sandbox.katana.pending else "none"
    known_items = ", ".join(sandbox.katana.known_issues) if sandbox.katana.known_issues else "none"

    lines = [
        f"sandbox: {sandbox.name}",
        f"budget{{bootstrap_max,compactions_used,tokens_remaining}}: "
        f"{sandbox.budget.bootstrap_max},{sandbox.budget.compactions_used},{tokens_str}",
        f"task: {task}",
        "katana:",
        f"  pending[{len(sandbox.katana.pending)}]: {pending_items}",
        f"  known_issues[{len(sandbox.katana.known_issues)}]: {known_items}",
    ]

    # Inject target profile if provided — prevents soldiers from conflating
    # source project type (what's on disk) with build target (what to produce).
    if target is not None:
        lines += [
            f"target_platform: {target.platform}",
            f"target_build_tool: {target.build_tool}",
            f"target_output_dir: {target.output_dir}",
            f"target_must_produce: {', '.join(target.output_files)}",
            f"CRITICAL: You are building a {target.platform}. "
            f"Do NOT modify source files unless task explicitly requires it.",
        ]

    # Append shared cached context blocks (deduplicated project context)
    if cached_context:
        for key, value in cached_context.items():
            if value:
                lines.append(f"# Shared context: {key}\n{value}")

    return "\n".join(lines) + "\n"