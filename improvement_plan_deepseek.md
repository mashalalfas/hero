# improvement_plan_deepseek.md

> **Model:** DeepSeek V4 Flash
> **Superpower:** 200k context window — I see the full river, not just the ripple
> **Tagline:** *"Your work has a shape. Let's see it."*

---

## One-Sentence Pitch

Replace the flat table with a **live Flow-Sprawl** — a time-layered swimlane visualization that turns HERO's concurrent sandbox work into a flowing current you can read at a glance, errors into visible flares, and bottlenecks into heat that demands attention.

---

## Visual Paradigm: The Flow-Sprawl

Not a tree (that's vertical hierarchy). Not a table (that's rows). This is a **horizontal time-current** — work flows left-to-right across the terminal, each sandbox is a swimlane river, and every dispatch task is a colored block moving through time.

```
┌──────────────────────────────────────────────────────────────────┐
│ HERO⚡ T:12,450/50k ████████░░ 25% | Tools:87 | ●3 ○5 | F:0 │ 14:32:19
├──────────────────────────────────────────────────────────────────┤
│ ┌─sook_pro────────────────────────────────────────── current ──┐ │
│ │ ·[14:30]███████████████████████████████████[14:32]           │ │
│ │   fix_theme ✓ 4.2s  ds     refine_spec ✓ 3.1s  ds      │ │
│ │ ····················╳═══╡RETRY══▶███████████░░░              │ │
│ │                    timeout 3.5s k2.6  ░compile ░2.1s░ds  │ │
│ └───────────────────────────────────────────────────────────────┘ │
│ ┌─freya─────────────────────────────────────────── current ──┐ │
│ │ ·[14:28]████████████████████░░░░░░░░░░░░░░░░░░[14:32]      │ │
│ │   add_search ✓ 5.1s  ds     write_test ● active  ds    │ │
│ │                                        ░░░░░░░░░░░░        │ │
│ └───────────────────────────────────────────────────────────────┘ │
│ ┌─qlearner───────────────────────────────────────── current ──┐ │
│ │ ○ idle since 14:10                                           │ │
│ └───────────────────────────────────────────────────────────────┘ │
│                                                                   │
│ ┌─Error Cluster────────────────────────────────────────────────┐ │
│ │ ⚡ 3 timeouts last 5min (sook_pro, freya)     ── common? ──▶│ │
│ │ ✗ 1 API rejection (qlearner, model: deepseek) ── quota? ──▶│ │
│ └───────────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────┤
│ [q]quit [↑↓]focus [→]detail [f]flare-log [p]pattern-search [/?]help│
└──────────────────────────────────────────────────────────────────┘
```

### Why Flow Over Tree or Table

| Aspect | Table (current) | Tree (Mashal) | Flow-Sprawl (DeepSeek) |
|--------|----------------|---------------|----------------------|
| Dimension | Rows of status | Vertical depth | Horizontal **time** + swimlanes |
| Strengths | Compact, familiar | Hierarchy, command chain | **Causality, duration, parallelism** |
| Best for | "What's running?" | "Who reports to whom?" | **"When did what happen, and how long?"** |
| Error visibility | Red badge in cell | Forked subtree | **Flare bar crossing swimlane** |
| Time awareness | None (instantaneous) | Implicit in position | **Explicit — X axis is time** |
| Pattern detection | Manual scanning | Manual scanning | **Auto-clustered on the right** |

The Flow-Sprawl is the viewport for someone who thinks in **causality chains and timing** — exactly what a 200k-context deep worker does.

---

## Key Features

### 1. Time-Layered Swimlanes (The Core)

Each sandbox is a horizontal swimlane. Time flows left to right. Within each lane:

- **Blocks** represent dispatched tasks (one per soldier assignment)
- **Block width** = task duration (proportional to real time)
- **Block color** = model assigned (deepseek=cyan, kimi=magenta, gemini=green, gpt=blue)
- **Block label** = task name (truncated) + status + duration + model code
- **Current time indicator** = a vertical `│` line at the rightmost position, moving right each tick
- **Past blocks** dim behind the current time; future-looking blocks (queued) shown as dashed outlines

This lets you answer instantly: *What's been happening in the last N minutes? What's taking too long?*

### 2. Active/Idle/Vertical Zoning

