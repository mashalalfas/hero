# VIEWPORT IMPROVE PLAN — DS4

> Elevating `hero viewport` from a live TUI dashboard into a **full tactical operations console** for the HERO army.

---

## Build Progress Summary

| Phase | What | Status | Lines Added |
|-------|------|--------|-------------|
| 1 | Foundation — state machine, stuck detection, delta, compaction | ✅ Complete | ~500 |
| 2 | Army Tree viewport (`--mode tree`) with command hierarchy | ✅ Complete | ~870 |
| 3a | Intelligence Zone — cross-sandbox bottleneck detection | ✅ Complete | ~400 |
| 3b | Budget Projections + Action Queue | ✅ Complete | (included in 3a) |
| 3c | Drill-down detail panel | 🔲 Pending | — |
| 3d | Escalation paths + model contention | 🔲 Pending | — |
| 4 | Health ring + goal layer + polish | 🔲 Pending | — |
| 5 | Polish & integration | 🔲 Pending | — |

Files built: 2,406 lines across 9 new/modified files

---

## Current State (v2 — Tree Mode)

```
╭─ HERO⚡ T:79,700/180,000 █████████░░░░ 44% | Tools:0 ●0 ○6 | 07:50 ─╮
╰────────────────────────────────────────────────────────────────────────╯
╭─ Intelligence Zone ────────────────────────────────────────────────────╮
│ Intelligence Zone — all clear                                          │
├─ Budget Projections ───────────────────────────────────────────────────┤
│ Sandbox      Used/Budget      %   Burn/min   ETA      Status          │
│ HERO         100/5,000       2%          1   5880m   healthy          │
│ Freya        8,200/50,000   16%         68    612m   healthy          │
│ qlearner     55,000/50,000 110%        458      —    critical ⚠      │
│ sook_pro     16,400/50,000  33%        137    246m   healthy          │
├─ Action Queue ─────────────────────────────────────────────────────────┤
│ 🔴 qlearner: 110% budget used — cap at 35k or swap model              │
╰────────────────────────────────────────────────────────────────────────╯
╭─ galaxy_oblivion (pipeline) ───────────────────────────────────────────╮
│ ● COMM → ✓ LEAD → ◌ ARCH → SOLDIERS → VERIFY → ARCHIVIST → COMM      │
╰────────────────────────────────────────────────────────────────────────╯
╭─ idle sandboxes ───────────────────────────────────────────────────────╮
│○ DocPalace  dead    ○ Freya  dead    ● HERO  working                   │
│○ SOOK  dead        ○ fury-os  dead                                    │
╰────────────────────────────────────────────────────────────────────────╯
```

**What now exists** (2 modes):
- `hero viewport` — original dashboard mode (Phase 1 enhanced with state machine)
- `hero viewport --mode tree` — Army Tree with Intel + Budget + Action panels

**Dashboard mode** still shows:
- Army-level header (tokens, tools, subagent counts, timestamp)
- Sandbox table with new 7-state statuses (WORKING, BLOCKED, DEAD, etc.)
- Delta banner showing changes since last view
- State machine: SPAWNING→BOOTING→WORKING→BLOCKED→COMPLETING→ARCHIVING→DEAD

**Tree mode** shows:
- Same army-level header
- Intelligence Zone (bottleneck detection: token choke, pipeline stall, error cascade)
- Budget Projections (burn rate, ETA, status per sandbox)
- Action Queue (prioritized suggestions with 🔴🟡🔵)
- Command hierarchy tree (COMM→LEAD→ARCH→SOLDIERS→VERIFY→ARCHIVIST→COMM)
- Collapsed idle sandboxes as compact single-line panels

---

