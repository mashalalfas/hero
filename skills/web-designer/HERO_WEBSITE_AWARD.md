# HERO System Website — Award-Winning Concept
**Council convened:** 2026-06-19
**Inspiration:** Exebenus (exebenus.com) — dark dashboard aesthetic, data-as-visual, "Two Futures" split-screen narrative
**Council members:** Analyst (Kimi K2.6), Reasoner (MiniMax M3), Deep Thinker (MiMo V2.5 Pro)

---

## Section 1: Core Concept

Exebenus proves that an industrial dashboard can be an award-winning brand statement — because the data *is* the design. Every counter, every status bar, every percentage IS the hero image. No fake screenshots, no mockups. The product *is* the interface.

HERO is an agent orchestrator — a command-and-control deck for AI armies. The core metaphor: **a mission control center for your AI workforce.** Instead of a drilling rig with "With Spotter vs Without Spotter," HERO shows "With Orchestration vs Without" — the same codebase, the same deadline, but diverging outcomes based on whether you have an automated agent army. The data elements shift from drilling metrics (ROP, stuck hours, $ lost) to developer metrics (token consumption, build time, agent throughput, failure rate, context utilization). The "Two Futures" split maps perfectly: same task, two pipelines; same team, two efficiencies; same deadline, two deliveries.

---

## Section 2: Three Concepts

### Concept A: Two Pipelines — The Agent Factory Floor

- **Vibe:** Industrial ops / mission-critical
- **One-liner:** "Same codebase. Two pipelines. Entirely different outcomes."
- **Hero:** A platform boot screen — top-left, a pulsing "HUB STATUS" indicator (green/amber/red). Center-screen, a live counter reading `21 ACTIVE SANDBOXES` that increments like a factory production tally. Below it, a scrolling log feed that streams soldier outputs in real-time — but too fast to read, just enough to feel the *machine running*.
- **The "Two Futures" split:** A horizontal split card directly below the hero. Left side: **"Manual" (without HERO).** Right side: **"Orchestrated" (with HERO).** Both show the same task — "Refactor user authentication module across 3 microservices." Left column: `5 agents, 47 min, 128K tokens consumed, 12% error rate`. Right column: `14 agents, 12 min, 64K tokens consumed, 2% error rate`. Each metric card glows dim red on the left, bright green on the right. A central divider line animates with a subtle neon pulse.
- **Key sections:**
  - **Pipeline Stage Status** — 5 horizontal progress bars (Navigate, Build, Harden, Verify, Archive), each showing a percentage and agent count for the current stage. The active stage bar pulses with a scan-line glow.
  - **Token Economy Dashboard** — A live area chart showing tokens consumed across all active sandboxes. A counter below reads `TOKENS SAVED: 1,847,203` with a green caret arrow ticking upward every few seconds. A secondary meter shows `CONTEXT UTILIZATION: 87%` — the efficiency of TOON compression.
  - **Circuit Breaker Panel** — Three small cards showing: `TRIPS: 0` (green), `QUARANTINES: 2` (amber), `DLQ DEPTH: 5` (amber). If any red numbers appear, the card border glows red. Uses the same "risk indicator" language as Exebenus's "Stuck Pipe" / "On Pace" status badges.
  - **Soldier Roster** — A horizontal scrolling table of active soldiers. Each row: `sandbox-name | status (live bar) | task-preview (truncated) | token: $budget_spent / $total | duration`. The table is cut off at 5 visible rows with a `+16 more` overflow indicator — classic dashboard density.
  - **Deadline Countdown** — `SPRINT DEADLINE: 4D 11H 23M`. A circular radial progress gauge around it showing percent of sprint elapsed. Color shifts from green → amber → red as deadline approaches.

- **Soldier task split:** (5 pieces, each ≤15K tokens)
  1. Hero platform screen + hub status indicator + live sandbox counter + scrolling log feed (HTML+CSS+JS animation)
  2. "Two Futures" split-screen comparison card with data counters and glow effects
  3. Pipeline stage progress bars with scan-line animation + Circuit Breaker panel
  4. Token Economy live chart (canvas/SVG) + TOON savings counter
  5. Soldier roster table + Deadline countdown radial gauge + navigation shell

---

