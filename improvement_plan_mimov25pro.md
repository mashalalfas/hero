# improvement_plan_mimo_v25_pro.md

## One-sentence pitch

**A "Code Intelligence Command Center" that turns the viewport from a resource monitor into a technical lead's brain — showing complexity heatmaps, dependency risk, build health, and refactoring signals across every sandbox in the army.**

---

## Visual Paradigm: The Code Intelligence Command Center

The current viewport answers: *"What's running?"*
The tree concept answers: *"Who's doing what?"*
**This answers: *"What's the codebase's health, and where should we focus?"***

Think of a Bloomberg Terminal for code. Three panels — each a different lens on the same system.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  HERO ⚡ Code Intelligence                    T:12,450/50K  ██░░░  25%  14:32│
│  [Health] [Complexity] [Deps] [Build] [Sessions]        ← mode tabs        │
├──────────────────────┬───────────────────────────────────────────────────────┤
│                      │                                                       │
│   RISK RADAR         │   COMPLEXITY HEATMAP                                  │
│                      │                                                       │
│   ██████  src/auth   │   auth/login.py      ████████████  cc:24  ⚠ HIGH     │
│   █████   src/api    │   auth/session.py    ████████      cc:16  ⚠ HIGH     │
│   ████    src/viewport│   api/routes.py      ██████        cc:12  ● MEDIUM   │
│   ███     src/models │   viewport/renderer  ████          cc:8   ○ LOW      │
│   ██      src/utils  │   models/user.py     ███           cc:6   ○ LOW      │
│                      │   utils/cache.py     ██            cc:3   ○ LOW      │
│   ↑ change freq ×    │                                                       │
│     complexity = risk │   ■ hot  ░ cold  (files touched in last 24h)         │
│                      │                                                       │
├──────────────────────┼───────────────────────────────────────────────────────┤
│                      │                                                       │
│   DEPENDENCY GRAPH   │   SESSION TELEMETRY                                   │
│                      │                                                       │
│   auth ──► api       │   Sandbox     Model       Tokens/min  Eff%  Status   │
│    │  ╲              │   ─────────────────────────────────────────────────── │
│    ▼   ▼             │   sook_pro    deepseek    847         72%   ● active │
│  store  session      │   freya       kimi-k2.6   1,203       61%   ● active │
│    ▲                 │   qlearner    deepseek    623         85%   ○ idle   │
│    │                 │                                                       │
│   models             │   Efficiency = useful tokens / total tokens           │
│                      │   (excludes retries, compaction, error recovery)      │
│   ⚠ auth→session     │                                                       │
│     circular dep     │   ████████████ sook   avg: 72%  trend: ↑ +3%         │
│                      │   ████████░░░ freya  avg: 61%  trend: ↓ -8% ⚠       │
│                      │                                                       │
├──────────────────────┴───────────────────────────────────────────────────────┤
│  [q]uit [r]efresh [Tab] panel [↑↓] navigate [Enter] drill-down [f]ilter     │
│  [1-9] sandbox  [m] mode switch  [/] search  [c] collapse  [s] snapshot     │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Layout Philosophy

**Three-column responsive grid** that adapts to terminal width:

| Width ≥ 120 | Width 80–119 | Width < 80 |
|---|---|---|
| 3 columns | 2 columns + stacked bottom | Single column, tabbed modes |
| All panels visible | Top panels + scrollable bottom | Keyboard-driven mode switching |

---

## Key Features

### 1. Complexity Heatmap (left panel)

Visual representation of code complexity per file/module in each sandbox:

- **Cyclomatic complexity** (via `radon` or AST analysis) — how many branches, loops, conditions
- **Lines of code** — raw size indicator
- **Change frequency** — how often a file was modified in recent sessions (git log analysis)
- **Visual encoding**: bar width = complexity score, color = red/yellow/green thresholds

```
src/auth/login.py      ████████████  cc:24  ⚠ HIGH     (changed 8x in 3 days)
src/auth/session.py    ████████      cc:16  ⚠ HIGH     (changed 3x in 3 days)
src/api/routes.py      ██████        cc:12  ● MEDIUM   (changed 12x in 3 days) ← hotspot
```

**Why it matters**: Technical leads need to know *where the bodies are buried*. A file with cc:24 that's been touched 8 times in 3 days is a ticking time bomb. A file with cc:8 that hasn't been touched in a month is stable.

### 2. Risk Radar (top-left quadrant)

