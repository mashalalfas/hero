# improvement_plan_step35.md

> **Model:** stepfun-plan/step-3.5-flash-2603 — *The Communicator*
> **Role:** Always-on, user-facing viewport. Clarity. Context. Calm.

---

## One-sentence pitch

A **command-center cockpit** that tells you the army's full story in one glance — health ring on top, at-a-glance sandbox grid in the middle, and a real-time mission log at the bottom — so you can understand state, spot trouble, and drill into anything before you type a single command.

---

## Visual Paradigm

### The Cockpit Layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ⚡ HERO Command Center                                  2025-05-25 08:17 │
│                                                                            │
│  [HEALTH RING]          Army pulse indicator — green/yellow/red ring      │
│  76%                   with center stats (tokens, active, avg latency)    │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ sook_pro │ │  Freya   │ │qlearner  │ │  her     │ │(idle)    │      │
│  │ ● active │ │ ● active │ │ ○ idle   │ │ ◌ pending│ │          │      │
│  │ step-3.5 │ │deepseek  │ │          │ │ gpt-4o   │ │          │      │
│  │ 76% ████ │ │ 43% ███░ │ │ 12% ██░░░│ │ 68% ████░│ │          │      │
│  │fix theme │ │add search│ │          │ │lang trans│ │          │      │
│  │        2│ │        17│ │          │ │        3│ │          │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│  (status)     (status)     (status)     (status)     (status)             │
│                                                                            │
│  ┌─ row legend ─────────────────────────────────────────────────────────┐│
│  │  1. status icon  2. sandbox name  3. model  4. token bar + %        ││
│  │  5. tool calls   6. live task description (truncated)               ││
│  └─────────────────────────────────────────────────────────────────────┘│
├──────────────────────────────────────────────────────────────────────────┤
│ MISSION LOG — real-time feed                                              │
│  08:17  ▶ sook_pro  step-3.5  fix theme switcher  (active)               │
│  08:16  ✔ Freya     deepseek   add search bar  DONE in 47s               │
│  08:15  ✗ her       gpt-4o     lang translate  TIMEOUT→retry #1          │
│  08:14  ▶ qlearner  —          optimize solver  queued                   │
│  08:10  ✔ Freya     deepseek   add search bar  VERIFY PASS               │
│  ...  (auto-scrolls, newest on top)                                      │
├──────────────────────────────────────────────────────────────────────────┤
│ [1-5] focus  [f] filter  [l] log  [h] health  [r] refresh  [q] quit      │
└──────────────────────────────────────────────────────────────────────────┘
```

### What makes this feel like a cockpit

| Layer | What you see | Why it matters |
|-------|-------------|----------------|
| **Health ring** | Army aggregate pulse + center numbers | One second to know "is everything okay?" |
| **Sandbox grid** | All sandboxes as colour-coded cards in a row | At-a-glance: who's working, who's idle, who's in trouble |
| **Mission log** | Time-ordered event feed | Understand *what's happening* and *what just happened* |
| **Keyboard strip** | Quick-reference shortcuts | No guessing — muscle memory in one glance |

---

## Key Features

### 1. Army Health Ring (new, top bar)
A circular / donut-style health indicator rendered in Rich using Braille or block characters, drawn with the `Segment` API or a simple ASCII approximation.

- **Color:** green (all healthy), yellow (at least one sandbox > 50%), red (at least one failed)
- **Center text:** `76%` (overall usage), `●3/5` (active/idle count), `~47s` (average task latency)
- **Sub-ring:** inner ring shows budget consumption, outer ring shows active-sandbox proportion
- **Purpose:** answer "is the army okay?" before you look at anything else

### 2. Sandbox Card Grid (replaces the table)
Each sandbox becomes a **self-contained card**, not a table row. Cards are richer per unit:

```
┌──────────────┐
│ sook_pro     │  ← sandbox name (bold)
│ ● active     │  ← status icon + text, colour-coded
│ step-3.5     │  ← model assigned
│ 76% ████████ │  ← token bar with percentage
│ tools: 2     │  ← tool call count
│ fix theme sw │  ← current task, truncated
└──────────────┘
```

Benefits over the table:
- **More at a glance** — task description, tool count, model all in one card
- **Visual grouping** — cards form a natural visual row you can scan fast
- **Colour-coded border** — each card's border color = its health (green/yellow/red)
- **Expandable** — press a number key or Enter to flip the card open into a detail view

### 3. Mission Log (new, bottom third)
A time-ordered, colour-coded feed of significant events drawn as Rich text:

- `▶` green  — task started
- `✔` green  — task completed (shows duration)
- `✗` red    — task failed (shows error type)
- `🔄` yellow — retry initiated
- `◌` grey   — task queued
- `↗` cyan   — sandbox dispatched / model changed

The log pulls from the **dispatch directory timeline** (sorted by file mtime or timestamp field), giving you the narrative of what the army has been doing, not just its current state.

- **Auto-scroll:** newest at top, scroll with `↑↓` to read history
- **Compact mode:** `[l]` toggles between log on / off (gives grid more vertical space)
- **Filter:** `[f]` filter log by sandbox name or status keyword
- **Entry limit:** keeps last 40 entries to avoid memory bloat

### 4. Sandbox Detail Drill-Down
Press `Enter` or `1-5` on a sandbox card to flip it into **detail mode**:

```
╔══════════════════════════════════════════════╗
║ sook_pro — DETAIL                             ║
╠══════════════════════════════════════════════╣
║ Status:   ● active  Model: step-3.5-flash    ║
║ Budget:   3800 / 5000  (76%)                 ║
║ Tools:    17 calls  Subagents: 2 active      ║
║ Task:     fix theme switcher — toggle broken ║
║ Started:  08:12 UTC  Elapsed: 5m 03s         ║
╠══════════════════════════════════════════════╣
║ Recent tool calls:                            ║
║  08:16  read  src/theme.py  (OK)             ║
║  08:15  bash pytest tests/theme  (PASS)      ║
║  08:14  edit  src/theme.py  line 42          ║
╠══════════════════════════════════════════════╣
║ [b] back  [e] events  [k] kill  [q] quit     ║
╚══════════════════════════════════════════════╝
```

The detail panel surfaces what a table row can't: elapsed time, per-call breakdown, and action affordances like kill or event log.

### 5. Keyboard Layout (three tiers)

| Key | Tier 1 (default) | Tier 2 (detail view) | Tier 3 (log filter) |
|-----|-----------------|----------------------|---------------------|
| `q` | Quit | Quit | Quit |
| `r` | Force refresh | — | — |
| `1-9` | Focus sandbox N | — | — |
| `Enter` | Open detail | Close detail | — |
| `l` | Toggle mission log | — | — |
| `f` | — | — | Open filter prompt |
| `h` | Show health overlay | — | — |
| `b` | — | Back to grid | — |
| `e` | — | Show event log | — |
| `k` | — | Kill sandbox | — |
| `↑↓` | Scroll log | Scroll detail | Scroll filter results |
| `ESC` | Clear filter / back | Back to grid | Clear filter |

Three tiers keeps it simple but powerful — no mode stacking, each layer is self-contained.

### 6. Health Overlay (`[h]`)
A transient full-width strip at the top showing per-sandbox health summary:

```
 HEALTH: sook_pro ●76%  Freya ●43%  qlearner ○12%  her ◌68%  (army: ● yellow)