### Concept B: The Fleet Command — Real-Time Agent Ops Center

- **Vibe:** Strategic command / live ops
- **One-liner:** "Your AI army. One command deck."
- **Hero:** A top nav bar with `FLEET STATUS: 21/21 ONLINE` — each dot is a live sandbox indicator, green when active, grey when idle, red when quarantined. Below it, the entire hero area is a **live agent grid**: 3×4 cards of miniature agent statues, each with a small waveform animation showing it's thinking. Below the grid, a single bold stat: `47 AGENTS DEPLOYED TODAY | 0 ERRORS | 100.0% UPTIME`. No logo needed — the fleet IS the brand.
- **The "Two Futures" split:** Named **"Before HERO / After HERO"** — a toggle switch, not a static split. User toggles between two states of the SAME dashboard. "Before" view: all lights red, circuit breaker tripped, DLQ overflowing, agents spinning in place with error halos. "After" view: same grid positions, but green, flowing, with real task progress. The toggle is a neon slider that arcs with electricity on switch. Data underneath shows the difference: `RECOVERY TIME: 3s vs 14min | THROUGHPUT: 12x | TOKEN COST: -62%`.
- **Key sections:**
  - **Deploy Pipeline** — A horizontal timeline with 5 nodes (Navigate → Build → Harden → Verify → Archive). Each node shows how many sandboxes are currently at that stage as a glowing number. Connecting lines are progress bars with particle flow animation (small dots moving along the line).
  - **Agent Health Matrix** — A 4×4 grid of status tiles. Each tile shows one sandbox: a mini sparkline (10s rolling window of agent activity), a status badge (Active / Hibernating / Quarantined / Completed), and tokens used. Bad tiles get a red left border + pulsing exclamation. Good tiles get a green left border + checkmark.
  - **DLQ Console** — A live feed of failed tasks. Each entry: `sandbox-id | task-name | FAILED x3 | auto-quarantine in 4s → [QUARANTINED]`. Entries auto-dismiss after 5 seconds, creating ambient motion. A counter at top: `DLQ: 3 PENDING | 12 RESOLVED TODAY`.
  - **Budget Burn Rate** — A dual-axis gauge. Left: `TEAM TOKEN BUDGET $1,847 / $10,000`. Right: `BURN RATE: 347 tok/min`. The gauge is a vertical bar that fills from bottom, with the fill color gradient shifting from green to amber to red as budget depletes.
  - **Performance Delta** — A before/after comparison in one card. A bar chart with two bars per metric: "Manual" (grey, translucent) vs "With HERO" (bright cyan). Metrics: Build Time (-68%), Token Cost (-52%), Error Rate (-91%), Agent Utilization (+215%).

- **Soldier task split:** (6 pieces, each ≤15K tokens)
  1. Fleet status top bar with live sandbox dots + hero agent grid with waveform animations
  2. "Before HERO / After HERO" toggle switch with full dashboard restyle and delta data
  3. Deploy Pipeline horizontal timeline with particle flow animation + node counters
  4. Agent Health Matrix (4×4 grid) with sparklines and status tiles
  5. DLQ Console live feed with auto-dismiss entries + Budget Burn Rate vertical gauge
  6. Performance Delta comparison bar chart + global CSS theme (dark base, neon accents)

---

### Concept C: Deadline Drive — The Time-Critical Narrative

