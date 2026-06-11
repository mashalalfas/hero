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


def build_context(
    sandbox: SandboxData,
    task: str,
    cached_context: dict[str, str] | None = None,
) -> str:
    """Build TOON context block for agent injection.

    Args:
        sandbox: Sandbox data with name, budget, and katana state.
        task: Task description for the soldier.
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

    # Append shared cached context blocks (deduplicated project context)
    if cached_context:
        for key, value in cached_context.items():
            if value:
                lines.append(f"# Shared context: {key}\n{value}")

    return "\n".join(lines) + "\n"