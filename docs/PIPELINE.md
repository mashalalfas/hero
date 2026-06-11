# HERO Army Pipeline — Logical Flow

## Core Principle: No user prompts between steps.

The Communicator runs the full pipeline start-to-finish for every deployment.
The user gives one command. The army handles the rest.

---

## The Flow

```
USER
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│  1. COMMUNICATOR (Step 3.5 Flash)                          │
│     - Receives user request                                 │
│     - Validates: is this a deployment task?                 │
│       YES → step 2                                          │
│       NO  → handle directly (chat, info, etc)               │
│     - Decides sandbox + high-level task                     │
└─────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│  2. LEAD (MiMo V2.5)                                       │
│     - Reads sandbox structure (PLAN.md, src files, build)   │
│     - Runs project analysis (flutter analyze, tsc, etc)     │
│     - Breaks task into small focused subtasks               │
│       (max 2 files per subtask)                             │
│     - Writes subtasks to dispatch queue (~/.hero/dispatch/) │
│     - **No soldiers spawned yet**                           │
└─────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│  3. SOLDIERS (Step 3.5 Flash / DeepSeek V4 Flash)          │
│     - Communicator reads dispatch queue                     │
│     - Spawns ALL soldiers IN PARALLEL via sessions_spawn    │
│     - Each soldier: 1 file pair, 1 focused task             │
│     - Each soldier writes REAL code (no TODOs)              │
│     - Each soldier self-verifies (build check)              │
│     - **Waits for ALL soldiers to complete**                │
└─────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│  4. VERIFIER (Step 3.5 Flash)                               │
│     - Runs project build (flutter build, vite build, etc)   │
│     - Runs analyzer (flutter analyze, tsc --noEmit, etc)    │
│     - Quick scan for security red flags                     │
│     - PASS → step 5                                         │
│     - FAIL → re-queue failing soldier(s) with error detail  │
└─────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│  5. ARCHIVIST (MiniMax M2.7)                                │
│     - Reads what soldiers changed (git diff --stat)         │
│     - Reads soldier completion summaries                    │
│     - Updates daily memory: `memory/YYYY-MM-DD.md`          │
│     - Updates project section in MEMORY.md if significant   │
│     - **Never rewrites files destructively**                │
└─────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│  6. COMMUNICATOR (me)                                       │
│     - Summarizes results to user:                           │
│       • What was done (files changed, lines added/removed)  │
│       • Build status (pass/fail)                            │
│       • Any issues found                                    │
│     - Keeps it brief (user likes brief)                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Rules

### No Solo Work
The Communicator never writes code. Never runs builds. Never updates memory.
Every task is routed through the army.

### No Skipping Steps
Every deployment runs all 6 steps. No shortcuts. No "this is too small."
Even a 1-line fix goes through: Lead → Soldier → Verifier → Archivist.

### Soldiers: 1 Task, 2 Files, No Scope Creep
- Max 2 files per soldier
- One focused task per soldier
- If scope creep detected → halve the task, spawn another soldier
- Soldiers must self-verify: build/analyze after writing

### Verifier: Fail Fast
- If soldier output breaks the build → re-queue with full error context
- Max 2 retries per soldier
- After 2 retries → escalate to user

### Archivist: Append Only
- Never rewrite memory files destructively
- Append new sections, insert targeted entries
- Timestamp everything

### Communicator: Report, Don't Build
- **Never write code.** That's the Lead/Soldiers' job.
- **Never go heads-down silent.** Update user after every step.
- When soldiers are spawned → say so. When they finish → report.
- Users should never have to ask "so?" — that means you went quiet.
- **One message per milestone:** "Lead done → here's the plan." "Soldiers deployed." "Build results: ✅/❌"
- Format: `✅ [step] — [summary]`
- Don't ask "what next" — user will say if they want more

### This File is Law
If you break these rules, update your memory so it never happens again.

---

## Implementation (CLI Commands)

```
hero assemble --sandbox X --task "Y"
  → Runs (Plan → Queue) in one shot

hero dispatch spawn
  → Reads queue → outputs sessions_spawn JSON

sessions_spawn [from dispatch]
  → Launches soldiers → waits for completion

[Verifier runs automatically after soldiers done]

hero archivist
  → Updates memory files with session data
```

But the ideal is ONE command:

```
hero go --sandbox X --task "Y"
  → Full pipeline: Plan → Queue → Spawn → Verify → Archive → Report
```

---

## Current Status (2026-05-24)

| Step | Automation | Who runs it |
|------|-----------|-------------|
| 1. Communicator | Manual | me (Claw) |
| 2. Lead | Semi-auto (`hero assemble`) | Lead sub-agent |
| 3. Soldiers | Manual (`sessions_spawn`) | me (Claw) reading dispatch |
| 4. Verifier | Manual | me (Claw) |
| 5. Archivist | Manual (`sessions_spawn`) | me (Claw) |
| 6. Report | Manual | me (Claw) |

**Gap:** Steps 3-5 require manual intervention. `hero go` would close the gap.

---

## Current Status (2026-05-24 13:48)

| Phase | Feature | Status |
|-------|---------|--------|
| 0 | `hero orchestrate` fix | ✅ Done |
| 1 | `hero dispatch spawn` | ✅ Done |
| 2 | `hero assemble` | ✅ Done |
| **3** | **`hero go` — full pipeline** | **✅ Done** |
| 4 | QA gate (soldier output review) | 🔲 Todo |
| 5 | git commit workflow | 🔲 Todo |

### `hero go` output
- Console: full 6-phase status with sessions_spawn commands
- Manifest: `~/.hero/pipeline/<task_id>.json` — structured pipeline file
- Communicator reads manifest → spawns soldiers → verifies → archives → reports