**Composite risk score** = `complexity × change_frequency × (1 / test_coverage)`

Ranked list of the riskiest modules across all sandboxes. This is the "what could blow up" view.

- Files are scored and ranked by composite risk
- Trend indicators (↑↓→) show if risk is increasing or decreasing
- Click/Enter to drill into a specific file's dependency tree

**Risk tiers**:
- 🔴 **CRITICAL** (score > 80): High complexity, frequently changed, low test coverage
- 🟡 **WARNING** (score 40–80): Two of three factors elevated
- 🟢 **HEALTHY** (score < 40): Well-tested, stable, or low complexity

### 3. Dependency Graph (bottom-left quadrant)

ASCII-rendered module dependency visualization:

```
auth ──► api
 │  ╲
 ▼   ▼
store  session
 ▲
 │
models

⚠ auth→session circular dependency detected
```

- **Nodes** = modules/packages
- **Edges** = import relationships (direction matters)
- **Red edges** = circular dependencies
- **Dotted edges** = weak/optional dependencies
- **Impact radius**: select a node → highlight all downstream consumers

This uses Python's `ast` module to parse imports — no external dependency required.

### 4. Build Health Matrix (right panel)

Aggregated CI/CD and test status per sandbox:

| Sandbox | Last Build | Tests | Coverage | Flaky | Build Time |
|---------|-----------|-------|----------|-------|------------|
| sook_pro | ✅ 2m ago | 47/48 | 72% | 1 | 34s |
| freya | ✅ 15m ago | 23/23 | 68% | 0 | 12s |
| qlearner | ❌ 1h ago | 19/22 | 45% | 3 | 8s ⚠ |

**Data sources**:
- Git status (uncommitted changes, branch, ahead/behind)
- Test results from last dispatch (parsed from task output)
- Build times from dispatch metadata
- Flaky test detection (tests that flip between pass/fail across runs)

### 5. Session Telemetry (bottom-right quadrant)

Live performance metrics per active sandbox:

```
Sandbox     Model       Tokens/min  Eff%  Status   Trend
─────────────────────────────────────────────────────────
sook_pro    deepseek    847         72%   ● active  ↑ +3%
freya       kimi-k2.6   1,203       61%   ● active  ↓ -8% ⚠
qlearner    deepseek    623         85%   ○ idle    ──
```

- **Tokens/min**: throughput indicator (higher = faster model/task)
- **Eff%**: useful output tokens / total tokens consumed (excludes retries, compaction overhead)
- **Trend**: rolling 5-minute average vs previous period

**Efficiency calculation**:
```python
efficiency = (tokens_in_final_output) / (total_tokens_used - compaction_tokens - retry_tokens)
```

This reveals which models are cost-effective for which task types.

### 6. Mode Tabs

The viewport becomes **multi-modal** — each tab is a different lens:

| Tab | Hotkey | Purpose |
|-----|--------|---------|
| **Health** | `1` | Default view — risk radar + build status + telemetry |
| **Complexity** | `2` | Full-screen complexity heatmap across all sandboxes |
| **Deps** | `3` | Full-screen dependency graph with interactive navigation |
| **Build** | `4` | CI/CD matrix + test history + flaky test tracker |
| **Sessions** | `5` | Detailed per-sandbox session logs + token breakdown |

---

## Data Sources

### Existing (no new dependencies)

| Source | What it provides | Where |
|--------|-----------------|-------|
| `StateCache` | Sandbox state, status, budget | `hero.state.cache` |
| Dispatch files | Task, model, tool calls, subagent count | `~/.hero/dispatch/*.toon` |
| `IndexState` | Sandbox registry | `hero.state.index` |
| Git (via `subprocess`) | Branch, uncommitted files, log | `subprocess.run(["git", ...])` |
| Python `ast` module | Import graph for dependency analysis | stdlib |

### New integrations (lightweight)

| Source | What it provides | How |
|--------|-----------------|-----|
| `radon` (optional) | Cyclomatic complexity | `pip install radon` — single dep, no daemon |
| `git log --since` | Change frequency per file | stdlib subprocess, no install |
| Dispatch output parsing | Test pass/fail counts, build times | Regex on task completion output |
| Token accounting | Efficiency metrics | Extend `MetricsCollector` with output token tracking |

### No external services required

Everything runs locally. No API calls, no network dependencies. Git and Python AST are already available. `radon` is the only new package, and it's a single `pip install` with zero configuration.

---

## Interaction Map