- **Vibe:** Race against time / sprint urgency
- **One-liner:** "Same deadline. Two results. One HERO."
- **Hero:** A full-screen **clock face** — not analog, but a massive radial progress ring with `SPRINT D-4` in the center. The ring fills clockwise, colored green at start, amber at midpoint, red at the end. Below it, a rotating set of punchlines: `"Ship 21 projects in parallel"` → `"Zero manual handoffs"` → `"Your team, 6x faster"`. Each fades in/out every 3 seconds. Around the clock, four counter widgets sit at the compass points: `AGENTS: 47`, `BUILDS: 213`, `TOKENS: 1.8M`, `ERRORS: 0`.
- **The "Two Futures" split:** A **Gantt chart split-screen**. Same project timeline (6-week sprint), two lanes. Top lane: **"Without HERO"** — tasks overlap chaotically, dependencies block, deadlines slip with red warning lines extending past the finish. Bottom lane: **"With HERO"** — tasks cleanly parallelized, dependencies auto-resolved, all finish before the vertical "NOW" marker with green checkmarks. A delta counter between the lanes: `SCHEDULE SAVED: 11 DAYS | PARALLELISM: 8.4x | BLOCKERS AVOIDED: 14`.
- **Key sections:**
  - **Sprint Velocity Dashboard** — A live histogram showing story points completed per day. Two overlaid lines: actual velocity (neon cyan) vs projected velocity (dashed grey). As actual stays above projection, the area under the curve fills green. If it dips below, it fills red. A stat below: `VELOCITY: 47 pts/day | +215% vs manual`.
  - **Parallelism Heatmap** — A 24-hour grid (rows = sandboxes, columns = hours). Green cells = agent actively working, grey = idle, red = blocked. The "Without HERO" version would be almost all grey/red. "With HERO" shows dense green. A small inset shows the delta as a single number: `IDLE TIME REDUCTION: 78%`. This one data visual tells the entire story.
  - **Blocker Board** — Three cards showing the current top blockers, styled like error alerts. Each shows: `blocker-type | sandbox | auto-resolved? | time-to-resolve`. These cycle in from a live queue, creating a sense of real-time incident management. Total counter: `BLOCKERS TODAY: 3 | AUTO-RESOLVED: 3 | MANUAL: 0`.
  - **Deadline Probability Meter** — A vertical gauge labeled `ON-TIME PROBABILITY`. The needle swings between 0-100%. Base state shows `94%` (with HERO). A ghost needle behind it shows `23%` (without HERO). The gauge has zones: red (0-50%), amber (50-80%), green (80-100%). The needle gently wobbles, giving it that real-algorithm feel.
  - **Retrospective Snapshot** — A compact card showing end-of-sprint stats, formatted as a final report card: `SHIPPED: 21/21 projects | ON TIME: 100% | OVERTIME: 0 hrs | BUDGET: 82% used | TEAM SATISFACTION: +63%`. This loads last so the user scrolls to feel the win.

- **Soldier task split:** (6 pieces, each ≤15K tokens)
  1. Full-screen sprint clock with radial ring + rotating punchlines + 4 compass counter widgets
  2. "Two Futures" Gantt chart split-screen with delta counter (chaos vs clean parallelism)
  3. Sprint Velocity histogram with overlaid actual/projected lines and fill animation
  4. Parallelism Heatmap 24-hour grid with green/grey/red cells + idle time delta
  5. Blocker Board live cards + Deadline Probability Meter with ghost needle
  6. Retrospective Snapshot card + page layout shell + scroll-triggered animation orchestration

---

## Section 3: Council Verdict

**Verdict: UNANIMOUS — Concept A ("Two Pipelines") wins the build.**

**Rationale from each council member:**

- **Analyst (Kimi K2.6):** "Concept A has the strongest visual hook. The factory-floor dashboard with live sandbox counters and pipeline progress bars creates immediate recognition — this is a *system* that runs. The split-screen Comparison Card is the cleanest translation of Exebenus's signature narrative device. Users will see '14 agents, 12 min, 2% error rate' vs '5 agents, 47 min, 12%' and *feel* the value proposition before reading a single headline."

- **Reasoner (MiniMax M3):** "Concept A's information architecture is the most defensible. Each section maps to a clear developer concern: pipeline progression → 'is it working?', token economy → 'is it efficient?', circuit breaker → 'is it reliable?', soldier roster → 'who's working?', deadline countdown → 'will we ship?'. This narrative arc is scannable in under 3 seconds. Concept B is a close second but risks overwhelming first-time visitors with information density. Concept C is brilliant for late-stage prospects but too narrow for the hero — time pressure isn't the universal first impression."

- **Deep Thinker (MiMo V2.5 Pro):** "Concept A has the best edge-case coverage. It works for all three visitor personas: (1) the CTO looking for ROI — sees token savings and build time reduction; (2) the developer evaluating tooling — sees pipeline stages and agent roster; (3) the ops engineer — sees circuit breaker and DLQ. It also accommodates the largest range of visitor states: fast-scrolling mobile (big numbers, minimal copy), deeply-investigating desktop (drill-down charts), and presentation-mode (split-screen as demo piece). Build this first. Concept B's fleet map can be the 'Projects' page. Concept C's sprint clock can be the 'Demo' interactive. But Concept A is the home page."

