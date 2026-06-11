"""SandboxState — per-sandbox state file management.

Integrates StateCache for lazy loading and TTL-based caching.
Katana (MEMORY.toon) data is only read when explicitly requested,
avoiding unnecessary disk I/O on every status call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hero.state.toon import toon_read, toon_write
from hero.state.cache import StateCache, default_cache


HOME = Path.home()
SANDBOX_DIR = HOME / ".hero" / "sandboxes"

# Shared cache — same instance as MetricsCollector so invalidations propagate
_cache = default_cache


def invalidate_cache(sandbox_name: str | None = None) -> None:
    """Invalidate the module-level StateCache.

    Call this after any mutation (spawn, complete, budget change) so
    subsequent reads get fresh data from disk.

    Args:
        sandbox_name: Specific sandbox to invalidate. If None, clears
                      the entire cache.
    """
    _cache.invalidate(sandbox_name)


def get_cache() -> StateCache:
    """Return the shared StateCache instance for external use."""
    return _cache


@dataclass
class BudgetData:
    """Budget state for a sandbox."""
    bootstrap_max: int = 5000
    compactions_used: int = 0
    tokens_remaining: int = 5000


@dataclass
class KatanaData:
    """Katana (pending tasks, known issues) data."""
    pending: list[str] = field(default_factory=list)
    known_issues: list[str] = field(default_factory=list)


@dataclass
class SandboxData:
    """Complete sandbox state data."""
    name: str
    path: str
    budget: BudgetData = field(default_factory=BudgetData)
    skills: list[str] = field(default_factory=list)
    katana: KatanaData = field(default_factory=KatanaData)
    status: str = "idle"


class SandboxState:
    """Manages per-sandbox state files (BUDGET.toon, SKILLS.toon, MEMORY.toon, HEARTBEAT.toon).

    Integrates with BudgetState to provide the full Katana cycle:
    - spawn_task(): adds pending task and decrements budget tokens
    - complete_task(): removes from pending and increments budget tokens
    - compact_budget(): resets compactions_used counter

    Uses StateCache for TTL-based caching of reads to avoid redundant
    disk I/O on repeated status calls.
    """

    def __init__(self, sandbox_name: str, base_path: Path | None = None) -> None:
        self.sandbox_name = sandbox_name
        if base_path:
            self.base_path = base_path / sandbox_name
        else:
            self.base_path = SANDBOX_DIR / sandbox_name
        self._budget_state: "BudgetState | None" = None

    @property
    def budget_state(self) -> "BudgetState":
        """Get or create BudgetState for this sandbox."""
        if self._budget_state is None:
            from hero.state.budget import BudgetState
            self._budget_state = BudgetState(self.sandbox_name, base_path=self.base_path)
        return self._budget_state

    @property
    def budget_file(self) -> Path:
        return self.base_path / "BUDGET.toon"

    @property
    def skills_file(self) -> Path:
        return self.base_path / "SKILLS.toon"

    @property
    def memory_file(self) -> Path:
        return self.base_path / "MEMORY.toon"

    @property
    def heartbeat_file(self) -> Path:
        return self.base_path / "HEARTBEAT.toon"

    def load(self, sandbox_name: str | None = None, use_cache: bool = True,
             include_katana: bool = True) -> dict[str, Any]:
        """Load all sandbox state files and return as a combined dict.

        Uses StateCache when *use_cache* is True (default). Katana data
        (MEMORY.toon) is read only when *include_katana* is True.

        Args:
            sandbox_name: Sandbox to load (defaults to self.sandbox_name).
            use_cache:     Use StateCache for reads when True.
            include_katana: Read MEMORY.toon for katana data. Pass False
                            to skip katana entirely (saves one disk read).
        """
        name = sandbox_name or self.sandbox_name

        # Only use cache when we want the full state (with katana)
        if use_cache and include_katana:
            cached = _cache.get(name)
            if cached is not None:
                return cached

        if not self.base_path.exists():
            self.base_path.mkdir(parents=True, exist_ok=True)
            state = self._empty_state(name)
            if use_cache and include_katana:
                _cache.set(name, state)
            return state

        # Load BUDGET.toon
        budget_data = toon_read(self.budget_file)
        budget = BudgetData(
            bootstrap_max=budget_data.get("bootstrap_max", 5000),
            compactions_used=budget_data.get("compactions_used", 0),
            tokens_remaining=budget_data.get("tokens_remaining", 5000),
        )

        # Load SKILLS.toon
        skills_data = toon_read(self.skills_file)
        skills = skills_data.get("skills", [])

        # Katana is lazy — only read MEMORY.toon when requested
        if include_katana:
            memory_data = toon_read(self.memory_file)
            katana_pending = memory_data.get("pending", [])
            katana_issues = memory_data.get("known_issues", [])
        else:
            katana_pending = []
            katana_issues = []

        # Load HEARTBEAT.toon
        heartbeat_data = toon_read(self.heartbeat_file)

        state = {
            "name": name,
            "path": heartbeat_data.get("path", str(self.base_path)),
            "budget": {
                "bootstrap_max": budget.bootstrap_max,
                "compactions_used": budget.compactions_used,
                "tokens_remaining": budget.tokens_remaining,
            },
            "skills": skills,
            "katana": {
                "pending": katana_pending,
                "known_issues": katana_issues,
            },
            "status": heartbeat_data.get("status", "idle"),
        }

        if use_cache and include_katana:
            _cache.set(name, state)

        return state

    def save(self, sandbox_name: str | None = None, data: dict[str, Any] | None = None) -> None:
        """Save sandbox state data to individual TOON files.

        Also invalidates the StateCache for this sandbox so the next
        read picks up the fresh data.
        """
        name = sandbox_name or self.sandbox_name

        if data is None:
            data = self._empty_state(name)

        self.base_path.mkdir(parents=True, exist_ok=True)

        budget = data.get("budget", {})
        toon_write(self.budget_file, {
            "bootstrap_max": budget.get("bootstrap_max", 5000),
            "compactions_used": budget.get("compactions_used", 0),
            "tokens_remaining": budget.get("tokens_remaining", 5000),
        })

        skills = data.get("skills", [])
        toon_write(self.skills_file, {"skills": skills})

        katana = data.get("katana", {})
        toon_write(self.memory_file, {
            "pending": katana.get("pending", []),
            "known_issues": katana.get("known_issues", []),
        })

        toon_write(self.heartbeat_file, {
            "name": name,
            "path": data.get("path", str(self.base_path)),
            "status": data.get("status", "idle"),
        })

        # Invalidate cache so next read hits disk
        _cache.invalidate(name)

    def _empty_state(self, name: str) -> dict[str, Any]:
        """Return an empty state dict for a new sandbox."""
        return {
            "name": name,
            "path": str(self.base_path),
            "budget": {
                "bootstrap_max": 5000,
                "compactions_used": 0,
                "tokens_remaining": 5000,
            },
            "skills": [],
            "katana": {
                "pending": [],
                "known_issues": [],
            },
            "status": "idle",
        }

    def update_status(self, status: str) -> None:
        """Update only the status field."""
        heartbeat_data = toon_read(self.heartbeat_file) if self.heartbeat_file.exists() else {}
        heartbeat_data["status"] = status
        heartbeat_data["name"] = self.sandbox_name
        heartbeat_data["path"] = str(self.base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        toon_write(self.heartbeat_file, heartbeat_data)
        _cache.invalidate(self.sandbox_name)

    def add_pending_task(self, task: str) -> None:
        """Add a task to the pending list and decrement budget (spawn)."""
        memory_data = toon_read(self.memory_file) if self.memory_file.exists() else {}
        pending = memory_data.get("pending", [])
        pending.append(task)
        memory_data["pending"] = pending
        self.base_path.mkdir(parents=True, exist_ok=True)
        toon_write(self.memory_file, memory_data)
        self.budget_state.spawn_decrement()
        _cache.invalidate(self.sandbox_name)

    def add_known_issue(self, issue: str) -> None:
        """Add an issue to the known issues list."""
        memory_data = toon_read(self.memory_file) if self.memory_file.exists() else {}
        known_issues = memory_data.get("known_issues", [])
        known_issues.append(issue)
        memory_data["known_issues"] = known_issues
        self.base_path.mkdir(parents=True, exist_ok=True)
        toon_write(self.memory_file, memory_data)
        _cache.invalidate(self.sandbox_name)

    def complete_task(self, task: str) -> bool:
        """Remove a task from pending list and increment budget (complete).

        Returns True if task was found and removed, False if not found.
        """
        memory_data = toon_read(self.memory_file) if self.memory_file.exists() else {}
        pending = memory_data.get("pending", [])

        if task not in pending:
            return False

        pending.remove(task)
        memory_data["pending"] = pending
        self.base_path.mkdir(parents=True, exist_ok=True)
        toon_write(self.memory_file, memory_data)
        self.budget_state.complete_increment()
        _cache.invalidate(self.sandbox_name)
        return True

    def spawn_task(self, task: str) -> None:
        """Add a task to pending and spawn a soldier."""
        self.add_pending_task(task)

    def compact_budget(self) -> None:
        """Reset compactions_used counter in budget."""
        self.budget_state.compact_reset()

    def get_katana_status(self) -> dict[str, Any]:
        """Get Katana status: pending tasks, known issues, and budget state.

        Forces a cache-bypassing load so katana data is always fresh.
        """
        state_data = self.load(use_cache=False, include_katana=True)
        return {
            "pending": state_data["katana"]["pending"],
            "known_issues": state_data["katana"]["known_issues"],
            "budget": state_data["budget"],
        }
