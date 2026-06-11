"""Soldier spawning for OpenClaw — uses hermes-agent CLI subprocess (legacy)
and OpenClaw dispatch queue (current).

The launch() method supports both paths:
  - By default it calls subprocess.Popen with hermes-agent -z (backwards compat)
  - If USE_DISPATCH_QUEUE env var is set, it writes to the dispatch queue instead.

Usage:
    hero spawn --sandbox sook-pro --task "fix theme switcher lag"
    → calls hermes-agent CLI subprocess
    → soldier_id returned as hex uuid prefix
"""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

import yaml

from hero.logging import get_logger
from hero.reliability.circuit_breaker import (
    is_quarantined,
    record_failure,
    record_success,
)
from hero.soldier.context import BudgetConfig, KatanaData, build_context
from hero.soldier.dispatch import enqueue
from hero.state.budget_history import record_event


logger = get_logger("spawner")

ARMY_CONFIG_PATH = Path.home() / ".hero" / "army.yaml"
DISPATCH_DIR = Path.home() / ".hero" / "dispatch"

# Path to the hermes-agent binary (backwards-compat for tests and existing workflows)
HERMES_AGENT_BIN = Path(__file__).parent.parent.parent / "bin" / "hermes-agent"


def load_army_config() -> dict:
    """Load army configuration from ~/.hero/army.yaml."""
    if ARMY_CONFIG_PATH.exists():
        with open(ARMY_CONFIG_PATH) as f:
            return yaml.safe_load(f)
    return {}


def _compute_complexity(task: str, files: list[str], project_size: int = 0) -> int:
    """Compute task complexity score (1-10) based on task description, files, and project size.

    Scoring:
    - Task description length: <50 chars -> +1, 50-200 -> +2, >200 -> +3
    - Number of files mentioned: 1 -> +1, 2-3 -> +2, >3 -> +3
    - Keywords: "architecture", "refactor", "redesign", "migrate" -> +2
    - Keywords: "test" -> +1
    - Project size (src file count): <50 -> +0, 50-200 -> +1, >200 -> +2
    - Clamp result to 1-10
    """
    score = 0

    # Task description length
    task_len = len(task)
    if task_len < 50:
        score += 1
    elif task_len <= 200:
        score += 2
    else:
        score += 3

    # Number of files mentioned
    num_files = len(files)
    if num_files == 1:
        score += 1
    elif num_files <= 3:
        score += 2
    else:
        score += 3

    # Keywords
    task_lower = task.lower()
    if any(kw in task_lower for kw in ["architecture", "refactor", "redesign", "migrate"]):
        score += 2
    if "test" in task_lower:
        score += 1

    # Project size
    if project_size >= 200:
        score += 2
    elif project_size >= 50:
        score += 1

    # Clamp to 1-10
    return max(1, min(10, score))


def estimate_budget(task: str, files: list[str] | None = None, project_size: int = 0) -> int:
    """Estimate token budget based on task complexity.

    Returns 1000 (simple), 5000 (moderate), or 20000 (complex) tokens.

    Args:
        task: Task description string.
        files: List of file paths mentioned or affected.
        project_size: Number of source files in the project.

    Returns:
        Token budget (1000, 5000, or 20000).

    Edge cases:
        - Empty task returns minimum budget (500)
        - Estimation failure returns default (5000)
        - Minimum budget floor: 500 tokens
    """
    try:
        if not task or not task.strip():
            return 500

        if files is None:
            files = []

        score = _compute_complexity(task, files, project_size)

        if score <= 3:
            return 1000
        elif score <= 6:
            return 5000
        else:
            return 20000
    except Exception:
        return 5000