---

## Section 4: Recommended MVP

**Build Concept A — "Two Pipelines" — in 6 pieces, each ≤15K tokens.**

### Build Order

| Phase | Piece | Description | Visual Elements | Tokens Est. |
|-------|-------|-------------|-----------------|-------------|
| 1 | **Shell + Hero** | Full-page dark shell with top nav. HUB STATUS indicator (green pulse when active). `21 ACTIVE SANDBOXES` counter with increment animation. Streaming log feed with typewriter-style scroll | Gradient dark background `#0a0a0f`, thin neon border `#00ffcc`, monospace font, scan-line overlay on hero | ~12K |
| 2 | **"Two Futures" Split Card** | Horizontal comparison card. Left: Manual (red-tinted), Right: HER0 (green-tinted). Data counters: agent count, duration, tokens consumed, error rate. Central animated divider line | Card with `#1a1a2e` bg, `#ff3355` / `#00ffcc` accent glows, counters with number roll animation, `--split` CSS property for divider pulse | ~14K |
| 3 | **Pipeline Stage Bars** | 5 horizontal progress bars (Navigate, Build, Harden, Verify, Archive). Active stage pulses with neon scan-line. Percentage + agent count per stage | Bar with gradient fill, `#00ffcc` scan-line animation, `::after` particle dots, stage labels in mono uppercase | ~10K |
| 4 | **Token Economy + Circuit Breaker** | Area chart (rolling window of token consumption) with `TOKENS SAVED` counter and `CONTEXT UTILIZATION` gauge. Three circuit breaker cards (Trips, Quarantines, DLQ depth) with border color states | Canvas/SVG chart, counter with increment-on-intersect, gauge radial or horizontal, card color states via CSS `:has(.status-red)` | ~15K |
| 5 | **Soldier Roster Table** | Horizontal scrollable table: sandbox name, status bar, task preview (truncated), token budget, duration. 5 visible rows + "+N more" overflow indicator. Status bars as thin animated fill lines | Table with `#12121a` row bg alternating, status bar as `<div>` width=progress, truncation with gradient fade | ~11K |
| 6 | **Deadline Countdown + Integration** | Radial circular gauge with `SPRINT DEADLINE: 4D 11H 23M` in center. Color transition green→amber→red as deadline nears. Stitch all 6 pieces into one scrollable page with scroll-triggered animation entry | SVG radial ring with `stroke-dashoffset`, `countdown` interval, `IntersectionObserver` for scroll-triggered counters | ~13K |

### Implementation Notes
- All counters use `requestAnimationFrame` with `IntersectionObserver` — only animate when in viewport
- Data values are REPLACEABLE via a single `window.HERO_DATA` JS object — makes demo-mode trivial
- Dark base: `#0a0a0f` body, card surfaces `#12121a` / `#1a1a2e`, text `#e0e0e0` primary / `#808090` secondary
- Font stack: `'JetBrains Mono', 'Fira Code', monospace` for all data; `Inter, system-ui, sans-serif` for headings
- All animations use `prefers-reduced-motion: no-preference` guard
- No external dependencies — pure HTML + CSS + vanilla JS in a single file per piece

---

## Section 5: Color Palette (Exebenus-inspired)

| Role | Hex | Usage | Example |
|------|-----|-------|---------|
| **Dark base** | `#0a0a0f` | Body background, the "void" of the dashboard | The entire page canvas |
| **Surface** | `#12121a` | Card backgrounds, table rows, panel surfaces | All dashboard cards and status panels |
| **Surface raised** | `#1a1a2e` | Elevated panels, hover states, active cards | The split comparison card, active circuit breaker |
| **Surface border** | `#252540` | Subtle card borders, divider lines | Card outlines, table row separators |
| **Primary accent — Cyan** | `#00ffcc` | Success, active, HERO side of split, pipeline progress | HERO-side metrics, healthy indicators, TOON savings |
| **Alert — Amber** | `#ffb347` | Warning, non-critical issues, near-threshold | Quarantined agents, 75%+ token budget, amber deadline zone |
| **Danger — Red** | `#ff3355` | Failure, high risk, "Without HERO" side, critical alerts | Error counts, tripped breakers, red deadline zone |
| **Neutral accent** | `#7c7c9a` | Secondary text, inactive indicators, ghost values | Manual-side metrics (non-HERO), greyed status dots |
| **Code / mono** | `#a0a0f0` | Log feed text, code snippets, terminal output | The streaming log feed, CLI command displays |
| **Highlight** | `#ffffff` | Primary numbers, bold stats, headline emphasis | `21 ACTIVE SANDBOXES`, `TOKENS SAVED: 1,847,203` |

