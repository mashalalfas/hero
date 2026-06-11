# HERO Viewport — Model Competition: All Entries

> Compiled for Kimi K2.6 review and feedback.
> Each model submitted their own unique vision for taking `hero viewport` to the next level.

---

## Entry 1: Step 3.5 Flash (Communicator) — `improvement_plan_step35.md`

**Role:** Always-on, user-facing. Clarity. Context. Calm.

**One-sentence pitch:** A command-center cockpit that tells you the army's full story in one glance — health ring on top, at-a-glance sandbox grid in the middle, and a real-time mission log at the bottom.

**Visual paradigm:** Three-layer cockpit layout:
1. **Health Ring** (top) — donut-style army pulse, green/yellow/red with center stats
2. **Sandbox Card Grid** (middle) — each sandbox is a self-contained card (name, status, model, token bar %, tool calls, task description)
3. **Mission Log** (bottom) — scrolling time-ordered event feed from dispatch files

**Key features:**
- Army health ring — answer "is everything okay?" in 200ms
- Card grid — richer per-sandbox display than flat table
- Mission log — the "what just happened" layer
- Detail drill-down on Enter — full sandbox detail with recent tool calls
- Three-tier keyboard: default / detail / log filter
- Health overlay on `[h]` key

**Keyboard:** `1-9` focus, `Enter` drill, `l` toggle log, `f` filter, `h` health, `r` refresh, `q` quit

---

## Entry 2: MiMo V2.5 (Lead) — `improvement_plan_mimov25.md`

**Role:** Orchestrator — 1M context, cross-sandbox intelligence.

**One-sentence pitch:** A Command Center viewport that surfaces system-level intelligence — cross-sandbox bottlenecks, resource conflicts, escalation paths, and pipeline health.

**Visual paradigm:** Three-zone situation room:
1. **Intelligence Zone** (left) — "What's wrong right now?" Bottlenecks, failures, stalled pipelines, error cascades
2. **Resource Map** (center) — "Where is everything going?" Token allocation heatmap, model contention, cost projections
3. **Action Queue** (right) — "What do I need to decide?" Pending escalations, suggested model swaps, dependency blocks

**Key features:**
- Cross-sandbox bottleneck detection (token choke, model contention, pipeline stall)
- Escalation path visualization (failed → retry → escalation chain)
- Resource allocation heatmap (per-model token distribution)
- Dependency chain awareness (sandbox waiting-on graphs)
- Budget projection (ETA to exhaustion per sandbox)
- Quick action panel (auto-retry, model swap, pause, kill)

**New data sources:** Git status, dispatch history, model cost registry, dependency graph, escalation log

**Keyboard:** `Tab` cycle zones, `Enter` act, `a` auto-retry, `m` model swap, `k` kill, `p` pause, `f` filter, `h` history, `/` search

**Total estimate:** 6-9 hours implementation

---

## Entry 3: MiMo V2.5 Pro (Architect) — `improvement_plan_mimov25pro.md`

**Role:** Deep code reasoning, specs, architecture.

**One-sentence pitch:** A Code Intelligence Command Center that turns the viewport from a resource monitor into a technical lead's brain — showing complexity heatmaps, dependency risk, build health, and refactoring signals.

**Visual paradigm:** Three-column responsive grid with mode tabs:
1. **Risk Radar** — composite risk score = complexity × change_frequency × (1/test_coverage)
2. **Complexity Heatmap** — per-file cyclomatic complexity with change frequency
3. **Dependency Graph** — ASCII import graph with circular dependency detection

**Mode tabs (keyboard-switchable):**
- Health (1) — default: risk radar + build status + telemetry
- Complexity (2) — full-screen complexity heatmap
- Deps (3) — full-screen dependency graph
- Build (4) — CI/CD matrix + test history
- Sessions (5) — per-sandbox telemetry + token efficiency

**Key features:**
- Risk radar — ranked list of riskiest modules across all sandboxes
- Complexity heatmap — per-file cyclomatic complexity (via `radon` or AST)
- Dependency graph — Python import analysis, circular dep detection
- Build health matrix — last build, test count, coverage, flaky tests
- Session telemetry — tokens/min, efficiency %, trend indicators
- Responsive layout — 3-col/2-col/1-col based on terminal width

**New data sources:** Python `ast` (stdlib), git log, optional `radon` package, dispatch output parsing

**Architecture:** New `ComplexityCollector`, `DependencyCollector`, `BuildHealthCollector`, `TelemetryCollector` following existing pattern

---

## Entry 4: DeepSeek V4 Flash (Soldier/Deep Worker) — `improvement_plan_deepseek.md`

**Role:** Deep worker — 200k context, code flow visualization, error analysis.

**One-sentence pitch:** A Diagnostic Control Room that watches the army's execution fabric, clusters failure modes, surfaces hotpaths, and suggests tactical corrections.

**Visual paradigm:** Graph heatmap — nodes are soldiers/sandboxes/tasks, edges are call dependencies and state transfers, color is health.

