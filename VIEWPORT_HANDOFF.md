# HERO Viewport — Session Handoff

> Use this doc to continue work on the Army Tree viewport in a new session.

---

## Project Location

```
~/Development/HERO/
```

Activate: `cd ~/Development/HERO && source .venv/bin/activate`

Run tree viewport: `hero viewport --once --mode tree`
Run dashboard mode: `hero viewport --once`

---

## What's Been Built (2,406 lines)

| File | Purpose |
|------|---------|
| `src/hero/viewport/states.py` | `SandboxState` enum (7 states) + `compute_sandbox_state()` |
| `src/hero/viewport/delta.py` | `SessionDelta` dataclass + delta banner renderer |
| `src/hero/viewport/compaction.py` | `CompactionEngine` — rolling 30min event window, caps 100 events |
| `src/hero/viewport/metrics.py` | Extended: `no_progress_counter`, `last_state_override`, `previous_army` |
| `src/hero/viewport/tree.py` | `TreeNode`, `PipelineState`, `build_tree()` — reads pipeline JSON + dispatch files |
| `src/hero/viewport/tree_renderer.py` | `build_tree_layout()`, `_render_tree_panel()`, `_render_intel_panel()`, `_render_budget_panel()`, `_render_action_panel()`, `_render_collapsed_sandbox()`, `_estimate_height()` |
| `src/hero/viewport/intel.py` | `Bottleneck`, `BudgetProjection`, `Action` dataclasses + `detect_bottlenecks()`, `compute_budget_projections()`, `generate_actions()` |
| `src/hero/viewport/renderer.py` | `run_tree()` entry point (header + tree layout) |
| `src/hero/commands/viewport.py` | `--mode dashboard|tree` flag (already wired) |

---

## Current Viewport Output

```
╭─ HERO⚡ T:79,700/180,000 █████████░░░░ 44% | Tools:0 ●0 ○6 | 07:50 ─╮
╰────────────────────────────────────────────────────────────────────────╯
╭─ Intelligence Zone ────────────────────────────────────────────────────╮
│ (bottleneck detection — all clear or flagged issues)                   │
├─ Budget Projections ───────────────────────────────────────────────────┤
│ Sandbox      Used/Budget    %   Burn/min   ETA      Status            │
│ HERO         100/5,000     2%          1   5880m   healthy            │
│ qlearner     55,000/50,000 110%       458     —    critical ⚠        │
├─ Action Queue ─────────────────────────────────────────────────────────┤
│ 🔴 [CRITICAL] qlearner: 110% budget used                              │
╰────────────────────────────────────────────────────────────────────────╯
╭─ galaxy_oblivion ──────────────────────────────────────────────────────╮
│ ● COMM running                                                         │
│ └── ✓ LEAD done                                                        │
│     └── ◌ ARCH queued — Verify → Fix → Archive                         │
│         ├── ◌ SOLDIER queued model: step-3.5                           │
│         └── ◌ VERIFY dispatched → ◌ ARCHIVIST → ◌ COMM pending        │
╰────────────────────────────────────────────────────────────────────────╯
╭○ DocPalace  dead    ○ Freya  dead    ● HERO  working                   ╮
╰────────────────────────────────────────────────────────────────────────╯
```

---

## What's Still Pending

### Phase 3c — Drill-Down Detail Panel (next priority)
- Select sandbox in tree → show full detail panel
- Show: exact budget breakdown, compaction count, last task, errors, git status
- Arrow key navigation for tree nodes (`↑↓`)
- `Enter` to drill in, `ESC` to go back

### Phase 3d — Escalation Paths + Model Contention
- Visual retry chain in tree (failed→retry_1→retry_2→escalation)
- Model contention detection (same model requested by 3+ sandboxes)
- Escalation path visualization in Intel panel

### Phase 4 — Health Ring + Goal Layer
- Top-of-viewport health ring (separate bars: budget, errors, idle)
- Mission/objective banner
- Goal progress indicator

### Phase 5 — Polish
- Mode switching between Command / Situation / Pulse
- Compact mode for narrow terminals
- Color consistency across both modes
- Keyboard help overlay (`?` key)

---

## Architecture Patterns (Follow These)

### Adding a new panel to tree mode

1. Add your panel renderer function in `tree_renderer.py`
2. Accept it as a parameter in `build_tree_layout()`
3. Append the panel to `tree_panels` list before the pipeline trees
4. Compute data in `run_tree()` in `renderer.py` and pass to `build_tree_layout()`

### Adding new metrics/intel

1. Add dataclasses in `intel.py`
2. Add detection/computation function in `intel.py`
3. Call from `run_tree()` in `renderer.py`
4. Render via new `_render_*_panel()` in `tree_renderer.py`

### General rules

- One soldier at a time (no parallel flooding)
- Soldiers build code, I review and polish
- Use `stepfun-plan/step-3.6` for soldiers (fast, reliable)
- Test: `python3 -m py_compile` then `hero viewport --once --mode tree`
- Never modify `states.py`, `delta.py`, or `compaction.py` (Phase 1 is frozen)

---

## Key Contacts

- **Mashal** — the human, gives direction
- **Kimi K2.6** — review expert (simulated via MiMo V2.5 Pro or Step 3.6)
- **Communicator** (Claw) — me, I route tasks and polish output

---

## Prompt for the Soldier (copy-paste template)

```
Build [feature X] for the HERO viewport tree mode.

Read existing code in:
- ~/Development/HERO/src/hero/viewport/tree.py
- ~/Development/HERO/src/hero/viewport/tree_renderer.py  
- ~/Development/HERO/src/hero/viewport/intel.py
- ~/Development/HERO/src/hero/viewport/renderer.py

Do NOT modify: states.py, delta.py, compaction.py

[Specific instructions for feature X]

After writing:
1. python3 -m py_compile <new/modified files>
2. hero viewport --once --mode tree (verify no crash)
```