## DS4 Vision: Tactical Operations Console

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  HERO⚡  ▓▓▓▓▓▓▓▓░░░ 44%   Tools:42  DLQ:3  CB:⚡1  ●3 ○7  Pipelines: 1   │
│  Budget: 79.7k/180k    Burn: 1.2k/min   ETA: 83min    ⏱ 03:13:36          │
├──────┬─────────────────┬───────────────────────────────────────────────────┤
│FOCUS │  Sandboxes      │  Live Events/Log                                 │
│      ├─────────────────┤───────────────────────────────────────────────────┤
│      │  Name     Tks   │  07:14:23  [sook_pro] 🛠 tool_call: search(...)  │
│      │  HERO     ▓▓░2% │  07:14:20  [sook_pro] 📝 task: fix theme        │
│      │  Freya    ▓░░16%│  07:13:55  [qlearner] ✅ dispatch complete       │
│      │  sook_pro ▓▓30% │  07:13:12  [HERO]    ⚠ circuit open (3 fails)   │
│      │  qlearner ▓▓▓90%│  07:12:44  [fury-os] ◌ dispatch enqueued        │
│      │  ...            │  07:12:01  [DLQ]     ✗ task_abc124 -> retry     │
│      ├─────────────────┴───────────────────────────────────────────────────┤
│      │  Mini sparklines (last 60s)                                        │
│      │  Tokens: ▁▂▃▄▅▆▇██▇▆▅▄▃▂▁   Active: ▁▁▁▁▃▆█▇▅▃▁▁▁▁▁             │
├──────┴─────────────────────────────────────────────────────────────────────┤
│  [q]quit [r]refresh [/]search [↑↓]navigate [Enter]drill [t]toggle panels  │
│  [e]export [a]alerts [Tab]focus [s]ort  🔴 2 alerts active                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## DS4 Improvement Tiers

### TIER 1 — Info-Rich Header (Foundation)

| # | Feature | Why |
|---|---------|-----|
| 1.1 | **Burn rate** — tokens/min computed over last N samples | Know how fast you're spending |
| 2.1 | **Time-to-empty** — ETA based on burn rate + remaining | Budget planning |
| 3.1 | **DLQ badge** — dead letter queue count in header | Surface failures immediately |
| 4.1 | **Circuit Breaker badge** — ⚡ + count of open circuits | Surface reliability issues |
| 5.1 | **Pipeline badge** — count of running pipelines | Know what's in flight |
| 6.1 | **Alert counter** — 🔴 N alerts active (from threshold engine) | Proactive awareness |

**Implementation:** Extend `ArmyMetrics` dataclass with `burn_rate`, `eta_minutes`, `dlq_count`, `circuit_open_count`, `pipeline_count`, `active_alerts`. Collect from dispatch/state/alert stores.

---

### TIER 2 — Log Panel (Real-time Awareness)

| # | Feature | Why |
|---|---------|-----|
| 2.1 | **Scrolling event log** — right/bottom panel with recent events | See what soldiers are doing *now* |
| 2.2 | **Event sources:** tool_calls, dispatches, completions, errors, circuit events | Full visibility |
| 2.3 | **Color-coded log lines:** 🛠 tool, 📝 task, ✅ complete, ⚠ warn, ✗ error | Scan by eye |
| 2.4 | **Buffered rolling log** (last 50-200 events in memory, tail from `hero.jsonl`) | No disk thrash |
| 2.5 | **Auto-scroll** with pause-on-interact | Follow latest or review history |

**Implementation:** New `LogBuffer` class (in-memory ring buffer + file tail). New `_render_log_panel()` in renderer. Split layout into sandboxes-left / log-right (60/40 split). Log events published by soldier spawn/complete/error hooks.

---

### TIER 3 — Sparklines & History (Trends)

| # | Feature | Why |
|---|---------|-----|
| 3.1 | **Token consumption sparkline** — last 60s at 2s intervals | See spikes/drops |
| 3.2 | **Active soldier sparkline** — parallel count over time | See concurrency changes |
| 3.3 | **History ring buffer** (30 samples in memory) | Lightweight, no disk writes |
| 3.4 | **Toggle sparklines** with `[g]` key | Users who want compact view |
| 3.5 | **Per-sandbox mini sparkline** in table row | See individual trends |

**Implementation:** New `HistoryBuffer` class (deque of `(timestamp, tokens_used, active_count)` snapshots). `SparklineRenderer` converts to unicode sparkline chars (`▁▂▃▄▅▆▇█`). Store in `ArmyMetrics.history`.

---

### TIER 4 — Drill-Down & Detail Panel

| # | Feature | Why |
|---|---------|-----|
| 4.1 | **Select sandbox** → detail panel replaces log | Focus mode with depth |
| 4.2 | **Details shown:** exact budget breakdown, compaction count, last task, recent errors, git status, build status, dispatch history | Operational context |
| 4.3 | **Task description** from dispatch files | Know exactly what's running |
| 4.4 | **Katana priorities** for selected sandbox | See known issues context |
| 4.5 | **`Enter`** to drill in, `ESC` or `Backspace` to go back | Natural navigation |
| 4.6 | **Arrow keys** (↑↓) to navigate sandbox list | Keyboard-driven UX |