### Gradient Usage
- **Hero glow:** `radial-gradient(circle at 50% 30%, rgba(0, 255, 204, 0.03) 0%, transparent 70%)` — subtle cyan ambient glow behind hero
- **Progress fills:** `linear-gradient(90deg, #00ffcc, #00cc88)` — pipeline bar gradient, animated width
- **Danger fills:** `linear-gradient(90deg, #ff3355, #cc0033)` — failed states, error bars

---

## Section 6: Data Elements List

All live numbers, animated counters, and status indicators. These ARE the visual design — no screenshots, no stock imagery.

### Hero Section
| Element | Type | Example Value | Animation |
|---------|------|---------------|-----------|
| HUB STATUS indicator | Dot + label | `● ONLINE` | Pulse glow every 2s (green → brighter green) |
| Active sandbox counter | Number | `21` | Increments on sandbox join; initial count-up on page load |
| Sandbox unit label | Text | `ACTIVE SANDBOXES` | Static, uppercase, letter-spaced |
| Log feed lines | Scrolling text | `[sandbox-07] → Agent deployed: code-reviewer-3.7-flash` | Typewriter effect, 50ms per char, infinite scroll |
| Log feed speed | Sub-label | `FEED: 12 msgs/sec` | Static number, updates on interval |

### Two Futures Split Card
| Element | Type | Example Value | Animation |
|---------|------|---------------|-----------|
| Side label left | Text | `WITHOUT HERO` | Dim red glow persist |
| Side label right | Text | `WITH HERO` | Bright cyan glow persist |
| Agent count L | Number | `5` | Static (bad) |
| Agent count R | Number | `14` | Static (good, green) |
| Duration L | Duration | `47 min` | Static (bad) |
| Duration R | Duration | `12 min` | Static (good, green) |
| Tokens consumed L | Number | `128,000` | Static (bad) |
| Tokens consumed R | Number | `64,000` | Static (good, green) |
| Error rate L | Percentage | `12%` | Red pulsing border |
| Error rate R | Percentage | `2%` | Green steady border |
| Delta arrow | Icon | `↓68%` (cost) | Gentle bounce, repeating |
| Divider line | Line | Vertical separator | Neon glow wave traveling top→bottom continuously |
| Task label | Text | `"Refactor auth module — 3 microservices"` | Static, centered below counters |

### Pipeline Stage Bars
| Element | Type | Example Value | Animation |
|---------|------|---------------|-----------|
| Stage name (×5) | Text | `NAVIGATE` | Static, uppercase |
| Progress bar fill (×5) | Percentage width | `73%` | Width animates on enter, then gentle breathing pulse on active stage |
| Active stage indicator | Glow | Only one stage pulsing | Scan-line traveling L→R across the active bar |
| Agent count per stage | Number | `4 agents` | Static, updates when agents move stages |
| Stage completion label | Text | `COMPLETE` / `IN PROGRESS` / `PENDING` | Color-coded: green/green/amber, or grey |

### Token Economy
| Element | Type | Example Value | Animation |
|---------|------|---------------|-----------|
| Token savings counter | Number | `1,847,203` | Increments upward, ~200/s, slows on round numbers |
| Savings label | Text | `TOKENS SAVED` | Static |
| Savings arrow | Arrow icon | `↗` | Gentle upward float |
| Context utilization | Percentage | `87%` | Radial or horizontal fill, wobbles ±1% |
| Utilization label | Text | `CONTEXT UTILIZATION` | Static |
| Chart area | SVG/Canvas | Rolling 24h area chart | Dots appear with data entry, area fill animated |
| Chart Y-axis label | Text | `TOKENS (K)` | Static |

