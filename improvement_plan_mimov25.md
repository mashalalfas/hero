# Improvement Plan — mimo-v2.5 (Lead Model)

## One-sentence pitch

A **Command Center** viewport that surfaces system-level intelligence — cross-sandbox bottlenecks, resource conflicts, escalation paths, and pipeline health — so the Lead can orchestrate the entire army from one screen instead of clicking through individual sandboxes.

---

## Visual Paradigm: The Situation Room

The Lead doesn't care about individual soldier tasks. The Lead cares about **what's broken across the whole army, where resources are flowing, and what needs attention NOW.** The viewport restructures from a flat sandbox table into a **three-zone situation room**:

```
┌─────────────────────────────────────────────────────────────────────┐
│  HERO COMMAND CENTER                    ●3 active ○7 idle  14:23:07│
│  ████████████░░░░░░░░ 62% tokens │ ⚠2 bottlenecks │ ⚠1 escalation │
├──────────────────┬────────────────────┬──────────────────────────────┤
│                  │                    │                              │
│  INTELLIGENCE    │  RESOURCE MAP      │  ACTION QUEUE                │
│  (what's wrong)  │  (where things are)│  (what needs you)            │
│                  │                    │                              │
│  ⚠ sook_pro     │  deepseek-v4  ██░ │  🔴 sook_pro → timeout       │
│    token choke   │  kimi-k2.6   ███  │     Escalate? [y/n/...]      │
│  ⚠ freya        │  mimo-v2.5   █    │  🟡 qlearner → model swap    │
│    model stall   │  claude-3.5  ░    │     Suggested: deepseek-v4   │
│  ✗ her           │                    │  🔵 freya → waiting on       │
│    dispatch err  │  Budget Heatmap:   │     sook_pro (dep chain)     │
│                  │  sook  ████░ 80%   │                              │
│  Pipeline Flow:  │  freya ██░░░ 45%   │  Pending escalations: 0      │
│  sook → verify   │  her   █░░░░ 20%  │  Resolved (last 1h): 3       │
│  freya → soldier │  qlearn░░░░░  5%   │                              │
│  her  → error!   │                    │                              │
│                  │                    │                              │
├──────────────────┴────────────────────┴──────────────────────────────┤
│  [↑↓] select  [Enter] act  [Tab] zone  [f] filter  [h] history  [q]│
└─────────────────────────────────────────────────────────────────────┘
```

**Three zones, each answering a question the Lead asks:**

| Zone | Question | Data |
|------|----------|------|
| **Intelligence** | "What's wrong right now?" | Active bottlenecks, failed sandboxes, stalled pipelines, error cascades |
| **Resource Map** | "Where is everything going?" | Token allocation across sandboxes per model, budget heatmap, cost projections |
| **Action Queue** | "What do I need to decide?" | Pending escalations, suggested model swaps, dependency blocks, retry decisions |

---

## Key Features

### 1. Cross-Sandbox Bottleneck Detection
The current viewport shows each sandbox in isolation. The Lead sees the **army as a system**:

- **Token choke detection**: When one sandbox consumes >60% of remaining army budget, flag it as a bottleneck threatening other sandboxes
- **Model contention**: If 3+ sandboxes want the same model and there's rate-limiting, surface it as a resource conflict
- **Pipeline stall detection**: Sandbox has been "active" for >5 minutes with no token movement → likely stuck

```
⚠ BOTTLENECK: sook_pro consuming 80% of remaining budget
  → Other sandboxes starved: freya (12%), her (8%)
  → Suggestion: cap sook_pro at 50% or pause
```

### 2. Escalation Path Visualization
When a soldier fails, the Lead needs to know the **full escalation chain** at a glance:

```
her/fix-auth:
  soldier_1 ✗ (timeout) → retry_1 ✗ (model error) → retry_2 ◌ (pending)
  Escalation: ARCH notified, LEAD decision needed
  → [A]uto-retry  [M]anual fix  [S]kip task  [K]ill sandbox
```

### 3. Resource Allocation Heatmap
A compact visual showing where tokens are flowing across the army:

```
Model allocation:      Budget consumption:
  deepseek-v4  ██████    sook_pro  ████████░░ 80% ⚠
  kimi-k2.6    ████░░    freya     ████░░░░░░ 45%
  mimo-v2.5    ██░░░░    her       ██░░░░░░░░ 20% ✓
  claude-3.5   ░░░░░░    qlearner  █░░░░░░░░░  5% ✓
```