**Implementation:** Add `focused_sandbox: str | None` to render state. When focused, switch log panel to detail panel calling `_render_detail_panel(sb_name)`. Use `StateCache` to pull full sandbox state, plus read KATANA/HEARTBEAT files.

---

### TIER 5 — Search & Filter

| # | Feature | Why |
|---|---------|-----|
| 5.1 | **`/` to search** — typeahead filter on sandbox name | Find sandboxes fast in large armies |
| 5.2 | **Filter bar** appears at bottom when `/` is pressed | Clean UX |
| 5.3 | **Live filtering** as you type | Instant results |
| 5.4 | **`ESC` to clear** filter | Quick exit |
| 5.5 | **Column sort** with `[s]` — cycle sort by name, tokens, tools, status | Reorder how you want |

**Implementation:** Add `search_query: str` to render state. On `/` key, enter raw input mode (echo characters). Filter sandbox list in `build_layout`. Sort with `_sort_key` toggle.

---

### TIER 6 — Export & Snapshot

| # | Feature | Why |
|---|---------|-----|
| 6.1 | **`[e]` to export** — dump current state to JSON/TOON file | Share, diff, archive |
| 6.2 | **Auto-named files:** `viewport_2026-05-25_0713.toon` | Chronological archive |
| 6.3 | **Export location:** `~/.hero/viewport/snapshots/` | Organized |
| 6.4 | **`--export` flag** for non-interactive capture | Scriptable, CI use |
| 6.5 | **`--watch --interval 10 --export`** headless periodic snapshot | Monitoring pipeline |

**Implementation:** New `export_state()` function. `_dump_metrics_to_toon(army)`. CLI flags: `--export`, `--watch`, `--interval`. File rotation or date-stamped naming.

---

### TIER 7 — Adaptive Layout & Themes

| # | Feature | Why |
|---|---------|-----|
| 7.1 | **Terminal-width responsive** — wider term gets log panel, narrow term gets compact mode | Works on any screen |
| 7.2 | **`[t]` to toggle panels** — cycle layouts: full / no-log / no-sparklines | User preference |
| 7.3 | **Color themes** — dark (default), light, mono (colorblind-friendly) | Accessibility |
| 7.4 | **`--theme` flag** and `[c]` to cycle | Choose on the fly |
| 7.5 | **Theme config** in `~/.hero/viewport/config.yaml` | Persist preference |

**Implementation:** `ViewportConfig` dataclass, `load_config()` from yaml. `Theme` dataclass with color palette. Each `_render_*` function takes `theme`. Width detection via `shutil.get_terminal_size()`.

---

### TIER 8 — Mouse Support

| # | Feature | Why |
|---|---------|-----|
| 8.1 | **Click sandbox row** → focus/drill | Feels native |
| 8.2 | **Scroll log panel** with mouse wheel | Natural navigation |
| 8.3 | **Click header labels** → sort by column | No keyboard needed |
| 8.4 | **Rich mouse support** enabled via `Console(mouse=True)` | Built into Rich, just activate |

**Implementation:** Rich supports mouse capture with `Live` + `Console(mouse=True)`. Parse `MouseEvent` from input stream. Map click coordinates to table rows. Fall back gracefully if mouse unsupported.

---

### TIER 9 — Alert Engine

| # | Feature | Why |
|---|---------|-----|
| 9.1 | **Configurable thresholds** — token %, error rate, circuit opens | Define what matters |
| 9.2 | **Visual alert badge** in header — 🔴 count | At-a-glance |
| 9.3 | **Alert panel** — list active alerts with timeline | Investigate |
| 9.4 | **`[a]` to toggle alert panel** | On-demand |
| 9.5 | **Alert log** — persisted to `~/.hero/viewport/alerts.jsonl` | History, audit |
| 9.6 | **Terminal bell/notification** on critical alerts (`\a`) | Get attention |
| 9.7 | **Alert config** in `~/.hero/viewport/config.yaml` | User-defined rules |

**Implementation:** `AlertEngine` class that evaluates `AlertRule` instances against each `ArmyMetrics` snapshot. Rules: `token_pct > 80`, `error_rate > 5/min`, `circuit_open > 0`, `dlq_count > 10`. Alert state stored in `AlertStore` (JSONL file). Badge in header, list in panel.

---

### TIER 10 — Gauges & Visual Widgets