def get_model_for_role(role: str = "soldier",
                       round_index: int | None = None) -> tuple[str, str]:
    """Get model and provider for a given role.

    Supports round-robin for roles with multiple models.
    For OpenClaw: returns model in 'provider/model' format for sessions_spawn.

    Args:
        role: One of lead, architect, soldier, researcher, archivist, utility,
              communicator
        round_index: Explicit round-robin index (omit for automatic)

    Returns:
        Tuple of (model_full_name, model_short_name)
    """
    army = load_army_config()
    roles = army.get("roles", {})

    role_config = roles.get(role, roles.get("soldier", {}))

    # Handle single model
    if "model" in role_config:
        provider = role_config.get("provider", "")
        model = role_config["model"]
        model_full = f"{provider}/{model}" if provider else model
        return model_full, model

    # Handle multiple models with round-robin
    models = role_config.get("models", [])
    if not models:
        return "stepfun-plan/step-3.5-flash", "step-3.5-flash"  # fallback

    # Use a simple counter file for round-robin
    counter_file = Path.home() / ".hero" / f".{role}_counter"
    try:
        if counter_file.exists():
            count = int(counter_file.read_text().strip())
        else:
            count = 0
    except (ValueError, OSError):
        count = 0

    if round_index is not None:
        idx = round_index % len(models)
    else:
        idx = count % len(models)
        counter_file.write_text(str(count + 1))

    selected = models[idx]
    provider = selected.get("provider", "")
    model = selected["model"]
    model_full = f"{provider}/{model}" if provider else model
    return model_full, model


def _build_hermes_command(task: str, sandbox_path: Path,
                          budget: BudgetConfig,
                          role: str = "soldier",
                          model_override: tuple[str, str] | None = None) -> list[str]:
    """Build the hermes-agent CLI command list."""
    if model_override:
        model_full, model_short = model_override
    else:
        model_full, model_short = get_model_for_role(role)

    context = build_context(
        SandboxData(
            name=sandbox_path.name,
            budget=budget,
            katana=KatanaData(pending=[], known_issues=[]),
        ),
        task,
    )
    return [
        str(HERMES_AGENT_BIN),
        "-z",
        context,
        "--model", model_full,
        "--workdir", str(sandbox_path),
    ]


def _resolve_tokens(sandbox_name: str, base_path: Path, budget: BudgetConfig) -> int:
    """Read current tokens_remaining from BUDGET.toon or fall back to BudgetConfig."""
    try:
        from hero.state.budget import BudgetState

        bs = BudgetState(sandbox_name, base_path=base_path)
        data = bs.load()
        return data.get("tokens_remaining", 0)
    except Exception:
        return budget.tokens_remaining if budget.tokens_remaining is not None else 0


