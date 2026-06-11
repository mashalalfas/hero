# HERO Viewport + Token Efficiency — Implementation Spec

## Overview
Make HERO CLI exceptional: add a live viewport/dashboard showing token usage, tool calls, active subagents, and context budget. Reduce token burn via caching and lazy loading.

## Architecture

```
┌─────────────────────────────────────────────┐
│  HERO CLI Commands                          │
│  (status, spawn, go, tell, etc.)            │
└──────────────┬──────────────────────────────┘
               │ uses
┌──────────────▼──────────────────────────────┐
│  Cache Layer (hero.state.cache)             │
│  - LRU in-memory cache for sandbox states   │
│  - TTL-based invalidation (30s default)     │
│  - Batch read for multi-sandbox ops         │
└──────────────┬──────────────────────────────┘
               │ feeds
┌──────────────▼──────────────────────────────┐
│  Metrics Collector (hero.viewport.metrics)  │
│  - Token counter (estimates from TOON)      │
│  - Tool call interceptor                    │
│  - Subagent tracker (reads dispatch dir)    │
└──────────────┬──────────────────────────────┘
               │ renders
┌──────────────▼──────────────────────────────┐
│  Viewport Dashboard (hero.viewport.renderer)│
│  - Rich-based TUI                           │
│  - Live refresh (2s interval)               │
│  - Color-coded health indicators            │
└─────────────────────────────────────────────┘
```

---

## Module 1: Cache Layer (hero/state/cache.py)

**Purpose:** Eliminate redundant disk reads.

**API:**
```python
class StateCache:
    """LRU cache for sandbox state files."""
    
    def get(self, sandbox_name: str) -> dict | None:
        """Get cached state. Returns None if expired/missing."""
        
    def set(self, sandbox_name: str, state: dict, ttl_seconds: int = 30) -> None:
        """Cache state with TTL."""
        
    def invalidate(self, sandbox_name: str | None = None) -> None:
        """Invalidate one or all cached entries."""
        
    def batch_load(self, sandbox_names: list[str]) -> dict[str, dict]:
        """Load multiple sandboxes, using cache where valid."""
```

**Rules:**
- Cache hits: skip disk I/O entirely
- Cache misses: read from disk, store in cache
- Auto-invalidate on spawn/complete (mutations)
- Default TTL: 30 seconds

---

## Module 2: Metrics Collector (hero/viewport/metrics.py)

**Purpose:** Track token usage, tool calls, subagent state in real-time.

**Data Model:**
```python
@dataclass
class SandboxMetrics:
    name: str
    tokens_used: int           # estimated from task prompts
    tokens_remaining: int      # from budget state
    tool_calls: int            # intercepted count
    subagent_count: int        # active soldiers
    status: str                # idle | active | error
    progress: float            # 0.0 - 1.0 if known
    current_task: str | None   # what it's working on
    last_updated: datetime

@dataclass
class ArmyMetrics:
    total_tokens_used: int
    total_tokens_budget: int
    total_tool_calls: int
    active_subagents: int
    idle_subagents: int
    sandboxes: list[SandboxMetrics]
```

**Collection Strategy:**
1. **Tokens:** Estimate from dispatch queue file sizes + prompt templates
2. **Tool calls:** Count `*.json` files in dispatch dir (each = potential tool use)
3. **Subagents:** Read `~/.hero/dispatch/*.json` — count `status == "running"`
4. **Refresh:** Poll every 2 seconds, update in-memory metrics store

---

## Module 3: Viewport Renderer (hero/viewport/renderer.py)

**Purpose:** Draw the TUI dashboard.

**Layout:**
```
┌─ HERO ⚡ Viewport ─────────────────────────┐
│ Tokens:  12.4K/50K  ████████░░░░  25%     │
│ Tools:   8 calls    |  Agents: 3 active   │
│──────────────────────────────────────────│
│ Sandbox      Status  Tokens   Task        │
│ qlearner     active  ████░░░  audio-fix   │
│ sook_pro     idle    ░░░░░░░  —           │
│ fury-os      active  ██████░  theme       │
└──────────────────────────────────────────┘
```

**Features:**
- Color coding: green (<50%), yellow (50-80%), red (>80%)
- Progress bars using `rich.progress`
- Auto-refresh every 2s
- Keyboard: `q` quit, `r` manual refresh

**Dependencies:** `rich` (add to pyproject.toml)

---

## Module 4: Dashboard Command (hero/commands/viewport.py)

**New CLI command:**
```bash
hero viewport              # Full-screen live dashboard
hero viewport --once       # Single snapshot, exit
hero viewport --sandbox X  # Focus on one sandbox
```

---

## Module 5: Integration Points

**Update existing commands to use cache:**

1. `hero status` → Use `StateCache.batch_load()` instead of looped `SandboxState.load()`
2. `hero spawn` → Invalidate cache for target sandbox after spawn
3. `hero go` → Show viewport overlay if `--viewport` flag

---

## Token Efficiency Rules

1. **Batch reads:** One `os.listdir()` + selective file reads, not N individual reads
2. **Lazy evaluation:** Don't read katana state unless `--verbose`
3. **Memoize analysis:** Cache `flutter analyze` results for 60s
4. **TOON streaming:** Where possible, stream TOON without full JSON materialization

---

## Acceptance Criteria

- [ ] `hero status` runs in <100ms (currently ~500ms)
- [ ] `hero viewport` shows live dashboard with accurate metrics
- [ ] `hero spawn` invalidates cache automatically
- [ ] Dashboard shows: tokens used/budget, tool calls, active agents, sandbox status
- [ ] Color-coded health indicators work
- [ ] Auto-refresh every 2 seconds
- [ ] No redundant disk reads on repeated commands

---

## Files to Create/Modify

**New files:**
- `src/hero/state/cache.py`
- `src/hero/viewport/__init__.py`
- `src/hero/viewport/metrics.py`
- `src/hero/viewport/renderer.py`
- `src/hero/viewport/collector.py`
- `src/hero/commands/viewport.py`

**Modified files:**
- `src/hero/state/sandbox.py` — integrate cache
- `src/hero/commands/status.py` — use batch_load
- `src/hero/commands/spawn.py` — invalidate cache
- `src/hero/commands/go.py` — add --viewport flag
- `src/hero/cli.py` — register viewport command
- `pyproject.toml` — add `rich` dependency