| # | Feature | Why |
|---|---------|-----|
| 10.1 | **Radial/thermometer gauge** for army-level token usage | Visual impact |
| 10.2 | **Animated gauge fill** on refresh (Rich supports this) | Satisfying, informative |
| 10.3 | **Per-sandbox mini gauge** in table (wider bar + % + absolute) | More info density |
| 10.4 | **Progress bar variants** — show remaining vs consumed, two-tone | Clearer picture |

**Implementation:** `_render_gauge()` using Rich `Progress` widget or custom unicode block art. `_render_sparkline()` for trend. Gauge replaces/reinforces the text bar in header.

---

## Implementation — Kimi's Plan (Actual Build Order)

```
Phase 1 — Foundation (1 session) ✅ DONE
├── State machine (7 states: SPAWNING→BOOTING→WORKING→BLOCKED→COMPLETING→ARCHIVING→DEAD)
├── Stuck detection (5 no-progress cycles → BLOCKED)
├── "Since Last View" delta banner
├── Event compaction engine (rolling 30min window)

Phase 2 — Mashal's Tree (1 session) ✅ DONE
├── Tree rendering with box-drawing connectors (├── └── │)
├── Per-node status coloring (● ✓ ◌ ✗ 🔄)
├── Error branch visualization (RETRY nodes off failed soldiers)
├── Collapsible/collapsed idle sandbox view

Phase 3a — Intel Zone (1 soldier) ✅ DONE
├── Cross-sandbox bottleneck detection (token choke, stall, cascade, CB)
├── Intel panel at top of tree layout

Phase 3b — Budget + Actions (1 soldier) ✅ DONE
├── Budget projections (burn rate, ETA, status per sandbox)
├── Action queue (prioritized suggestions)

Phase 3c — Drill-Down Detail Panel (pending)
├── Select sandbox → show full detail (budget, errors, task, model)
├── Arrow key navigation in tree

Phase 3d — Escalation Paths + Model Contention (pending)
├── Visual retry chain (failed→retry_1→retry_2→escalation)
├── Model contention detection (same model requested by 3+ sandboxes)

Phase 4 — Health Ring + Goal Layer (pending)
├── Top-of-viewport health ring (separate bars for budget/errors/idle)
├── Mission/objective banner
├── Goal progress indicator

Phase 5 — Polish (pending)
├── Mode switching (Tab: Command → Situation → Pulse)
├── Compact mode for narrow terminals
├── Keyboard mode-aware navigation
```

---

## Architecture (Current)

### Files (2,406 lines total)

```
src/hero/viewport/
├── __init__.py              # 1 line
├── states.py        (NEW)  # 89 lines   — SandboxState enum + compute_sandbox_state()
├── delta.py         (NEW)  # 178 lines  — SessionDelta dataclass + delta banner
├── compaction.py    (NEW)  # 161 lines  — CompactionEngine, Event dataclass
├── metrics.py       (MOD)  # 316 lines  — no_progress_counter, last_state_override, previous_army
├── tree.py          (NEW)  # 459 lines  — TreeNode, PipelineState, build_tree()
├── tree_renderer.py (NEW)  # 410 lines  — build_tree_layout(), _render_*_panel()
├── intel.py         (NEW)  # 402 lines  — Bottleneck, BudgetProjection, Action, detection functions
├── renderer.py      (MOD)  # 390 lines  — run_tree() entry point, header in tree mode
└── commands/viewport.py (MOD)           — --mode flag (dashboard|tree)
```

### Key Dataclasses

```python
# states.py
@dataclass
class SandboxState:
    enum: SPAWNING, BOOTING, WORKING, BLOCKED, COMPLETING, ARCHIVING, DEAD

# delta.py
@dataclass
class SessionDelta:
    new_sandboxes: list[str]
    finished_sandboxes: list[str]
    errored_count: int
    budget_delta: int
    time_elapsed: str

# intel.py
@dataclass
class Bottleneck:
    sandbox_name: str
    kind: str          # token_choke | model_contention | pipeline_stall | error_cascade | circuit_breaker
    severity: str      # critical | warning | info
    detail: str
    impacted_sandboxes: list[str]
    suggestion: str

@dataclass
class BudgetProjection:
    sandbox_name: str
    tokens_used: int
    tokens_budget: int
    usage_pct: float
    burn_rate: float
    eta_minutes: int | None
    status: str  # healthy | warning | critical

@dataclass
class Action:
    priority: str  # high | medium | low
    sandbox: str
    action_type: str  # retry | model_swap | pause | cap_budget | investigate
    description: str
    suggestion: str

# tree.py
@dataclass
class TreeNode:
    role: str        # COMM, LEAD, ARCH, SOLDIER, VERIFY, ARCHIVIST, RETRY
    name: str
    status: str
    model: str | None
    task: str | None
    children: list[TreeNode]
    is_error: bool
    error_detail: str | None
    retry_count: int

@dataclass
class PipelineState:
    sandbox_name: str
    task: str
    root_node: TreeNode
    active: bool
    created_at: datetime | None
```