### Circuit Breaker Panel
| Element | Type | Example Value | Animation |
|---------|------|---------------|-----------|
| Trip counter | Number | `0` | Static green; on trip → flash red, increment |
| Trip status badge | Badge | `CLEAN` / `TRIPPED` | Normal glow / pulsing red |
| Quarantine count | Number | `2` | Static amber; on new → flash, increment |
| Quarantine status | Badge | `ISOLATED` | Amber steady glow |
| DLQ depth | Number | `5` | Static amber; decrements on resolve |
| DLQ status | Badge | `PENDING` / `DRAINING` | Amber / cycling blue |
| Card border | CSS border | Colored by worst status | Green/amber/red dynamic border |

### Soldier Roster Table
| Element | Type | Example Value | Animation |
|---------|------|---------------|-----------|
| Sandbox name | Text | `sandbox-07` | Static monospace |
| Status bar | Thin progress | `73% width` | Width animates + color gradient (red→amber→green) |
| Leader agent model | Text | `flash-3.7` | Static |
| Task preview | Text truncated | `"Refactor user auth..."` | Static with gradient fade on right edge |
| Token budget spent | Number | `$847 / $1,200` | Increments occasionally |
| Duration elapsed | Duration | `4m 12s` | Live HH:MM:SS timer per row |
| Overflow label | Text | `+16 more` | Fade-in on IntersectionObserver |

### Deadline Countdown
| Element | Type | Example Value | Animation |
|---------|------|---------------|-----------|
| Radial ring fill | SVG stroke | `stroke-dashoffset` based on % elapsed | Smooth continuous fill as time passes |
| Ring color | Gradient | Green → Amber → Red | Transition at 50% (amber) and 80% (red) |
| Central time | Duration | `4D 11H 23M` | Live countdown decrement |
| Days label | Text | `DAYS` | Static above time |
| Elapsed percentage | Percentage | `37%` | Static below time |
| Sprint label | Text | `SPRINT DEADLINE` | Static above ring |

### Ambient / Background Elements
| Element | Type | Description |
|---------|------|-------------|
| Scan-line overlay | CSS pseudo | Thin horizontal lines at 2px spacing, opacity 0.03, moving down slowly |
| Grid background | CSS | Subtle 1px grid at 40px spacing, opacity 0.02 |
| Corner glow | Radial gradient | One per quadrant of hero section, very subtle colored glow |
| Floating particle | CSS absolute | 3-5 tiny dots (2px) floating slowly in hero area, one per accent color |
| Neon border pulse | CSS animation | Card borders gently pulse between 0.5 opacity and 1.0 opacity over 4s |
| Counter shimmer | CSS | Large numbers have a subtle light trail at the leading edge on increment |

---

## Appendix: Exebenus → HERO Design Translation Map

| Exebenus Element | HERO Equivalent | Translation Note |
|-----------------|-----------------|------------------|
| Drilling rig status | HUB STATUS / sandbox fleet | "Rig" → "Sandbox" — both are units of work |
| "With Spotter / Without Spotter" | "With HERO / Without HERO" | Direct mapping — same comparison, different domain |
| ROP +33% (speed metric) | Build Time -68% (speed metric) | Both measure throughput improvement |
| $0 Lost (cost metric) | Tokens Saved (cost metric) | Replaced dollar value with token economy |
| Hours Behind (delay metric) | Duration difference (delay metric) | Same concept: how much time is saved |
| Stuck Pipe (failure state) | Circuit Tripped (failure state) | Both represent critical failures that halt operations |
| Recommendation (AI action) | Pipeline Stage (system action) | Both show what the system is doing right now |
| Risk Mitigated (outcome badge) | Build Complete / Verified (outcome badge) | Both show positive status outcome |
| Progress ring (% complete) | Deadline ring (% elapsed) | Same circular data visualization pattern |
| Data counters (hours, dollars) | Data counters (tokens, agents, build time) | Same "numbers as decoration" philosophy |

---

*Document prepared by HERO Council. Design decisions traceable to Exebenus.com aesthetic analysis and HERO system capabilities documentation.*
