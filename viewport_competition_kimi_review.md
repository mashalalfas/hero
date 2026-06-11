# HERO Viewport Competition — Kimi K2.6 Review

> Reviewer: Kimi K2.6 (long-context analyst, synthesis focus)
> Date: 2026-05-25
> Subject: Systematic review of 7 viewport competition entries

---

## 1. Overall Assessment

### Strongest Entry: MiMo V2.5 (Lead) — "Command Center"

**Why it wins:** It's the only entry that answers the question the operator actually has at 8pm when something's gone wrong: *"What do I need to decide, right now?"*

The three-zone situation room (Intelligence / Resource Map / Action Queue) maps cleanly onto human decision-making:
1. **What's broken?** (left zone)
2. **Where are resources stuck?** (center zone)
3. **What can I do about it?** (right zone)

This is the only entry with an explicit **action layer** — quick actions like auto-retry, model swap, kill, pause. The rest are passive monitors. A viewport that doesn't help you *act* is just a fancy log tail.

**Key differentiator:** Cross-sandbox intelligence. All other entries are sandbox-local (except DeepSeek's graph, which is structural not strategic). MiMo V2.5 actually reasons about *relationships between sandboxes* — bottlenecks, contention, dependency chains. That's the leap from "monitoring" to "orchestration."

**Honorable mention — strongest visual concept:** DeepSeek's code flow graph. Beautiful. If you want to understand *why* the army is slow, nothing beats a live topology graph. But it's a diagnostic tool, not a command center. You wouldn't live in it.

---

## 2. Per-Entry Feedback

### Entry 1: Step 3.5 Flash — "Cockpit"
**Strengths:** Cleanest mental model. "Is everything okay?" is the fundamental question. The health ring + card grid + mission log is a solid, scannable layout. Low implementation cost.

**Gaps:**
- Passive. No action layer — you see the problem, then switch to a different tool to fix it.
- Card grid is 1:1 with sandboxes. Doesn't scale beyond ~9 sandboxes (terminal real estate).
- Mission log is just a log. Could be smarter — deduplicate noise, surface signal.

**Feasibility:** ⭐⭐⭐⭐⭐ (1-2 sessions, almost pure UI on existing data)

---

### Entry 2: MiMo V2.5 — "Command Center" *(Winner)*
**Strengths:** Cross-sandbox reasoning, explicit action queue, escalation path visualization, budget projection. Answers "what do I decide?" not "what's happening?"

**Gaps:**
- Dependency graph and escalation paths require historical data that may not exist yet (dispatch history depth).
- Heatmap visualization in terminal is non-trivial — needs careful character-set rendering.
- 6-9 hours estimate is optimistic for a first pass with clean architecture.

**Feasibility:** ⭐⭐⭐⭐ (3-4 sessions for v1, 6-9 for full feature set)

---

### Entry 3: MiMo V2.5 Pro — "Code Intelligence"
**Strengths:** Risk radar (complexity × change frequency × test coverage) is genuinely insightful. The mode-tab system (Health/Complexity/Deps/Build/Sessions) gives depth without clutter.

**Gaps:**
- Over-indexed on code health. Most operators care about *army health*, not cyclomatic complexity, most of the time.
- Requires `radon` (external dependency) and AST parsing — adds install friction.
- Build health matrix assumes CI/CD integration that may not exist yet.
- "7 days" estimate is realistic — this is a separate product, not a viewport enhancement.

**Feasibility:** ⭐⭐ (7 days, high complexity, new collectors, external deps)

**Verdict:** This is v3 or a separate "tech-lead mode." Ship it later.

---

### Entry 4: DeepSeek V4 Flash — "Diagnostic Console"
**Strengths:** Code flow graph is the best visual in the competition. Error pattern clustering (hash-based dedup) is a genuinely useful idea — you don't want 50 copies of the same traceback. Anomaly trails (divergence from baseline) is smart.

**Gaps:**
- Graph rendering in terminal is the hardest UI problem in the set. Needs a layout engine.
- "Intelligent tactical suggestions" is hand-wavy — what's the inference mechanism?
- History baselines require 15+ cycles of data before it's useful.
- Error fingerprinting needs stable stack traces (not guaranteed with subprocess-based soldiers).

**Feasibility:** ⭐⭐⭐ (3-5 sessions, but graph layout is a rabbit hole)

---

### Entry 5: MiniMax M2.7 — "Knowledge Ops Center"
**Strengths:** Information lifecycle view (Input → Processing → Output) is a fresh angle. Knowledge gap tracker ("?" bubbles) is cute and useful. Archive trail gives closure on completed work.

**Gaps:**
- Relies on `~/.hero/knowledge/`, `~/.hero/gaps/`, `~/.hero/archive/` — directory conventions that don't exist yet.
- Documentation density is a vanity metric — high density doesn't mean *useful* documentation.
- Three-lane river is pretty but space-inefficient for narrow terminals.

**Feasibility:** ⭐⭐⭐⭐ (2-3 sessions if directories exist; 1 extra session to create them)

---

### Entry 6: Step 3.6 — "Velocity Center"
**Strengths:** NOW feed is genuinely addictive — real-time event stream with color coding. Delta strip (change since last refresh) is a simple idea with high utility. Acceleration metrics ("ACCELERATING / DECELERATING / CRITICAL VELOCITY") are emotionally resonant.

**Gaps:**
- Velocity without context is misleading — fast ≠ healthy.
- History buffer (30 cycles JSONL) needs to be implemented first — this is a new infra requirement.
- Sparklines in pure terminal are fiddly (unicode block characters, alignment).
- "Threshold watchers" needs configurable thresholds — more UI surface.

**Feasibility:** ⭐⭐⭐ (3-4 sessions, history infra first)

---

### Entry 7: Mashal — "Command Hierarchy Tree"
**Strengths:** Box-drawing tree showing the actual command chain (USER → COMM → LEAD → ARCH → SOLDIERS → VERIFY → ARCHIVIST) is *the* canonical view. Error forking as retry branches is visually intuitive. Tab to jump pipelines is a great navigation pattern.

**Gaps:**
- Tree is hard to navigate with `↑↓` when it's deep (more than ~15 nodes).
- Fixed-width boxes don't handle long sandbox names or multi-line task descriptions.
- No summary layer — you see every node, which is noise at scale.
- Tree layout algorithm (vertical with box drawing) is medium-hard in terminal.

**Feasibility:** ⭐⭐⭐⭐ (2-3 sessions)

**Personal note:** This is my second-favorite concept. It's the viewport that best represents *what HERO actually is* — a command hierarchy, not a resource dashboard.

---

## 3. What They ALL Missed

These seven entries are strong, but every single one optimizes for **passive consumption**. None of them built an explicit **compaction layer** for when the operator has been away for 4 hours and comes back to 800 events.

### Missing: Compaction / Summarization

**The problem:** The NOW feed (Step 3.6), Mission Log (Step 3.5), and Activity Stream (everyone) will become unreadable after 30 minutes of active army work. An operator returning from lunch needs a summary, not a replay.

**What's needed:**
- **Session compaction** — "Last 2 hours: 3 sandboxes spawned, 2 errors (both recovered), 1 pipeline completed, budget at 62%."
- **Significant event extraction** — not every tool call, just state changes (spawn, finish, error, kill, escalation).
- **Drill-back** — compacted view expands on demand to show the underlying stream.

None of the entries mention this. It's table stakes for an operator-facing tool.

### Missing: Goal / Mission Layer

Every entry asks "is the army healthy?" or "what's happening?" — zero entries ask "are we making progress toward the actual goal?"

**What's needed:**
- Top-of-viewport banner: current objective / target / deadline
- Progress bar or indicator toward that objective
- Blocker detection: "You told LEAD to research X. It's been 45 minutes. Nothing has been written to ~/.hero/knowledge/. Is it stuck?"

This connects the viewport to *why the army exists*, not just *that it exists*.

### Missing: Sandbox Lifecycle State Machine

All entries sandbox status as a binary or 3-state (idle/running/error). But a sandbox goes through states:

```
SPAWNING → BOOTING → WORKING → BLOCKED → COMPLETING → ARCHIVING → DEAD
```

A viewport that shows "running" for a sandbox that's been running for 20 minutes with zero tool calls is misleading. You need **stuck detection** — same status + no tool calls for N cycles = BLOCKED, not RUNNING.

Only MiMo V2.5 touches this with "stalled pipeline" detection, but it's implicit, not a first-class state.

### Missing: Budget as a First-Class Concern

Step 3.5's health ring is green/yellow/red. But *why* is it yellow? Budget? Errors? Idle sandboxes? The ring conflates orthogonal concerns.

**What's needed:**
- Separate budget bar (token burn rate, cost projection, exhaustion ETA)
- Separate error count
- Separate idle count
- Aggregate "health" as a derived metric, not the source of truth

MiMo V2.5 has budget projection, but buries it in the Resource Map. It should be always-visible.

### Missing: The "What Changed Since I Left" View

This is related to compaction but different: when you open the viewport after being away, the first thing you want to know is *what's different*. Not a full replay — just the delta.

A "Since last view" banner with:
- New sandboxes spawned
- Sandboxes that finished or died
- New errors (count)
- Budget delta

None of the entries include this. It's a 30-line addition to any entry.

---

## 4. Recommendation: What to Build for v2

### The Combination: MiMo V2.5 + Mashal's Tree + Step 3.5 Health Ring

**Rationale:**
- **MiMo V2.5** gives you the action layer and cross-sandbox intelligence (the brain).
- **Mashal's Tree** gives you the structural truth of the command hierarchy (the skeleton).
- **Step 3.5 Health Ring** gives you the instant "is everything okay?" pulse (the heartbeat).

You want **three viewport modes**, not one monolith:

| Mode | Source | Use Case |
|------|--------|----------|
| **Command** | Mashal's Tree | "Who's doing what, what's the chain?" |
| **Situation** | MiMo V2.5 | "What needs my decision?" |
| **Pulse** | Step 3.5 Ring | "Is everything okay?" (quick glance) |

### Implementation Order

**Phase 1 — Foundation (1-2 sessions)**
1. Compaction/summarization layer (session delta, significant events)
2. Stuck detection (state machine: SPAWNING/BOOTING/WORKING/BLOCKED/COMPLETING/ARCHIVING/DEAD)
3. "Since last view" delta banner

These are infrastructure that all three modes depend on. Do these first.

**Phase 2 — Mashal's Tree (1 session)**
4. Tree rendering (box-drawing, collapse/expand)
5. Per-node status coloring
6. Error branch visualization
7. Tab to switch pipelines

The tree is the simplest visual to get right and gives immediate structural clarity.

**Phase 3 — MiMo V2.5 Core (2 sessions)**
8. Three-zone layout (Intelligence / Resource Map / Action Queue)
9. Cross-sandbox bottleneck detection (token choke, model contention)
10. Budget projection with exhaustion ETA
11. Quick action panel (auto-retry, model swap, kill, pause)

This is the main event. Start with zone 1 (Intelligence) since it's highest-utility.

**Phase 4 — Health Ring + Goal Layer (1 session)**
12. Top-of-viewport health ring (separate bars for budget/errors/idle, aggregate health score)
13. Mission/objective banner at very top
14. Goal progress indicator

**Phase 5 — Polish and Integration (1 session)**
15. Mode switching (Tab to cycle: Command → Situation → Pulse)
16. Keyboard mode-aware navigation
17. Color consistency across modes
18. Compact mode for narrow terminals

### What to Explicitly NOT Build in v2

- **DeepSeek's code flow graph** — graph layout is a research project. Put it in v3.
- **MiMo V2.5 Pro's complexity heatmap** — requires external tools (`radon`), separate data pipeline.
- **MiniMax's knowledge river** — relies on directory conventions that don't exist. Revisit after knowledge management infra is built.
- **Step 3.6's velocity sparklines** — requires 30-cycle history buffer. Add after compaction is stable.

### The v2 Philosophy

**One viewport, three lenses:**
- **Command** (tree) — structural truth
- **Situation** (MiMo) — decision intelligence  
- **Pulse** (ring) — instant health

All three share the same compaction layer, stuck detection, and budget tracking. The operator switches lenses based on what question they're asking.

This is better than any single entry because it acknowledges that *different questions require different visualizations*. A tree is great for "who's involved" but terrible for "where's the bottleneck." A heatmap is great for "what's hot" but terrible for "what should I do."

Build the three modes. Keep them simple. Connect them with shared state. Ship fast.

---

## Appendix: Quick Ranking

| Rank | Entry | Score | Notes |
|------|-------|-------|-------|
| 1 | MiMo V2.5 | 9/10 | Best decision intelligence, action layer |
| 2 | Mashal's Tree | 8.5/10 | Best structural truth, clean concept |
| 3 | Step 3.5 Cockpit | 7.5/10 | Cleanest baseline, needs action |
| 4 | Step 3.6 Velocity | 7/10 | Best real-time feel, needs context |
| 5 | DeepSeek Graph | 6.5/10 | Best visual, hardest to build |
| 6 | MiniMax Knowledge | 6/10 | Good concept, infra-dependent |
| 7 | MiMo V2.5 Pro | 5/10 | Best analysis, wrong scope for viewport |

**Winner's margin:** MiMo V2.5 wins on *actionability*. Every other entry tells you what's happening. MiMo V2.5 tells you what to do about it. In an operator tool, that's the difference between monitoring and commanding.

---

*Review by Kimi K2.6 — long-context analysis, synthesis over speed.*