### Key Dataclass Changes

```python
@dataclass
class ArmyMetrics:
    total_tokens_used: int
    total_tokens_budget: int
    burn_rate: float = 0.0          # tokens per minute (NEW)
    eta_minutes: int = 0             # time to empty (NEW)
    dlq_count: int = 0               # DLQ size (NEW)
    circuit_open_count: int = 0      # open circuit breakers (NEW)
    pipeline_count: int = 0          # active pipelines (NEW)
    active_alerts: int = 0           # triggered alerts (NEW)
    history: list[Snapshot] = ...    # time-series samples (NEW)
    ...

@dataclass
class ViewportConfig:
    theme: str = "dark"
    refresh_interval: float = 2.0
    log_buffer_size: int = 200
    history_samples: int = 30
    alert_rules: list[AlertRule] = ...
    ...
```

### Event Publishing Points

Existing hooks in the system that should publish to the viewport log:

| Event | Source | Emits |
|-------|--------|-------|
| Soldier spawn | `hero spawn`, PipelineExecutor | `📝 task: <desc>` |
| Tool call | Soldier agent callback | `🛠 tool: <name>(...)` |
| Dispatch complete | PipelineExecutor | `✅ dispatch <id> complete` |
| Dispatch fail | PipelineExecutor / CB | `✗ dispatch <id> failed: <reason>` |
| Circuit open | CircuitBreaker | `⚠ circuit open for <service>` |
| Circuit half-open | CircuitBreaker | `◐ circuit half-open for <service>` |
| Circuit closed | CircuitBreaker | `🟢 circuit closed for <service>` |
| DLQ enqueue | DeadLetterQueue | `✗ DLQ: <task_id> -> <reason>` |
| DLQ retry | `hero dlq retry` | `🔄 DLQ retry: <task_id>` |
| Pipeline step | PipelineExecutor | `▶ pipeline <id> step N/M` |

---

## Success Criteria

| Metric | Current | DS4 Target |
|--------|---------|------------|
| Info density | 3 panels, 5 datapoints | 3-5 dynamic panels, 15+ datapoints |
| Event visibility | None | Rolling log of last 200 events |
| Trend visibility | None | Sparklines for last 60s |
| Navigation | 4 keys (q/r/1-9/ESC) | 12+ keys + mouse + search |
| Customization | None | 2+ themes, layout toggle, config file |
| Export | None | JSON/TOON snapshot + headless mode |
| Alerting | None | Configurable thresholds + visual badges |
| Drill-down | Single sandbox filter | Full detail panel with katana/budget/errors |

---

## UX Principles (DS4)

1. **Zero-config should still look good** — defaults are smart
2. **Keyboard primary, mouse secondary** — terminal power-user first
3. **Every key do one thing well** — no overloaded shortcuts
4. **More data, not more noise** — optional panels are collapsed by default
5. **Color is information, not decoration** — green/yellow/red has rules
6. **Snappy on 2s refresh** — no I/O in the render loop (cache everything)
7. **Graceful degradation** — small terminals get compact view, not broken layout

---

## Appendix: Keyboard Map (DS4)

```
Global
  q           Quit
  ?           Show help overlay

Navigation
  ↑/↓         Navigate sandbox list
  Enter       Drill into selected sandbox
  ESC         Back / Clear filter / Exit drill

View Toggles
  r           Force refresh
  t           Toggle panel layout (full / no-log / compact)
  g           Toggle sparklines on/off
  a           Toggle alert panel
  /           Enter search mode

Sorting
  s           Cycle sort: name → tokens → tools → status

Drill-Down
  Tab         Toggle focus between sandbox list and detail panel
  Enter       Open detail for selected sandbox
  ESC/b       Back to overview

Export
  e           Export current snapshot to ~/.hero/viewport/snapshots/

Mouse
  Click       Select sandbox / focus panel
  Scroll      Scroll log panel
```

---

*DS4 — Build once, use every day. The viewport should be the first thing you open and the last thing you close.*
