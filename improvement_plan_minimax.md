# improvement_plan_minimax.md

## One-sentence pitch

The HERO viewport becomes a **Knowledge Operations Center** — a live dashboard showing information flow through the army: what's been documented, what's been learned, research threads in flight, knowledge gaps, and the archival trail of every completed task.

---

## Visual Paradigm: Information Flow Map

Not a tree (that's Mashal's) and not a flat table (that's the current one). A **three-lane river diagram** showing how information moves through the army's work cycle:

```
╔══════════════════════════════════════════════════════════════════╗
║  HERO Knowledge Ops ⚡  │ T:12,450/50,000 │ ●3 ○2 │ 14:32:07  ║
╠══════════════════════════════════════════════════════════════════╣
║                                                               ║
║  ◀─ INPUT ────────▶│◀── PROCESSING ─────────▶│◀── OUTPUT ──▶║
║                                                               ║
║  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐        ║
║  │ 📥 INBOX    │   │ 🔬 RESEARCH │   │ 📦 ARCHIVE  │        ║
║  │ 3 requests  │   │ 5 threads   │   │ 12 docs     │        ║
║  │ ○ sook_pro  │   │ ● LEAD      │   │ ✓ spec-234  │        ║
║  │ ● freya     │   │ ◌ ARCH×2    │   │ ✓ fix-099   │        ║
║  │ ◌ qlearner  │   │ ● SOLDIER×3 │   │ ✓ optimize  │        ║
║  └─────────────┘   └─────────────┘   └─────────────┘        ║
║                                                               ║
║  KNOWLEDGE GAPS ─────────────────────────────────────────────║
║  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          ║
║  │? auth   │ │? deploy │ │? API    │ │? test   │  +2 more ║
║  │ schema  │ │流程      │ │design   │ │coverage │          ║
║  └──────────┘ └──────────┘ └──────────┘ └──────────┘          ║
║                                                               ║
╚══════════════════════════════════════════════════════════════════╝
                              [q]uit [r]efresh [/]search [d]rill-down
```

**The three lanes represent the natural lifecycle of information:**

1. **INPUT** (left) — requests coming in, inboxes, backlog
2. **PROCESSING** (center) — active research threads, soldiers working, LEAD/ARCH decomposition
3. **OUTPUT** (right) — completed docs, archived specs, verified outputs

**Knowledge Gap bubbles** at the bottom show where the army has identified missing information — things that weren't found, topics that need research, incomplete documentation.

---

## Key Features

### 1. Three-Lane Information Flow
Every piece of work entering HERO flows through input → processing → output. The viewport shows where any given task is in that pipeline. This maps naturally to how the army already works: COMM receives (input) → LEAD/ARCH decompose (processing) → VERIFY/ARCHIVIST deliver (output).

### 2. Knowledge Gap Tracker
When a soldier or ARCH encounters missing information (can't find docs, unclear requirements, no prior art), that gap gets logged as a "?" bubble. When research fills the gap, the bubble turns into a ✓ and moves to the archive lane. This gives a live view of what the army *doesn't* know — which is often more valuable than knowing what it does.

### 3. Research Thread Timeline
Each active thread shows as a horizontal progress indicator:
```
Thread: "fix theme switcher" ──●───────────── 60% ── ARCH-2
  ├─ ✓ decoded theme system
  ├─ ✓ found CSS vars in globals.css
  ├─ ● reading component library docs
  └─ ◌ still need: Storybook stories for ThemeProvider
```
This gives you the *context* of what's happening, not just that it's running.

### 4. Documentation Density Indicators
Each sandbox shows a "doc density" meter: how much documentation/specs exist relative to the work done. A sandbox that's shipped 5 tasks but has 0 docs is a risk — shown as a red ⚠ badge. The army that documents well is the army that doesn't repeat mistakes.

### 5. Archive Trail
The rightmost lane shows the last N completed items across all sandboxes — a scrolling history of what's been delivered. Acts as a live changelog of army output.

---

## Data Sources

Beyond the existing `state.cache` and `dispatch/` files, the Knowledge Ops viewport pulls from:

| Source | What it contributes |
|--------|---------------------|
| `~/.hero/dispatch/*.toon` | Active task metadata, current step, model assigned |
| `~/.hero/knowledge/` | When we implement doc-indexing, this dir holds archived outputs |
| `~/.hero/gaps/` | Gap tracking file — what was flagged as unknown during execution |
| `hero.state.cache` | Sandbox status, token usage |
| `~/.hero/archive/` | Completed task records with doc references |
| Git status (optional) | If sandbox has a git repo, show dirty/clean + uncommitted changes |

---

## Interaction Map

| Key | Action |
|-----|--------|
| `←→` | Move between input / processing / output lanes |
| `↑↓` | Navigate items within the active lane |
| `Enter` | Drill into selected item — show full research thread, doc links, gap details |
| `/` | Search across all knowledge: gaps, threads, archived docs |
| `g` | Toggle knowledge gap overlay (highlight all unresearched topics) |
| `d` | Toggle doc density mode (show risk badges per sandbox) |
| `t` | Timeline view — horizontal scroll of all active threads |
| `Tab` | Cycle through sandboxes |
| `r` | Refresh |
| `q` | Quit |

**Drill-down panel** (on Enter):
```
┌──────────────────────────────────────────┐
│ Thread: "fix theme switcher"             │
│ Status: ● Active — ARCH-2               │
│────────────────────────────────----------│
│ RESEARCH TRAIL:                          │
│  ✓ 14:02 — Received from COMM           │
│  ✓ 14:03 — Decoded theme system         │
│  ✓ 14:05 — Found CSS vars (globals.css) │
│  ● 14:07 — Reading component lib docs    │
│  ◌ 14:08 — Need: Storybook stories       │
│────────────────────────────────----------│
│ KNOWLEDGE GAPS:                          │
│  ? Storybook: ThemeProvider stories      │
│  ? CSS: dark mode token reference        │
│────────────────────────────────----------│
│ OUTPUT ARTIFACTS:                        │
│  ↳ spec-234.md (ARCHIVIST filed)        │
│  ↳ fix-099.patch (VERIFY approved)       │
└──────────────────────────────────────────┘
```

---

## Why This Fits MiniMax M2.7

As the **Researcher and Archivist** of the HERO army, my value isn't just doing tasks — it's knowing what the army knows, what it's missed, and what it still needs to learn. The current viewport shows that work *exists*; this viewport shows work in the context of *knowledge lifecycle*.

A tree shows hierarchy. A table shows inventory. A knowledge flow map shows *learning* — which is what a researcher does.

This dashboard answers the questions I actually care about:
- "What's in flight right now?" → Processing lane
- "What's been completed and documented?" → Archive lane  
- "What's the army *missing*?" → Knowledge Gap bubbles
- "Where's the risk?" → Doc density indicators
- "What's the trail of decisions?" → Research thread timeline

---

## Quick Start (if implemented)

```bash
# Run the knowledge ops viewport
hero viewport --mode knowledge

# Or in live mode with all features
hero viewport

# Filter to one sandbox's knowledge flow
hero viewport --sandbox sook_pro

# One-shot snapshot
hero viewport --once --mode knowledge
```

Expected output on first run (with active work):
```
HERO Knowledge Ops ⚡ ─────────────────────────────────────────────
T:8,200/50,000 (16%) │ ●4 ○1 │ 14:32:07

◀───────────────▼───────────────▶

  INPUT          PROCESSING         OUTPUT
 ┌───────┐     ┌───────────┐     ┌─────────┐
 │📥 2   │     │🔬 4      │     │📦 18   │
 │ ●freya│     │ ●LEAD    │     │ ✓spec-X│
 │ ○sook │     │ ◌ARCH×2  │     │ ✓fix-09│
 │ ◌qler │     │ ●SOL×3   │     │ ✓deploy│
 └───────┘     └───────────┘     └─────────┘

 KNOWLEDGE GAPS: 4 unresolved
 ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
 │?auth │ │?dep  │ │?API  │ │?test │
 │schema│ │流程  │ │design│ │cov   │
 └──────┘ └──────┘ └──────┘ └──────┘

KEYBOARD: ←→ lanes │ ↑↓ navigate │ Enter drill │ / search │ g gaps
```