### Navigation

| Key | Context | Action |
|-----|---------|--------|
| `q` | Global | Quit viewport |
| `r` | Global | Force refresh |
| `Tab` | Global | Cycle through mode tabs (Health → Complexity → Deps → Build → Sessions) |
| `Shift+Tab` | Global | Reverse tab cycle |
| `↑↓` | Any panel | Navigate items within focused panel |
| `Enter` | On item | Drill-down: expand detail view for selected item |
| `Escape` | Drill-down | Return to overview |
| `1-9` | Global | Focus sandbox by number |
| `/` | Global | Search/filter — type to filter files, sandboxes, or modules |
| `f` | Panel | Toggle filter for current panel (e.g., show only HIGH risk) |
| `c` | Graph | Collapse/expand node in dependency graph |
| `s` | Global | Save snapshot to `~/.hero/viewport/snapshot-{timestamp}.txt` |
| `m` | Global | Quick mode switch (type mode number after `m`) |

### Drill-down behavior

**Enter on a risk item** → shows:
- Full file path
- Complexity breakdown (per-function cc scores)
- Dependency tree (what it imports, what imports it)
- Recent change history (git log --oneline -10)
- Test coverage for this specific file (if available)

**Enter on a sandbox** → shows:
- Full session timeline (dispatches, completions, errors)
- Token breakdown by phase (bootstrap, execution, compaction)
- Model performance comparison for this sandbox
- Error log with timestamps

### Filters

| Filter | Syntax | Example |
|--------|--------|---------|
| Risk level | `risk:high` | Show only high-risk files |
| Sandbox | `sb:sook` | Show only sook_pro sandbox |
| Status | `status:active` | Show only active sandboxes |
| Model | `model:deepseek` | Show only deepseek-powered sessions |
| Time | `since:2h` | Show only changes in last 2 hours |

---

## Why This Fits the Architect Model

### The Architect thinks in systems

The tree concept is about *process flow* — who does what, in what order. That's the Lead's perspective.

The Architect's perspective is different: **What's the structural health of the system we're building?**

- Which files are becoming unmaintainable?
- Where are the circular dependencies that will bite us later?
- Which sandbox is burning tokens inefficiently?
- What's the real cost-per-feature across different models?

### Code intelligence > process visualization

The current viewport is a resource monitor (tokens, tools, status). The tree is a process monitor (workflow, roles, handoffs). **This is a code intelligence platform** — it answers questions that only matter to someone who thinks about the *system*:

1. **"Is this codebase getting healthier or sicker?"** → Complexity trend over time
2. **"What should I refactor first?"** → Risk radar ranking
3. **"Which model is most cost-effective for this task type?"** → Session telemetry efficiency
4. **"Where are the architectural violations?"** → Dependency graph with circular dep detection

### Implementation path is clean

The current architecture already separates concerns well:
- `metrics.py` handles data collection
- `renderer.py` handles presentation
- `viewport.py` handles CLI entry

My plan extends each layer without breaking anything:
- `metrics.py` → add `ComplexityCollector`, `DependencyCollector`, `BuildHealthCollector`
- `renderer.py` → add mode tabs, panel layouts, interactive navigation
- `viewport.py` → add `--mode` flag for default tab selection

### No new external dependencies (except optional `radon`)

Everything else uses Python stdlib (`ast`, `subprocess`, `json`) and existing HERO infrastructure (`StateCache`, `IndexState`, dispatch files).

---

## Quick Start (if implemented)

### Phase 1: Foundation (Day 1–2)

```bash
# 1. Add complexity collection (optional radon, fallback to AST)
pip install radon  # optional — AST fallback works without it

# 2. Extend MetricsCollector
# hero/viewport/metrics.py
# + ComplexityMetrics: per-file cc scores, LOC
# + ChangeFrequency: git log --name-only --since="3 days ago"
# + RiskScore: complexity × frequency × (1/coverage)

# 3. Add mode tab system to renderer
# hero/viewport/renderer.py
# + TabState enum: HEALTH, COMPLEXITY, DEPS, BUILD, SESSIONS
# + build_layout() → dispatch to mode-specific layout builders
```

### Phase 2: Panels (Day 3–4)

