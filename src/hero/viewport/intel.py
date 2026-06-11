"""hero.viewport.intel — Cross-sandbox bottleneck detection for the Intelligence Zone.

Detects:
  - Token choke: sandbox consuming >60% of remaining army budget
  - Pipeline stall: WORKING sandbox with zero tool calls for >30s
  - Error cascade: sandbox with error/failed status and retry_count > 2
  - Circuit breaker: sandbox quarantined via circuit_breaker module
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hero.viewport.metrics import ArmyMetrics, SandboxMetrics
from hero.viewport.states import SandboxState


# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class Bottleneck:
    """Detected bottleneck in the army pipeline."""

    sandbox_name: str
    kind: str  # "token_choke" | "model_contention" | "pipeline_stall" | "error_cascade" | "circuit_breaker"
    severity: str  # "critical" | "warning" | "info"
    detail: str  # human-readable description
    impacted_sandboxes: list[str]
    suggestion: str  # what to do about it


@dataclass
class BudgetProjection:
    """Projected budget exhaustion for a sandbox."""

    sandbox_name: str
    tokens_used: int
    tokens_budget: int
    usage_pct: float
    burn_rate: float  # tokens per minute
    eta_minutes: int | None  # minutes until exhaustion, None if no burn rate
    status: str  # "healthy" | "warning" | "critical"


@dataclass
class Action:
    """Suggested remediation action."""

    priority: str  # "high" | "medium" | "low"
    sandbox: str
    action_type: str  # "retry" | "model_swap" | "pause" | "cap_budget" | "investigate"
    description: str
    suggestion: str  # what to do


def detect_bottlenecks(
    army: ArmyMetrics,
    dispatch_data: dict[str, dict[str, Any]],
) -> list[Bottleneck]:
    """Scan all sandboxes for bottlenecks.

    Parameters
    ----------
    army:
        Current army-level metrics snapshot.
    dispatch_data:
        Per-sandbox dispatch info keyed by sandbox name. Each value is the
        dispatch dict (from ``~/.hero/dispatch/``). Should contain at minimum
        keys used by this function: ``status``, ``retry_count``, ``tool_calls``,
        ``last_updated``, ``model``.

    Returns
    -------
    list[Bottleneck]
        Detected bottlenecks, ordered by severity (critical first).
    """
    bottlenecks: list[Bottleneck] = []
    now = time.time()

    if army.total_tokens_budget == 0:
        return bottlenecks

    remaining_budget = army.total_tokens_budget - army.total_tokens_used
    remaining_ratio = remaining_budget / army.total_tokens_budget

    for sb in army.sandboxes:
        dispatch = dispatch_data.get(sb.name, {})

        # ── 1. Token choke ────────────────────────────────────────────────
        # Sandbox using >60% of *remaining* army budget.
        if remaining_budget > 0 and sb.tokens_used > 0:
            sb_share = sb.tokens_used / remaining_budget
            if sb_share > 0.6:
                bottlenecks.append(Bottleneck(
                    sandbox_name=sb.name,
                    kind="token_choke",
                    severity="critical",
                    detail=(
                        f"{sb.name} is consuming {sb_share:.0%} of remaining army budget"
                        f" ({sb.tokens_used:,} of {remaining_budget:,} remaining)"
                    ),
                    impacted_sandboxes=[sb.name],
                    suggestion=(
                        "Reduce worker count, switch to cheaper model, or "
                        "increase army token budget"
                    ),
                ))

        # ── 2. Pipeline stall ─────────────────────────────────────────────
        # WORKING sandbox with zero new tool calls for >30 seconds.
        if sb.status == SandboxState.WORKING.value or sb.status == "active" or sb.status == "running":
            last_updated = dispatch.get("last_updated")
            if last_updated is not None:
                try:
                    elapsed = now - float(last_updated)
                except (ValueError, TypeError):
                    elapsed = 0.0
            else:
                elapsed = 0.0

            if sb.no_progress_counter >= 15 and elapsed > 30:
                # 15 no-progress cycles at 2s refresh = ~30s
                bottlenecks.append(Bottleneck(
                    sandbox_name=sb.name,
                    kind="pipeline_stall",
                    severity="warning",
                    detail=(
                        f"{sb.name} is WORKING but has produced zero new tool calls"
                        f" for {elapsed:.0f}s ({sb.no_progress_counter} cycles)"
                    ),
                    impacted_sandboxes=[sb.name],
                    suggestion=(
                        "Check if sandbox is waiting on external input or stuck in loop. "
                        "Consider escalating to COMM or restarting."
                    ),
                ))

        # ── 3. Error cascade ──────────────────────────────────────────────
        # Sandbox with error/failed status and retry_count > 2.
        retry_count = dispatch.get("retry_count", 0) or 0
        if sb.status in ("error", "failed") and retry_count > 2:
            bottlenecks.append(Bottleneck(
                sandbox_name=sb.name,
                kind="error_cascade",
                severity="critical",
                detail=(
                    f"{sb.name} has failed {retry_count} times"
                    f" (status: {sb.status})"
                ),
                impacted_sandboxes=[sb.name],
                suggestion=(
                    "Pause retries. Investigate root cause in error logs. "
                    "Escalate to COMM for architecture review."
                ),
            ))

        # ── 4. Circuit breaker ────────────────────────────────────────────
        from hero.reliability.circuit_breaker import is_quarantined as cb_quarantined
        if cb_quarantined(sb.name):
            bottlenecks.append(Bottleneck(
                sandbox_name=sb.name,
                kind="circuit_breaker",
                severity="critical",
                detail=f"{sb.name} is quarantined by circuit breaker (3+ consecutive failures)",
                impacted_sandboxes=[sb.name],
                suggestion=(
                    "Sandbox is quarantined. Unquarantine after root cause fix, "
                    "or wait 10 minutes for stale cooldown auto-reset."
                ),
            ))

    # ── 5. Model contention (army-level) ──────────────────────────────────
    # If >50% of WORKING sandboxes share the same model, flag it.
    working_sbs = [
        sb for sb in army.sandboxes
        if sb.status in ("active", "running", "working")
    ]
    if working_sbs:
        model_counts: dict[str, list[str]] = {}
        for sb in working_sbs:
            model = sb.model or dispatch_data.get(sb.name, {}).get("model")
            if model:
                model_counts.setdefault(model, []).append(sb.name)

        for model, names in model_counts.items():
            if len(names) >= max(3, len(working_sbs) // 2):
                bottlenecks.append(Bottleneck(
                    sandbox_name="army",
                    kind="model_contention",
                    severity="info",
                    detail=(
                        f"{len(names)}/{len(working_sbs)} active sandboxes use {model} — "
                        "possible rate-limit or latency bottleneck"
                    ),
                    impacted_sandboxes=names,
                    suggestion=(
                        "Consider spreading load across different models or "
                        "reducing parallel workers."
                    ),
                ))

    # Sort: critical first, then warning, then info
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    bottlenecks.sort(key=lambda b: severity_order.get(b.severity, 3))
    return bottlenecks


# ── Budget projections ──────────────────────────────────────────────────────

def compute_budget_projections(
    army: ArmyMetrics,
    prev_army: ArmyMetrics | None = None,
) -> list[BudgetProjection]:  # noqa: E306
    """Compute per-sandbox budget burn projections.

    Parameters
    ----------
    army:
        Current army metrics snapshot.
    prev_army:
        Previous snapshot for burn-rate calculation.  If *None* or the
        elapsed time is < 1 second a default burn rate of ``tokens_used / 120``
        (assumes 2 minutes of history) is used.

    Returns
    -------
    list[BudgetProjection]
        One entry per sandbox that has a non-zero budget.
    """
    projections: list[BudgetProjection] = []
    now = time.time()

    # Derive elapsed seconds from prev_army if available.
    elapsed: float | None = None
    if prev_army is not None:
        # We don't have timestamps on ArmyMetrics, so use a rough heuristic:
        # assume previous snapshot was taken REFRESH_INTERVAL seconds ago.
        from hero.viewport.renderer import REFRESH_INTERVAL
        elapsed = REFRESH_INTERVAL

    for sb in army.sandboxes:
        if sb.tokens_budget == 0:
            continue

        usage_pct = sb.tokens_used / sb.tokens_budget

        # ── Burn rate ──────────────────────────────────────────────────
        burn_rate: float  # tokens / minute
        if prev_army is not None and elapsed is not None and elapsed >= 1.0:
            prev_sb = next(
                (s for s in prev_army.sandboxes if s.name == sb.name), None
            )
            if prev_sb is not None:
                delta_used = sb.tokens_used - prev_sb.tokens_used
                burn_rate = (delta_used / elapsed) * 60.0  # per minute
            else:
                burn_rate = sb.tokens_used / 120.0  # assume 2 min history
        else:
            burn_rate = sb.tokens_used / 120.0  # assume 2 min history

        burn_rate = max(burn_rate, 0.0)

        # ── ETA ────────────────────────────────────────────────────────
        eta_minutes: int | None
        tokens_remaining = max(0, sb.tokens_budget - sb.tokens_used)
        if burn_rate > 0 and tokens_remaining > 0:
            eta = tokens_remaining / burn_rate
            eta_minutes = max(1, int(round(eta)))
        else:
            eta_minutes = None

        # ── Status ─────────────────────────────────────────────────────
        if usage_pct < 0.5:
            status = "healthy"
        elif usage_pct <= 0.8:
            status = "warning"
        else:
            status = "critical"

        projections.append(BudgetProjection(
            sandbox_name=sb.name,
            tokens_used=sb.tokens_used,
            tokens_budget=sb.tokens_budget,
            usage_pct=usage_pct,
            burn_rate=burn_rate,
            eta_minutes=eta_minutes,
            status=status,
        ))

    return projections


# ── Action queue ─────────────────────────────────────────────────────────────

def generate_actions(
    bottlenecks: list[Bottleneck],
    projections: list[BudgetProjection],
) -> list[Action]:
    """Generate suggested remediation actions from bottlenecks and projections.

    Priority rules
    ---------------
    - Critical bottleneck → high
    - Critical budget projection → high
    - Pipeline stall → medium
    - Warning budget → medium
    - Everything else → low
    """
    actions: list[Action] = []

    # Track which sandboxes already have a high-priority action to avoid dupes.
    high_priority_sbs: set[str] = set()

    # ── From bottlenecks ────────────────────────────────────────────────
    for b in bottlenecks:
        if b.severity == "critical":
            actions.append(Action(
                priority="high",
                sandbox=b.sandbox_name,
                action_type=_bottleneck_action_type(b.kind),
                description=f"[{b.severity.upper()}] {b.sandbox_name}: {b.kind}",
                suggestion=b.suggestion,
            ))
            if b.sandbox_name != "army":
                high_priority_sbs.add(b.sandbox_name)
        elif b.kind == "pipeline_stall":
            actions.append(Action(
                priority="medium",
                sandbox=b.sandbox_name,
                action_type="investigate",
                description=f"[{b.severity.upper()}] {b.sandbox_name}: {b.kind}",
                suggestion=b.suggestion,
            ))
        elif b.kind == "model_contention":
            actions.append(Action(
                priority="medium",
                sandbox=b.sandbox_name,
                action_type="model_swap",
                description=f"[{b.severity.upper()}] {b.sandbox_name}: {b.kind}",
                suggestion=b.suggestion,
            ))
        else:
            actions.append(Action(
                priority="low",
                sandbox=b.sandbox_name,
                action_type="investigate",
                description=f"[{b.severity.upper()}] {b.sandbox_name}: {b.kind}",
                suggestion=b.suggestion,
            ))

    # ── From budget projections ─────────────────────────────────────────
    for p in projections:
        if p.status == "critical" and p.sandbox_name not in high_priority_sbs:
            actions.append(Action(
                priority="high",
                sandbox=p.sandbox_name,
                action_type="cap_budget",
                description=(
                    f"[CRITICAL] {p.sandbox_name}: "
                    f"{p.usage_pct:.0%} budget used"
                ),
                suggestion=(
                    f"Sandbox at {p.usage_pct:.0%} budget. "
                    f"Cap at {int(p.tokens_budget * 0.7):,} tokens or swap to cheaper model. "
                    f"Burn rate: {p.burn_rate:.0f} tok/min. ETA: {p.eta_minutes or 'N/A'} min."
                ),
            ))
            high_priority_sbs.add(p.sandbox_name)
        elif p.status == "warning" and p.sandbox_name not in high_priority_sbs:
            actions.append(Action(
                priority="medium",
                sandbox=p.sandbox_name,
                action_type="cap_budget",
                description=(
                    f"[WARNING] {p.sandbox_name}: "
                    f"{p.usage_pct:.0%} budget used"
                ),
                suggestion=(
                    f"Monitor closely. Current burn: {p.burn_rate:.0f} tok/min. "
                    f"ETA exhaustion: {p.eta_minutes or 'N/A'} min. "
                    f"Consider reducing parallel workers."
                ),
            ))

    # Sort: high → medium → low
    priority_order = {"high": 0, "medium": 1, "low": 2}
    actions.sort(key=lambda a: priority_order.get(a.priority, 3))
    return actions


def _bottleneck_action_type(kind: str) -> str:
    """Map a bottleneck kind to an action type."""
    mapping = {
        "token_choke": "cap_budget",
        "pipeline_stall": "investigate",
        "error_cascade": "retry",
        "circuit_breaker": "pause",
        "model_contention": "model_swap",
    }
    return mapping.get(kind, "investigate")


# ── Sandbox Detail (drill-down) ─────────────────────────────────────────────

@dataclass
class SandboxDetail:
    """Full detail snapshot for a single sandbox drill-down."""

    name: str
    status: str
    model: str | None = None
    current_task: str | None = None
    workdir: str | None = None
    tokens_used: int = 0
    tokens_budget: int = 0
    usage_pct: float = 0.0
    compactions_used: int = 0
    tool_calls: int = 0
    subagent_count: int = 0
    no_progress_counter: int = 0

    # Pipeline
    pipeline_task: str | None = None
    pipeline_steps: dict | None = None
    pipeline_created: str | None = None

    # Dispatch tasks
    dispatch_tasks: list[dict] = field(default_factory=list)

    # Errors
    errors: list[dict] = field(default_factory=list)

    # Katana
    pending_tasks: list[str] = field(default_factory=list)
    known_issues: list[str] = field(default_factory=list)

    # Last compacted event summary
    last_compacted: str | None = None


# ── Git helpers ─────────────────────────────────────────────────────────────

def _git_summary(workdir: str | None) -> str | None:
    """Return a one-line git summary (branch + dirty status) for a workdir."""
    if not workdir or not Path(workdir).exists():
        return None
    try:
        import subprocess
        branch = subprocess.run(
            ["git", "-C", workdir, "branch", "--show-current"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        if not branch:
            # Detached head — try to get commit hash
            branch = subprocess.run(
                ["git", "-C", workdir, "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=5
            ).stdout.strip()
            branch = f"detached@{branch}" if branch else None
        dirty = subprocess.run(
            ["git", "-C", workdir, "status", "--porcelain"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        if branch is None:
            return None
        suffix = " [dirty]" if dirty else ""
        return f"{branch}{suffix}"
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return None


def collect_sandbox_detail(
    sandbox_name: str,
    army: ArmyMetrics | None = None,
    dispatch_map: dict[str, dict] | None = None,
) -> SandboxDetail:
    """Collect all available detail for one sandbox.

    Sources:
      - ArmyMetrics (for the matching SandboxMetrics)
      - ~/.hero/dispatch/*.{toon,json}
      - ~/.hero/pipeline/*.json (for pipeline manifest)
      - ~/.hero/sandboxes/<name>/ (budget, katana)
      - git status (via workdir from dispatch)

    Parameters
    ----------
    sandbox_name:
        Name of the sandbox to detail.
    army:
        Optional ArmyMetrics snapshot (avoids re-reading all files).
    dispatch_map:
        Optional pre-loaded dispatch map {task_id: dispatch_dict}.

    Returns
    -------
    SandboxDetail
        Populated detail record.
    """
    # ── 1. From ArmyMetrics ────────────────────────────────────────────
    sb_metrics: SandboxMetrics | None = None
    if army:
        sb_metrics = next((s for s in army.sandboxes if s.name == sandbox_name), None)

    # ── 2. From sandbox state files ────────────────────────────────────
    from hero.state.sandbox import SandboxState
    ss = SandboxState(sandbox_name)
    state_data = ss.load(include_katana=True)

    budget = state_data.get("budget", {})
    bootstrap_max = budget.get("bootstrap_max", 5000)
    tokens_remaining = budget.get("tokens_remaining", 5000)
    compactions_used = budget.get("compactions_used", 0)

    katana = state_data.get("katana", {})
    pending_tasks: list[str] = katana.get("pending", [])
    known_issues: list[str] = katana.get("known_issues", [])

    # ── 3. From dispatch files ─────────────────────────────────────────
    from hero.viewport.tree import _load_dispatch_files
    if dispatch_map is None:
        dispatch_map = _load_dispatch_files(sandbox_name)

    dispatch_tasks: list[dict] = []
    errors: list[dict] = []
    workdir: str | None = None
    model: str | None = None

    for tid, dd in dispatch_map.items():
        entry = {
            "task_id": tid,
            "label": dd.get("label", ""),
            "model": dd.get("model", ""),
            "role": dd.get("role", ""),
            "status": dd.get("status", "unknown"),
            "task": dd.get("task", "")[:120] if dd.get("task") else "",
            "created_at": dd.get("created_at", ""),
            "completed_at": dd.get("completed_at", ""),
            "budget": dd.get("budget", 0),
            "max_tokens": dd.get("max_tokens", 0),
        }
        dispatch_tasks.append(entry)

        # Track workdir and model from latest non-completed task
        if dd.get("status") in ("active", "running", "working", "dispatched"):
            workdir = dd.get("workdir", workdir)
            model = dd.get("model", model)

        # Collect errors
        result = dd.get("result")
        if dd.get("status") in ("error", "failed", "timeout") and result:
            errors.append({
                "task_id": tid,
                "role": dd.get("role", ""),
                "detail": str(result)[:200],
            })

    if not workdir and dispatch_tasks:
        workdir = dispatch_tasks[0].get("workdir")

    # ── 4. From pipeline manifest ───────────────────────────────────────
    from hero.viewport.tree import _load_pipeline_manifest
    manifest = _load_pipeline_manifest(sandbox_name)
    pipeline_task: str | None = None
    pipeline_steps: dict | None = None
    pipeline_created: str | None = None
    if manifest:
        pipeline_task = manifest.get("task", "")[:200]
        pipeline_steps = manifest.get("steps", {})
        pipeline_created = manifest.get("created_at", "")

    # ── 5. Git summary ─────────────────────────────────────────────────
    git_summary = _git_summary(workdir)

    # ── 6. Compose ──────────────────────────────────────────────────────
    tokens_used = sb_metrics.tokens_used if sb_metrics else (bootstrap_max - tokens_remaining)
    tokens_budget = sb_metrics.tokens_budget if sb_metrics else bootstrap_max
    usage_pct = tokens_used / max(tokens_budget, 1)

    return SandboxDetail(
        name=sandbox_name,
        status=sb_metrics.status if sb_metrics else state_data.get("status", "idle"),
        model=model or (sb_metrics.model if sb_metrics else None),
        current_task=sb_metrics.current_task if sb_metrics else None,
        workdir=workdir or state_data.get("path"),
        tokens_used=tokens_used,
        tokens_budget=tokens_budget,
        usage_pct=usage_pct,
        compactions_used=compactions_used,
        tool_calls=sb_metrics.tool_calls if sb_metrics else 0,
        subagent_count=sb_metrics.subagent_count if sb_metrics else 0,
        no_progress_counter=sb_metrics.no_progress_counter if sb_metrics else 0,
        pipeline_task=pipeline_task,
        pipeline_steps=pipeline_steps,
        pipeline_created=pipeline_created,
        dispatch_tasks=dispatch_tasks,
        errors=errors,
        pending_tasks=pending_tasks,
        known_issues=known_issues,
        last_compacted=git_summary,
    )
