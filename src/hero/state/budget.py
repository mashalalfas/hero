"""BudgetState - budget tracking for Katana cycle management."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hero.state.budget_history import record_event
from hero.state.toon import toon_write, toon_read


HOME = Path.home()
SANDBOX_DIR = HOME / ".hero" / "sandboxes"


@dataclass
class BudgetData:
    """Budget data structure."""
    bootstrap_max: int
    compactions_used: int
    tokens_remaining: int


class BudgetState:
    """Manages budget tracking per sandbox.

    Katana cycle behavior:
    - Spawn: decrements tokens_remaining
    - Complete: increments tokens_remaining
    - Compact: resets compactions_used
    """

    def __init__(self, sandbox_name: str, base_path: Path | None = None) -> None:
        self.sandbox_name = sandbox_name
        self.base_path = base_path or (SANDBOX_DIR / sandbox_name)
        self.budget_file = self.base_path / "BUDGET.toon"

    def load(self, sandbox_name: str | None = None) -> dict[str, Any]:
        """Load budget data for a sandbox."""
        name = sandbox_name or self.sandbox_name

        if not self.budget_file.exists():
            # Return default budget for new sandbox
            return {
                "bootstrap_max": 5000,
                "compactions_used": 0,
                "tokens_remaining": 5000,
            }

        data = toon_read(self.budget_file)

        return {
            "bootstrap_max": data.get("bootstrap_max", 5000),
            "compactions_used": data.get("compactions_used", 0),
            "tokens_remaining": data.get("tokens_remaining", 5000),
        }

    def save(self, sandbox_name: str | None = None, data: dict[str, Any] | None = None) -> None:
        """Save budget data for a sandbox."""
        name = sandbox_name or self.sandbox_name

        if data is None:
            data = self.load(name)

        self.base_path.mkdir(parents=True, exist_ok=True)
        toon_write(self.budget_file, data)

    def update(self, sandbox_name: str | None = None, field: str | None = None, value: int | None = None) -> None:
        """Update a specific budget field.

        Args:
            sandbox_name: Name of sandbox (uses default if None)
            field: Field to update ('bootstrap_max', 'compactions_used', 'tokens_remaining')
            value: New value for the field
        """
        name = sandbox_name or self.sandbox_name

        if field is None or value is None:
            return

        data = self.load(name)

        if field in ("bootstrap_max", "compactions_used", "tokens_remaining"):
            data[field] = value
            self.save(name, data)

        # Invalidate SandboxState cache so next load() sees fresh data
        try:
            from hero.state.sandbox import _cache
            _cache.invalidate(name)
        except ImportError:
            pass

    def spawn_decrement(self, amount: int = 100) -> int:
        """Decrement tokens_remaining on spawn. Returns new value."""
        data = self.load(self.sandbox_name)
        before = data["tokens_remaining"]
        new_value = max(0, before - amount)
        data["tokens_remaining"] = new_value
        self.save(self.sandbox_name, data)

        record_event(
            sandbox=self.sandbox_name,
            event="spawn",
            before=before,
            after=new_value,
        )

        # Invalidate SandboxState cache
        try:
            from hero.state.sandbox import _cache
            _cache.invalidate(self.sandbox_name)
        except ImportError:
            pass

        return new_value

    def complete_increment(self, amount: int = 50) -> int:
        """Increment tokens_remaining on complete. Returns new value."""
        data = self.load(self.sandbox_name)
        before = data["tokens_remaining"]
        new_value = min(data["bootstrap_max"], before + amount)
        data["tokens_remaining"] = new_value
        self.save(self.sandbox_name, data)

        record_event(
            sandbox=self.sandbox_name,
            event="complete",
            before=before,
            after=new_value,
        )

        # Invalidate SandboxState cache
        try:
            from hero.state.sandbox import _cache
            _cache.invalidate(self.sandbox_name)
        except ImportError:
            pass

        return new_value

    def compact_reset(self) -> None:
        """Reset compactions_used to 0 after compaction."""
        data = self.load(self.sandbox_name)
        before = data.get("compactions_used", 0)
        data["compactions_used"] = 0
        self.save(self.sandbox_name, data)

        record_event(
            sandbox=self.sandbox_name,
            event="compact",
            before=before,
            after=0,
        )

        # Invalidate SandboxState cache
        try:
            from hero.state.sandbox import _cache
            _cache.invalidate(self.sandbox_name)
        except ImportError:
            pass

    def record_compaction(self) -> int:
        """Record a compaction usage. Returns new compactions_used count."""
        data = self.load(self.sandbox_name)
        before = data.get("compactions_used", 0)
        new_value = before + 1
        data["compactions_used"] = new_value
        self.save(self.sandbox_name, data)

        record_event(
            sandbox=self.sandbox_name,
            event="compaction_record",
            before=before,
            after=new_value,
        )

        # Invalidate SandboxState cache
        try:
            from hero.state.sandbox import _cache
            _cache.invalidate(self.sandbox_name)
        except ImportError:
            pass

        return new_value

    def record_usage(self, tokens_used: int) -> None:
        """Deduct actual tokens used from remaining budget."""
        state = self.load()
        remaining = state.get("tokens_remaining", 5000)
        compactions = state.get("compactions_used", 0)
        
        remaining -= tokens_used
        compactions += 1
        
        state["tokens_remaining"] = max(0, remaining)
        state["compactions_used"] = compactions
        self.save(self.sandbox_name, state)

    def is_exhausted(self) -> bool:
        """Check if tokens_remaining is 0 (budget exhausted)."""
        data = self.load(self.sandbox_name)
        return data["tokens_remaining"] <= 0

    def get_remaining_ratio(self) -> float:
        """Get ratio of tokens_remaining to bootstrap_max (0.0 to 1.0)."""
        data = self.load(self.sandbox_name)
        if data["bootstrap_max"] == 0:
            return 0.0
        return data["tokens_remaining"] / data["bootstrap_max"]