```

Useful when you're in detail view or log view and need a quick health pulse without going back.

---

## Data Sources

| Signal | Source | How read |
|--------|--------|---------|
| Token usage, status, model | `hero.state.cache` (already used) | `batch_load` — no change |
| Tool calls, task, subagent count | `~/.hero/dispatch/*.toon` / `*.json` | Already read by `_read_dispatch_files()` |
| **Event log / mission feed** | `~/.hero/dispatch/*.toon` mtime + timestamp field | Sort by file mtime descending, last 40 |
| **Average task latency** | Dispatch files: compare `started_at` to `completed_at` or current time | New field in `SandboxMetrics` |
| **Per-sandbox tool call breakdown** | Dispatch history or a new `~/.hero/tool_log/<sandbox>.jsonl` append-only log | Optional enhancement |
| **Git status** (optional) | `git -C <sandbox_path> status --porcelain` | Lazy, only when detail panel open |
| **Budget reset count** (optional) | `hero.state.budget` compaction count | Already partially in `metrics.py` |

The first three are zero-cost additions — they reuse existing files. Git status and budget reset are optional enhancements that only activate on demand.

---

## Interaction Map

```
┌──────────────────────────────────────────────────────────┐
│                   INTERACTION FLOW                        │
│                                                           │
│  Live Mode ──────────────────────────────────────────►   │
│    1. User opens `hero viewport`                          │
│    2. Health ring draws immediately                        │
│    3. Sandbox cards populate from cache                    │
│    4. Mission log loads last 40 dispatch events            │
│    5. Auto-refresh every 2s (same as current)              │
│                                                           │
│  Navigation ──────────────────────────────────────────►   │
│    [1-9] → highlight + focus card N                        │
│    ↑↓    → scroll mission log                              │
│    Enter → flip card to detail panel                       │
│    ESC   → back to grid / clear filter                     │
│    [l]   → toggle mission log on/off                       │
│    [f]   → type filter string (sandbox name or status)     │
│    [h]   → flash health overlay strip                       │
│                                                           │
│  Detail View ──────────────────────────────────────────►  │
│    [e]   → show full event list for this sandbox           │
│    [k]   → confirm kill (write sentinel file)              │
│    [b]   → back to grid                                    │
│                                                           │
│  Quit ────────────────────────────────────────────────►   │
│    [q]   → clean exit, restore terminal                    │
└──────────────────────────────────────────────────────────┘
```

### What's preserved from current viewport
- `--once` mode: prints a one-shot grid snapshot, no live loop
- `--sandbox X`: focus opens directly into detail view for that sandbox
- Auto-refresh interval: still 2s, configurable in future
- Keyboard quit (`q`): unchanged behavior

### What's new
- Mission log event feed — the "what just happened" layer missing today
- Card-level detail drill-down — context on demand without leaving the TUI
- Health overlay — army-wide pulse available from any view
- Filter and search — find specific sandboxes or events without mental gymnastics

---

## Why This Fits stepfun-plan/step-3.5-flash-2603

> *The Communicator. Always-on. User-facing. Clarity over cleverness.*

### The reasoning

The Communicator model's strength is **synthesizing context into clear signals**. A table row tells you one sandbox's numbers; a card tells you that sandbox's story. A header bar tells you one aggregate; a health ring tells you the army's pulse.

The current viewport is a **table of facts**. The cockpit is a **story of state**:

- **Health ring** = "is everything okay?" — answered in 200ms of glance time, no parsing needed
- **Sandbox grid** = "who's doing what" — each card is a mini status report, not a data row
- **Mission log** = "what just happened" — the narrative layer the table never had

This is what a Communicator wants to see: **not just the numbers, but what they mean**.

### Design philosophy

- **Calm density:** information is packed but breathing room prevents overwhelm — 8 sandboxes visible, each card readable at a glance
- **Colour as signal, not decoration:** green/yellow/red has meaning; the health ring makes it the dominant signal
- **Depth on demand:** the default view stays at summary level; drill into a sandbox when you need it, don't force the details on every refresh
- **Consistency with current behavior:** the existing refresh loop, keyboard shortcuts, and data collection pipeline are preserved and extended, not replaced

### What would make me excited to open this every morning

1. **The health ring** — one look, I know if I need to worry
2. **The card grid** — I can see all sandboxes in one sweep, spot the red card immediately
3. **The mission log** — I catch up on what happened overnight without digging through dispatch files
4. **Enter-to-drill** — I can satisfy any curiosity without context-switching to another terminal

---

## Quick Start (if implemented)

### Phase 1 — Core cockpit (this plan)
1. Add `SandboxCard` renderer to `renderer.py` — Rich Panel-based card per sandbox
2. Add `MissionLog` collector — reads dispatch mtime + timestamp, last 40 events
3. Add `HealthRing` — lightweight ASCII/Braille ring using `rich.segment` or text fallback
4. Add three-tier keyboard handler — existing input loop extended with new key bindings
5. Wire `--sandbox X` to open detail view directly

### Phase 2 — Detail panel
1. Implement `SandboxDetail` panel — flips from card view on `Enter`
2. Add `kill sandbox` action — writes sentinel file, reuses existing kill pathway
3. Add `event log` view per sandbox — `[e]` in detail shows filtered mission events

### Phase 3 — Polish
1. Add `--compact` flag — hide mission log, cards stay
2. Add `--quiet` flag — health ring + grid only, no log
3. Add git status in detail panel (lazy-loaded, `--git` flag)
4. Add configurable refresh interval (`--interval N`)

### Phase 4 — Optional extras
1. Per-sandbox tool call breakdown panel
2. Budget reset counter in health ring center
3. Colour theme toggle (dark terminal vs light terminal detection)
4. Export snapshot as ANSI escape sequence for logging / alerts

---

*Communicator vision — clarity through structure, not density.*
