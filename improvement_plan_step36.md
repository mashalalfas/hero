# improvement_plan_step36.md

## One-sentence pitch

A **velocity-centric command center** that shows the HERO army as a live, breathing organism — tracking what's accelerating, decelerating, and crossing thresholds in real time, so you see the motion before you see the numbers.

---

## Visual Paradigm (your unique concept)

```
┌─────────────────────────────────────────────────────────────────┐
│ HERO⚡ VELOCITY COMMAND CENTER      2026-05-25 08:17:12 UTC    │
│ ████████████████░░░░░░░░ 62% · ●3 ○6 ▒2  ↓3 →↑1  ⚡ 2.4x     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─ NOW (this refresh cycle) ───────────────────────────────┐  │
│  │ [0.2s] freya: ARCH → soldier_1 spawned (step-3.5)       │  │
│  │ [0.5s] sook_pro: token delta +340 tokens/min            │  │
│  │ [1.1s] qlearner: tool_call (exec) velocity spike       │  │
│  │ [1.8s] freya: VERIFY complete → 3/3 passed             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─ DELTA STRIP (change since last refresh) ──────────────┐  │
│  │ freya    [██████████] +340 tok/min ▲▲  active=5→7      │  │
│  │ sook_pro [██████░░░░] +120 tok/min ▲   active=2→3      │  │
│  │ qlearner[██░░░░░░░░]  +15 tok/min —  idle:new→idle     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─ VELOCITY GRAPH (last 60s) ────────────────────────────┐  │
│  │ 4.0 ┤        ╭─╮                                         │  │
│  │ 3.0 ┤   ╭───╯ ╰─╮    ╭──╮                                │  │
│  │ 2.0 ┤╭──╯       ╰────╯  ╰──╮                            │  │
│  │ 1.0 ┤╯                      ╰───╮                        │  │
│  │ 0.0 ┼──────────────────────────┴─ sandboxes ──── t     │  │
│  │     freya     sook_pro     qlearner    her              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─ ACCELERATION METRICS ──────────────────────────────────┐  │
│  │  sook_pro   ████████░░  2.4x  ACCELERATING 🔥           │  │
│  │  freya      ██████░░░░  1.8x  ACCELERATING ▲           │  │
│  │  qlearner   ███░░░░░░░  0.6x  DECELERATING ▼           │  │
│  │  her        ██████████  3.1x  CRITICAL VELOCITY ⚡      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─ THRESHOLD WATCHERS (pinged events) ───────────────────┐  │
│  │  ⚠ freya    → 85% budget (was 72%)   [2 cycles ago]   │  │
│  │  ↑ sook_pro → model switch: st3.5→deepseek             │  │
│  │  ✓ qlearner → 5 tool calls in 1s (burst complete)     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  [q]quit  [r]hard refresh  [s]stream toggle  [↑↓]sandbox  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Features

### 1. **NOW Feed — Real-time Activity Stream**

A scrolling feed of the most recent events across all sandboxes, timestamped to the refresh cycle. Events include:

- `spawn` — soldier created (with model and role)
- `tool_call` — tool invocation with duration and type
- `status_flip` — sandbox or subagent changed state
- `budget_delta` — tokens consumed in this cycle
- `error` — any error event with context
- `complete` — subtask finished
- `retry` — retry triggered with fallback model

Each event is color-coded by type and shows relative timing (`[0.2s]`, `[1.1s]` from last refresh). The feed scrolls upward, keeping the freshest events at the top. This is the "what's happening RIGHT NOW" pane.

**Why it matters:** In a live TUI, the most valuable information is *what changed since I last looked*. The feed makes that instant.

### 2. **Delta Strip — Change Detection**

A compact horizontal strip showing per-sandbox deltas since the last refresh:

```
freya    [██████████] +340 tok/min ▲▲  active=5→7
```

Each sandbox gets:
- A mini bar showing the magnitude of change (scaled to the max delta across all sandboxes)
- Numeric delta for tokens consumed this cycle (converted to tokens/min)
- Direction arrows for key state changes: ▲▲=accelerating fast, ▲=accelerating, —=stable, ▼=decelerating
- Count deltas for critical counters: active agents, tool calls, errors

**Why it matters:** The v1 viewport shows current state. Delta Strip shows *motion*. You immediately see which sandbox just woke up, which is slowing down, and which just crossed a threshold.

### 3. **Velocity Graph — Sparkline Trend View**

A compact time-series graph showing tokens/min (or tool calls/min) for each sandbox over the last 60 seconds. Built with Rich's Sparkline or a custom Unicode graph:

```
4.0 ┤        ╭─╮
3.0 ┤   ╭───╯ ╰─╮    ╭──╮
2.0 ┤╭──╯       ╰────╯  ╰──╮
1.0 ┤╯                      ╰───╮
0.0 ┼──────────────────────────┴─ sandboxes ──── t
```

Each line is color-coded by sandbox. The graph updates in-place, scrolling left as time advances. This gives you the *trend* — is this sandbox spiking, plateauing, or dying?

**Why it matters:** One number (current tokens) tells you where you are. A trend tells you where you're going. Command centers need both.

### 4. **Acceleration Metrics — Rate-of-Change Display**

A ranked list showing each sandbox's velocity multiplier relative to its baseline:

```
sook_pro   ████████░░  2.4x  ACCELERATING 🔥
freya      ██████░░░░  1.8x  ACCELERATING ▲
qlearner   ███░░░░░░░  0.6x  DECELERATING ▼
her        ██████████  3.1x  CRITICAL VELOCITY ⚡
```

- The bar shows the magnitude of acceleration (relative to the highest in the current set)
- The multiplier shows how many times the baseline rate (average over last 30s)
- Labels: ACCELERATING (1.5x+), DECELERATING (0.7x-), CRITICAL VELOCITY (3x+), STABLE (within 0.7–1.5x)
- Icons: ▲, ▼, 🔥, ⚡, —

**Why it matters:** This is the model-specific insight. A table shows state; acceleration shows *dynamics*. A sandbox at 80% budget that's decelerating is fine. A sandbox at 40% budget accelerating at 3x will burn out in 30 seconds.

### 5. **Threshold Watchers — Event-Based Alerts**

A pane showing recent threshold crossings and notable events that triggered notifications:

```
⚠ freya    → 85% budget (was 72%)   [2 cycles ago]
↑ sook_pro → model switch: st3.5→deepseek
✓ qlearner → 5 tool calls in 1s (burst complete)
```

Each event has:
- An icon: ⚠=warning, ↑=model switch, ✓=milestone, ✗=error, ⚡=burst
- The sandbox name
- A natural-language description of what happened
- A recency tag: `[just now]`, `[1 cycle ago]`, `[2 cycles ago]`

**Why it matters:** Raw tables require you to *watch* for changes. Threshold watchers *tell you* something changed and what it means. This turns the dashboard from a mirror into a signal system.

### 6. **Compact Mode — Minimal State Overview**

For quick glances or narrow terminals:

```
HERO⚡  3 active  ·  ▼2 accelerating  ·  ⚠1 threshold
freya   ████████░░  85%  2.4x  ▲▲
sook_pro█████████░  72%  1.8x  ▲
qlearner████░░░░░░  34%  0.6x  ▼
her     █████████░  91%  3.1x  ⚡
```

Three lines total: header summary, sandbox strip, status row. Everything in the right-to-left reading flow: identity → velocity → alert state.

---

## Data Sources

### Existing (already collected in v1)
- `hero.state.cache` — sandbox state (status, budget, tokens)
- `~/.hero/dispatch/*.toon` — active dispatch tasks (model, tool_calls, subagent_count)
- `hero.state.budget` — per-sandbox budget tracking
- `hero.state.index` — sandbox registry

### New additions

#### 1. **History Buffer** (`~/.hero/viewport_history.jsonl`)
Append-only log of each refresh cycle's metrics snapshot. Used for:
- Computing velocity (rate of change over time)
- Drawing the 60-second velocity graph
- Detecting thresholds and generating watcher events
- Calculating acceleration multipliers

Schema per cycle:
```json
{
  "ts": "2026-05-25T08:17:12Z",
  "sandboxes": [
    {
      "name": "freya",
      "tokens_used": 2840,
      "tool_calls": 47,
      "active_subagents": 5,
      "status": "running"
    }
  ]
}
```

Keep last 30 cycles (~60 seconds at 2s refresh). Rolled on each refresh.

#### 2. **Event Stream** (in-memory, per refresh)
Current refresh events are detected by diffing against previous cycle's metrics. Events are classified into types:

| Type | Trigger | Example |
|------|---------|---------|
| `spawn` | `subagent_count` increased | "soldier_1 spawned (step-3.5)" |
| `complete` | subagent count decreased naturally | "VERIFY complete → 3/3 passed" |
| `status_flip` | status field changed | "freya: idle → running" |
| `budget_delta` | tokens_used changed | "+340 tokens in 2.0s" |
| `tool_call` | tool_calls increased | "exec tool call (duration: 0.3s)" |
| `burst` | tool_calls increased by >3 in one cycle | "5 tool calls in 2s burst" |
| `model_switch` | model field changed | "model: st3.5 → deepseek" |
| `threshold` | usage_ratio crossed 0.8 or 0.95 | "→ 85% budget" |
| `error` | status became "error" or "failed" | "Timeout error on soldier_2" |

#### 3. **Baseline Window** (last 15 cycles / ~30 seconds)
For each sandbox, maintain a rolling baseline of average tokens/min and tool_calls/min. The acceleration multiplier = current_rate / baseline_rate. This smooths out noise while still catching real acceleration events.

#### 4. **Git Integration** (optional, opt-in)
For sandboxes that are git repos, read `git status --porcelain` to detect:
- Uncommitted changes count
- Recent commit activity
- Branch changes

Shown as a tiny `[±3 files]` indicator next to sandbox name.

#### 5. **CI/CD Status** (optional, opt-in)
For sandboxes with a `Makefile` or GitHub Actions workflow, detect:
- Last build status (success/failure)
- Build duration trend
- Test pass rate

Shown as `[build:✓]` or `[build:✗]` indicator.

---

## Interaction Map

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Force immediate refresh (skip interval) |
| `s` | Toggle stream mode: full velocity view ↔ compact overview |
| `↑` / `↓` | Move selection highlight between sandboxes |
| `Enter` | Drill into selected sandbox: show full history graph + event log + breakdown |
| `p` | Pause auto-refresh (toggle) |
| `t` | Toggle threshold watcher pane on/off |
| `e` | Filter: show only sandboxes with recent errors |
| `v` | Toggle velocity graph style: sparkline → bar → off |
| `1-9` | Focus mode: show only selected sandbox (expanded detail) |
| `?` | Show key reference |

### Drill-Down Detail View

When you `Enter` on a sandbox, you get a full-screen detail:

```
freya — DETAIL VIEW
═══════════════════════════════════════════════════════════════════
Budget:      ████████████████████░░░░  2840/5000  56.8%
Velocity:    2.4x (342 tok/min)   ▲▲  accelerating
Active:      7 soldiers  3 retry branches
Last error:  [none]

VELOCITY GRAPH (60s window)
3.5 ┤              ╭─╮
2.5 ┤     ╭──╮    ╰─╯     ╭──╮
1.5 ┤╭──╮╯  ╰──╮        ╭─╯  ╰──╮
0.5 ┤╯  ╰──╮   ╰────────╯       ╰──
    └──────┴─────────────────────────── t (60s)
    spawntrigger → model_switch → ACCELERATE

RECENT EVENTS
[0.0s] soldier_7 spawned (deepseek)
[0.3s] tool_call: exec (duration: 0.2s)
[1.1s] status: idle → active (freya)
[1.8s] threshold: → 72% budget
[2.0s] ⚡ VELOCITY SPIKE: 3.1x average

RECENT TOOL CALLS
exec       ████████████████░░░░░░  42 calls  avg 120ms
read       ████████░░░░░░░░░░░░░░  18 calls  avg 45ms
write      ██████░░░░░░░░░░░░░░░   12 calls  avg 80ms
exec       ████░░░░░░░░░░░░░░░░░    6 calls  avg 2.1s ⚠

[done]
```

---

## Why This Fits step-3.6

### I am fast and new — velocity is my natural lens

My training emphasizes **reasoning speed** and **token efficiency**. I think in rates of change, acceleration, and momentum — not just static states. The velocity viewport reflects this:

1. **Motion before state.** When I look at a system, I first ask: what's changing? What's accelerating? What's about to break? The NOW Feed and Delta Strip surface motion immediately.

2. **Rate-of-change reasoning.** Acceleration multipliers (2.4x, 3.1x) are how I naturally express system dynamics. A table of percentages requires interpretation. "2.4x accelerating" is immediate and actionable.

3. **Event streams over snapshots.** I process information as a stream of events — "tool_call happened", "status flipped", "budget dropped". The NOW Feed mirrors how I actually perceive system state: as a sequence of updates, not a frozen picture.

4. **Threshold awareness.** I'm trained to watch for threshold crossings and anomalous patterns. The Threshold Watchers pane operationalizes this: it doesn't just show numbers, it highlights the moments that matter.

5. **Compact + expandable.** My responses aim for brevity with optional depth. The compact mode gives you the full signal in one glance; drill-down gives you the data when you need it. No wasted space, no unnecessary hierarchy — just signal-to-noise maximization.

6. **Real-time alignment.** I respond to each message as it arrives. The viewport refreshes every 2 seconds. The velocity metrics close the loop: the dashboard moves at the same tempo I do.

---

## Quick Start (if implemented)

### Phase 1: Core Infrastructure
1. Add `history.py` module — rolling buffer of 30-cycle metrics snapshots
2. Add `events.py` module — diff engine that classifies change events between cycles
3. Extend `MetricsCollector` to maintain the history buffer in memory

### Phase 2: Renderer Extensions
4. Build `_render_now_feed()` — event stream display (top pane)
5. Build `_render_delta_strip()` — per-sandbox change visualization (2nd pane)
6. Build `_render_velocity_graph()` — sparkline trend view (3rd pane)
7. Build `_render_acceleration()` — ranked velocity multiplier list (4th pane)
8. Build `_render_watchers()` — threshold event log (bottom pane)
9. Create `build_velocity_layout()` that arranges these panes

### Phase 3: Compact Mode
10. Add `compact=True` mode that collapses to 3-line overview
11. Wire up the `s` key to toggle between full and compact

### Phase 4: Interaction
12. Implement drill-down detail view (Enter key on sandbox)
13. Add pause toggle (`p` key) and velocity graph style toggle (`v` key)
14. Wire up arrow key navigation and selection highlight

### Phase 5: Polish
15. Add git status and CI/CD detection to metrics collector (opt-in)
16. Smooth animations for velocity graph updates (if Rich supports it)
17. Color tuning: ensure velocity indicators are distinguishable at a glance
18. Performance: ensure rendering stays under 100ms per cycle

### The Result

A viewport that doesn't just show you what the army *is* — it shows you what the army *is doing*. You see the motion, the velocity, the accelerations and decelerations. You don't have to wait for something to break to know something is changing. The dashboard *is* the motion.

---

*Plan by stepfun-plan/step-3.6 — velocity, acceleration, and real-time motion*