The layout is split into zones top-to-bottom:

```
┌─ Header ──────────────────────────────────────────┐
│ Army-level: tokens, tools, active/idle, timestamp │
├─ Active Sandboxes ────────────────────────────────┤
│ Swimlanes for sandboxes with running/dispatched   │
│ work (sorted: most recently active first)         │
├─ Idle Sandboxes (collapsed) ──────────────────────┤
│ ○ qlearner ○ sook_api ○ her      [e]xpand all    │
├─ Analysis Panel ──────────────────────────────────┤
│ Error clusters, pattern suggestions, hot spots    │
└─ Footer ──────────────────────────────────────────┘
```

The **Analysis Panel** is the secret weapon — see Feature 5.

### 3. Flare-Anchored Error Display

When a task fails or errors, a **flare** appears at its time position:

```
         ╳
   ──────╫█████████────
         ║
         ║  timeout at 3.5s
         ║  retry → k2.6 dispatched
         ▼
```

- Flare = vertical red bar `╳` crossing the swimlane height
- Flare width = retry duration (if retrying)
- Flare label shows error type + model switch on retry
- Multiple flares close together = **cluster** (see Feature 6)

### 4. Model-Switching Visual Grammar

When a task retries on a different model, the block changes color mid-stream:

```
██████████████████████████████████████
ds (deepseek)     ╳     k2.6 (kimi)
              timeout
```

This is a **model handoff signature** — you can spot at a glance which models are reliable vs which ones keep timing out.

### 5. Intelligent Analysis Panel (The Deep Part)

This is what makes the viewport *think*, not just show. The panel on the bottom auto-generates:

| Insight | How It Works |
|---------|-------------|
| **Error clusters** | "3 timeouts in sook_pro last 5min" — temporal proximity detection |
| **Hot models** | "deepseek timed out 4x today, kimi 0x" — per-model fail rate |
| **Bottleneck detection** | "write_test tasks average 12s (2x other types)" — task-type duration anomaly |
| **Token rate warning** | "sook_pro burning 800t/min, will exhaust budget in 3min" — trend projection |
| **Retry cascade** | "3 retries → same error 'API timeout' → quota issue?" — pattern matching |
| **Silent sandbox** | "freya dispatched 20min ago, no activity" — hung detection |

Each insight is a single line with a confidence-text color (green=info, yellow=warning, red=critical). Press `Enter` on an insight to expand it with details.

### 6. Pattern Search (`/`)

Press `/` to enter pattern-search mode. You can query:

```
/timeout          → highlights all timeout flares
/deepseek fail    → highlights deepseek failures only
/duration > 10s   → highlights tasks running > 10s
/budget > 80%     → sandboxes near budget limit
```

Results show as highlighted blocks and a count in the search bar.

### 7. Detail Drill-Down (`Enter` on block)

Select any task block with `↑↓→←` and press `Enter` to see a detail popup:

```
┌─ Task Detail ───────────────────────────────────┐
│ Task:    fix_theme_switcher                     │
│ Model:   deepseek (step-3.5)                    │
│ Status:  ✓ Done    Duration: 4.2s               │
│ Started: 14:30:12  Ended: 14:30:16              │
│ Tokens:  1,240 used                             │
│ Tools:   3 calls (read, edit, exec)             │
│ Errors:  none                                   │
│ ──────────────────────────────────────────────── │
│ [v] View stdout    [l] Log file    [s] Share     │
└──────────────────────────────────────────────────┘
```

---

## Data Sources

| Source | Currently Used? | New in Flow-Sprawl |
|--------|----------------|-------------------|
| `hero.state.cache` | ✅ Tokens, budget | ✅ + status timestamps |
| `~/.hero/dispatch/*.toon` | ✅ Tool calls, model | ✅ + timestamps, duration, error info |
| `~/.hero/dispatch/*.json` | ✅ Fallback | ✅ + error messages |
| `hero.state.index` | ✅ Sandbox list | ✅ same |
| **`~/.hero/error_log/*.toon`** | ❌ | ✅ NEW — error events with timestamp + type + model |
| **`~/.hero/task_history.toon`** | ❌ | ✅ NEW — completed task log (duration, model, error count) |
| **`~/.hero/model_roster.toon`** | ❌ | ✅ NEW — available models, per-model cost/rate limits |
| **Git status (optional)** | ❌ | 🔜 Phase 2 — auto-detect active branches per sandbox |

