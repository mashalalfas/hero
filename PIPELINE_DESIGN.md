# HERO Pipeline Design

```
                              HERO PIPELINE FLOW
 ─────────────────────────────────────────────────────────────────────

                            [Planning Phases — Bypassable]
  Council → Research → PE ──[Proposal]──→ Communicator
       ┌─────────────────────────┤ approve? ├───────────────────────┐
       │  YES ──→ PE writes ──→ Architect ──→ Lead ──→ Soldiers    │
       │  NO  ──→ PE iterates or closes                            │
       └────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
                          ┌─────────────────────────────────────────┐
                          │         EXECUTION LINE (Mandatory)       │
                          │                                         │
                          │  ┌───────────────────────────────────┐  │
                          │  │      ①  NAVIGATION               │  │
                          │  │  Archivist: graphify + hero map  │  │
                          │  │  → NAVIGATION_TREE.md            │  │
                          │  │  Lead reads it before spawning   │  │
                          │  │  Communicator checks on queries  │  │
                          │  └───────────────────────────────────┘  │
                          │            ↓                            │
                          │  ┌───────────────────────────────────┐  │
                          │  │      ②  PRE-COMMIT               │  │
                          │  │  Gitleaks · eslint · Copyright   │  │
                          │  └───────────────────────────────────┘  │
                          │            ↓                            │
                          │  ┌───────────────────────────────────┐  │
                          │  │      ③  BUILD                    │  │
                          │  │  Compile · Obfuscate · ProGuard  │  │
                          │  │  Auto-version                     │  │
                          │  └───────────────────────────────────┘  │
                          │            ↓                            │
                          │  ┌───────────────────────────────────┐  │
                          │  │      ④  HARDEN                   │  │
                          │  │  Trivy · Semgrep · Root detect   │  │
                          │  │  Cert pinning                     │  │
                          │  └───────────────────────────────────┘  │
                          │            ↓                            │
                          │  ┌───────────────────────────────────┐  │
                          │  │      ⑤  LEGAL                    │  │
                          │  │  License scan · SBOM · EULA/PP   │  │
                          │  └───────────────────────────────────┘  │
                          │            ↓                            │
                          │  ┌───────────────────────────────────┐  │
                          │  │      ⑥  CI/PR                    │  │
                          │  │  Tests · Security scan · Verify  │  │
                          │  └───────────────────────────────────┘  │
                          │            ↓                            │
                          │  ┌───────────────────────────────────┐  │
                          │  │      ⑦  VERIFY                   │  │
                          │  │  Composite score ≥70 → proceed   │  │
                          │  │  Score <50 → FIX loop            │  │
                          │  └───────────────────────────────────┘  │
                          │            ↓                            │
                          │  ┌───────────────────────────────────┐  │
                          │  │      ⑧  ARCHIVE                  │  │
                          │  │  Store artifacts · SBOM · Journal │  │
                          │  │  Archivist Phase 3 (incl. Navig.) │  │
                          │  └───────────────────────────────────┘  │
                          └─────────────────────────────────────────┘
```

---

## Stage Details

| # | Stage | Tooling | Gate | Who Runs It |
|---|-------|---------|------|-------------|
| ① | **NAVIGATION** | `graphify --update` + `hero map` | NAVIGATION_TREE.md written | **Archivist** (sub-task) |
| ② | **PRE-COMMIT** | Gitleaks, eslint, copyright scan | No secrets, lint passes | Soldier |
| ③ | **BUILD** | npm build, flutter build, ProGuard | Binary compiles | Soldier |
| ④ | **HARDEN** | Trivy, Semgrep, root detect | No CRITICAL CVEs | Soldier |
| ⑤ | **LEGAL** | license-checker, SBOM, EULA | All licenses clear | Soldier |
| ⑥ | **CI/PR** | Tests, security scan, artifacts | All tests pass | Soldier |
| ⑦ | **VERIFY** | Composite score | Score ≥ 70 🟢 | Lead |
| ⑧ | **ARCHIVE** | Git, memory, artifact store | Logged + journaled | **Archivist** (Phase 3) |

## Mode Presets

| Mode | Stages | Use Case |
|------|--------|----------|
| `smart` (default) | All 8 stages | Full rebuild, auto-detect |
| `quick` | navigate + pre-commit + build + verify | Fast dev iteration |
| `ci` | pre-commit + build + cipr + verify | CI pipeline simulation |
| `audit` | harden + legal | Security/legal review |
| `full` | All 8 stages | Production deploy |

---

## Role Responsibilities (Navigation)

| Role | Responsibility | When |
|------|---------------|------|
| **Archivist** | Builds/updates `NAVIGATION_TREE.md` using graphify + hero map | After every work cycle (sub-task) + on-demand via `hero navigate` |
| **Lead** | Reads `NAVIGATION_TREE.md` before spawning soldiers. Includes relevant sections in soldier context payload | Before every spawn |
| **Communicator** | Checks `NAVIGATION_TREE.md` before answering project questions | On user inquiry about any project |

---

## The Navigation Cycle

```
 Work completes
     ↓
 Archivist runs graphify --update + hero map
     ↓
 Synthesizes both graphs → updates NAVIGATION_TREE.md
     ↓
 Next session starts
     ↓
 Lead reads navigation tree → spawns informed soldiers
 Communicator checks tree → answers user questions
     ↓
 Work completes → cycle repeats
```

---

## How to Run

```bash
# Full pipeline (default = smart mode: all 8 stages)
hero go --sandbox <name> --task "<desc>"

# Mode presets
hero go --sandbox <name> --task "<desc>" --mode quick   # navigate + pre-commit + build + verify
hero go --sandbox <name> --task "<desc>" --mode ci      # pre-commit + build + cipr + verify
hero go --sandbox <name> --task "<desc>" --mode audit   # harden + legal only
hero go --sandbox <name> --task "<desc>" --mode full    # all 8 stages

# Stage range (run a subset in order)
hero go --sandbox <name> --task "<desc>" --from navigate --to build

# Single stage
hero go --sandbox <name> --task "<desc>" --stage harden

# Rebuild navigation tree only
hero go --sandbox <name> --task "" --stage navigate

# Full pipeline with auto-execution
hero go --sandbox <name> --task "<desc>" --auto

# Skip verify gate (dev mode)
hero go --sandbox <name> --task "<desc>" --no-verify

# Skip archive phase
hero go --sandbox <name> --task "<desc>" --no-archive
```

---

## Scoring

| Score | Color | Action |
|-------|-------|--------|
| ≥ 70 | 🟢 PASS | Proceed to next stage |
| 50-69 | 🟡 WARN | Proceed with warning |
| < 50 | 🔴 FAIL | Block pipeline, re-queue fix |

**Navigation stage scoring:** Binary — tree exists & current = PASS. Missing or stale = WARN.

---

## Pipeline Config Locations

```
Pipeline definitions:   ~/.hero/PIPELINE.md
Army roles:             ~/.hero/army.yaml
Archivist prompts:      ~/.hero/prompts/phases/archivist-phase3.md
                        ~/Development/HERO/src/hero/prompts/defaults/roles/archivist.md
Navigation trees:       <project>/knowledge/NAVIGATION_TREE.md
```

---

> **Last updated:** 2026-06-09 · Stage ① (NAVIGATION) added as Archivist sub-task.