class SoldierSpawner:
    """Launches soldier agents via hermes-agent CLI subprocess.

    Also supports writing to the OpenClaw dispatch queue when the
    ``USE_DISPATCH_QUEUE`` environment variable is set.
    """

    def __init__(self, sandbox_path: Path):
        """Initialize spawner with sandbox path.

        Args:
            sandbox_path: Path to the sandbox directory.
        """
        self.sandbox_path = sandbox_path

    def launch(self, task: str, budget: BudgetConfig, role: str = "soldier",
               model_override: tuple[str, str] | None = None) -> str:
        """Launch a soldier agent via hermes-agent CLI subprocess.

        If ``USE_DISPATCH_QUEUE`` env var is set (truthy), writes the task
        to the OpenClaw dispatch queue instead of calling hermes-agent directly.

        Records a ``spawn`` budget-history event before and after launch
        so token consumption trends are trackable over time.

        Args:
            task: Task description for the soldier.
            budget: Budget configuration for the soldier.
            role: Army role (lead, architect, soldier, researcher, archivist,
                  utility)
            model_override: Optional (model_full, model_short) tuple to skip
                            round-robin

        Returns:
            Task/soldier ID (hex uuid prefix) for the launched task.
            Raises RuntimeError if the sandbox is quarantined.

        Raises:
            RuntimeError: If the sandbox is currently quarantined.
        """
        # ── Circuit breaker: refuse to spawn quarantined sandboxes ──────
        sandbox_name = self.sandbox_path.name
        if is_quarantined(sandbox_name):
            logger.warning(
                "Spawn refused — sandbox quarantined",
                sandbox=sandbox_name,
            )
            raise RuntimeError(
                f"Sandbox '{sandbox_name}' is quarantined due to "
                f"consecutive failures. Use `hero unquarantine {sandbox_name}` "
                f"or wait for auto-cooldown (10 min)."
            )

        # ── Capture pre-spawn budget state ──────────────────────────────
        tokens_before = _resolve_tokens(sandbox_name, self.sandbox_path.parent, budget)

        use_queue = os.environ.get("USE_DISPATCH_QUEUE", "1").strip() not in ("", "0", "false", "False")

        if use_queue:
            soldier_id = self._launch_via_queue(task, budget, role, model_override)
        else:
            soldier_id = self._launch_hermes_cli(task, budget, role, model_override)

        # ── Capture post-spawn budget state and record event ─────────────
        tokens_after = _resolve_tokens(sandbox_name, self.sandbox_path.parent, budget)
        record_event(
            sandbox=sandbox_name,
            event="spawn",
            before=tokens_before,
            after=tokens_after,
        )

        return soldier_id

    def _launch_hermes_cli(self, task: str, budget: BudgetConfig,
                           role: str,
                           model_override: tuple[str, str] | None) -> str:
        """Launch via the hermes-agent CLI subprocess (legacy path)."""
        sandbox_name = self.sandbox_path.name

        if model_override:
            model_full, model_short = model_override
        else:
            model_full, model_short = get_model_for_role(role)

        # Get timeout from army config or fallback to defaults
        army = load_army_config()
        role_config = army.get("roles", {}).get(role, {})
        timeout_map = {
            "communicator": 120,
            "lead": 600,
            "architect": 300,
            "soldier": 600,
            "researcher": 300,
            "archivist": 300,
            "utility": 120,
        }
        run_timeout = role_config.get("timeout", timeout_map.get(role, 600))

        # Build lean TOON prompt for the soldier
        from hero.soldier.context import SandboxData, KatanaData
        sandbox_data = SandboxData(
            name=self.sandbox_path.name,
            budget=budget,
            katana=KatanaData(pending=[], known_issues=[]),
        )
        context = build_context(sandbox=sandbox_data, task=task)

        cmd = [
            str(HERMES_AGENT_BIN),
            "-z",
            context,
            "--model", model_full,
            "--workdir", str(self.sandbox_path),
        ]

        process = subprocess.Popen(
            cmd,
            cwd=str(self.sandbox_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        soldier_id = uuid.uuid4().hex[:8]
        self._create_heartbeat(soldier_id)
        # Subprocess launched successfully
        record_success(sandbox_name)
        return soldier_id

    def _launch_via_queue(self, task: str, budget: BudgetConfig,
                          role: str,
                          model_override: tuple[str, str] | None) -> str:
        """Write task to OpenClaw dispatch queue with model fallback.

        Attempts to enqueue with the primary model. If enqueue fails
        (returns None or raises), tries one fallback model from the
        role's model_fallbacks list in army.yaml.

        Records success/failure via circuit breaker after each attempt.
        """
        sandbox_name = self.sandbox_path.name
        army = load_army_config()
        role_config = army.get("roles", {}).get(role, {})

        if model_override:
            model_full, model_short = model_override
        else:
            model_full, model_short = get_model_for_role(role)

        max_tokens = role_config.get("max_tokens_injected", 8000)
        context_window = role_config.get("context_window", 131072)

        timeout_map = {
            "communicator": 120, "lead": 600, "architect": 300,
            "soldier": 600, "researcher": 300, "archivist": 300,
            "utility": 120,
        }
        run_timeout = role_config.get("timeout", timeout_map.get(role, 600))
        label = (f"{sandbox_name}-{role}-"
                 f"{task[:20].lower().replace(' ', '-')}")

        # Record budget before spawn
        before_budget = budget.bootstrap_max
        record_event(
            sandbox=sandbox_name,
            event="spawn",
            before=before_budget,
            after=before_budget - budget.bootstrap_max,
        )

        # ── Primary attempt ────────────────────────────────────────────
        task_id = self._do_enqueue(
            sandbox_name, task, role, model_full, model_short,
            budget, run_timeout, label, max_tokens, context_window,
        )

        # ── Fallback if primary failed ─────────────────────────────────
        if task_id is None:
            fallback_models = role_config.get("model_fallbacks", [])
            if fallback_models:
                fallback_model = self._resolve_fallback_model(
                    fallback_models, role_config, role
                )
                if fallback_model:
                    fallback_full, fallback_short = fallback_model
                    logger.warning(
                        "Enqueue failed — trying fallback model",
                        sandbox=sandbox_name,
                        primary_model=model_short,
                        fallback_model=fallback_short,
                        role=role,
                    )
                    task_id = self._do_enqueue(
                        sandbox_name, task, role,
                        fallback_full, fallback_short,
                        budget, run_timeout, label,
                        max_tokens, context_window,
                    )
                    if task_id is not None:
                        logger.info(
                            "Fallback enqueue succeeded",
                            sandbox=sandbox_name,
                            model=fallback_short,
                            task_id=task_id,
                        )

        # ── Circuit breaker: record outcome ────────────────────────────
        if task_id is not None:
            record_success(sandbox_name)
            record_event(
                sandbox=sandbox_name,
                event="spawn_complete",
                before=before_budget,
                after=before_budget - budget.bootstrap_max,
            )
            return task_id
        else:
            now_quarantined = record_failure(sandbox_name)
            logger.error(
                "Enqueue failed after all attempts",
                sandbox=sandbox_name,
                now_quarantined=now_quarantined,
            )
            raise RuntimeError(
                f"Failed to enqueue task for sandbox '{sandbox_name}' "
                f"after all model attempts. Sandbox "
                f"{'quarantined' if now_quarantined else 'still active'}."
            )

    def _do_enqueue(self, sandbox_name: str, task: str, role: str,
                    model_full: str, model_short: str,
                    budget: BudgetConfig, run_timeout: int,
                    label: str, max_tokens: int,
                    context_window: int) -> str | None:
        """Core enqueue operation, returning task_id or None on failure."""
        try:
            task_id = enqueue(
                sandbox=sandbox_name,
                task=task,
                role=role,
                model=model_full,
                model_short=model_short,
                budget=budget.bootstrap_max,
                workdir=str(self.sandbox_path),
                timeout=run_timeout,
                label=label,
                max_tokens=max_tokens,
                context_window=context_window,
            )
            if task_id:
                self._create_heartbeat(task_id)
                return task_id
            return None
        except Exception as exc:
            logger.error(
                "Enqueue raised exception",
                sandbox=sandbox_name,
                model=model_short,
                error=str(exc),
            )
            return None

    def _resolve_fallback_model(
        self,
        fallback_models: list[str],
        role_config: dict,
        role: str,
    ) -> tuple[str, str] | None:
        """Resolve a fallback model name to (model_full, model_short).

        Look up the fallback model name in the role's 'models' list to
        find its provider. If not found, use a fallback to the role's
        default fallback pair (stepfun-plan/step-3.5-flash).
        """
        models_list = role_config.get("models", [])

        for fb_name in fallback_models:
            # Look for a matching entry in the models list
            for m in models_list:
                if isinstance(m, dict) and m.get("model") == fb_name:
                    provider = m.get("provider", "")
                    model_full = f"{provider}/{fb_name}" if provider else fb_name
                    return model_full, fb_name

            # If models_list doesn't have dict entries, check if fallback
            # names are simple strings that match directly
            if fb_name in models_list:
                # models_list contains strings, try default provider
                return fb_name, fb_name

        # Last resort: return a hardcoded fallback
        logger.warning(
            "No matching fallback model found in role config",
            role=role,
            fallback_models=fallback_models,
        )
        return "stepfun-plan/step-3.5-flash", "step-3.5-flash"

    def _create_heartbeat(self, soldier_id: str) -> None:
        """Write a HEARTBEAT.toon file for the spawned soldier.

        Called after both hermes-agent and dispatch-queue launches so the
        heartbeat always exists regardless of the launch path.

        Args:
            soldier_id: The soldier/task ID returned by the launch path.
        """
        from hero.soldier.heartbeat import HeartbeatState

        hb = HeartbeatState(self.sandbox_path.name, base_path=self.sandbox_path.parent)
        hb.create(soldier_id)