### New Files

**`~/.hero/error_log/`** — one `.toon` file per error event:

```
timestamp: 1745472642
sandbox: sook_pro
task_id: fix_theme_switcher
error_type: timeout
model: deepseek
duration: 12.5
retry_model: kimi
retry_task_id: retry_fix_theme_switcher_1
```

**`~/.hero/task_history.toon`** — append-only task log:

```
task_id: fix_theme_switcher
sandbox: sook_pro
model: deepseek
started: 1745472638
completed: 1745472642
status: done
tool_calls: 3
tokens_used: 1240
error: null
```

These files are tiny, append-only, and cheap to read. The Flow-Sprawl can scan the last N entries to build its time-layered view and error clusters.

---

## Interaction Map

| Key | Action |
|-----|--------|
| `↑↓` | Move focus between swimlanes (sandboxes) |
| `→` | Expand focused swimlane (show more history) |
| `←` | Collapse swimlane to compact view |
| `Enter` | Drill into selected task block → detail popup |
| `/` | Enter pattern-search mode |
| `Tab` | Cycle focus: swimlanes → analysis panel → header |
| `f` | Toggle flare log (show all errors as list) |
| `p` | Toggle pattern analysis panel |
| `c` | Clear all flares (dismiss acknowledged errors) |
| `e` | Expand all collapsed idle sandboxes |
| `r` | Force refresh |
| `q` | Quit |
| `1-9` | Jump to sandbox by numeric index (left sidebar) |
| `ESC` | Back to overview from drill-down |

### Mouse Support (Phase 2)

- Click on a task block → detail popup
- Click on a flare → show error details + retry status
- Scroll in swimlane area → scroll horizontally through time
- Right-click → context menu: "View log", "Kill task", "Force retry"

---

## Why This Fits DeepSeek V4 Flash

I am a deep worker. My entire design is about **seeing the whole battlefield across time**.

| DeepSeek Trait | How It Maps to Flow-Sprawl |
|----------------|---------------------------|
| **200k context** — I think in long spans | Time-layered view spanning minutes of work, not just current snapshot |
| **Pattern matching** — I detect structure across large data | Auto-clustered error analysis panel finds temporal patterns |
| **Causal reasoning** — I trace why chains | Flare blocks show error → retry → success in a single visual chain |
| **Deep thinker** — I don't just answer, I analyze | Analysis panel doesn't just show metrics; it **asks questions** ("quota issue?", "common pattern?") |
| **Code-aware** — I understand system flow | Each task block maps to a real soldier dispatch; you can trace code → execution → result |
| **No fluff** — I cut to the signal | Flow-Sprawl is denser than a table but more readable — one terminal page gives you the full time-state of all sandboxes |

When I open this viewport, I want to see:

1. **The last N minutes of every sandbox** — not just "what's running now" but "what just happened and for how long"
2. **Where the pain is** — errors glow red immediately, clusters get attention
3. **Where to optimize** — which models are slow, which tasks take too long
4. **What's about to break** — token exhaustion warnings, hung tasks
5. **A story** — each sandbox's swimlane tells a narrative of dispatches → outputs

I don't want a status board. I want a **situation display** that matches how I think.

---

## Quick Start (If Implemented)

```bash
# Full Flow-Sprawl dashboard
hero viewport

# Focus one sandbox
hero viewport --sandbox sook_pro

# Show last 10 minutes only
hero viewport --window 10m

# Export current view as SVG
hero viewport --snapshot viewport.svg

# Pattern search mode (CLI)
hero viewport --search "timeout"
```

Implementation would extend `renderer.py` with a new `FlowSprawlRenderer` class, add a `time_window` config, and write a lightweight `TaskHistoryStore` to read/write `task_history.toon`. The Rich `Layout` + `Table` patterns already in the codebase are flexible enough to support this without a framework change.

---

## Summary

The tree shows *who reports to whom*. The table shows *what's running now*. The **Flow-Sprawl** shows *what's been happening, what's taking too long, and where the patterns are*.

That's how a deep worker with 200k context sees the world — not as a hierarchy, not as a list, but as a **current of events flowing through time**.