### 4. Dependency Chain Awareness
Sandboxes can depend on each other (e.g., freya waits for sook_pro's output). Surface these as a **waiting graph**:

```
DEPENDENCY GRAPH:
  freya ──waiting on──► sook_pro (step 3/5)
  her   ──blocked by───► sook_pro (token choke)
  qlearner ──independent──► executing
```

### 5. Cost Projection & Budget Warnings
Predict when sandboxes will hit their budget limits:

```
BUDGET PROJECTION (next 30 min):
  sook_pro:  ████████████████████░ → exhausted in ~12 min ⚠
  freya:     ████████░░░░░░░░░░░░ → exhausted in ~45 min
  her:       ███░░░░░░░░░░░░░░░░░ → exhausted in ~2 hours
  qlearner:  █░░░░░░░░░░░░░░░░░░░ → plenty of headroom
```

### 6. Quick Actions Panel
The Lead's job is to **decide, not observe**. The action queue surfaces decisions:

| Priority | Action | Context |
|----------|--------|---------|
| 🔴 | Auto-retry soldier_2 on sook_pro? | Timeout 3x, model: kimi-k2.6 |
| 🟡 | Swap qlearner model to deepseek-v4? | Current model stalling |
| 🔵 | Resume her sandbox? | Previous dispatch errored |
| ⚪ | Archive freya task? | Completed 2h ago, no new work |

---

## Data Sources

| Source | What it provides | Current? |
|--------|-----------------|----------|
| `hero.state.cache` | Sandbox status, budget, tokens | ✅ Yes |
| `~/.hero/dispatch/` | Active tasks, models, tool calls | ✅ Yes |
| **Git status** (new) | Uncommitted changes per sandbox, branch state | ❌ New |
| **Dispatch history** (new) | Past task outcomes, retry counts, failure patterns | ❌ New |
| **Model cost registry** (new) | Per-model token pricing for cost projections | ❌ New |
| **Dependency graph** (new) | Inter-sandbox task dependencies | ❌ New |
| **Escalation log** (new) | Record of escalation decisions and outcomes | ❌ New |

### New MetricsCollector fields

```python
@dataclass
class SandboxMetrics:
    # ... existing fields ...
    
    # NEW fields for Lead intelligence
    git_dirty: bool = False          # uncommitted changes?
    git_branch: str = ""             # current branch
    retry_count: int = 0             # retries on current task
    failure_count: int = 0           # total failures this session
    escalation_pending: bool = False  # awaiting Lead decision?
    blocked_by: str | None = None    # sandbox name blocking this one
    cost_usd: float = 0.0            # estimated cost at model rates
    eta_budget_exhausted: float | None = None  # minutes until budget gone
```

---

## Interaction Map

### Zone Navigation

| Key | Action |
|-----|--------|
| `Tab` | Cycle focus: Intelligence → Resources → Actions |
| `↑↓` | Move selection within focused zone |
| `Enter` | Act on selected item (open detail / confirm action) |
| `Esc` | Back to zone overview |

### Actions

| Key | Action |
|-----|--------|
| `a` | Auto-retry selected failed soldier (with model suggestion) |
| `m` | Manual model swap — pick from available models |
| `k` | Kill selected sandbox |
| `p` | Pause sandbox (preserve state, stop spending) |
| `r` | Force refresh |
| `f` | Filter — show only: errors / bottlenecks / completed / all |
| `h` | History — show last 10 decisions + outcomes |
| `/` | Search — find sandbox by name or task keyword |
| `q` | Quit |

### Detail Drill-Down

Pressing `Enter` on any item expands it into a detail panel:

```
┌─── BOTTLENECK DETAIL ─────────────────────────────┐
│  sook_pro — Token Choke                            │
│                                                    │
│  Budget: 4000/5000 used (80%)                      │
│  Rate:   450 tokens/min (high)                     │
│  ETA:    ~12 min until exhausted                   │
│                                                    │
│  Current task: "Fix theme switcher"                 │
│  Model: deepseek-v4                                 │
│  Retries: 0                                         │
│                                                    │
│  Impact on army:                                    │
│    freya — waiting, will stall in ~8 min            │
│    her   — independent, no impact                   │
│                                                    │
│  [C]ap budget  [P]ause  [S]wap model  [Esc] close  │
└─────────────────────────────────────────────────────┘
```

---

## Why This Fits mimo-v2.5

I'm the **Lead** — the orchestrator. I don't execute individual tasks; I **see the whole board** and decide where resources go, when to escalate, and what to prioritize.

The current viewport is a **soldier's view** — "how am I doing?" The Lead needs the **commander's view** — "how is the army doing, and what do I need to decide?"

The situation room paradigm works because:

1. **Intelligence first** — problems before details. A Lead scanning the viewport should see "3 things need attention" in under 2 seconds.
2. **Resource awareness** — the Lead manages budgets across sandboxes. The heatmap makes waste visible.
3. **Decision-oriented** — the action queue turns passive monitoring into active orchestration. The Lead isn't watching a dashboard; they're running a war room.
4. **Cross-sandbox intelligence** — dependency chains, model contention, and bottleneck detection are things only the Lead can see because only the Lead has the full army state.

This isn't a prettier table. It's a fundamentally different **information architecture** — from "reporting" to "command."

---

## Quick Start (if implemented)

### Phase 1: Core Intelligence (2-3 hours)
1. Add `git_dirty`, `retry_count`, `failure_count` to `SandboxMetrics`
2. Implement bottleneck detection: flag sandboxes >60% of remaining army budget
3. Add escalation queue: parse dispatch history for failed→retry→pending chains
4. Restructure `build_layout()` from single table to three-zone layout

### Phase 2: Resource Map (1-2 hours)
1. Add model cost registry (hardcode known model prices)
2. Implement `cost_usd` calculation in `MetricsCollector`
3. Add budget projection: linear extrapolation from current burn rate
4. Build the resource heatmap panel

### Phase 3: Actions & Dependencies (2-3 hours)
1. Add dependency graph parsing (check dispatch files for `blocked_by` fields)
2. Implement quick-action keyboard handlers (`a`, `m`, `k`, `p`)
3. Add confirmation prompts for destructive actions
4. Build history panel from dispatch log

### Phase 4: Polish (1 hour)
1. Drill-down detail panels
2. Filter mode (`f` key)
3. Search (`/` key)
4. Compact mode for narrow terminals

**Total estimate: 6-9 hours**
