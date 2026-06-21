"""Circuit breaker for hook failures.

Prevents cascading failures: after 3 consecutive failures on the same
hook within a session, the hook is marked **degraded** and skipped for
the remainder of the session.  Degraded hooks are surfaced at the next
``on_session_start`` event so operators can address them.

State is written to ``~/.hero/hooks/circuit.json``.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

CIRCUIT_PATH = Path.home() / ".hero" / "hooks" / "circuit.json"
MAX_STRIKES = 3


@dataclass
class HookCircuit:
    """Per-hook circuit breaker state."""

    hook_id: str
    failure_count: int = 0
    degraded: bool = False
    degraded_at: float = 0.0
    last_failure: str = ""
    last_failure_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "hook_id": self.hook_id,
            "failure_count": self.failure_count,
            "degraded": self.degraded,
            "degraded_at": self.degraded_at,
            "last_failure": self.last_failure,
            "last_failure_at": self.last_failure_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> HookCircuit:
        return cls(
            hook_id=d["hook_id"],
            failure_count=d.get("failure_count", 0),
            degraded=d.get("degraded", False),
            degraded_at=d.get("degraded_at", 0.0),
            last_failure=d.get("last_failure", ""),
            last_failure_at=d.get("last_failure_at", 0.0),
        )


class CircuitBreaker:
    """Session-scoped circuit breaker for hooks.

    ``record_failure`` increments the counter; after ``MAX_STRIKES`` (3)
    consecutive failures, the hook is marked **degraded** and skipped.

    ``record_success`` resets the failure counter, allowing the hook to
    recover.

    ``reset_session`` clears all state — called on ``on_session_start``.
    """

    def __init__(self) -> None:
        CIRCUIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._circuits: dict[str, HookCircuit] = {}
        self._load()

    def _load(self) -> None:
        if not CIRCUIT_PATH.exists():
            return
        try:
            raw = json.loads(CIRCUIT_PATH.read_text())
            self._circuits = {
                k: HookCircuit.from_dict(v) for k, v in raw.items()
            }
        except (json.JSONDecodeError, KeyError, TypeError):
            self._circuits = {}

    def _save(self) -> None:
        raw = {k: v.to_dict() for k, v in self._circuits.items()}
        CIRCUIT_PATH.write_text(json.dumps(raw, indent=2))

    def is_degraded(self, hook_id: str) -> bool:
        """Check whether *hook_id* is currently degraded.

        Args:
            hook_id: Hook identifier.

        Returns:
            ``True`` if the circuit is open (degraded).
        """
        circuit = self._circuits.get(hook_id)
        if circuit is None:
            return False
        return circuit.degraded

    def record_failure(self, hook_id: str, error: str) -> bool:
        """Record a failure for *hook_id*.

        If the failure count reaches ``MAX_STRIKES``, the hook is
        degraded.

        Args:
            hook_id: Hook identifier.
            error: Description of the failure.

        Returns:
            ``True`` if the hook was just degraded by this failure.
        """
        now = time.time()
        circuit = self._circuits.get(hook_id)
        if circuit is None:
            circuit = HookCircuit(hook_id=hook_id)
            self._circuits[hook_id] = circuit

        circuit.failure_count += 1
        circuit.last_failure = error
        circuit.last_failure_at = now

        if circuit.failure_count >= MAX_STRIKES and not circuit.degraded:
            circuit.degraded = True
            circuit.degraded_at = now
            self._save()
            return True

        self._save()
        return False

    def record_success(self, hook_id: str) -> None:
        """Record a success, resetting the failure counter.

        Args:
            hook_id: Hook identifier.
        """
        circuit = self._circuits.get(hook_id)
        if circuit is None:
            return
        circuit.failure_count = 0
        if circuit.degraded:
            circuit.degraded = False
            circuit.degraded_at = 0.0
        self._save()

    def reset_session(self) -> None:
        """Clear all circuit breaker state for a new session."""
        self._circuits.clear()
        if CIRCUIT_PATH.exists():
            CIRCUIT_PATH.unlink()

    def get_degraded(self) -> list[HookCircuit]:
        """Return all currently degraded hooks.

        Returns:
            List of ``HookCircuit`` instances for degraded hooks.
        """
        return [c for c in self._circuits.values() if c.degraded]

    def get_all(self) -> dict[str, HookCircuit]:
        """Return all circuit states.

        Returns:
            Dict mapping hook_id to HookCircuit.
        """
        return dict(self._circuits)


# Singleton instance
hook_circuit = CircuitBreaker()