**Key features:**
- Code Flow Graph — live army topology; shows shape of work, not just state
- Error Pattern Clustering — error dedup by stack-trace fingerprint, trend indicators, root cause hypothesis
- Bottleneck Radar — token rate, dispatch queue depth, soldier wait time, I/O stall detection
- Intelligent Tactical Suggestions — one-line corrections based on observed patterns
- Anomaly Trails — divergence from historical baseline with delta badge

**New data sources:** Soldier stdout/stderr error fingerprints (hashed stack traces), timing metadata, history baselines

**Keyboard:** `g` toggle graph layout, `e` error clusters, `b` bottleneck radar, `s` suggestions, `Enter` drill node, `Tab` cycle sandboxes

---

## Entry 5: MiniMax M2.7 (Researcher/Archivist) — `improvement_plan_minimax.md`

**Role:** Research, documentation, knowledge management.

**One-sentence pitch:** A Knowledge Operations Center showing information flow through the army — what's been documented, what's been learned, research threads in flight, knowledge gaps, and the archival trail.

**Visual paradigm:** Three-lane river diagram showing information lifecycle:
1. **Input Lane** (left) — requests, inboxes, backlog
2. **Processing Lane** (center) — active research threads, soldiers working, LEAD/ARCH decomposition
3. **Output Lane** (right) — completed docs, archived specs, verified outputs

**Key features:**
- Three-lane information flow — input → processing → output
- Knowledge Gap Tracker — "?" bubbles for missing info, "✓" when filled
- Research Thread Timeline — per-thread progress with sub-steps
- Documentation Density Indicators — doc/specs vs work done per sandbox
- Archive Trail — scrolling history of completed deliverables

**New data sources:** `~/.hero/knowledge/`, `~/.hero/gaps/`, `~/.hero/archive/`, git status

**Keyboard:** `←→` lanes, `↑↓` navigate, `Enter` drill, `/` search, `g` gaps overlay, `d` doc density, `t` timeline view

---

## Entry 6: Step 3.6 (Fast Worker) — `improvement_plan_step36.md`

**Role:** Fast, newer model — velocity and real-time motion focus.

**One-sentence pitch:** A velocity-centric command center showing the HERO army as a live, breathing organism — tracking what's accelerating, decelerating, and crossing thresholds in real time.

**Visual paradigm:** Multi-pane velocity dashboard:
1. **NOW Feed** (top) — real-time activity stream, events color-coded by type
2. **Delta Strip** — per-sandbox change detection since last refresh
3. **Velocity Graph** — sparkline trend view (tokens/min over 60s)
4. **Acceleration Metrics** — ranked velocity multiplier (baseline vs current)
5. **Threshold Watchers** — event-based alerts when thresholds are crossed

**Key features:**
- NOW Feed — scrolling stream of spawn/tool_call/status_flip/budget_delta events
- Delta Strip — per-sandbox magnitude of change with direction arrows
- Velocity Graph — time-series sparkline, color-coded by sandbox
- Acceleration metrics — multiplier vs baseline (ACCELERATING/DECELERATING/CRITICAL VELOCITY)
- Threshold Watchers — notifications for threshold crossings, model switches, bursts
- Compact mode — 3-line overview for narrow terminals

**New data sources:** History buffer (JSONL, 30 cycles), event stream from diff engine, baseline window (15 cycles), optional git/CI status

**Keyboard:** `s` toggle stream/compact, `p` pause refresh, `t` toggle threshold pane, `e` error filter, `v` toggle graph style, `Enter` drill

---

## Supplementary: Mashal's Tree Concept — `Ideas_by_me.md`

**Concept:** Command hierarchy tree — work flowing from USER → COMM → LEAD → ARCH → SOLDIERS → VERIFY → ARCHIVIST → COMM, with error forking.

**Visual:** Vertical tree with box-drawing characters, each node is a fixed-width box with role/status/model. Errors sprout retry branches naturally. Multiple pipelines as sibling root trees.

**Keyboard:** `↑↓` navigate, `←→` collapse/expand, `Enter` drill, `/` search, `Tab` jump pipelines, `e` error-only toggle

---

## Comparison Matrix

| Model | Concept | Core Question | Target User | Visual Style | Data Complexity | Implementation |
|-------|---------|---------------|-------------|--------------|----------------|----------------|
| Step 3.5 | Cockpit | "Is everything okay?" | Operator | 3-layer stacked | Low | 1-2 sessions |
| MiMo V2.5 | Situation Room | "What needs my decision?" | Commander | 3-zone split | Medium | 6-9 hours |
| MiMo V2.5 Pro | Code Intel | "Is the code healthy?" | Tech Lead | Multi-tab responsive | Medium-High | 7 days |
| DeepSeek | Diagnostic Console | "What's the root cause?" | Debugger | Graph heatmap | Medium | 3-5 sessions |
| MiniMax | Knowledge Ops | "What do we know?" | Researcher | 3-lane river | Low-Medium | 2-3 sessions |
| Step 3.6 | Velocity Center | "What's accelerating?" | Real-time operator | Multi-pane stream | Medium | 3-4 sessions |
| **Mashal (Tree)** | Command Hierarchy | "Who's doing what?" | Manager | Vertical tree | Low-Medium | 2-3 sessions |
