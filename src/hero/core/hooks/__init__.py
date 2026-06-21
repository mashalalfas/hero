"""
hero.core.hooks — HERO Hook System.

Git-hooks-for-AI: declarative hooks that enforce agent behaviour rules.
Three layers:
1. Declarative config — ``~/.openclaw/hooks/hooks.yaml``
2. Operational runner — ``hero hook`` CLI commands
3. Event scripts — POSIX-sh scripts in ``events/`` directory

Failure tiers: CRITICAL (block), IMPORTANT (warn+fix), OPTIONAL (silent).
"""

from hero.core.hooks.config import HookConfig, load_hooks_config
from hero.core.hooks.cache import HookCache, hook_cache
from hero.core.hooks.circuit import CircuitBreaker, hook_circuit
from hero.core.hooks.runner import HookRunner, HookResult, run_hooks_for_event

__all__ = [
    "HookConfig",
    "load_hooks_config",
    "HookCache",
    "hook_cache",
    "CircuitBreaker",
    "hook_circuit",
    "HookRunner",
    "HookResult",
    "run_hooks_for_event",
]