```bash
# 4. Complexity heatmap panel
# + File → (cc, LOC, change_count) mapping
# + Sorted by risk score, color-coded bars
# + Enter → per-file drill-down with function-level breakdown

# 5. Dependency graph panel
# + ast.parse() imports from each .py file
# + Build directed graph (module → imported modules)
# + Detect cycles (DFS-based)
# + ASCII render with box-drawing characters

# 6. Build health matrix
# + Parse test results from dispatch output
# + Track flaky tests across runs
# + Aggregate per-sandbox build metrics
```

### Phase 3: Interaction (Day 5–6)

```bash
# 7. Tab navigation (Tab/Shift+Tab)
# 8. Drill-down with Enter/Escape
# 9. Search/filter with /
# 10. Snapshot export with s
```

### Phase 4: Polish (Day 7)

```bash
# 11. Responsive layout (3-col → 2-col → 1-col)
# 12. Trend indicators (↑↓→) for all metrics
# 13. Session telemetry efficiency calculation
# 14. Keyboard shortcut hints in footer
```

### Configuration

```toml
# hero.toml
[viewport]
default_mode = "health"        # health | complexity | deps | build | sessions
refresh_interval = 2.0         # seconds
complexity_threshold = 15      # cc score that triggers HIGH warning
risk_lookback_days = 3         # how far back to analyze change frequency
enable_radon = true            # use radon if installed, fallback to AST
```

---

## Architecture: New Module Structure

```
hero/viewport/
├── __init__.py
├── metrics.py              # existing — extend with new collectors
├── renderer.py             # existing — extend with mode system
├── complexity.py           # NEW — cyclomatic complexity analysis
├── dependencies.py         # NEW — AST-based import graph
├── build_health.py         # NEW — CI/test status aggregation
├── telemetry.py            # NEW — session efficiency metrics
├── panels/                 # NEW — panel renderers
│   ├── __init__.py
│   ├── risk_radar.py       # risk-ranked file list
│   ├── heatmap.py          # complexity heatmap
│   ├── dep_graph.py        # dependency visualization
│   ├── build_matrix.py     # build/test status table
│   └── session_table.py    # telemetry table
└── navigation.py           # NEW — tab system, drill-down, search
```

### Data flow

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│  Data Layer  │────▶│  Processing  │────▶│  Presentation │
│              │     │              │     │               │
│ StateCache   │     │ Complexity   │     │ Layout        │
│ Dispatch     │     │ Risk Score   │     │ Panels        │
│ Git          │     │ Dep Graph    │     │ Navigation    │
│ AST          │     │ Telemetry    │     │ Drill-down    │
│ radon (opt)  │     │              │     │               │
└─────────────┘     └──────────────┘     └───────────────┘
       │                    │                    │
       ▼                    ▼                    ▼
  metrics.py          complexity.py         renderer.py
                      dependencies.py       panels/
                      build_health.py       navigation.py
                      telemetry.py
```

### Extension points

The existing `MetricsCollector.collect()` returns `ArmyMetrics`. I'd extend this pattern:

```python
# Existing
class MetricsCollector:
    def collect(self) -> ArmyMetrics: ...

# New collectors (same pattern)
class ComplexityCollector:
    def collect(self, sandbox_names: list[str]) -> ComplexityReport: ...

class DependencyCollector:
    def collect(self, sandbox_names: list[str]) -> DependencyGraph: ...

class BuildHealthCollector:
    def collect(self, sandbox_names: list[str]) -> BuildHealthReport: ...

class TelemetryCollector:
    def collect(self, sandbox_names: list[str]) -> TelemetryReport: ...
```

Each collector is independent, cacheable, and can be run on-demand or on-refresh. The renderer composes them into the final layout based on the active mode tab.

---

## Summary

| Aspect | Current v1 | Tree Concept | Code Intelligence (this plan) |
|--------|-----------|-------------|-------------------------------|
| **Primary question** | What's running? | Who's doing what? | Is the code healthy? |
| **Visual paradigm** | Flat table | Org chart / tree | Multi-panel dashboard |
| **Data focus** | Tokens, status | Roles, workflow | Complexity, risk, deps |
| **Target user** | Operator | Manager | Technical lead |
| **Interaction** | Filter by sandbox | Navigate tree | Mode tabs + drill-down |
| **Unique value** | Resource monitoring | Process visibility | Code intelligence |

These three concepts are **complementary**, not competing. The best viewport would combine all three as mode tabs:

1. **Status** (current v1) — quick resource check
2. **Workflow** (tree) — process visibility
3. **Intelligence** (this plan) — code health and architectural insight

---

*Plan by mimo-v25-pro (Architect) — Code Intelligence Command Center*
