"""hero.viewport.metrics — collects sandbox and army-level metrics.

Reads from:
  - ``hero.state.cache``  — cached sandbox state
  - ``~/.hero/dispatch/``  — active dispatch task JSON files
  - ``hero.state.budget`` — per-sandbox budget tracking
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from hero.state.cache import StateCache, default_cache
from hero.viewport import states
from hero.state.usage import sum_sandbox_usage

DISPATCH_DIR = Path.home() / ".hero" / "dispatch"
HERO_HOME = Path.home() / ".hero"


@dataclass
class SandboxMetrics:
    """Per-sandbox metrics snapshot."""

    name: str
    tokens_used: int = 0
    tokens_remaining: int = 0
    tokens_budget: int = 5000
    tool_calls: int = 0
    subagent_count: int = 0
    status: str = "idle"
    progress: float = 0.0
    current_task: str | None = None
    model: str | None = None  # model assigned to active soldier
    last_updated: datetime = field(default_factory=datetime.utcnow)
    no_progress_counter: int = 0  # consecutive refresh cycles with zero tool call increase
    last_state_override: str | None = None  # computed state from state machine (overrides status)

    @property
    def usage_ratio(self) -> float:
        """0.0 – 1.0 fraction of budget consumed (used / budget)."""
        if self.tokens_budget == 0:
            return 0.0
        return self.tokens_used / self.tokens_budget

    @property
    def health_color(self) -> str:
        """'green' | 'yellow' | 'red' based on budget consumption."""
        r = self.usage_ratio
        if r < 0.5:
            return "green"
        elif r < 0.8:
            return "yellow"
        return "red"

    @property
    def status_color(self) -> str:
        """Rich colour name for the sandbox status badge."""
        s = self.status.lower()
        if s in ("active", "running", "working", "booting"):
            return "cyan"
        elif s == "blocked":
            return "red"
        elif s in ("spawning", "completing", "archiving"):
            return "yellow"
        elif s == "dead":
            return "grey50"
        elif s == "idle":
            return "blue"
        elif s in ("error", "failed"):
            return "red"
        return "white"


@dataclass
class ArmyMetrics:
    """Army-level aggregate metrics."""

    total_tokens_used: int = 0
    total_tokens_budget: int = 0
    total_tool_calls: int = 0
    active_subagents: int = 0
    idle_subagents: int = 0
    sandboxes: list[SandboxMetrics] = field(default_factory=list)
    previous_army: ArmyMetrics | None = None  # reference to last snapshot for delta

    @property
    def usage_ratio(self) -> float:
        """0.0 – 1.0 fraction of total army budget consumed."""
        if self.total_tokens_budget == 0:
            return 0.0
        return self.total_tokens_used / self.total_tokens_budget

    @property
    def army_health(self) -> str:
        """Overall army health: 'green' | 'yellow' | 'red'."""
        if not self.sandboxes:
            return "grey"
        red = sum(1 for s in self.sandboxes if s.health_color == "red")
        yellow = sum(1 for s in self.sandboxes if s.health_color == "yellow")
        if red > 0:
            return "red"
        if yellow > 0:
            return "yellow"
        return "green"


class MetricsCollector:
    """Collects live metrics for the viewport dashboard.

    Reads from the shared ``default_cache`` so all viewport updates reuse
    already-cached data without hitting disk again.

    Maintains per-sandbox counters across ``collect()`` calls for stuck
    detection and state-machine transitions.
    """

    def __init__(self, cache: StateCache | None = None) -> None:
        self.cache = cache or default_cache
        self._prev_tool_calls: dict[str, int] = {}  # sandbox → last seen tool_call count
        self._no_progress_counters: dict[str, int] = {}  # sandbox → consecutive zero-progress cycles


    def collect(self, sandbox_names: list[str] | None = None) -> ArmyMetrics:
        """Return a fresh ArmyMetrics snapshot.

        Parameters
        ----------
        sandbox_names:
            Explicit list of sandboxes to include.  If *None*, all
            sandboxes registered in ``INDEX.toon`` are included.
        """
        from hero.state.index import IndexState

        if sandbox_names is None:
            index = IndexState()
            entries = index.list_sandboxes()
            sandbox_names = [e.get("name", "unknown") for e in entries]

        # Always read fresh from disk (server is separate process from CLI)
        from hero.state.sandbox import SandboxState
        cache_states = {}
        for name in sandbox_names:
            try:
                ss = SandboxState(name)
                cache_states[name] = ss.load(use_cache=False)
            except Exception:
                cache_states[name] = {}
        dispatch_files = self._read_dispatch_files()
        dispatch_map = {f["sandbox"]: f for f in dispatch_files}

        sandboxes: list[SandboxMetrics] = []
        total_used = 0
        total_budget = 0
        total_calls = 0
        active = 0
        idle = 0

        for name in sandbox_names:
            state = cache_states.get(name, {})
            budget = state.get("budget", {})
            bootstrap_max = budget.get("bootstrap_max", 5000)
            tokens_remaining = budget.get("tokens_remaining", 5000)
            compactions_used = budget.get("compactions_used", 0)
            
            # Calculate tokens used: use actual usage if available
            actual_used = sum_sandbox_usage(name)
            if actual_used > 0:
                tokens_used = actual_used
            else:
                # Fallback to estimation if no actual usage recorded
                base_used = bootstrap_max - tokens_remaining
                compaction_cost = compactions_used * 2000
                tokens_used = max(0, base_used + compaction_cost)
            
            # If active, estimate from dispatch files (only if no actual usage)
            disp = dispatch_map.get(name, {})
            if disp.get("status") == "running" and actual_used == 0:
                # Rough estimate: task length / 4 chars per token + overhead
                task_len = len(disp.get("task", ""))
                tokens_used += min(task_len // 4 + 500, tokens_remaining)
            
            # For display: show minimal usage on active sandboxes so bar isn't empty
            status = state.get("status", "idle")
            if status == "active" and tokens_used == 0:
                tokens_used = min(100, int(bootstrap_max * 0.02))  # 2% or 100 tokens

            m = SandboxMetrics(
                name=name,
                tokens_used=max(0, tokens_used),
                tokens_remaining=max(0, tokens_remaining),
                tokens_budget=bootstrap_max,
                tool_calls=disp.get("tool_calls", 0),
                subagent_count=disp.get("subagent_count", 0),
                status=status,
                current_task=disp.get("task") or None,
                model=disp.get("model") or None,
                last_updated=datetime.utcnow(),
            )
            tool_calls = m.tool_calls

            # ── state machine + stuck detection ──────────────────────────────
            prev_calls = self._prev_tool_calls.get(name, 0)
            if tool_calls > prev_calls:
                self._no_progress_counters[name] = 0
            else:
                self._no_progress_counters[name] = self._no_progress_counters.get(name, 0) + 1

            self._prev_tool_calls[name] = tool_calls
            no_progress = self._no_progress_counters.get(name, 0)

            # Compute state via state machine.
            computed_state = states.compute_sandbox_state(
                state_data=state,
                prev_state=None,
                tool_call_count=tool_calls,
                no_progress_counter=no_progress,
            )

            m.no_progress_counter = no_progress
            m.last_state_override = computed_state
            if computed_state != status:
                m.status = computed_state

            # ── Pipeline-aware status override ───────────────────────────────
            # If sandbox is idle/dead but has an active pipeline manifest,
            # show as "spawning" so the dashboard reflects pending work.
            if m.status in ("dead", "idle"):
                try:
                    from hero.viewport.tree import _load_pipeline_manifest
                    manifest = _load_pipeline_manifest(name)
                    if manifest and manifest.get("status") not in ("completed", "failed"):
                        m.status = "spawning"
                except Exception:
                    pass
            # ──────────────────────────────────────────────────────────────────────

            sandboxes.append(m)

            total_used += m.tokens_used
            total_budget += m.tokens_budget
            total_calls += m.tool_calls
            if status in ("running", "active"):
                active += m.subagent_count
            else:
                idle += 1

        return ArmyMetrics(
            total_tokens_used=total_used,
            total_tokens_budget=total_budget,
            total_tool_calls=total_calls,
            active_subagents=active,
            idle_subagents=idle,
            sandboxes=sandboxes,
        )

    def _read_dispatch_files(self) -> list[dict[str, Any]]:
        """Read ``~/.hero/dispatch/*.toon`` and ``*.json``, deduplicated by task_id.

        Prefers ``.toon`` when both formats exist for the same task_id.
        """
        results: list[dict[str, Any]] = []
        if not DISPATCH_DIR.exists():
            return results
        seen: set[str] = set()
        for pattern in ("*.toon", "*.json"):
            for f in sorted(DISPATCH_DIR.glob(pattern)):
                tid = f.stem
                if tid in seen:
                    continue
                seen.add(tid)
                try:
                    if f.suffix == ".toon":
                        data = _parse_viewport_toon(f.read_text())
                    else:
                        data = json.loads(f.read_text())
                    if data:
                        results.append(data)
                except (json.JSONDecodeError, OSError):
                    pass
        return results


def _parse_viewport_toon(content: str) -> dict | None:
    """Parse a TOON dispatch entry back into a dict for viewport display."""
    import re
    result: dict[str, Any] = {}
    for line in content.strip().split("\n"):
        line = line.rstrip()
        if not line:
            continue
        m = re.match(r"^(\w+):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            elif val == "null":
                val = None
            elif val == "true":
                val = True
            elif val == "false":
                val = False
            else:
                try:
                    if "." in val:
                        val = float(val)
                    else:
                        val = int(val)
                except ValueError:
                    pass
            result[key] = val
    return result if result else None


def collect(sandbox_filter: str | None = None) -> ArmyMetrics:
    """Module-level convenience: collect metrics, optionally filtered to one sandbox.

    Parameters
    ----------
    sandbox_filter:
        When set, only the matching sandbox is included in the result.

    Returns
    -------
    ArmyMetrics
    """
    collector = MetricsCollector()
    if sandbox_filter:
        from hero.state.index import IndexState
        index = IndexState()
        entries = index.list_sandboxes()
        all_names = [e.get("name", "unknown") for e in entries]
        # Resolve partial matches (e.g. "sook" → "sook_pro")
        matching = [n for n in all_names if sandbox_filter.lower() in n.lower()]
        return collector.collect(matching if matching else [sandbox_filter])
    return collector.collect(None)
