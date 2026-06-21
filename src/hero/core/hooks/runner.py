"""Hook runner — executes hook scripts with safety controls.

Applies the full hook lifecycle:
1. Check circuit breaker (skip degraded hooks)
2. Compute content hash, check cache (skip-if-clean)
3. Run script with timeout
4. Apply failure tier logic (CRITICAL→block, IMPORTANT→warn, OPTIONAL→silent)
5. Update circuit breaker state
6. Update cache
7. Log to audit trail
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hero.core.hooks.cache import HookCache, content_hash, hook_cache
from hero.core.hooks.circuit import CircuitBreaker, hook_circuit
from hero.core.hooks.config import HookConfig, get_hooks_for_event
from hero.logging import get_logger

logger = get_logger("hooks.runner")
AUDIT_DIR = Path.home() / ".hero" / "hooks" / "audit"

# Per-hook execution timeout (seconds)
DEFAULT_TIMEOUT = 30

# 5% of a typical 200k token session = 10000 tokens ceiling for all hooks
SESSION_TOKEN_CEILING = 10000


@dataclass
class HookResult:
    """Structured result of a single hook execution."""

    hook_id: str
    event: str
    action: str
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    cached: bool = False
    degraded: bool = False
    error: str = ""
    timestamp: float = field(default_factory=time.time)

    @property
    def tier(self) -> str:
        return {
            "block": "CRITICAL",
            "warn": "IMPORTANT",
            "silent": "OPTIONAL",
        }.get(self.action, "UNKNOWN")

    def to_dict(self) -> dict[str, Any]:
        return {
            "hook_id": self.hook_id,
            "event": self.event,
            "action": self.action,
            "tier": self.tier,
            "success": self.success,
            "exit_code": self.exit_code,
            "stdout": self.stdout[:500],
            "stderr": self.stderr[:500],
            "duration_ms": self.duration_ms,
            "cached": self.cached,
            "degraded": self.degraded,
            "error": self.error,
            "timestamp": self.timestamp,
        }


class HookRunner:
    """Execute hooks with circuit breaker, caching, and tiered failure handling.

    Usage::

        runner = HookRunner(config=load_hooks_config())
        results = runner.run_event("on_session_start")
    """

    def __init__(
        self,
        config: list[HookConfig],
        cache: HookCache | None = None,
        circuit: CircuitBreaker | None = None,
        session_token_budget: int = SESSION_TOKEN_CEILING,
    ) -> None:
        self._config = config
        self._cache = cache or hook_cache
        self._circuit = circuit or hook_circuit
        self._session_tokens_used = 0
        self._session_token_budget = session_token_budget

    def run_event(self, event: str, context: dict[str, Any] | None = None) -> list[HookResult]:
        """Run all enabled hooks for *event*.

        Hooks are executed in priority order (cheapest first: silent < warn < block).
        Each hook is checked against the circuit breaker and content-hash cache
        before execution.

        Args:
            event: Event name (e.g. ``on_session_start``).
            context: Optional key-value context passed to hook scripts
                     as environment variables (prefixed with ``HOOK_``).

        Returns:
            List of ``HookResult`` for each hook that was considered.
        """
        hooks = get_hooks_for_event(self._config, event)
        if not hooks:
            logger.debug("No hooks configured for event", event=event)
            return []

        results: list[HookResult] = []

        for hook in hooks:
            result = self._run_one(hook, context or {})
            results.append(result)

            # CRITICAL (block) failure stops event processing
            if not result.success and hook.action == "block" and not result.degraded:
                logger.warning(
                    "Blocking hook failed, halting event",
                    hook_id=hook.hook_id,
                    event=event,
                )
                break

        return results

    def _run_one(self, hook: HookConfig, context: dict[str, Any]) -> HookResult:
        """Execute a single hook with full safety envelope."""
        t0 = time.time()

        # 1. Circuit breaker check
        if self._circuit.is_degraded(hook.hook_id):
            logger.warning("Hook degraded, skipping", hook_id=hook.hook_id)
            return HookResult(
                hook_id=hook.hook_id,
                event=hook.event,
                action=hook.action,
                success=False,
                exit_code=-1,
                stdout="",
                stderr="",
                duration_ms=0,
                degraded=True,
                error="Circuit breaker open: hook is degraded",
            )

        # 2. Token budget check
        if self._session_tokens_used >= self._session_token_budget:
            logger.warning("Token budget exhausted", hook_id=hook.hook_id)
            return HookResult(
                hook_id=hook.hook_id,
                event=hook.event,
                action=hook.action,
                success=False,
                exit_code=-1,
                stdout="",
                stderr="",
                duration_ms=0,
                error="Session token budget exhausted",
            )

        # 3. Content-hash cache check
        if hook.cache_ttl > 0:
            ctx_str = json.dumps(context, sort_keys=True) if context else ""
            h = content_hash(hook.hook_id, hook.event, ctx_str)
            cached = self._cache.get(hook.hook_id, h)
            if cached is not None:
                logger.debug("Cache hit", hook_id=hook.hook_id)
                return HookResult(
                    hook_id=hook.hook_id,
                    event=hook.event,
                    action=hook.action,
                    success=cached.get("success", True),
                    exit_code=cached.get("exit_code", 0),
                    stdout=cached.get("stdout", ""),
                    stderr=cached.get("stderr", ""),
                    duration_ms=0,
                    cached=True,
                )

        # 4. Validate script exists
        script = hook.script_path
        if not script.exists():
            return self._handle_failure(
                hook, t0, f"Script not found: {script}",
            )

        if not os.access(script, os.X_OK):
            # Try to make it executable
            script.chmod(script.stat().st_mode | 0o111)

        # 5. Execute
        timeout = DEFAULT_TIMEOUT
        env = os.environ.copy()
        env["HOOK_EVENT"] = hook.event
        env["HOOK_ID"] = hook.hook_id
        env["HOOK_ACTION"] = hook.action
        env["HOOK_MAX_TOKENS"] = str(hook.max_tokens)
        for key, value in context.items():
            env[f"HOOK_{key.upper()}"] = str(value)

        try:
            proc = subprocess.run(
                [str(script)],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                cwd=hook.config_dir,
            )
            duration_ms = (time.time() - t0) * 1000
            stdout = proc.stdout
            stderr = proc.stderr
            exit_code = proc.returncode
            success = exit_code == 0

            result = HookResult(
                hook_id=hook.hook_id,
                event=hook.event,
                action=hook.action,
                success=success,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration_ms,
            )

            if success:
                self._circuit.record_success(hook.hook_id)
                # Cache successful result
                if hook.cache_ttl > 0:
                    ctx_str = json.dumps(context, sort_keys=True) if context else ""
                    h = content_hash(hook.hook_id, hook.event, ctx_str)
                    self._cache.set(
                        hook.hook_id,
                        h,
                        result.to_dict(),
                        ttl=hook.cache_ttl,
                    )
            else:
                self._handle_failure_result(hook, result)

            self._audit(result)
            self._session_tokens_used += hook.max_tokens
            return result

        except subprocess.TimeoutExpired:
            return self._handle_failure(
                hook, t0, f"Script timed out after {timeout}s",
            )
        except Exception as exc:
            return self._handle_failure(
                hook, t0, f"Execution error: {exc}",
            )

    def _handle_failure(self, hook: HookConfig, t0: float, error: str) -> HookResult:
        """Produce a failure result and update circuit breaker."""
        duration_ms = (time.time() - t0) * 1000
        result = HookResult(
            hook_id=hook.hook_id,
            event=hook.event,
            action=hook.action,
            success=False,
            exit_code=-1,
            stdout="",
            stderr=error,
            duration_ms=duration_ms,
            error=error,
        )
        self._handle_failure_result(hook, result)
        self._audit(result)
        return result

    def _handle_failure_result(self, hook: HookConfig, result: HookResult) -> None:
        """Apply failure tier logic and update circuit breaker."""
        degraded = self._circuit.record_failure(
            hook.hook_id,
            result.error or f"exit code {result.exit_code}",
        )
        if degraded:
            result.degraded = True
            logger.warning(
                "Hook degraded after 3 failures",
                hook_id=hook.hook_id,
            )

    def _audit(self, result: HookResult) -> None:
        """Log result to the audit trail."""
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        entry = result.to_dict()
        entry["timestamp"] = time.time()
        logger.info(
            "hook_result",
            hook_id=result.hook_id,
            event=result.event,
            success=result.success,
            cached=result.cached,
            degraded=result.degraded,
            duration_ms=round(result.duration_ms, 1),
        )

    @property
    def tokens_used(self) -> int:
        return self._session_tokens_used


def run_hooks_for_event(
    event: str,
    config_path: Path | None = None,
    context: dict[str, Any] | None = None,
) -> list[HookResult]:
    """Convenience: load config and run hooks for an event.

    Args:
        event: Event name.
        config_path: Optional path to hooks.yaml.
        context: Optional context dict for hook scripts.

    Returns:
        List of HookResult.
    """
    from hero.core.hooks.config import load_hooks_config

    hooks = load_hooks_config(config_path)
    runner = HookRunner(hooks)
    return runner.run_event(event, context)
